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


if __name__ == '__main__':
    unittest.main()
