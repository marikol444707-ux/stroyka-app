#!/usr/bin/env python3
"""Isolated release tests. Never calls a real service, database, or deployment."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/install-participant-duplicate-merge.sh'
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/participant_merge_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class Assets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = {'files': {'main.js': '/static/main.js', 'chunk.js': '/static/lazy.js', 'index.html': '/index.html'}, 'entrypoints': ['static/main.js']}
        for value in self.manifest['files'].values():
            path = self.root / value.lstrip('/')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        self.remote = {'https://example.test' + ('/app' if v == '/index.html' else v): v.encode() for v in self.manifest['files'].values()}

    def tearDown(self):
        self.temp.cleanup()

    def test_all_assets_including_lazy_chunk(self):
        self.assertEqual(release.verify_assets(self.root, self.manifest, self.remote.__getitem__, 'https://example.test'), 3)

    def test_missing_lazy_chunk_fails(self):
        del self.remote['https://example.test/static/lazy.js']
        with self.assertRaises(KeyError):
            release.verify_assets(self.root, self.manifest, self.remote.__getitem__, 'https://example.test')

    def test_corrupt_lazy_chunk_fails(self):
        self.remote['https://example.test/static/lazy.js'] = b'old content'
        with self.assertRaises(ValueError):
            release.verify_assets(self.root, self.manifest, self.remote.__getitem__, 'https://example.test')

    def test_unsafe_manifest_paths_rejected(self):
        for value in ['../secret', '/%2e%2e/secret', '//elsewhere/x', 'https://elsewhere/x', '/x?token=secret', '/a\\b', '/x#anchor', '/%252e%252e/secret', '/a%00b', '', '/']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                release.asset_path(value)

    def test_symlink_parent_rejected(self):
        (self.root / 'alias').symlink_to(self.root / 'static', target_is_directory=True)
        with self.assertRaises(ValueError):
            release.regular_asset(self.root, Path('alias/main.js'))

    def test_pending_not_cleanup_eligible(self):
        release.write_pending(self.root, 'a' * 40, 3)
        data = json.loads((self.root / 'installed-pending.json').read_text())
        self.assertFalse(data['checks']['browser'])
        self.assertFalse((self.root / 'deployed.json').exists())
        self.assertFalse((self.root / 'verified.json').exists())
        self.assertEqual(data['head'], 'a' * 40)


class Rollback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.run_git('init', '-q')
        self.run_git('config', 'user.email', 'test@example.test')
        self.run_git('config', 'user.name', 'Test')
        (self.repo / 'backend.txt').write_text('before')
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'before')
        self.before = self.run_git('rev-parse', 'HEAD').strip()
        (self.repo / 'backend.txt').write_text('target')
        self.run_git('commit', '-qam', 'target')
        self.target = self.run_git('rev-parse', 'HEAD').strip()
        self.backup = self.root / 'backup'
        self.backup.mkdir()
        self.log = self.root / 'calls'
        self.dropin = self.root / 'merge.conf'
        self.dropin.write_text('merge-enabled')
        (self.backup / 'publish-before.sh').write_text('echo publish >> "$CALL_LOG"\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        systemctl = self.bin / 'systemctl'
        systemctl.write_text('#!/bin/sh\necho "systemctl $*" >> "$CALL_LOG"\nexit "${SERVICE_FAIL:-0}"\n')
        systemctl.chmod(0o755)
        text = SCRIPT.read_text()
        self.rollback = text[text.index('rollback() {'):text.index('trap rollback ERR')]

    def tearDown(self):
        self.temp.cleanup()

    def run_git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True)

    def invoke(self, started, service_fail=0):
        env = dict(os.environ, BEFORE=self.before, TARGET=self.target, DROPIN=str(self.dropin), RELEASE_BACKUP=str(self.backup), UNIT_CREATED='1', DEPLOY_STARTED=str(started), CALL_LOG=str(self.log), SERVICE_FAIL=str(service_fail), PATH=str(self.bin) + ':' + os.environ['PATH'])
        # Failure injected at the same ERR trap boundary as the production installer.
        return subprocess.run(['bash', '-c', 'set -Eeuo pipefail\n' + self.rollback + '\ntrap rollback ERR\n(exit 17)'], cwd=self.repo, env=env, capture_output=True, text=True)

    def test_failure_after_checkout_restores_previous_backend_preserves_unknown(self):
        (self.repo / 'local-settings').write_text('preserve')
        result = self.invoke(0)
        self.assertEqual(result.returncode, 17)
        self.assertEqual(self.run_git('rev-parse', 'HEAD').strip(), self.before)
        self.assertEqual((self.repo / 'backend.txt').read_text(), 'before')
        self.assertEqual((self.repo / 'local-settings').read_text(), 'preserve')
        self.assertIn('publish', self.log.read_text())
        self.assertNotIn('restart', self.log.read_text())

    def test_conflicting_local_edit_not_destroyed_or_reported_rolled_back(self):
        (self.repo / 'backend.txt').write_text('unreviewed local edit')
        result = self.invoke(0)
        self.assertEqual(result.returncode, 17)
        self.assertEqual((self.repo / 'backend.txt').read_text(), 'unreviewed local edit')
        self.assertIn('АВТОМАТИЧЕСКИЙ ОТКАТ НЕ ПОДТВЕРЖДЁН', result.stdout)
        self.assertNotIn('publish', self.log.read_text())

    def test_failure_after_restart_keeps_access_capable_target_and_disables_new_mode(self):
        result = self.invoke(1)
        self.assertEqual(result.returncode, 17)
        self.assertEqual(self.run_git('rev-parse', 'HEAD').strip(), self.target)
        self.assertFalse(self.dropin.exists())
        self.assertIn('restart stroyka', self.log.read_text())
        self.assertNotIn('publish', self.log.read_text())
        self.assertIn('manual-recovery-required', (self.backup / 'recovery-status.txt').read_text())

    def test_failure_after_frontend_publication_does_not_restore_old_frontend(self):
        (self.repo / 'build').mkdir()
        (self.repo / 'build/index.html').write_text('target frontend')
        self.invoke(1)
        self.assertEqual((self.repo / 'build/index.html').read_text(), 'target frontend')
        self.assertNotIn('publish', self.log.read_text())

    def test_failed_service_recovery_is_not_success(self):
        result = self.invoke(1, 1)
        self.assertIn('АВТОМАТИЧЕСКИЙ ОТКАТ НЕ ПОДТВЕРЖДЁН', result.stdout)
        self.assertFalse((self.backup / 'deployed.json').exists())
        self.assertEqual(self.run_git('rev-parse', 'HEAD').strip(), self.target)

    def test_installer_never_writes_completion_marker(self):
        text = SCRIPT.read_text()
        self.assertNotIn("/'deployed.json'", text)
        self.assertNotIn("/'verified.json'", text)
        self.assertLess(text.index('DEPLOY_STARTED=1'), text.index('bash "$RELEASE_BACKUP/deploy-reviewed.sh"'))


if __name__ == '__main__':
    unittest.main()
