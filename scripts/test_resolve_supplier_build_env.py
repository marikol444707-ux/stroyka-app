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
        self.assertIn(
            'REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=false',
            result.stdout,
        )

    def test_material_capability_ui_mirrors_enabled_backend_runtime(self):
        result = self.resolve(
            'SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            'REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true',
            result.stdout,
        )

    def test_material_capability_service_value_overrides_env_file(self):
        result = self.resolve(
            'SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=false',
            'SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            'REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=false',
            result.stdout,
        )

    def test_invalid_material_capability_value_blocks_build(self):
        result = self.resolve(
            'SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=TRUE'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn(
            'SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED', result.stderr
        )

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

    def test_mixed_openings_require_payments_openings_and_review(self):
        names=('PAYMENTS','OPENING_CONFIRMATIONS','MIXED_OPENINGS','MIXED_OPENING_REVIEW')
        result=self.resolve(' '.join(f'SUPPLIER_{name}_ENABLED=1' for name in names))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('REACT_APP_SUPPLIER_MIXED_OPENINGS_ENABLED=true',result.stdout)
        result=self.resolve(' '.join(f'SUPPLIER_{name}_ENABLED=1' for name in names if name!='MIXED_OPENING_REVIEW'))
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,'')

    def test_legacy_binding_requires_all_contract_dependencies(self):
        names=('PAYMENTS','DEAL_PARTIES','CONTRACT_SNAPSHOTS','DOCUMENT_CONTRACT_BINDINGS','LEGACY_CONTRACT_BINDING')
        for missing in (None,*names[:-1]):
            result=self.resolve(' '.join(f'SUPPLIER_{name}_ENABLED=1' for name in names if name!=missing))
            if missing:
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(result.stdout,'')
            else:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('REACT_APP_SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED=true',result.stdout)

    def test_line_specs_cannot_ship_without_contract_modules(self):
        result=self.resolve('SUPPLIER_INVOICE_LINE_SPECS_ENABLED=1')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,'')
        names=('INVOICE_LINE_SPECS','DEAL_PARTIES','CONTRACT_SNAPSHOTS','DOCUMENT_CONTRACT_BINDINGS')
        self.assertEqual(self.resolve(' '.join(f'SUPPLIER_{n}_ENABLED=1' for n in names)).returncode,0)

    def test_legacy_line_review_requires_contract_dependencies(self):
        names=('PAYMENTS','DEAL_PARTIES','CONTRACT_SNAPSHOTS','DOCUMENT_CONTRACT_BINDINGS','LEGACY_LINE_REVIEW')
        for missing in (None,*names[:-1]):
            result=self.resolve(' '.join(f'SUPPLIER_{name}_ENABLED=1' for name in names if name!=missing))
            if missing:
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(result.stdout,'')
            else:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('REACT_APP_SUPPLIER_LEGACY_LINE_REVIEW_ENABLED=true',result.stdout)
