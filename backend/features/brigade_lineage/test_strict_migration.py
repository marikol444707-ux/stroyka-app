import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.brigade_lineage.strict_migration import (
    APPLY_CONFIRMATION,
    main,
    run_strict_migration,
)
from backend.features.brigade_lineage.strict_schema import (
    build_strict_migration_report,
)
from backend.features.brigade_lineage.test_strict_schema import (
    CONSTRAINT_NAMES,
    reports,
)


class FakeCursor:
    def __init__(self, fail_on=None):
        self.calls = []
        self.closed = False
        self.fail_on = fail_on

    def execute(self, sql, params=()):
        compact = " ".join(str(sql).split())
        self.calls.append((compact, tuple(params)))
        if self.fail_on and self.fail_on in compact:
            raise RuntimeError("simulated DDL failure")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor=None):
        self.cursor_value = cursor or FakeCursor()
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


class StrictLineageMigrationRunnerTests(unittest.TestCase):
    def test_dry_run_is_read_only_and_rolls_back_without_ddl(self):
        connection = FakeConnection()
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            return_value=reports(),
        ):
            result = run_strict_migration(connection)

        self.assertTrue(result["dryRun"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.cursor_value.closed)
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertNotIn("ALTER TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)

    def test_apply_executes_guarded_transaction_and_commits_after_green_postcheck(self):
        connection = FakeConnection()
        before = build_strict_migration_report(*reports())
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            side_effect=[reports(), reports(complete=True)],
        ):
            result = run_strict_migration(
                connection,
                apply=True,
                expected_change_count=before["changeCount"],
                expected_plan_sha256=before["planSha256"],
            )

        self.assertTrue(result["complete"])
        self.assertEqual(result["schemaWritesAttempted"], 15)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertIn("LOCK TABLE public.estimates", sql)
        self.assertIn("ALTER COLUMN source_type DROP DEFAULT", sql)
        self.assertIn("ALTER COLUMN source_type SET NOT NULL", sql)
        self.assertIn("ON DELETE RESTRICT", sql)
        self.assertIn("WHERE source_type='estimate'", sql)
        self.assertIn("WHERE sections_sha256 IS NOT NULL", sql)
        self.assertIn(
            "CREATE FUNCTION public.brigade_contract_items_source_guard", sql
        )
        self.assertNotIn("CREATE OR REPLACE FUNCTION", sql)
        self.assertIn("OLD.source_type IS DISTINCT FROM NEW.source_type", sql)
        self.assertIn("ev.sections_sha256 IS NOT NULL", sql)
        self.assertIn("bc.company_id IS DISTINCT FROM e.company_id", sql)
        self.assertIn(
            "CREATE TRIGGER trg_brigade_contract_items_source_guard", sql
        )
        self.assertIn(
            "CREATE TRIGGER trg_estimate_versions_snapshot_immutable", sql
        )

    def test_apply_rejects_plan_drift_before_first_ddl_statement(self):
        connection = FakeConnection()
        before = build_strict_migration_report(*reports())
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            return_value=reports(),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan changed"):
                run_strict_migration(
                    connection,
                    apply=True,
                    expected_change_count=before["changeCount"],
                    expected_plan_sha256="f" * 64,
                )

        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertNotIn("ALTER TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)
        self.assertTrue(connection.rolled_back)

    def test_apply_refuses_invalid_catalog_without_ddl(self):
        constraints, writers, deletion, lineage = reports()
        constraints["missingConstraints"].remove(CONSTRAINT_NAMES[0])
        constraints["invalidConstraints"] = [CONSTRAINT_NAMES[0]]
        current = build_strict_migration_report(
            constraints, writers, deletion, lineage
        )
        connection = FakeConnection()
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            return_value=(constraints, writers, deletion, lineage),
        ):
            result = run_strict_migration(
                connection,
                apply=True,
                expected_change_count=current["changeCount"],
                expected_plan_sha256=current["planSha256"],
            )

        self.assertEqual(result["failureReason"], "not_ready")
        self.assertTrue(result["rolledBack"])
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertNotIn("ALTER TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)

    def test_ddl_error_rolls_back_the_complete_transaction(self):
        connection = FakeConnection(
            FakeCursor(fail_on="ADD CONSTRAINT chk_brigade_contract_items")
        )
        before = build_strict_migration_report(*reports())
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            return_value=reports(),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated DDL failure"):
                run_strict_migration(
                    connection,
                    apply=True,
                    expected_change_count=before["changeCount"],
                    expected_plan_sha256=before["planSha256"],
                )

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.cursor_value.closed)

    def test_apply_rolls_back_every_ddl_when_postcheck_is_not_complete(self):
        connection = FakeConnection()
        before = build_strict_migration_report(*reports())
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            side_effect=[reports(), reports()],
        ):
            result = run_strict_migration(
                connection,
                apply=True,
                expected_change_count=before["changeCount"],
                expected_plan_sha256=before["planSha256"],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "postcheck_failed")
        self.assertTrue(result["rolledBack"])
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)
        self.assertGreater(result["schemaWritesAttempted"], 0)

    def test_apply_against_complete_schema_is_an_idempotent_noop(self):
        connection = FakeConnection()
        current = build_strict_migration_report(*reports(complete=True))
        with patch(
            "backend.features.brigade_lineage.strict_migration.collect_strict_reports",
            return_value=reports(complete=True),
        ):
            result = run_strict_migration(
                connection,
                apply=True,
                expected_change_count=0,
                expected_plan_sha256=current["planSha256"],
            )

        self.assertTrue(result["complete"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertNotIn("ALTER TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)

    def test_cli_requires_confirmation_count_and_sha_before_connecting(self):
        with patch(
            "backend.features.brigade_lineage.strict_migration._connect"
        ) as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([
                    "--apply",
                    "--confirm",
                    APPLY_CONFIRMATION,
                    "--expected-change-count",
                    "13",
                ])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
