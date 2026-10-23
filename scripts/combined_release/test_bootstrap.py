import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import bootstrap

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def archive(self,extras=None,tamper=False):
        code=b'# synthetic bootstrap\n';data=b'value\n'
        manifest={'package_files':{'bootstrap.py':hashlib.sha256(code).hexdigest(),'install.py':hashlib.sha256(data).hexdigest()}}
        values={'__main__.py':code,'package/bootstrap.py':code,'package/install.py':b'changed' if tamper else data,'package/manifest.json':json.dumps(manifest).encode(),'package/SHA256SUMS':b'fixture\n'}
        values.update(extras or {})
        p=self.root/'fixture.pyz'
        with zipfile.ZipFile(p,'w') as archive:
            for name,content in values.items():archive.writestr(name,content)
        return p
    def test_staging_preserves_exact_bytes_and_keeps_private_directory(self):
        destination=bootstrap.unpack(self.archive(),self.root)
        self.assertEqual((destination/'install.py').read_bytes(),b'value\n')
        self.assertEqual(destination.stat().st_mode&0o777,0o700)
    def test_tampered_payload_refused_before_creating_stage(self):
        archive=self.archive(tamper=True)
        with self.assertRaisesRegex(bootstrap.PackageError,'CONTENT'):bootstrap.unpack(archive,self.root)
        self.assertEqual(list(self.root.iterdir()),[archive])
    def test_traversal_and_unexpected_files_refused_before_any_extraction(self):
        for name in ('package/../escape','package/a/../../escape','/absolute','package/./hidden','other.py','package\\escape'):
            with self.subTest(name=name):
                archive=self.archive({name:b'x'})
                with self.assertRaises(bootstrap.PackageError):bootstrap.unpack(archive,self.root)
        self.assertFalse((self.root/'escape').exists())
    def test_entrypoint_must_match_ci_bound_bootstrap(self):
        archive=self.archive({'__main__.py':b'# modified\n'})
        with self.assertRaisesRegex(bootstrap.PackageError,'BOOTSTRAP'):bootstrap.unpack(archive,self.root)
    def test_wrong_host_cannot_extract_or_run(self):
        with patch.object(bootstrap.os,'geteuid',return_value=0),patch.object(bootstrap.socket,'gethostname',return_value='test-host'),patch.object(bootstrap,'unpack') as unpack:
            self.assertEqual(bootstrap.main(),1)
        unpack.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
