"""Required native CI check. Missing/blocked bwrap is FAILURE, never a skip."""
import json
import os
from pathlib import Path
import sys
import socket
import tempfile
import unittest

from .documents import extract_isolated,sandbox_command
from .test_documents import TEXT,docx
from .test_zip_documents import bundle
from ..invoker import _run_bounded


class SandboxTests(unittest.TestCase):
    def test_real_sandbox_extracts_docx(self):
        result=extract_isolated(docx(TEXT),'.docx')
        self.assertTrue(result['complete']);self.assertIn('Постоплата',str(result))

    def test_real_sandbox_extracts_zip_and_marks_unread_members(self):
        result=extract_isolated(bundle([('terms.docx',docx(TEXT)),('unread.xls',b'fixture')]),'.zip')
        self.assertFalse(result['complete'])
        self.assertIn('terms.docx',str(result));self.assertIn('неподдерживаемый формат',str(result))

    def test_host_files_environment_and_network_not_exposed(self):
        with tempfile.TemporaryDirectory(prefix='jev-private-probe-') as directory:
            marker=Path(directory)/'fixture-secret';marker.write_text('SYNTHETIC_PRIVATE')
            original=os.environ.get('JEV_FIXTURE_SECRET')
            os.environ['JEV_FIXTURE_SECRET']='SYNTHETIC_PRIVATE'
            try:
                with socket.socket() as host:
                    host.bind(('127.0.0.1',0));host.listen(1);port=host.getsockname()[1]
                    with socket.create_connection(('127.0.0.1',port),timeout=1):pass
                    connection,_=host.accept();connection.close()
                    script='import os,pathlib,socket,json; s=socket.socket(); s.settimeout(1); rc=s.connect_ex(("127.0.0.1",'+str(port)+')); print(json.dumps({"file":pathlib.Path('+repr(str(marker))+').exists(),"env":"JEV_FIXTURE_SECRET" in os.environ,"network":rc==0}))'
                    command=sandbox_command('.txt')[:-5]+[sys.executable,'-I','-c',script]
                    raw,code=_run_bounded(command,None,10)
                    self.assertEqual(code,0)
                    self.assertEqual(json.loads(raw),{'file':False,'env':False,'network':False})
            finally:
                if original is None:os.environ.pop('JEV_FIXTURE_SECRET',None)
                else:os.environ['JEV_FIXTURE_SECRET']=original


if __name__=='__main__':unittest.main()
