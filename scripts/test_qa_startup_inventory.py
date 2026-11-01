import ast
from pathlib import Path
import tempfile
import unittest
from scripts.qa_startup_inventory import StartupCalls, inventory


class InventoryTests(unittest.TestCase):
    def test_definitions_are_not_executed_but_defaults_and_decorators_are(self):
        visitor = StartupCalls()
        visitor.visit(ast.parse('@decorate()\ndef f(x=default()):\n dangerous()\nf()\n'))
        self.assertEqual([x['call'] for x in visitor.calls], ['decorate', 'default', 'f'])

    def test_imports_are_only_read_and_cycles_terminate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'backend').mkdir()
            (root / 'backend/main.py').write_text('from backend import helper\nraise RuntimeError("must never execute")\n')
            (root / 'backend/helper.py').write_text('import backend.main\nopen("MUST_NOT_EXIST", "w")\n')
            result = inventory(root)
            self.assertEqual(len(result['files']), 2)
            self.assertFalse(result['execution_allowed'])
            self.assertFalse((root / 'MUST_NOT_EXIST').exists())

    def test_dynamic_import_is_explicit_uncertainty(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'backend').mkdir()
            (root / 'backend/main.py').write_text('importlib.import_module(name)\n')
            self.assertEqual(inventory(root)['files'][0]['dynamic_call_lines'], [1])
