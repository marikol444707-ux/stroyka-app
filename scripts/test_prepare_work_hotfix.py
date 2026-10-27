import ast
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import prepare_work_hotfix as prepare


class WorkHotfixPreparationTests(unittest.TestCase):
    def test_only_source_paths_are_copied_and_environment_uploads_are_excluded(self):
        for name in ('backend/.env', 'backend/.env.bak.123', '.env', 'backend/uploads/customer.pdf',
                     'backend/uploads.backup/invoice.py', 'src/../../etc/passwd', '/etc/passwd',
                     '.git/config', 'build/main.js', 'node_modules/package/index.js'):
            self.assertFalse(prepare.allowed_source(name, True), name)
            self.assertFalse(prepare.allowed_source(name, False), name)
        self.assertTrue(prepare.allowed_source('src/NewComponent.jsx', False))
        self.assertTrue(prepare.allowed_source('public/logo.png', True))
        self.assertFalse(prepare.allowed_source('public/customer-photo.png', False))

    def test_binary_public_asset_is_copied_without_using_source_text_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'public').mkdir()
            data = b'\x89PNG\0\0binary\xff'
            (root / 'public/logo.png').write_bytes(data)
            self.assertEqual(prepare.read_stage_source(root, 'public/logo.png'), data)

    def test_symlink_source_cannot_read_a_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'backend').mkdir()
            (root / 'backend/.env').write_text('PRIVATE')
            (root / 'backend/source.py').symlink_to(root / 'backend/.env')
            with self.assertRaisesRegex(prepare.Stop, 'SOURCE_COPY_SYMLINK'):
                prepare.read_stage_source(root, 'backend/source.py')

    def test_wrong_host_exits_before_any_commands_or_staging(self):
        with patch.object(prepare.os, 'geteuid', return_value=0), patch.object(prepare.socket, 'gethostname', return_value='other'), patch.object(prepare, 'command') as command:
            with self.assertRaisesRegex(prepare.Stop, 'WRONG_HOST_OR_USER'):
                prepare.verify_baseline()
            command.assert_not_called()

    def test_only_pinned_payloads_are_written_and_tampering_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payloads = {'payload/test.py': {'revision': 'a' * 40, 'source': 'scripts/test.py', 'sha256': prepare.digest(b'pass\n')}}
            response = contextlib.nullcontext(io.BytesIO(b'altered'))
            with patch.object(prepare, 'PAYLOADS', payloads), patch.object(prepare.urllib.request, 'urlopen', return_value=response):
                with self.assertRaisesRegex(prepare.Stop, 'PINNED_PAYLOAD_CHANGED'):
                    prepare.fetch_payloads(root)
            self.assertFalse((root / 'payload/test.py').exists())

    def test_test_environment_never_inherits_production_credentials(self):
        with patch.dict('os.environ', {'DB_PASSWORD': 'PRIVATE_DB', 'AUTH_SECRET': 'PRIVATE_AUTH', 'SMTP_PASSWORD': 'PRIVATE_MAIL'}):
            environment = prepare.clean_env(Path('/tmp/synthetic-stage'))
        self.assertNotIn('DB_PASSWORD', environment)
        self.assertNotIn('AUTH_SECRET', environment)
        self.assertNotIn('SMTP_PASSWORD', environment)
        self.assertNotIn('PRIVATE', json.dumps(environment))

    def test_native_postgres_fixture_is_not_run_on_the_production_host(self):
        source = Path(prepare.__file__).read_text()
        self.assertNotIn('run_supplier_catalog_postgres_tests', source)
        self.assertNotIn("['initdb'", source)
        self.assertNotIn("['pg_restore'", source)
        for body in (source, prepare.SNAPSHOT_ADAPTER, prepare.PURE_TEST_ADAPTER):
            tree = ast.parse(body)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or '']
                    self.assertNotIn('backend.main', names)

    def test_production_control_commands_are_never_present(self):
        for source in (Path(prepare.__file__).read_text(), prepare.SNAPSHOT_ADAPTER):
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.List):
                    values = [element.value for element in node.elts if isinstance(element, ast.Constant) and isinstance(element.value, str)]
                    if values and values[0].endswith('systemctl'):
                        self.assertFalse(set(values) & {'start', 'stop', 'restart', 'reload', 'enable', 'disable'})

    def test_supplier_tests_run_real_assertions_without_importing_backend_startup(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-I', '-B', '-c', prepare.PURE_TEST_ADAPTER, str(root)],
                                capture_output=True, text=True, timeout=30,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertIn('PURE_BACKEND_ACCEPTANCE tests=3 skipped=0', result.stdout)

    def test_real_source_copy_merges_only_in_stage_and_never_copies_dotenv(self):
        from scripts import check_work_hotfix_merge as merge
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'app'
            stage = Path(directory) / 'stage'
            root.mkdir();stage.mkdir()
            for name in ('home', 'tmp'):
                (stage/name).mkdir()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            originals = {'src/current.js': b'old\n', 'public/logo.png': b'PNG\0binary',
                         'backend/.env': b'PRIVATE_PASSWORD', 'backend/new_source.py': b'pass\n',
                         'backend/uploads/customer.py': b'PRIVATE_CUSTOMER'}
            for name, data in originals.items():
                path = root/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(data)
            subprocess.run(['git', '-C', str(root), 'add', 'src/current.js', 'public/logo.png', 'backend/.env'], check=True)
            def read(path, name):
                return (path/name).read_bytes() if (path/name).exists() else None
            fake = SimpleNamespace(SOURCES={'src/current.js':{}, 'src/new.js':{}}, BASE='base', TARGET='target',
                read_current=read, merge_source=merge.merge_source,
                fetch_source=lambda revision,name,*_: (b'old\n' if name=='src/current.js' else None)
                    if revision=='base' else b'new\n')
            candidates={name:prepare.digest(b'new\n') for name in fake.SOURCES}
            # Use the same boundary contract as the pinned checker.
            fake.SOURCES={name:{'base':None,'target':None} for name in fake.SOURCES}
            with patch.object(prepare,'ROOT',root),patch.object(prepare,'CANDIDATE_HASHES',candidates):
                source,before=prepare.copy_source(stage,fake)
            self.assertEqual((source/'src/current.js').read_bytes(),b'new\n')
            self.assertEqual((source/'src/new.js').read_bytes(),b'new\n')
            self.assertEqual((source/'public/logo.png').read_bytes(),originals['public/logo.png'])
            self.assertTrue((source/'backend/new_source.py').is_file())
            self.assertFalse((source/'backend/.env').exists())
            self.assertFalse((source/'backend/uploads').exists())
            self.assertNotIn('backend/.env',before)
            for name,data in originals.items():
                self.assertEqual((root/name).read_bytes(),data)


if __name__ == '__main__':
    unittest.main()
