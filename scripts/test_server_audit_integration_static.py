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
                # Migration files have dedicated history/body checks below.
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

    def test_migration_files_preserved_except_reviewed_audit_parent(self):
        for ref, pattern in ((SERVER, 'migrations/versions/*'), (AUDIT, 'migrations/versions/010[3-9]*')):
            paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ref,
                'migrations/versions'], cwd=ROOT, text=True).splitlines()
            import fnmatch
            for path in paths:
                if fnmatch.fnmatch(path, pattern):
                    with self.subTest(path=path):
                        expected = source(ref, path)
                        actual = (ROOT / path).read_text()
                        if ref == AUDIT and path.endswith('/0103_room_owner_identity.py'):
                            # Only the not-deployed-on-this-server audit continuation
                            # changes parent; every SQL body and revision ID stays intact.
                            expected = expected.replace("down_revision = '0102_platform_company_features'",
                                "down_revision = '0104_jev_search_run_history'")
                            self.assertEqual(ast.dump(ast.parse(actual), include_attributes=False),
                                             ast.dump(ast.parse(expected), include_attributes=False))
                        else:
                            self.assertEqual(actual, expected)

    def test_graph_has_single_head_and_no_dangling_parent(self):
        graph = migration_graph()
        parents = {p for p in graph.values() if p is not None}
        self.assertFalse(parents - graph.keys())
        self.assertEqual(set(graph) - parents, {'0109_legacy_payment_requests'})
        for revision in graph:
            self.assertLessEqual(len(revision), 32)
            visited = set()
            cursor = revision
            while cursor is not None:
                self.assertNotIn(cursor, visited)
                visited.add(cursor)
                cursor = graph[cursor]

    def test_exact_pending_path_from_reported_server_revision(self):
        graph = migration_graph()
        pending = []
        cursor = '0109_legacy_payment_requests'
        while cursor != '0104_jev_search_run_history':
            pending.append(cursor)
            cursor = graph[cursor]
        self.assertEqual(list(reversed(pending)), [
            '0103_room_owner_identity', '0104_legacy_project_owners',
            '0105_settlement_cash_guard', '0106_document_version_owner',
            '0107_room_work_owner', '0108_project_create_requests',
            '0109_legacy_payment_requests'])
        self.assertNotIn('0101_job_candidates', graph)
        self.assertNotIn('0102_platform_company_features', graph)

    def test_required_schema_producers_precede_continuation(self):
        graph = migration_graph()
        ancestors = set()
        cursor = '0104_jev_search_run_history'
        while cursor is not None:
            ancestors.add(cursor)
            cursor = graph[cursor]
        for prefix in ('0023_', '0045_', '0055_', '0072_'):
            self.assertTrue(any(r.startswith(prefix) for r in ancestors), prefix)


def migration_graph():
    graph = {}
    for path in (ROOT / 'migrations/versions').glob('*.py'):
        values = {}
        for node in ast.parse(path.read_text()).body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in ('revision', 'down_revision')):
                values[node.targets[0].id] = ast.literal_eval(node.value)
        if values.get('revision'):
            if values['revision'] in graph:
                raise AssertionError('Duplicate revision ID')
            graph[values['revision']] = values.get('down_revision')
    return graph


if __name__ == '__main__':
    unittest.main()
