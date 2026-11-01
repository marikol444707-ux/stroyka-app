"""Offline tests only: AST, inert constants, temporary text fixtures."""
import ast
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.qa_bootstrap_plan import migration_order, preparation_plan, require_execution_allowed, recovery_gaps

ROOT = Path(__file__).resolve().parents[1]


class PreparationTests(unittest.TestCase):
    def test_backup_claims_are_not_restore_evidence_or_permission(self):
        required = recovery_gaps({})
        self.assertIn('restore_demonstrated', required)
        self.assertEqual(recovery_gaps({key: 'true' for key in required}), required)
        self.assertEqual(recovery_gaps({key: 1 for key in required}), required)
        self.assertEqual(recovery_gaps({key: True for key in required}), [])
        with self.assertRaises(RuntimeError):
            require_execution_allowed(recovery_gaps=[])

    def test_real_graph_and_unconditional_hold(self):
        plan = preparation_plan(ROOT / 'migrations/versions')
        self.assertEqual(len(plan['migration_order']), 98)
        self.assertEqual(plan['migration_order'][0], '0001_baseline')
        self.assertFalse(plan['execution_allowed'])
        self.assertFalse(plan['cleanup_allowed'])
        with self.assertRaisesRegex(RuntimeError, 'EXECUTION_NOT_ACCEPTED'):
            require_execution_allowed(approved=True, force=True)

    def test_inert_schema_exact_preservation(self):
        tree = ast.parse((ROOT / 'backend/bootstrap_schema.py').read_text())
        self.assertEqual(len(tree.body), 2)
        sql = ast.literal_eval(tree.body[1].value)
        self.assertEqual(hashlib.sha256(sql.encode()).hexdigest(), '8f402c3d1cc8f04adfd484c8295011bb6c73db386d4dee51b54efddd39ffe30c')

    def test_main_retains_existing_startup_order(self):
        tree = ast.parse((ROOT / 'backend/main.py').read_text())
        init = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'init_db')
        self.assertEqual(init.body[2].value.args[0].id, 'LEGACY_SCHEMA_BATCH')
        calls = [n.value.func.id for n in tree.body if isinstance(n, ast.Expr)
                 and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)]
        self.assertEqual(calls[calls.index('init_db')+1], 'ensure_agent_jobs_schema')

    def test_invalid_graphs_fail_closed(self):
        fixtures = [
            [('0109_legacy_payment_requests', 'missing')],
            [('0109_legacy_payment_requests', None), ('orphan', None)],
            [('0109_legacy_payment_requests', None), ('cycle', 'cycle')],
            [('0109_legacy_payment_requests', None), ('0109_legacy_payment_requests', None)],
        ]
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as folder:
                for i, (revision, parent) in enumerate(fixture):
                    Path(folder, f'{i}.py').write_text(f'revision={revision!r}\ndown_revision={parent!r}\n')
                with self.assertRaises(ValueError):
                    migration_order(folder)

    def test_planner_has_no_runtime_imports(self):
        tree = ast.parse((ROOT / 'scripts/qa_bootstrap_plan.py').read_text())
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertEqual(set(modules), {'ast', 'pathlib'})


if __name__ == '__main__':
    unittest.main()
