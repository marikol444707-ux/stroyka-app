"""Only mocked transports/connections. No app imports or external execution."""
import unittest
from unittest.mock import MagicMock, patch
from backend.bootstrap_schema import SCHEMA_STATEMENTS
from scripts import unified_release as release
from scripts.qa_bootstrap_plan import migration_order


def connection():
    conn = MagicMock()
    conn.autocommit = False
    conn.cursor.return_value.fetchone.return_value = (0,)
    return conn


def adapter():
    a = MagicMock()
    a.verify_target.return_value = ('stroyka-qa-db', 5432, 'stroyka_qa')
    a.code_sha.return_value = 'a' * 40
    for name in ('writers_stopped', 'verify_recovery_bundle', 'restore_demonstrated',
                 'schema_is_empty', 'verify_schema', 'verify_restored_bundle'):
        getattr(a, name).return_value = True
    a.schema_connection.return_value = connection()
    return a


class InternalTests(unittest.TestCase):
    def test_public_entry_does_not_touch_adapter(self):
        a = adapter()
        with self.assertRaisesRegex(ValueError, 'EXECUTION_NOT_ACCEPTED'):
            release.qa_apply_or_restore(a, force=True)
        self.assertEqual(a.mock_calls, [])

    def test_transaction_success_commits_once(self):
        c = connection()
        release._qa_schema_transaction(c, SCHEMA_STATEMENTS)
        self.assertEqual(c.cursor.return_value.execute.call_count, 736)
        c.commit.assert_called_once()
        c.rollback.assert_not_called()
        c.cursor.return_value.close.assert_called_once()

    def test_statement_failure_rolls_back_without_commit(self):
        c = connection()
        c.cursor.return_value.execute.side_effect = [None, None, RuntimeError('synthetic')]
        with self.assertRaises(RuntimeError):
            release._qa_schema_transaction(c, SCHEMA_STATEMENTS)
        c.rollback.assert_called_once()
        c.commit.assert_not_called()
        c.cursor.return_value.close.assert_called_once()

    def test_uncertain_commit_propagates_and_never_retries(self):
        c = connection()
        c.commit.side_effect = RuntimeError('synthetic response loss')
        with self.assertRaises(RuntimeError):
            release._qa_schema_transaction(c, SCHEMA_STATEMENTS)
        c.commit.assert_called_once()
        c.rollback.assert_called_once()

    def test_existing_schema_and_unreviewed_sql_rejected(self):
        c = connection()
        c.cursor.return_value.fetchone.return_value = (1,)
        with self.assertRaises(ValueError):
            release._qa_schema_transaction(c, SCHEMA_STATEMENTS)
        self.assertEqual(c.cursor.return_value.execute.call_count, 1)
        with self.assertRaises(ValueError):
            release._qa_schema_transaction(connection(), ('DELETE FROM users;',))

    def test_autocommit_rejected_before_cursor(self):
        c = connection()
        c.autocommit = True
        with self.assertRaises(ValueError):
            release._qa_schema_transaction(c, SCHEMA_STATEMENTS)
        c.cursor.assert_not_called()

    def test_prepare_order_and_no_start(self):
        a = adapter()
        result = release._qa_prepare_internal(a, expected_sha='a'*40,
            statements=SCHEMA_STATEMENTS, revisions=migration_order(release.ROOT / 'migrations/versions'))
        calls = [c[0] for c in a.mock_calls]
        self.assertLess(calls.index('quiesce_both_backends_and_workers'), calls.index('backup_database_files_code_and_config'))
        self.assertLess(calls.index('schema_connection().commit'), calls.index('apply_migrations'))
        a.schema_connection.return_value.close.assert_called_once()
        self.assertFalse(result['firstBackendMayStart'])
        self.assertFalse(result['cleanupAllowed'])

    def test_prepare_failed_backup_never_connects_or_migrates(self):
        a = adapter()
        a.restore_demonstrated.return_value = False
        with self.assertRaises(ValueError):
            release._qa_prepare_internal(a, expected_sha='a'*40, statements=SCHEMA_STATEMENTS,
                revisions=migration_order(release.ROOT / 'migrations/versions'))
        a.schema_connection.assert_not_called()
        a.apply_migrations.assert_not_called()

    def test_restore_order_and_failure_stops_following_steps(self):
        a = adapter()
        result = release._qa_restore_internal(a, 'synthetic bundle')
        names = [c[0] for c in a.mock_calls]
        self.assertLess(names.index('preserve_failed_state'), names.index('restore_database'))
        self.assertLess(names.index('restore_database'), names.index('restore_frontend'))
        self.assertFalse(result['servicesMayStart'])
        a = adapter()
        a.restore_database.side_effect = RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):
            release._qa_restore_internal(a, 'synthetic bundle')
        a.restore_uploads.assert_not_called()
        a.verify_restored_bundle.assert_not_called()

    def test_wrong_target_stops_before_writers(self):
        a = adapter()
        a.verify_target.return_value = ('other', 5432, 'other')
        with self.assertRaises(ValueError):
            release._qa_restore_internal(a, 'synthetic bundle')
        a.quiesce_both_backends_and_workers.assert_not_called()
