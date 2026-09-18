import unittest
from unittest.mock import patch

from backend.features.material_aliases.readiness_report import (
    REQUIRED_COLUMNS, collect_alias_readiness, run_alias_readiness,
)
from backend.features.material_control_ownership.test_readiness_report import FakeCursor, FakeConnection


SCHEMA = [dict(table_name=table, column_name=col)
          for table, cols in REQUIRED_COLUMNS.items() for col in cols]


class AliasReadinessReportTests(unittest.TestCase):
    def test_missing_schema_does_not_query_or_create_business_tables(self):
        cur = FakeCursor([[]])
        report = collect_alias_readiness(cur)
        self.assertFalse(report['schemaReady'])
        self.assertFalse(report['scanComplete'])
        self.assertEqual(len(cur.calls), 1)

    def test_collection_selects_only_needed_columns_and_has_limits(self):
        cur = FakeCursor([SCHEMA, [], []])
        report = collect_alias_readiness(cur)
        self.assertTrue(report['scanComplete'])
        self.assertFalse(report['readyForCutover'])
        self.assertTrue(all(sql.startswith('SELECT') for sql, _ in cur.calls))
        self.assertEqual([params for _, params in cur.calls[1:]], [(50001,), (50001,)])
        self.assertNotIn('updated_by', str(cur.calls))

    def test_project_scan_limit_cannot_produce_ready_report(self):
        cur = FakeCursor([SCHEMA, [{}, {}]])
        report = collect_alias_readiness(cur, row_limit=1)
        self.assertFalse(report['scanComplete'])
        self.assertEqual(report['reasonCode'], 'project_scan_limit_exceeded')
        self.assertEqual(len(cur.calls), 2)

    def test_alias_scan_limit_cannot_produce_ready_report(self):
        report = collect_alias_readiness(FakeCursor([SCHEMA, [], [{}, {}]]), row_limit=1)
        self.assertFalse(report['scanComplete'])
        self.assertEqual(report['reasonCode'], 'alias_scan_limit_exceeded')

    def test_invalid_limits_are_rejected_before_queries(self):
        for kwargs in ({'row_limit': 0}, {'row_limit': True}, {'row_limit': 100001},
                       {'preview_limit': -1}, {'preview_limit': 1001}):
            cur = FakeCursor([])
            with self.assertRaises(ValueError):
                collect_alias_readiness(cur, **kwargs)
            self.assertEqual(cur.calls, [])

    def test_success_uses_read_only_snapshot_and_rolls_back(self):
        cur = FakeCursor([SCHEMA, [], []])
        conn = FakeConnection(cur)
        report = run_alias_readiness(lambda: conn)
        self.assertEqual(conn.session, dict(readonly=True, autocommit=False, isolation_level='REPEATABLE READ'))
        self.assertTrue(report['readOnlyTransaction'])
        self.assertTrue(report['rolledBack'])
        self.assertEqual((conn.rollbacks, conn.commits), (1, 0))
        self.assertTrue(conn.closed and cur.closed)

    def test_failure_rolls_back_and_closes_without_commit(self):
        cur, conn = FakeCursor([]), None
        conn = FakeConnection(cur)
        with patch('backend.features.material_aliases.readiness_report.collect_alias_readiness', side_effect=RuntimeError('synthetic')):
            with self.assertRaises(RuntimeError):
                run_alias_readiness(lambda: conn)
        self.assertEqual((conn.rollbacks, conn.commits), (1, 0))
        self.assertTrue(conn.closed and cur.closed)
