"""Read-only S3 object-body backup component, not connected to production apply.

Only signed HTTPS GET is implemented. It does not copy ACLs, bucket policies or
version history, and does not establish an exclusive writer boundary. The
installer's S3 refusal remains until that complete procedure is verified.
"""
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import ssl
import stat
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

MAX_OBJECTS=50000
MAX_BYTES=16*1024**3
MAX_LIST_BYTES=8*1024**2
TOTAL_SECONDS=900

class BackupError(RuntimeError):pass

def need(value, code):
    if not value:raise BackupError(code)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise BackupError('S3_REDIRECT_REFUSED')

def private(path):
    path=Path(path)
    need(path.is_absolute() and path.resolve()==path and path.is_dir(),'PRIVATE_BACKUP_DIRECTORY_REQUIRED')
    info=path.stat()
    need(info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700,'PRIVATE_BACKUP_DIRECTORY_REQUIRED')
    return path

def regular(path):
    info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid()
         and stat.S_IMODE(info.st_mode)==0o600,'PRIVATE_BACKUP_FILE_REQUIRED')
    return info

class Reader:
    def __init__(self,env,*,context=None):
        self.endpoint=(env.get('S3_ENDPOINT_URL') or env.get('S3_ENDPOINT') or '').rstrip('/')
        parsed=urllib.parse.urlsplit(self.endpoint)
        need(parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password
             and not parsed.query and not parsed.fragment and '..' not in parsed.path.split('/'), 'S3_HTTPS_ENDPOINT_REQUIRED')
        self.bucket=env.get('S3_BUCKET','').strip()
        self.region=env.get('S3_REGION','ru-central1').strip() or 'ru-central1'
        self._access=(env.get('S3_ACCESS_KEY_ID') or env.get('AWS_ACCESS_KEY_ID') or '').strip()
        self._secret=(env.get('S3_SECRET_ACCESS_KEY') or env.get('AWS_SECRET_ACCESS_KEY') or '').strip()
        need(re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',self.bucket)
             and re.fullmatch(r'[A-Za-z0-9-]+',self.region) and self._secret
             and re.fullmatch(r'[A-Za-z0-9_+=.-]{1,256}',self._access),'S3_CONFIGURATION_REQUIRED')
        context=context or ssl.create_default_context()
        need(context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname,'S3_TLS_VERIFICATION_REQUIRED')
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler(),NoRedirect(),urllib.request.HTTPSHandler(context=context))
        self.deadline=time.monotonic()+TOTAL_SECONDS
        self.identity=digest([self.endpoint,self.bucket,self.region])
    def budget(self):need(time.monotonic()<self.deadline,'S3_OPERATION_BUDGET_EXCEEDED')
    def get(self,key=None,query=None,etag=None):
        self.budget()
        path=urllib.parse.urlsplit(self.endpoint).path+'/'+urllib.parse.quote(self.bucket,safe='')
        if key is not None:path+='/'+urllib.parse.quote(key,safe='/')
        encoded=urllib.parse.urlencode(sorted((query or {}).items()),quote_via=urllib.parse.quote,safe='-_.~')
        host=urllib.parse.urlsplit(self.endpoint).netloc
        now=dt.datetime.now(dt.timezone.utc);date=now.strftime('%Y%m%d');stamp=now.strftime('%Y%m%dT%H%M%SZ')
        empty=hashlib.sha256(b'').hexdigest()
        headers={'host':host,'x-amz-date':stamp,'x-amz-content-sha256':empty,'accept-encoding':'identity'}
        if etag is not None:
            need(isinstance(etag,str) and etag and len(etag)<1024 and not any(ord(c)<32 for c in etag),'S3_ETAG_INVALID')
            headers['if-match']=etag
        names=sorted(headers);signed=';'.join(names)
        canonical='\n'.join(['GET',path,encoded,''.join(n+':'+headers[n]+'\n' for n in names),signed,empty])
        scope=date+'/'+self.region+'/s3/aws4_request'
        message='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
        sign=lambda key,value:hmac.new(key,value.encode(),hashlib.sha256).digest()
        signing=sign(sign(sign(sign(('AWS4'+self._secret).encode(),date),self.region),'s3'),'aws4_request')
        signature=hmac.new(signing,message.encode(),hashlib.sha256).hexdigest()
        headers['Authorization']='AWS4-HMAC-SHA256 Credential='+self._access+'/'+scope+', SignedHeaders='+signed+', Signature='+signature
        url=urllib.parse.urlunsplit(('https',host,path,encoded,''))
        response=None
        try:
            response=self.opener.open(urllib.request.Request(url,headers=headers,method='GET'),timeout=20)
            need(response.status==200 and response.geturl()==url,'S3_RESPONSE_INVALID')
            need(response.headers.get('Content-Encoding','identity').lower()=='identity','S3_ENCODED_RESPONSE_REFUSED')
            return response
        except Exception as error:
            if response is not None:response.close()
            if isinstance(error,BackupError):raise
            raise BackupError('S3_READ_FAILED') from None
    def inventory(self,prefixes):
        need(isinstance(prefixes,tuple) and 0<len(prefixes)<=20
             and all(isinstance(p,str) and '\x00' not in p for p in prefixes),'S3_EXPLICIT_PREFIXES_REQUIRED')
        objects={};total=0
        for prefix in sorted(set(prefixes)):
            token=None;seen=set()
            while True:
                self.budget();query={'list-type':'2','max-keys':'1000','prefix':prefix}
                if token:query['continuation-token']=token
                with self.get(query=query) as response:
                    chunks=[];amount=0
                    while True:
                        self.budget();chunk=response.read1(min(65536,MAX_LIST_BYTES-amount+1))
                        if not chunk:break
                        amount+=len(chunk);need(amount<=MAX_LIST_BYTES,'S3_LIST_RESPONSE_INVALID');chunks.append(chunk)
                    raw=b''.join(chunks)
                need(len(raw)<=MAX_LIST_BYTES and b'<!DOCTYPE' not in raw.upper(),'S3_LIST_RESPONSE_INVALID')
                try:root=ET.fromstring(raw)
                except ET.ParseError:raise BackupError('S3_LIST_RESPONSE_INVALID') from None
                need(root.tag.rsplit('}',1)[-1]=='ListBucketResult','S3_LIST_RESPONSE_INVALID')
                children=lambda node,name:[x for x in node if x.tag.rsplit('}',1)[-1]==name]
                def field(node,name):
                    values=children(node,name);need(len(values)==1,'S3_LIST_RESPONSE_INVALID')
                    return values[0].text or ''
                need(field(root,'Prefix')==prefix,'S3_PREFIX_MISMATCH')
                for node in children(root,'Contents'):
                    key=field(node,'Key');size=field(node,'Size');etag=field(node,'ETag');modified=field(node,'LastModified')
                    need(key and len(key.encode())<=1024 and key.startswith(prefix) and size.isascii() and size.isdecimal()
                         and etag and len(etag)<1024 and not any(ord(c)<32 for c in etag) and modified,'S3_OBJECT_METADATA_INVALID')
                    row={'key':key,'size':int(size),'etag':etag,'modified':modified}
                    if key in objects:need(objects[key]==row,'S3_SNAPSHOT_CHANGED')
                    else:
                        objects[key]=row;total+=row['size']
                        need(len(objects)<=MAX_OBJECTS and total<=MAX_BYTES,'S3_BACKUP_BUDGET_EXCEEDED')
                truncated=field(root,'IsTruncated');need(truncated in ('true','false'),'S3_LIST_RESPONSE_INVALID')
                if truncated=='false':break
                token=field(root,'NextContinuationToken')
                need(token and len(token)<4096 and token not in seen,'S3_PAGINATION_INVALID');seen.add(token)
        return [objects[key] for key in sorted(objects)]
    def backup(self,destination,prefixes):
        root=private(destination);need(not any(root.iterdir()),'BACKUP_DIRECTORY_NOT_EMPTY')
        before=self.inventory(prefixes)
        objects=root/'objects';objects.mkdir(mode=0o700)
        copied=[]
        for row in before:
            self.budget();filename=hashlib.sha256(row['key'].encode()).hexdigest()+'.blob'
            fd=os.open(objects/filename,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as target,self.get(key=row['key'],etag=row['etag']) as source:
                need(source.headers.get('Content-Length','')==str(row['size']) and source.headers.get('ETag')==row['etag'],'S3_OBJECT_CHANGED')
                amount=0;checksum=hashlib.sha256()
                while True:
                    self.budget();chunk=source.read1(min(1024**2,row['size']-amount+1))
                    if not chunk:break
                    amount+=len(chunk);need(amount<=row['size'],'S3_OBJECT_SIZE_MISMATCH')
                    checksum.update(chunk);target.write(chunk)
                need(amount==row['size'],'S3_OBJECT_SIZE_MISMATCH');target.flush();os.fsync(target.fileno())
            copied.append(dict(row,filename=filename,sha256=checksum.hexdigest()))
        need(before==self.inventory(prefixes),'S3_SNAPSHOT_CHANGED')
        manifest={'format':1,'source_identity':self.identity,'prefixes':list(prefixes),'inventory_sha256':digest(before),'objects':copied,
                  'coverage':'current_object_bodies_only_no_acl_policy_or_version_history'}
        fd=os.open(root/'manifest.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as target:
            json.dump(manifest,target,ensure_ascii=False,sort_keys=True);target.flush();os.fsync(target.fileno())
        for directory in (objects,root):
            fd=os.open(directory,os.O_DIRECTORY|os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return verify(root)

def verify(destination):
    root=private(destination);regular(root/'manifest.json')
    need((root/'manifest.json').stat().st_size<=128*1024**2,'BACKUP_MANIFEST_INVALID')
    try:manifest=json.loads((root/'manifest.json').read_text())
    except (ValueError,UnicodeError):raise BackupError('BACKUP_MANIFEST_INVALID') from None
    need(manifest.get('format')==1 and isinstance(manifest.get('objects'),list)
         and len(manifest['objects'])<=MAX_OBJECTS,'BACKUP_MANIFEST_INVALID')
    objects=private(root/'objects');names=set();total=0;rows=[]
    for row in manifest['objects']:
        need(isinstance(row,dict) and isinstance(row.get('key'),str) and type(row.get('size')) is int
             and row['size']>=0 and isinstance(row.get('sha256'),str)
             and re.fullmatch(r'[0-9a-f]{64}',row['sha256'])
             and isinstance(row.get('etag'),str) and isinstance(row.get('modified'),str),'BACKUP_MANIFEST_INVALID')
        filename=hashlib.sha256(row['key'].encode()).hexdigest()+'.blob'
        need(row.get('filename')==filename and filename not in names,'BACKUP_MANIFEST_INVALID');names.add(filename)
        target=objects/filename;info=regular(target);checksum=hashlib.sha256()
        with target.open('rb') as source:
            for chunk in iter(lambda:source.read(1024**2),b''):checksum.update(chunk)
        need(info.st_size==row['size'] and checksum.hexdigest()==row['sha256'],'BACKUP_CONTENT_MISMATCH')
        total+=info.st_size;need(total<=MAX_BYTES,'BACKUP_MANIFEST_INVALID')
        rows.append({k:row[k] for k in ('key','size','etag','modified')})
    need({p.name for p in objects.iterdir()}==names and {p.name for p in root.iterdir()}=={'objects','manifest.json'},'BACKUP_FILE_SET_MISMATCH')
    need(digest(rows)==manifest.get('inventory_sha256'),'BACKUP_MANIFEST_INVALID')
    return {'objects':len(names),'bytes':total,'inventory_sha256':manifest['inventory_sha256'],'verified':True}
