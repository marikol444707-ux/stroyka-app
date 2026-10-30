import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

from .prepare_install import prepare,review_files,SERVICE,SOCKET,TMPFILES
from .settings import parse_settings


class PrepareInstallTests(unittest.TestCase):
    def test_host_uses_resolvable_root_group_and_gateway_keeps_numeric_socket_permissions(self):
        import grp,pwd
        self.assertEqual(pwd.getpwnam('root').pw_uid,0)
        self.assertEqual(grp.getgrnam('root').gr_gid,0)
        self.assertIn('\nUser=root\nGroup=root\n',SERVICE)
        self.assertNotIn('\nGroup=10000\n',SERVICE)
        self.assertIn('\nSocketGroup=10000\nSocketMode=0660\n',SOCKET)
        self.assertIn('d /run/stroyka-jev 0710 root 10000 -',TMPFILES)
        self.assertIn('d /var/lib/stroyka-jev/v2/private 0700 root root -',TMPFILES)
        self.assertIn('LoadCredential=admission.key:/etc/stroyka-jev/private/admission.key',SERVICE)

    def test_candidate_files_have_manifest_and_preserve_one_explicit_private_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'review'
            result=prepare(target,37,'123456789')
            self.assertTrue(result['prepared']);self.assertFalse(result['installation_ready'])
            manifest=json.loads((target/'REVIEW_MANIFEST.json').read_text())
            self.assertFalse(manifest['key_created']);self.assertFalse(manifest['services_changed'])
            self.assertTrue(manifest['blocked_by'])
            for row in manifest['files']:
                path=target/row['path']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['sha256'])
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            host=(target/'policy/host-bridge.json').read_bytes()
            self.assertEqual(host,(target/'policy/gateway-bridge.json').read_bytes())
            parsed=parse_settings(json.loads(host))
            self.assertEqual(parsed.owner.scope.company_id,37)
            self.assertEqual(parsed.owner.reply_chat_id,'123456789')
            self.assertFalse(any(path.name in ('.env','admission.key','apply.sh') for path in target.rglob('*')))

    def test_no_company_or_owner_fallback_and_no_partial_output_for_invalid_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            for company,owner in ((None,'123456789'),(True,'123456789'),(0,'123456789'),(37,''),(37,'@username'),(37,'-123')):
                target=Path(folder)/'review'
                with self.subTest(company=company,owner=owner),self.assertRaises((ValueError,TypeError)):
                    prepare(target,company,owner)
                self.assertFalse(target.exists())

    def test_existing_staging_and_foreign_work_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'review';target.mkdir();original=target/'original';original.write_text('keep')
            with self.assertRaises(FileExistsError):prepare(target,37,'123456789')
            self.assertEqual(list(target.iterdir()),[original]);self.assertEqual(original.read_text(),'keep')

    def test_live_targets_and_symlink_parents_are_refused(self):
        with self.assertRaises(ValueError):prepare('/etc/stroyka-jev-review',37,'123456789')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);real=root/'real';real.mkdir();link=root/'link';link.symlink_to(real)
            with self.assertRaises(ValueError):prepare(link/'review',37,'123456789')
            self.assertFalse((real/'review').exists())

    def test_systemd_verifies_both_units_offline_without_starting_any_service(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,text in review_files(37,'123456789').items():
                if name.startswith('units/'):(root/Path(name).name).write_text(text)
            # Syntax-only fixture dependency, not installed or started.
            (root/'docker.service').write_text('[Service]\nExecStart=/bin/true\n')
            result=subprocess.run(['/usr/bin/systemd-analyze','--man=no','--generators=no','verify',
                str(root/'stroyka-jev.service'),str(root/'stroyka-jev.socket'),str(root/'docker.service')],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
