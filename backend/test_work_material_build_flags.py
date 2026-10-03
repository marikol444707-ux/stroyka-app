import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = 'REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED'
spec = importlib.util.spec_from_file_location('work_build_verify', ROOT / 'scripts/verify-frontend-feature-build.py')
verify_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_module)


class WorkMaterialBuildFlagsTests(unittest.TestCase):
    def resolve(self, service='', contents=''):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / 'backend.env'
            env_path.write_text(contents)
            return subprocess.run(['bash', str(ROOT / 'scripts/resolve-frontend-build-env.sh'),
                                   service, str(env_path)], capture_output=True, text=True)

    def test_missing_backend_flag_explicitly_disables_frontend(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(KEY + '=0', result.stdout.splitlines())

    def test_backend_file_enables_frontend_without_exposing_other_values(self):
        result = self.resolve(contents='SECRET=private-value\nWORK_MATERIAL_ACCOUNTING_ENABLED="1"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(KEY + '=1', result.stdout.splitlines())
        self.assertNotIn('private-value', result.stdout + result.stderr)

    def test_service_overrides_file_in_both_directions(self):
        for service, file in (('0', '1'), ('1', '0')):
            with self.subTest(service=service):
                result = self.resolve('WORK_MATERIAL_ACCOUNTING_ENABLED=' + service,
                                      'WORK_MATERIAL_ACCOUNTING_ENABLED=' + file)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(KEY + '=' + service, result.stdout.splitlines())

    def test_duplicate_file_entries_match_backend_first_value(self):
        result = self.resolve(contents='WORK_MATERIAL_ACCOUNTING_ENABLED=0\nWORK_MATERIAL_ACCOUNTING_ENABLED=1\n')
        self.assertIn(KEY + '=0', result.stdout.splitlines())

    def test_invalid_value_blocks_release_without_echoing_it(self):
        result = self.resolve('WORK_MATERIAL_ACCOUNTING_ENABLED=private-invalid')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('private-invalid', result.stderr)

    def test_enabled_assignment_path_also_includes_work_material_mode(self):
        result = self.resolve('ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true '
                              'ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=2 WORK_MATERIAL_ACCOUNTING_ENABLED=1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(KEY + '=1', result.stdout.splitlines())
        self.assertIn('REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS=2', result.stdout)

    def build(self, mode, source='materialAccountingVersion stroyka:work-material-batch:v2:'):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'index.html').write_text(f'<meta name="stroyka-work-material-accounting" content="{mode}">')
        (root / 'main.js').write_text(source)
        (root / 'asset-manifest.json').write_text(json.dumps({'files': {'main.js': '/main.js'}}))
        return root

    def test_enabled_release_rejects_disabled_or_missing_build_flag(self):
        for mode in ('0', '%REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED%'):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'учёта материалов'):
                verify_module.verify(self.build(mode), KEY + '=1')

    def test_matching_builds_pass_and_disabled_backend_rejects_enabled_ui(self):
        verify_module.verify(self.build('1'), KEY + '=1')
        verify_module.verify(self.build('0', source='legacy'), KEY + '=0')
        with self.assertRaisesRegex(ValueError, 'учёта материалов'):
            verify_module.verify(self.build('1'), KEY + '=0')

    def test_enabled_build_requires_safe_submission_code(self):
        with self.assertRaisesRegex(ValueError, 'отправки работ'):
            verify_module.verify(self.build('1', source='legacy'), KEY + '=1')
