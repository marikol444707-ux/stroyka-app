import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch, Mock

from scripts import install_invoice_recovery as operator


class InvoiceReleaseFilesystemTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'app'
        self.root.mkdir()
        self.run_git('init', '-q')
        self.run_git('config', 'user.email', 'test@example.test')
        self.run_git('config', 'user.name', 'Synthetic test')
        self.files = ('backend/main.py', 'src/scanner.js', 'src/new.js')
        for name, content in [('backend/main.py', b'original = True\n'), ('src/scanner.js', b'export const old = true;\n'), (operator.ADAPTER, b'reasoning_repaired = True\n')]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'Synthetic production')
        self.base = self.run_git('rev-parse', 'HEAD').strip()
        self.run_git('checkout', '-qb', 'release')
        for name in self.files:
            (self.root / name).write_bytes(b'updated = True\n')
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'Synthetic release')
        self.release = self.run_git('rev-parse', 'HEAD').strip()
        self.run_git('checkout', '-q', 'master')
        self.pdf_before = b'original = True\npdf_repaired = True\n'
        (self.root / 'backend/main.py').write_bytes(self.pdf_before)
        self.backup = Path(self.temp.name) / 'adapter-backup'
        self.backup.mkdir()
        (self.backup / 'manifest.json').write_text(json.dumps({'head': self.base, 'appRoot': str(self.root), 'service': 'stroyka',
            'afterHash': operator.sha((self.root / operator.ADAPTER).read_bytes())}))
        for name, value in [('BASE', self.base), ('FILES', self.files), ('MAIN_BEFORE', operator.sha(self.pdf_before)),
                            ('ADAPTER_BEFORE', operator.sha((self.root / operator.ADAPTER).read_bytes()))]:
            context = patch.object(operator, name, value)
            context.start()
            self.addCleanup(context.stop)

    def run_git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True)

    def plan(self):
        return operator.plan(self.root, self.release, self.base, self.backup)

    def test_readonly_plan_preserves_head_and_current_hotfixes(self):
        changes = self.plan()
        self.assertEqual(set(changes), set(self.files))
        self.assertEqual(changes['backend/main.py']['before'], self.pdf_before)
        self.assertEqual(self.run_git('rev-parse', 'HEAD').strip(), self.base)
        self.assertFalse((self.root / 'src/new.js').exists())

    def test_committed_hotfix_does_not_depend_on_an_old_diagnostic_backup(self):
        shutil.rmtree(self.backup)
        self.assertEqual(set(operator.plan(self.root,self.release,self.base,None)),set(self.files))

    def test_changed_head_frontend_adapter_and_main_are_refused(self):
        cases = [('src/scanner.js', b'edited frontend'), (operator.ADAPTER, b'later adapter'), ('backend/main.py', b'later main')]
        for name, content in cases:
            path = self.root / name
            before = path.read_bytes()
            path.write_bytes(content)
            with self.assertRaises(operator.Stop):
                self.plan()
            path.write_bytes(before)
        with self.assertRaises(operator.Stop):
            operator.plan(self.root, self.release, '0'*40, self.backup)

    def test_existing_new_file_or_symlink_is_not_overwritten(self):
        path = self.root / 'src/new.js'
        path.write_text('keep my work')
        with self.assertRaises(operator.Stop):
            self.plan()
        path.unlink()
        path.symlink_to(self.root / 'src/scanner.js')
        with self.assertRaises(operator.Stop):
            self.plan()

    def test_partial_install_restores_precise_bytes_and_removes_only_added_files(self):
        changes = self.plan()
        stage = Path(self.temp.name) / 'stage'
        stage.mkdir()
        metadata = {'head': self.base, 'files': operator.backup_sources(self.root, stage, changes)}
        for name in self.files[:2]:
            operator.write_atomic(self.root / name, changes[name]['after'])
        operator.restore_sources(self.root, stage, metadata)
        self.assertEqual((self.root / 'backend/main.py').read_bytes(), self.pdf_before)
        self.assertEqual((self.root / 'src/scanner.js').read_bytes(), changes['src/scanner.js']['before'])
        self.assertFalse((self.root / 'src/new.js').exists())
        self.assertEqual((self.root / operator.ADAPTER).read_bytes(), b'reasoning_repaired = True\n')

    def test_later_edit_blocks_entire_rollback_before_any_file_is_restored(self):
        changes = self.plan()
        stage = Path(self.temp.name) / 'stage'
        stage.mkdir()
        metadata = {'head': self.base, 'files': operator.backup_sources(self.root, stage, changes)}
        for name in self.files:
            operator.write_atomic(self.root / name, changes[name]['after'])
        (self.root / 'src/new.js').write_text('later edit')
        with self.assertRaises(operator.Stop):
            operator.restore_sources(self.root, stage, metadata)
        self.assertEqual((self.root / 'backend/main.py').read_bytes(), changes['backend/main.py']['after'])

    def test_backup_corruption_prevents_rollback(self):
        changes = self.plan()
        stage = Path(self.temp.name) / 'stage'
        stage.mkdir()
        metadata = {'head': self.base, 'files': operator.backup_sources(self.root, stage, changes)}
        (stage / 'source-before/backend/main.py').write_text('corrupt')
        with self.assertRaises(operator.Stop):
            operator.restore_sources(self.root, stage, metadata)

    def test_failed_restart_triggers_full_rollback_and_keeps_backups(self):
        helper = Mock()
        helper.manifest_files.return_value = [Path('static/app.js')]
        def fake_build(root, stage, changes, unused):
            for folder in ['source', 'frontend', 'frontend-before']:
                (stage / folder).mkdir(exist_ok=True)
            (stage / 'frontend/asset-manifest.json').write_text('{}')
            return {}
        build = self.root / 'build'
        build.mkdir()
        (build / 'asset-manifest.json').write_text('{}')
        checker = Mock()
        checker.inspect_database.return_value = {'status': 'ready', 'readOnly': True}
        with patch.object(operator, 'load_helper', side_effect=[helper, checker]), \
             patch.object(operator, 'build_frontend', side_effect=fake_build), \
             patch.object(operator, 'healthy'), patch.object(operator, 'restart', side_effect=[RuntimeError('Synthetic failure'), None]):
            with self.assertRaisesRegex(operator.Stop, 'restored_previous_version'):
                operator.apply(self.root, self.release, self.base, self.backup, Path(self.temp.name))
        self.assertEqual((self.root / 'backend/main.py').read_bytes(), self.pdf_before)
        self.assertFalse((self.root / 'src/new.js').exists())
        self.assertTrue(list(Path(self.temp.name).glob('stroyka-invoice-update-*/patch.json')))

    def run_full_fixture(self, fail_publish=False):
        build = self.root / 'build'
        (build / 'static').mkdir(parents=True)
        for name in ['index.html', 'asset-manifest.json', 'static/app.js']:
            (build / name).write_text('old ' + name)
        helper, checker = Mock(), Mock()
        helper.manifest_files.return_value = [Path('static/app.js')]
        helper.backup_frontend.side_effect = lambda source, destination: shutil.copytree(source, destination)
        checker.inspect_database.return_value = {'status': 'ready', 'readOnly': True}
        def fake_build(root, stage, changes, unused):
            (stage / 'source').mkdir()
            (stage / 'frontend/static').mkdir(parents=True)
            for name in ['index.html', 'asset-manifest.json', 'static/app.js']:
                (stage / 'frontend' / name).write_text('new ' + name)
            return {}
        def fake_publish(root, source):
            for name in ['index.html', 'asset-manifest.json', 'static/app.js']:
                shutil.copy2(source / name, build / name)
            if fail_publish and source.name == 'frontend':
                raise RuntimeError('Synthetic publish failure')
        with patch.object(operator, 'load_helper', side_effect=[helper, checker]), \
             patch.object(operator, 'build_frontend', side_effect=fake_build), \
             patch.object(operator, 'healthy'), patch.object(operator, 'restart'), \
             patch.object(operator, 'publish', side_effect=fake_publish):
            return operator.apply(self.root, self.release, self.base, self.backup, Path(self.temp.name))

    def test_success_checks_frontend_bytes_but_waits_for_browser_and_keeps_rollback(self):
        result = self.run_full_fixture()
        self.assertFalse(result['complete'])
        self.assertEqual(result['state'], 'installed_awaiting_browser')
        self.assertFalse(result['checks']['browser'])
        self.assertEqual((self.root / 'build/index.html').read_text(), 'new index.html')
        self.assertFalse((Path(result['backup']) / 'source').exists())
        self.assertFalse((Path(result['backup']) / 'deployed.json').exists())
        self.assertTrue((Path(result['backup']) / 'frontend-before/index.html').is_file())

    def test_partial_frontend_publication_failure_restores_source_and_old_frontend(self):
        with self.assertRaisesRegex(operator.Stop, 'restored_previous_version'):
            self.run_full_fixture(fail_publish=True)
        self.assertEqual((self.root / 'backend/main.py').read_bytes(), self.pdf_before)
        self.assertEqual((self.root / 'build/index.html').read_text(), 'old index.html')
        self.assertEqual((self.root / 'build/asset-manifest.json').read_text(), 'old asset-manifest.json')


if __name__ == '__main__':
    unittest.main()
