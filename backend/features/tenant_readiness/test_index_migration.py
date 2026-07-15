import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.tenant_readiness.index_migration import (
    APPLY_CONFIRMATION,
    INDEX_NAME,
    build_index_report,
    main,
    run_index_migration,
)


def facts(*, present=False, rows=8, columns=None):
    indexes = []
    if present:
        indexes.append({
            "name": INDEX_NAME,
            "definition": (
                "CREATE INDEX idx_work_journal_company_project "
                "ON public.work_journal USING btree (company_id, project)"
            ),
        })
    return {
        "work_journal": {
            "exists": True,
            "columns": set(columns or {"company_id", "project"}),
            "indexes": indexes,
            "totalRows": rows,
        }
    }


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params)))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.session_calls = []
        self.committed = False
        self.rolled_back = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class TenantIndexMigrationTests(unittest.TestCase):
    def test_report_plans_only_missing_work_journal_index(self):
        report = build_index_report(facts())

        self.assertTrue(report["readyForApply"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["missingCount"], 1)
        self.assertEqual(report["missingIndexes"][0]["indexName"], INDEX_NAME)
        self.assertEqual(
            report["rollbackSql"],
            ["DROP INDEX IF EXISTS idx_work_journal_company_project;"],
        )

    def test_existing_equivalent_index_is_complete(self):
        report = build_index_report(facts(present=True))

        self.assertTrue(report["complete"])
        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["missingCount"], 0)

    def test_equivalent_index_with_another_name_is_complete(self):
        existing = facts()
        existing["work_journal"]["indexes"] = [{
            "name": "idx_existing_owner_lookup",
            "definition": (
                "CREATE INDEX idx_existing_owner_lookup "
                "ON public.work_journal USING btree (company_id, project)"
            ),
        }]

        report = build_index_report(existing)

        self.assertTrue(report["complete"])
        self.assertEqual(report["matchingIndex"], "idx_existing_owner_lookup")

    def test_partial_index_does_not_satisfy_full_table_requirement(self):
        existing = facts()
        existing["work_journal"]["indexes"] = [{
            "name": "idx_partial_owner_lookup",
            "definition": (
                "CREATE INDEX idx_partial_owner_lookup "
                "ON public.work_journal USING btree (company_id, project) "
                "WHERE company_id IS NOT NULL"
            ),
        }]

        report = build_index_report(existing)

        self.assertFalse(report["complete"])
        self.assertEqual(report["missingCount"], 1)

    def test_missing_required_column_blocks_apply(self):
        report = build_index_report(facts(columns={"company_id"}))

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["blockers"][0]["reason"], "columns_missing")
        self.assertEqual(report["blockers"][0]["columns"], ["project"])

    def test_dry_run_is_read_only_and_rolls_back(self):
        connection = FakeConnection()
        with patch(
            "backend.features.tenant_readiness.index_migration.collect_index_facts",
            return_value=facts(),
        ):
            result = run_index_migration(connection)

        self.assertTrue(result["dryRun"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        self.assertEqual(
            connection.session_calls,
            [{"readonly": True, "autocommit": False}],
        )
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.cursor_value.closed)

    def test_apply_creates_index_only_after_exact_plan_guard(self):
        connection = FakeConnection()
        before = build_index_report(facts())
        after = build_index_report(facts(present=True))
        with patch(
            "backend.features.tenant_readiness.index_migration.collect_index_facts",
            side_effect=[facts(), facts(present=True)],
        ):
            result = run_index_migration(
                connection,
                apply=True,
                expected_missing_count=1,
                expected_plan_sha256=before["planSha256"],
            )

        self.assertTrue(result["complete"])
        self.assertEqual(result["schemaWritesAttempted"], 1)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_work_journal_company_project "
            "ON work_journal(company_id,project)",
            sql,
        )
        self.assertEqual(result["postSummary"], after["summary"])

    def test_apply_rejects_plan_drift_before_create(self):
        connection = FakeConnection()
        with patch(
            "backend.features.tenant_readiness.index_migration.collect_index_facts",
            return_value=facts(),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan changed"):
                run_index_migration(
                    connection,
                    apply=True,
                    expected_missing_count=1,
                    expected_plan_sha256="f" * 64,
                )

        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertNotIn("CREATE INDEX", sql)
        self.assertTrue(connection.rolled_back)

    def test_cli_requires_confirmation_count_and_sha(self):
        with patch(
            "backend.features.tenant_readiness.index_migration.psycopg2.connect"
        ) as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([
                    "--apply",
                    "--confirm",
                    APPLY_CONFIRMATION,
                    "--expected-missing-count",
                    "1",
                ])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
