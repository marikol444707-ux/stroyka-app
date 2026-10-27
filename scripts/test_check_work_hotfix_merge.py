import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_work_hotfix_merge as check


class WorkHotfixMergeTests(unittest.TestCase):
    def test_independent_server_edits_survive_real_three_way_merge(self):
        base = b'header\ninvoice=old\nseparator\nfooter\nserver=old\n'
        local = base.replace(b'server=old', b'server=production_fix')
        incoming = base.replace(b'invoice=old', b'invoice=supplier_fix')
        status, merged = check.merge_source(local, base, incoming)
        self.assertEqual(status, 'applicable_preserving_local_changes')
        self.assertIn(b'server=production_fix', merged)
        self.assertIn(b'invoice=supplier_fix', merged)

    def test_same_line_edits_are_conflicts_and_not_a_candidate(self):
        status, merged = check.merge_source(b'x=local\n', b'x=old\n', b'x=incoming\n')
        self.assertEqual(status, 'conflict')
        self.assertIsNone(merged)

    def test_untracked_different_source_is_not_overwritten(self):
        self.assertEqual(check.merge_source(b'local\n', None, b'incoming\n'), ('conflict', None))

    def test_source_symlinks_cannot_read_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config' / 'private').write_text('private')
            (root / 'backend').symlink_to(root / 'config', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'SOURCE_SYMLINK_REQUIRES_REVIEW'):
                check.read_current(root, 'backend/private')

    def run_inspect(self, base, incoming, mutate=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'backend').mkdir()
            source = root / 'backend/main.py'
            source.write_bytes(base)
            pins = {'backend/main.py': {'base': check.digest(base), 'target': check.digest(incoming)}}
            def fetch(revision, path, expected):
                if mutate and revision == check.TARGET:
                    source.write_bytes(mutate)
                return base if revision == check.BASE else incoming
            with patch.object(check, 'SOURCES', pins):
                report = check.inspect(root, fetch)
            return report, source.read_bytes()

    def test_report_keeps_startup_and_installation_gates_closed(self):
        base = b'def init_db():\n    return "legacy_updates"\n\nx = 1\n'
        incoming = base.replace(b'x = 1', b'x = 2')
        report, actual = self.run_inspect(base, incoming)
        self.assertEqual(actual, base)
        self.assertTrue(report['text_merge_applicable'])
        self.assertTrue(report['init_db_code_unchanged'])
        self.assertFalse(report['installation_ready'])
        self.assertFalse(report['database_accessed'])
        self.assertFalse(report['services_changed'])
        self.assertEqual(report['startup_data_gate'], 'NOT_EVALUATED')
        self.assertEqual(report['merged_application_tests'], 'NOT_RUN')

    def test_startup_code_changes_block_the_compatibility_result(self):
        base = b'def init_db():\n    return 1\n'
        report, actual = self.run_inspect(base, base.replace(b'return 1', b'return 2'))
        self.assertEqual(actual, base)
        self.assertFalse(report['text_merge_applicable'])
        self.assertFalse(report['init_db_code_unchanged'])

    def test_concurrent_edit_is_detected_and_never_rolled_back(self):
        base = b'def init_db():\n    return 1\n\nx = 1\n'
        changed = base + b'y = "concurrent_edit"\n'
        report, actual = self.run_inspect(base, base.replace(b'x = 1', b'x = 2'), changed)
        self.assertFalse(report['source_stable_during_check'])
        self.assertFalse(report['text_merge_applicable'])
        self.assertEqual(actual, changed)

    def test_errors_do_not_print_exception_details_or_secrets(self):
        with patch('sys.argv', ['check']), patch.object(check, 'inspect', side_effect=RuntimeError('SECRET')):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(check.main(), 1)
        self.assertNotIn('SECRET', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['code'], 'RuntimeError')

    def test_tampered_download_is_rejected_before_any_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(check, 'SOURCES', {'x.py': {'base': None, 'target': check.digest(b'pass\n')}}):
                with self.assertRaisesRegex(ValueError, 'PINNED_SOURCE_HASH_MISMATCH'):
                    check.inspect(Path(directory), lambda *args: b'altered')

    def test_conflict_details_show_only_redacted_server_code(self):
        base = b'def scan():\n    return "old"\n'
        local = b'def scan():\n    return "private-key-739812"  # private comment\n'
        incoming = b'def scan():\n    return "supplier-fixed"\n'
        report = check.describe_conflict(local, base, incoming)
        self.assertTrue(report['details_complete'])
        self.assertEqual(report['blocks'][0]['line'], 2)
        value = json.dumps(report)
        self.assertIn('PRIVATE_LITERAL', value)
        self.assertNotIn('private-key-739812', value)
        self.assertNotIn('private comment', value)

    def test_multiline_numeric_and_fstring_private_literals_are_redacted(self):
        base = b'def scan():\n    return 1\n'
        current = b'def scan():\n    text = """private line one\nprivate line two"""\n    return f"private-text-{value}", 918273645\n'
        lines = check.sanitized_source(current, base, base)
        result = ''.join(lines)
        self.assertEqual(len(lines), len(current.splitlines()))
        self.assertNotIn('private line', result)
        self.assertNotIn('private-text-', result)
        self.assertNotIn('918273645', result)

    def test_published_literals_are_retained_in_conflict_details(self):
        base = b'def scan():\n    return "old"\n'
        incoming = b'def scan():\n    return "supplier-fixed"\n'
        local = b'def scan():\n    return "supplier-fixed", "private"\n'
        report = check.describe_conflict(local, base, incoming)
        self.assertTrue(report['details_complete'])
        value = json.dumps(report)
        self.assertIn('supplier-fixed', value)
        self.assertNotIn('"private"', value)

    def test_conflict_details_are_not_emitted_without_an_actual_conflict(self):
        self.assertFalse(check.describe_conflict(b'x=1\n', b'x=1\n', b'x=2\n')['details_complete'])

    def test_oversized_merge_block_uses_small_function_diff_without_unblocking(self):
        base = ('def scan():\n' + ''.join('    x%d = %d + 1\n' % (i, i) for i in range(350))).encode()
        incoming = base.replace(b' + 1\n', b' + 2\n')
        current = base.replace(b'    x175 = 175 + 1\n', b'    x175 = "private-value-773219"\n')
        status, candidate = check.merge_source(current, base, incoming)
        self.assertEqual(status, 'conflict')
        self.assertIsNone(candidate)
        report = check.describe_conflict(current, base, incoming)
        self.assertTrue(report['details_complete'])
        self.assertEqual(report['details_kind'], 'function_local_diffs')
        self.assertTrue(report['original_merge_remains_blocked'])
        self.assertLess(len(report['functions'][0]['local_change_diff'].splitlines()), 20)
        self.assertNotIn('private-value-773219', json.dumps(report))
        self.assertIn('PRIVATE_LITERAL', json.dumps(report))

    def test_function_diff_excludes_untouched_function_and_private_fstring_text(self):
        base = b'def scan():\n    return 1\n\ndef unrelated():\n    return 10\n'
        incoming = base.replace(b'return 1\n', b'return 2\n')
        current = base.replace(b'return 1\n', b'return f"private-prefix-{1}", 918273645\n')
        report = check.describe_function_differences(current, base, incoming)
        self.assertTrue(report['details_complete'])
        self.assertEqual([row['function'] for row in report['functions']], ['scan'])
        value = json.dumps(report)
        self.assertNotIn('private-prefix-', value)
        self.assertNotIn('918273645', value)
        self.assertNotIn('unrelated', value)

    def test_global_changes_are_not_hidden_by_function_only_diagnostics(self):
        base = b'flag = 1\ndef scan():\n    return 1\n'
        report = check.describe_function_differences(base, base, base.replace(b'flag = 1', b'flag = 2'))
        self.assertFalse(report['details_complete'])
        self.assertEqual(report['code'], 'UPSTREAM_GLOBAL_CHANGES_REQUIRE_REVIEW')

    def function_merge_fixture(self):
        base = (b'def init_db():\n    return "legacy startup"\n\n'
                b'def get_work_journal():\n    return {"scope": "company", "status": "old"}\n\n'
                b'def unrelated():\n    return "original"\n')
        incoming = base.replace(b'"status": "old"', b'"status": "new"')
        current = base.replace(b'"status": "old"', b"'status' : 'old'")
        current = current.replace(b'return "original"', b'return "SERVER FIX MUST SURVIVE"')
        self.assertEqual(check.merge_source(current, base, incoming), ('conflict', None))
        return current, base, incoming

    def test_verified_function_merge_preserves_every_unrelated_source_byte(self):
        current, base, incoming = self.function_merge_fixture()
        status, merged = check.merge_source(current, base, incoming, python_functions=True)
        self.assertEqual(status, 'applicable_verified_function_merge')
        self.assertIn(b'SERVER FIX MUST SURVIVE', merged)
        self.assertEqual(merged, current.replace(b"'status' : 'old'", b'"status": "new"'))
        self.assertEqual(check.function_ast(merged, 'init_db'), check.function_ast(current, 'init_db'))

    def test_different_server_logic_is_not_resolved_by_function_replacement(self):
        current, base, incoming = self.function_merge_fixture()
        changed = current.replace(b"'status' : 'old'", b"'status' : 'production-change'")
        self.assertEqual(check.merge_reviewed_python_functions(changed, base, incoming), ('conflict', None))

    def test_server_comments_cannot_be_discarded_even_when_asts_match(self):
        current, base, incoming = self.function_merge_fixture()
        changed = current.replace(b'def get_work_journal():\n', b'def get_work_journal():\n    # Preserve operator note\n')
        self.assertEqual(check.function_ast(changed, 'get_work_journal'), check.function_ast(base, 'get_work_journal'))
        self.assertEqual(check.merge_reviewed_python_functions(changed, base, incoming), ('conflict', None))

    def test_duplicate_function_names_block_replacement(self):
        current, base, incoming = self.function_merge_fixture()
        current += b'\ndef get_work_journal():\n    return {}\n'
        self.assertEqual(check.merge_reviewed_python_functions(current, base, incoming), ('conflict', None))

    def test_unreviewed_functions_or_globals_cannot_be_changed(self):
        current, base, incoming = self.function_merge_fixture()
        self.assertEqual(check.merge_reviewed_python_functions(current, base, incoming + b'\nflag = 1\n'), ('conflict', None))
        self.assertEqual(check.merge_reviewed_python_functions(current, base, incoming.replace(b'"original"', b'"unreviewed"')), ('conflict', None))

    def test_already_updated_semantics_keep_local_formatting(self):
        current, base, incoming = self.function_merge_fixture()
        current = current.replace(b"'status' : 'old'", b"'status' : 'new'")
        status, merged = check.merge_reviewed_python_functions(current, base, incoming)
        self.assertEqual(status, 'applicable_verified_function_merge')
        self.assertEqual(merged, current)

    def test_structural_merge_is_not_reported_as_a_text_merge_or_ready_installation(self):
        current, base, incoming = self.function_merge_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'backend').mkdir()
            (root / 'backend/main.py').write_bytes(current)
            pins = {'backend/main.py': {'base': check.digest(base), 'target': check.digest(incoming)}}
            with patch.object(check, 'SOURCES', pins):
                report = check.inspect(root, lambda revision, *_: base if revision == check.BASE else incoming)
            self.assertTrue(report['source_merge_applicable'])
            self.assertFalse(report['text_merge_applicable'])
            self.assertTrue(report['init_db_code_unchanged'])
            self.assertFalse(report['installation_ready'])
            self.assertEqual(report['startup_data_gate'], 'NOT_EVALUATED')
            self.assertEqual((root / 'backend/main.py').read_bytes(), current)

    def test_startup_fingerprints_cover_constants_without_exposing_their_values(self):
        source = b'OWN_EXPENSE_NO_PROJECT_CATEGORY = "PRIVATE_CATEGORY"\ndef init_db():\n    return 1\n'
        hashes = check.startup_fingerprints(source)
        self.assertEqual(set(hashes), {'init_db', 'OWN_EXPENSE_NO_PROJECT_CATEGORY'})
        self.assertNotIn('PRIVATE_CATEGORY', json.dumps(hashes))
        self.assertNotEqual(hashes['OWN_EXPENSE_NO_PROJECT_CATEGORY'], check.startup_fingerprints(
            source.replace(b'PRIVATE_CATEGORY', b'OTHER_CATEGORY'))['OWN_EXPENSE_NO_PROJECT_CATEGORY'])


if __name__ == '__main__':
    unittest.main()
