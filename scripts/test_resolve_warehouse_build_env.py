import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('warehouse_build_env', Path(__file__).with_name('resolve-warehouse-build-env.py'))
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class WarehouseBuildFlagsTests(unittest.TestCase):
    def test_quality_mode_enables_both_frontend_panels(self):
        flags = resolver.resolve('WAREHOUSE_DISTRIBUTION_ENABLED=1 WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=1 OWNED_DISTRIBUTION_QUALITY_ENABLED=1', '')
        self.assertEqual(flags, ['REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true',
                                 'REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=true',
                                 'REACT_APP_INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED=false'])

    def test_service_overrides_file_without_exporting_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backend.env'
            path.write_text('WAREHOUSE_DISTRIBUTION_ENABLED=1\nWAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=1\nSECRET=not-for-output\n')
            flags = resolver.resolve('WAREHOUSE_DISTRIBUTION_ENABLED=0', str(path))
        self.assertEqual(flags, ['REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=false',
                                 'REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=false',
                                 'REACT_APP_INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED=false'])

    def test_intercompany_panel_follows_backend_flag_and_parent_workspace(self):
        flags = resolver.resolve(
            'WAREHOUSE_DISTRIBUTION_ENABLED=1 INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED=1', '')
        self.assertEqual(flags[-1], 'REACT_APP_INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED=true')
        flags = resolver.resolve('INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED=1', '')
        self.assertEqual(flags[-1], 'REACT_APP_INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED=false')

    def test_inconsistent_quality_configuration_blocks_build(self):
        with self.assertRaises(ValueError):
            resolver.resolve('OWNED_DISTRIBUTION_QUALITY_ENABLED=1', '')
