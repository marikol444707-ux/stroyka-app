"""The release entrypoint must preserve the API's company-owned alias mode."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
KEY = 'REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED'


class AliasBuildFlagsTests(unittest.TestCase):
    def resolve(self, service='', file=''):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backend.env'
            path.write_text(file)
            # Ambient frontend flags must not override the backend configuration.
            env = dict(os.environ, REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED='1')
            return subprocess.run(['bash', str(ROOT / 'scripts/resolve-frontend-build-env.sh'),
                                   service, str(path)], env=env, capture_output=True, text=True)

    def test_default_disabled_is_explicit(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(KEY + '=0', result.stdout.splitlines())

    def test_enabled_backend_file_enables_owned_editor(self):
        result = self.resolve(file='COMPANY_MATERIAL_ALIASES_ENABLED=1\nSECRET=never-export\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(KEY + '=1', result.stdout.splitlines())
        self.assertNotIn('never-export', result.stdout + result.stderr)

    def test_service_overrides_file_in_both_directions(self):
        for service, file in [('0', '1'), ('1', '0')]:
            with self.subTest(service=service):
                result = self.resolve('COMPANY_MATERIAL_ALIASES_ENABLED=' + service,
                                      'COMPANY_MATERIAL_ALIASES_ENABLED=' + file)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(KEY + '=' + service, result.stdout.splitlines())

    def test_quoted_file_and_assignment_enabled_branch_preserve_alias_flag(self):
        result = self.resolve('ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=2',
                              "COMPANY_MATERIAL_ALIASES_ENABLED='1'\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(KEY + '=1', result.stdout.splitlines())

    def test_invalid_backend_mode_blocks_build_without_output(self):
        result = self.resolve('COMPANY_MATERIAL_ALIASES_ENABLED=true')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('COMPANY_MATERIAL_ALIASES_ENABLED', result.stderr)


if __name__ == '__main__':
    unittest.main()
