"""Real local HTTPS S3 protocol fixture; synthetic objects/credentials only."""
import contextlib
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.parse
from scripts import s3_documents_backup as s3

ACCESS='SYNTHETIC_ACCESS'
SECRET='synthetic-only-secret'
DATA={'uploads/company-1/накладная.pdf':b'%PDF-synthetic\x00\xff','uploads/../../outside':b'synthetic path','uploads/empty':b''}

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def reply(self,status,body,headers=None):
        self.send_response(status)
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        self.server.methods.append('GET')
        # Independently derive the signature from the actual HTTP request.
        authorization=self.headers.get('Authorization','')
        try:
            fields=dict(part.split('=',1) for part in authorization.removeprefix('AWS4-HMAC-SHA256 ').split(', '))
            credential=fields['Credential'].split('/');names=fields['SignedHeaders'].split(';')
            assert credential[0]==ACCESS and credential[2:]==['ru-central1','s3','aws4_request']
            parsed=urllib.parse.urlsplit(self.path)
            query=urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parsed.query)),quote_via=urllib.parse.quote,safe='-_.~')
            canonical='\n'.join(['GET',parsed.path,query,''.join(n+':'+self.headers[n]+'\n' for n in names),';'.join(names),hashlib.sha256(b'').hexdigest()])
            scope='/'.join(credential[1:]);message='AWS4-HMAC-SHA256\n'+self.headers['X-Amz-Date']+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
            key=('AWS4'+SECRET).encode()
            for part in credential[1:]:key=hmac.new(key,part.encode(),hashlib.sha256).digest()
            assert hmac.compare_digest(fields['Signature'],hmac.new(key,message.encode(),hashlib.sha256).hexdigest())
        except Exception:
            self.reply(403,b'authentication failed');return
        mode=self.server.mode
        if mode=='redirect':self.reply(302,b'',{'Location':'https://unrelated.invalid/private'});return
        parsed=urllib.parse.urlsplit(self.path);query=urllib.parse.parse_qs(parsed.query,keep_blank_values=True)
        if 'list-type' in query:
            self.server.list_calls+=1
            prefix=query.get('prefix',[''])[0]
            if mode=='bad_xml':self.reply(200,b'<!DOCTYPE bad><bad/>');return
            import xml.etree.ElementTree as ET
            root=ET.Element('ListBucketResult',xmlns='http://s3.amazonaws.com/doc/2006-03-01/')
            ET.SubElement(root,'Prefix').text=prefix
            keys=sorted(k for k in DATA if k.startswith(prefix))
            if mode=='snapshot_change' and self.server.list_calls>1:keys=keys[:-1]
            if mode in ('pagination','pagination_cycle'):
                token=query.get('continuation-token',[''])[0]
                keys=keys[:1] if not token else keys[1:]
                truncated=not token or mode=='pagination_cycle'
                if truncated:ET.SubElement(root,'NextContinuationToken').text='token +/=' if mode=='pagination' else 'repeat'
            else:truncated=False
            ET.SubElement(root,'IsTruncated').text=str(truncated).lower()
            for key in keys:
                item=ET.SubElement(root,'Contents')
                for field,value in [('Key',key),('Size',str(len(DATA[key]))),('ETag','"'+hashlib.md5(DATA[key]).hexdigest()+'"'),('LastModified','2026-01-01T00:00:00Z')]:ET.SubElement(item,field).text=value
            self.reply(200,ET.tostring(root));return
        key=urllib.parse.unquote(parsed.path).removeprefix('/test-bucket/')
        if key not in DATA:self.reply(404,b'not found');return
        body=DATA[key];etag='"'+hashlib.md5(body).hexdigest()+'"'
        if self.headers.get('If-Match')!=etag:self.reply(412,b'precondition failed');return
        if mode=='etag_change':etag='"changed"'
        if mode=='truncated_object':body=body[:-1]
        if mode=='broken_body':
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.send_header('ETag',etag);self.end_headers()
            self.wfile.write(body[:-1]);self.close_connection=True;return
        headers={'ETag':etag}
        if mode=='encoded':headers['Content-Encoding']='gzip'
        self.reply(200,body,headers)

