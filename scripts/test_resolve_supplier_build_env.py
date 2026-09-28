import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SupplierBuildFlagsTests(unittest.TestCase):
    def resolve(self, service='', file=''):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backend.env'
            path.write_text(file)
            return subprocess.run(['bash', str(ROOT / 'scripts/resolve-frontend-build-env.sh'),
                                   service, str(path)], capture_output=True, text=True)

    def test_default_off_is_explicit(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('PAYMENTS', 'OPENING_CONFIRMATIONS', 'ALLOCATED_REFUNDS'):
            self.assertIn(f'REACT_APP_SUPPLIER_{name}_ENABLED=false', result.stdout)

    def test_all_enabled_without_exporting_secrets(self):
        names = ('PAYMENTS', 'OPENING_CONFIRMATIONS', 'ALLOCATED_REFUNDS',
                 'PAYMENT_ALLOCATIONS', 'SETTLEMENTS')
        result = self.resolve(file='SECRET=not-for-output\n' + '\n'.join(
            f'SUPPLIER_{name}_ENABLED=1' for name in names))
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in names[:3]:
            self.assertIn(f'REACT_APP_SUPPLIER_{name}_ENABLED=true', result.stdout)
        self.assertNotIn('not-for-output', result.stdout + result.stderr)

    def test_service_overrides_file(self):
        result = self.resolve('SUPPLIER_PAYMENTS_ENABLED=0', 'SUPPLIER_PAYMENTS_ENABLED=1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REACT_APP_SUPPLIER_PAYMENTS_ENABLED=false', result.stdout)

    def test_file_duplicates_match_runtime_first_value_wins(self):
        result = self.resolve(file='SUPPLIER_PAYMENTS_ENABLED=0\nSUPPLIER_PAYMENTS_ENABLED=1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REACT_APP_SUPPLIER_PAYMENTS_ENABLED=false', result.stdout)

    def test_incomplete_refund_dependencies_block_build(self):
        for missing in ('PAYMENTS', 'PAYMENT_ALLOCATIONS', 'SETTLEMENTS'):
            with self.subTest(missing=missing):
                service = ' '.join(f'SUPPLIER_{name}_ENABLED=1' for name in
                    ('PAYMENTS', 'PAYMENT_ALLOCATIONS', 'SETTLEMENTS', 'ALLOCATED_REFUNDS') if name != missing)
                result = self.resolve(service)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('SUPPLIER_' + missing + '_ENABLED', result.stderr)

    def test_openings_require_payments(self):
        self.assertNotEqual(self.resolve('SUPPLIER_OPENING_CONFIRMATIONS_ENABLED=1').returncode, 0)

    def test_invalid_value_does_not_silently_disable_payments(self):
        result = self.resolve('SUPPLIER_PAYMENTS_ENABLED=true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SUPPLIER_PAYMENTS_ENABLED', result.stderr)
