"""Review files preserve existing owner and legacy state; no apply operation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from .prepare_install import review_files,prepare,SERVICE,SOCKET
from .runtime_config import parse_runtime
from .test_runtime_config import policies
from ..settings import parse_settings


class ReviewTests(unittest.TestCase):
    def test_owner_is_copied_from_installed_policy_never_company_one_fallback(self):
        old,_=policies();legacy=parse_settings(old);files=review_files(legacy)
        host=json.loads(files['policy/runtime.json']);gateway=json.loads(files['policy/commercial.json'])
        self.assertEqual(host['bridge']['company_id'],37)
        self.assertEqual(host['bridge']['telegram_user_id'],old['telegram_user_id'])
        self.assertEqual(host['bridge'],gateway['bridge'])
        self.assertNotIn('profile',gateway);self.assertNotIn('key',gateway)
        self.assertEqual(parse_runtime(host,legacy=legacy).bridge.queue.pipeline.protocol,3)

    def test_units_are_separate_graceful_and_restart_bootstrap_without_limit_lockout(self):
        self.assertIn('stroyka-jev-commercial.socket',SERVICE)
        self.assertIn('StartLimitIntervalSec=0',SERVICE)
        self.assertIn('Restart=on-failure',SERVICE);self.assertIn('TimeoutStopSec=infinity',SERVICE)
        self.assertIn('/etc/stroyka-jev-commercial/private/admission.key',SERVICE)
        self.assertNotIn(':/etc/stroyka-jev/private/admission.key',SERVICE)
        self.assertIn('FileDescriptorName=commercial',SOCKET)
        self.assertIn('/run/stroyka-jev/commercial.sock',SOCKET)
        self.assertNotIn('/admission.sock',SOCKET)

    def test_preparation_creates_only_new_review_staging_and_checksums(self):
        old,_=policies();legacy=parse_settings(old)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);stage=root/'review'
            result=prepare(stage,legacy)
            self.assertFalse(result['installation_ready']);self.assertFalse(result['services_changed'])
            self.assertFalse(result['key_created'])
            manifest=json.loads((stage/'REVIEW_MANIFEST.json').read_text())
            self.assertEqual(manifest['additional_container_mounts'],[])
            for row in manifest['files']:
                path=stage/row['path']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['sha256'])
                self.assertEqual(path.stat().st_mode&0o777,0o600)
            before={p.relative_to(stage):p.read_bytes() for p in stage.rglob('*') if p.is_file()}
            with self.assertRaises(FileExistsError):prepare(stage,legacy)
            after={p.relative_to(stage):p.read_bytes() for p in stage.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            self.assertEqual(list(root.iterdir()),[stage])