class S3ReadOnlyBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();root=Path(cls.temp.name)
        cert=root/'cert.pem';key=root/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],check=True,capture_output=True)
        cls.context=ssl.create_default_context(cafile=str(cert))
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
        cls.server.socket=tls.wrap_socket(cls.server.socket,server_side=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def setUp(self):
        self.server.mode='normal';self.server.methods=[];self.server.list_calls=0
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.env={'S3_ENDPOINT_URL':'https://localhost:'+str(self.server.server_port),'S3_BUCKET':'test-bucket','S3_REGION':'ru-central1','S3_ACCESS_KEY_ID':ACCESS,'S3_SECRET_ACCESS_KEY':SECRET}
    def reader(self):return s3.Reader(self.env,context=self.context)
    def test_real_https_signed_backup_checks_all_bodies_and_uses_only_get(self):
        result=self.reader().backup(self.root,('uploads/',))
        self.assertEqual(result['objects'],3);self.assertEqual(result['bytes'],sum(map(len,DATA.values())))
        self.assertEqual(set(self.server.methods),{'GET'})
        self.assertFalse((self.root.parent/'outside').exists())
        manifest=json.loads((self.root/'manifest.json').read_text())
        self.assertIn('no_acl_policy_or_version_history',manifest['coverage'])
        self.assertNotIn(SECRET,(self.root/'manifest.json').read_text())
        self.assertNotIn(ACCESS,(self.root/'manifest.json').read_text())
        self.assertEqual(s3.verify(self.root),result)
    def test_pagination_preserves_unicode_and_opaque_continuation_token(self):
        self.server.mode='pagination';rows=self.reader().inventory(('uploads/',))
        self.assertEqual({r['key'] for r in rows},set(DATA))
    def test_changed_inventory_refuses_to_mark_backup_complete(self):
        self.server.mode='snapshot_change'
        with self.assertRaisesRegex(s3.BackupError,'SNAPSHOT_CHANGED'):self.reader().backup(self.root,('uploads/',))
        self.assertFalse((self.root/'manifest.json').exists())
    def test_cyclic_pagination_fails_with_fixed_non_sensitive_error(self):
        self.server.mode='pagination_cycle'
        with self.assertRaisesRegex(s3.BackupError,'PAGINATION'):self.reader().inventory(('uploads/',))
    def test_changed_object_etag_refuses_backup(self):
        self.server.mode='etag_change'
        with self.assertRaisesRegex(s3.BackupError,'OBJECT_CHANGED'):self.reader().backup(self.root,('uploads/',))
        self.assertFalse((self.root/'manifest.json').exists())
    def test_wrong_size_and_encoded_bodies_are_refused(self):
        for mode in ('truncated_object','encoded','broken_body'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                self.server.mode=mode
                with self.assertRaises(s3.BackupError):self.reader().backup(Path(directory),('uploads/',))
    def test_redirect_is_never_followed(self):
        self.server.mode='redirect'
        with self.assertRaises(s3.BackupError):self.reader().inventory(('uploads/',))
        self.assertEqual(self.server.methods,['GET'])
    def test_xml_doctype_is_rejected(self):
        self.server.mode='bad_xml'
        with self.assertRaises(s3.BackupError):self.reader().inventory(('uploads/',))
    def test_tls_verification_cannot_be_disabled(self):
        context=ssl._create_unverified_context()
        with self.assertRaisesRegex(s3.BackupError,'TLS_VERIFICATION'):s3.Reader(self.env,context=context)
    def test_untrusted_certificate_is_rejected(self):
        with self.assertRaisesRegex(s3.BackupError,'READ_FAILED'):s3.Reader(self.env).inventory(('uploads/',))
    def test_http_and_credentials_in_endpoint_are_refused_before_request(self):
        for value in ('http://localhost','https://user:password@localhost','https://localhost?token=private'):
            with self.subTest(value=value),self.assertRaises(s3.BackupError):s3.Reader(dict(self.env,S3_ENDPOINT_URL=value))
    def test_tampered_local_body_refuses_verification(self):
        self.reader().backup(self.root,('uploads/',))
        next((self.root/'objects').iterdir()).write_bytes(b'changed')
        with self.assertRaisesRegex(s3.BackupError,'CONTENT_MISMATCH'):s3.verify(self.root)
    def test_symlink_cannot_substitute_for_backed_up_object(self):
        self.reader().backup(self.root,('uploads/',))
        target=next((self.root/'objects').iterdir());target.unlink();target.symlink_to('/etc/hostname')
        with self.assertRaisesRegex(s3.BackupError,'PRIVATE_BACKUP_FILE'):s3.verify(self.root)
    def test_extra_local_files_prevent_verified_backup_status(self):
        self.reader().backup(self.root,('uploads/',));(self.root/'objects'/'unexpected').write_bytes(b'x')
        with self.assertRaisesRegex(s3.BackupError,'FILE_SET_MISMATCH'):s3.verify(self.root)
    def test_manifest_symlink_is_rejected_before_reading_external_file(self):
        self.reader().backup(self.root,('uploads/',));target=self.root/'manifest.json'
        target.unlink();target.symlink_to('/etc/hostname')
        with self.assertRaisesRegex(s3.BackupError,'PRIVATE_BACKUP_FILE'):s3.verify(self.root)
    def test_object_budget_exhaustion_is_not_reported_as_success(self):
        with patch.object(s3,'MAX_OBJECTS',1),self.assertRaisesRegex(s3.BackupError,'BUDGET'):self.reader().inventory(('uploads/',))
    def test_expired_deadline_prevents_any_network_request(self):
        reader=self.reader();reader.deadline=0
        with self.assertRaisesRegex(s3.BackupError,'BUDGET'):reader.inventory(('uploads/',))
        self.assertEqual(self.server.methods,[])
    def test_foreign_files_in_destination_are_not_overwritten(self):
        (self.root/'existing').write_bytes(b'keep')
        with self.assertRaisesRegex(s3.BackupError,'NOT_EMPTY'):self.reader().backup(self.root,('uploads/',))
        self.assertEqual((self.root/'existing').read_bytes(),b'keep')

if __name__=='__main__':unittest.main(verbosity=2)
