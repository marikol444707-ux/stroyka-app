"""Source-only integration checks. No application import, database or HTTP."""
import ast
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = 'acb1a3838a13cb650440340a774be46f1a3830a8'
SERVER = '57023611c6090c1bdf63a107a28eefadd1afb492'
AUDIT = 'a398d3874208038dd7dec3b2d9cf56ab66aa9487'


def source(ref, path):
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT, text=True)


def definitions(text):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


class SourcePreservationTests(unittest.TestCase):
    def test_server_main_definitions_preserved(self):
        self.check_definitions(SERVER)

    def test_audit_main_definitions_preserved(self):
        self.check_definitions(AUDIT)

    def check_definitions(self, ref):
        old = definitions(source(BASE, 'backend/main.py'))
        expected = definitions(source(ref, 'backend/main.py'))
        actual = definitions((ROOT / 'backend/main.py').read_text())
        for name, value in expected.items():
            if value != old.get(name):
                with self.subTest(name=name):
                    self.assertEqual(actual.get(name), value)

    def test_exclusive_files_from_both_lines_preserved(self):
        def changed(ref):
            return set(subprocess.check_output(['git', 'diff', '--name-only', BASE, ref],
                       cwd=ROOT, text=True).splitlines())
        server, audit = changed(SERVER), changed(AUDIT)
        for ref, paths in ((SERVER, server - audit), (AUDIT, audit - server)):
            for path in sorted(paths):
                # Migration history is deliberately unresolved, never certified here.
                if path.startswith('migrations/'):
                    continue
                with self.subTest(ref=ref, path=path):
                    self.assertEqual((ROOT / path).read_text(), source(ref, path))

    def test_jev_server_logic_with_audit_transaction_assignments(self):
        path = 'backend/features/job_candidates/routes.py'
        class StripTransactions(ast.NodeTransformer):
            def visit_Assign(self, node):
                if ast.unparse(node) == 'conn.autocommit = False':
                    return None
                return self.generic_visit(node)
        actual = ast.parse((ROOT / path).read_text())
        assignments = sum(isinstance(n, ast.Assign) and ast.unparse(n) == 'conn.autocommit = False'
                          for n in ast.walk(actual))
        self.assertEqual(assignments, 7)
        self.assertEqual(ast.dump(StripTransactions().visit(actual), include_attributes=False),
                         ast.dump(ast.parse(source(SERVER, path)), include_attributes=False))

    def test_preview_registration_contract_identical_to_both_parents(self):
        def protected(text):
            return [ast.dump(n, include_attributes=False) for n in ast.parse(text).body
                    if 'warehouse_anomaly' in ast.unparse(n)]
        current = protected((ROOT / 'backend/main.py').read_text())
        for ref in (SERVER, AUDIT):
            self.assertEqual(current, protected(source(ref, 'backend/main.py')))

    def test_migration_files_not_rewritten(self):
        # Confirms preservation, NOT a usable combined upgrade graph.
        for ref, pattern in ((SERVER, 'migrations/versions/*'), (AUDIT, 'migrations/versions/010[3-9]*')):
            paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ref,
                'migrations/versions'], cwd=ROOT, text=True).splitlines()
            import fnmatch
            for path in paths:
                if fnmatch.fnmatch(path, pattern):
                    with self.subTest(path=path):
                        self.assertEqual((ROOT / path).read_text(), source(ref, path))


if __name__ == '__main__':
    unittest.main()
