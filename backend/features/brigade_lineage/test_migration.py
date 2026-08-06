import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import psycopg2.extensions

from backend.features.brigade_lineage.migration import (
    APPLY_CONFIRMATION,
    MigrationPhaseError,
    SnapshotPhaseError,
    _apply_ready_rows,
    _assert_snapshot_schema,
    _ensure_bci_schema,
    _ensure_snapshot_schema,
    _load_lineage_rows,
    _plan_sha256,
    _validate_schema_state,
    build_migration_report,
    classify_lineage_row,
    main,
    run_migration,
)


TARGETS = {
    ("brigade_contract_items", "source_type"): (
        "character varying", "varchar", 20, "'legacy'::character varying"
    ),
    ("brigade_contract_items", "source_estimate_version_id"): (
        "integer", "int4", None, None
    ),
    ("brigade_contract_items", "source_section_index"): (
        "integer", "int4", None, None
    ),
    ("brigade_contract_items", "source_item_index"): (
        "integer", "int4", None, None
    ),
    ("brigade_contract_items", "source_item_key"): (
        "character varying", "varchar", 255, None
    ),
    ("estimate_versions", "sections_sha256"): (
        "character varying", "varchar", 64, None
    ),
}


def schema(*, complete=True):
    columns = {}
    if complete:
        for (table, name), (data_type, udt_name, length, default) in TARGETS.items():
            columns[(table, name)] = {
                "table_name": table,
                "column_name": name,
                "data_type": data_type,
                "udt_name": udt_name,
                "character_maximum_length": length,
                "is_nullable": "YES",
                "column_default": default,
            }
    return {
        "tables": {"brigade_contract_items", "estimate_versions"},
        "columns": columns,
    }


def ready_row(record_id=41, **overrides):
    row = {
        "contract_item_id": record_id,
        "source_type": None,
        "source_estimate_version_id": None,
        "source_section_index": None,
        "source_item_index": None,
        "source_item_key": None,
    }
    row.update(overrides)
    return row


def classified_ready(record_id=41):
    return classify_lineage_row(ready_row(record_id))


def classified_stored(record_id=41, source_type="legacy"):
    row = ready_row(record_id, source_type=source_type)
    if source_type == "estimate":
        row.update(
            source_estimate_version_id=71,
            source_section_index=0,
            source_item_index=2,
            source_item_key="71:0:2",
        )
    return classify_lineage_row(row)


class FakeCursor:
    def __init__(self, update_rowcount=0):
        self.calls = []
        self.rowcount = 0
        self.update_rowcount = update_rowcount
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if compact.startswith("UPDATE public.brigade_contract_items"):
            self.rowcount = self.update_rowcount

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, update_rowcount=0):
        self.update_rowcount = update_rowcount
        self.cursors = []
        self.session_calls = []
        self.commit_count = 0
        self.rollback_count = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        cursor = FakeCursor(self.update_rowcount)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


class PhaseTwoCursorFailureConnection(FakeConnection):
    def cursor(self, **_kwargs):
        if self.cursors:
            raise RuntimeError("connection lost before phase two")
        return super().cursor(**_kwargs)


class UncertainPhaseTwoCommitConnection(FakeConnection):
    def commit(self):
        self.commit_count += 1
        if self.commit_count == 2:
            raise RuntimeError("connection lost during phase two commit")


class UncertainPhaseOneCommitConnection(FakeConnection):
    def commit(self):
        self.commit_count += 1
        if self.commit_count == 1:
            raise RuntimeError("connection lost during snapshot commit")


def plan(classified, state):
    return state, classified, build_migration_report(state, classified)


class BrigadeLineageMigrationTests(unittest.TestCase):
    def test_only_fully_empty_lineage_is_ready_for_legacy(self):
        ready = classify_lineage_row(ready_row())
        partial = classify_lineage_row(ready_row(source_section_index=0))

        self.assertEqual((ready["status"], ready["reason"]), ("ready", "legacy_lineage_empty"))
        self.assertEqual(
            (partial["status"], partial["reason"]),
            ("needs_review", "source_type_missing_with_coordinates"),
        )

    def test_valid_stored_source_shapes_are_preserved(self):
        rows = [
            classified_stored(1, "legacy"),
            classified_stored(2, "estimate"),
            classified_stored(3, "manual"),
            classified_stored(4, "pricelist"),
        ]

        self.assertEqual([row["status"] for row in rows], ["stored"] * 4)
        self.assertEqual([row["sourceType"] for row in rows], [
            "legacy", "estimate", "manual", "pricelist"
        ])

    def test_invalid_stored_shapes_fail_closed(self):
        cases = [
            ready_row(source_type="legacy", source_item_index=0),
            ready_row(source_type="manual", source_item_key="x"),
            ready_row(source_type="pricelist", source_estimate_version_id=9),
            ready_row(source_type="estimate", source_estimate_version_id=9),
            ready_row(source_type=" Estimate "),
            ready_row(source_type="unknown"),
        ]

        self.assertTrue(all(classify_lineage_row(row)["status"] == "needs_review" for row in cases))

    def test_plan_hash_is_order_independent_and_bound_to_contract(self):
        first = [classified_ready(9), classified_ready(3)]
        second = list(reversed(first))

        self.assertEqual(_plan_sha256(first), _plan_sha256(second))
        self.assertEqual(len(_plan_sha256(first)), 64)
        self.assertNotEqual(_plan_sha256(first), _plan_sha256([classified_ready(3)]))

    def test_report_preview_is_bounded_and_contains_no_business_text(self):
        rows = [classified_ready(index) for index in range(1, 103)]
        report = build_migration_report(schema(complete=False), rows)

        self.assertEqual(report["summary"]["readyLegacy"], 102)
        self.assertEqual(len(report["backfillPreview"]), 100)
        self.assertTrue(report["previewTruncated"])
        self.assertEqual(set(report["backfillPreview"][0]), {"contractItemId", "reason"})

    def test_schema_validation_accepts_missing_but_rejects_incompatible_columns(self):
        _validate_schema_state(schema(complete=False), require_complete=False)
        valid = schema()
        _validate_schema_state(valid, require_complete=True)

        mutations = [
            ("source_type", "data_type", "text"),
            ("source_item_key", "character_maximum_length", 120),
            ("source_item_index", "is_nullable", "NO"),
            ("source_type", "column_default", "'manual'::character varying"),
            ("sections_sha256", "column_default", "''::character varying"),
        ]
        for name, field, value in mutations:
            with self.subTest(name=name, field=field):
                broken = schema()
                table = "estimate_versions" if name == "sections_sha256" else "brigade_contract_items"
                broken["columns"][(table, name)][field] = value
                with self.assertRaisesRegex(RuntimeError, name):
                    _validate_schema_state(broken, require_complete=False)

    def test_partial_source_type_without_default_is_repairable_but_not_complete(self):
        partial = schema()
        partial["columns"][("brigade_contract_items", "source_type")][
            "column_default"
        ] = None

        _validate_schema_state(partial, require_complete=False)
        with self.assertRaisesRegex(RuntimeError, "source_type"):
            _validate_schema_state(partial, require_complete=True)
        report = build_migration_report(partial, [classified_stored()])
        self.assertFalse(report["migrationComplete"])
        self.assertEqual(report["schema"]["state"], "partial")
        self.assertFalse(report["schema"]["complete"])
        self.assertTrue(report["schema"]["columnsComplete"])

    def test_partial_schema_with_legacy_default_is_rejected_as_unproven(self):
        suspicious = schema()
        suspicious["columns"].pop(
            ("brigade_contract_items", "source_item_key")
        )

        with self.assertRaisesRegex(RuntimeError, "partial.*default"):
            _validate_schema_state(suspicious, require_complete=False)

    def test_missing_base_table_fails_closed(self):
        broken = schema(complete=False)
        broken["tables"].remove("estimate_versions")

        with self.assertRaisesRegex(RuntimeError, "estimate_versions"):
            _validate_schema_state(broken, require_complete=False)

    def test_snapshot_phase_refuses_to_commit_if_assignment_table_is_missing(self):
        broken = schema()
        broken["tables"].remove("brigade_contract_items")
        with patch(
            "backend.features.brigade_lineage.migration._load_schema_state",
            return_value=broken,
        ):
            with self.assertRaisesRegex(RuntimeError, "brigade_contract_items"):
                _assert_snapshot_schema(FakeCursor())

    def test_schema_sql_is_nullable_additive_defaulted_and_has_no_constraints(self):
        cursor = FakeCursor()
        _ensure_snapshot_schema(cursor)
        _ensure_bci_schema(cursor)
        sql = " ".join(call[0] for call in cursor.calls)

        self.assertIn("sections_sha256 VARCHAR(64) NULL", sql)
        self.assertIn("source_type VARCHAR(20) NULL", sql)
        self.assertIn("source_estimate_version_id INTEGER NULL", sql)
        self.assertIn("source_section_index INTEGER NULL", sql)
        self.assertIn("source_item_index INTEGER NULL", sql)
        self.assertIn("source_item_key VARCHAR(255) NULL", sql)
        self.assertIn("ALTER COLUMN source_type SET DEFAULT 'legacy'", sql)
        for forbidden in ("NOT NULL", "CONSTRAINT", "FOREIGN KEY", "CREATE INDEX"):
            self.assertNotIn(forbidden, sql)
        self.assertIn("ALTER TABLE public.estimate_versions", sql)
        self.assertIn("ALTER TABLE public.brigade_contract_items", sql)

    def test_lineage_read_is_schema_qualified(self):
        cursor = FakeCursor()

        _load_lineage_rows(cursor, schema(complete=False))

        self.assertIn(
            "FROM public.brigade_contract_items bci",
            cursor.calls[-1][0],
        )

    def test_guarded_update_targets_only_exact_empty_lineage_ids(self):
        cursor = FakeCursor(update_rowcount=2)
        updated = _apply_ready_rows(cursor, [classified_ready(9), classified_ready(3)])
        sql, params = cursor.calls[-1]

        self.assertEqual(updated, 2)
        self.assertEqual(params, ("legacy", [3, 9]))
        self.assertIn("id = ANY(%s::INTEGER[])", sql)
        for column in (
            "source_type", "source_estimate_version_id", "source_section_index",
            "source_item_index", "source_item_key",
        ):
            self.assertIn(column + " IS NULL", sql)

    def test_dry_run_is_repeatable_read_readonly_and_rolls_back_without_writes(self):
        connection = FakeConnection()
        before = [classified_ready()]
        with patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            return_value=plan(before, schema(complete=False)),
        ):
            result = run_migration(connection)

        self.assertTrue(result["dryRun"])
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.commit_count, 0)
        self.assertEqual(connection.rollback_count, 1)
        self.assertTrue(connection.session_calls[0]["readonly"])
        self.assertEqual(
            connection.session_calls[0]["isolation_level"],
            psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ,
        )
        self.assertFalse(any("ALTER TABLE" in sql for sql, _ in connection.cursors[0].calls))

    def test_phase_one_failure_rolls_back_without_starting_phase_two(self):
        connection = FakeConnection()
        with patch(
            "backend.features.brigade_lineage.migration._ensure_snapshot_schema",
            side_effect=RuntimeError("snapshot lock timeout"),
        ):
            with self.assertRaisesRegex(SnapshotPhaseError, "snapshot lock timeout") as raised:
                run_migration(connection, True, 0, "0" * 64)

        self.assertTrue(raised.exception.phase_one_rolled_back)
        self.assertFalse(raised.exception.snapshot_outcome_unknown)
        self.assertEqual(connection.commit_count, 0)
        self.assertEqual(connection.rollback_count, 1)
        self.assertEqual(len(connection.cursors), 1)

    def test_phase_one_commit_failure_reports_unknown_additive_outcome(self):
        connection = UncertainPhaseOneCommitConnection()
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ):
            with self.assertRaises(SnapshotPhaseError) as raised:
                run_migration(connection, True, 0, "0" * 64)

        self.assertFalse(raised.exception.phase_one_rolled_back)
        self.assertTrue(raised.exception.snapshot_outcome_unknown)
        self.assertTrue(raised.exception.retry_safe)
        self.assertEqual(connection.commit_count, 1)
        self.assertEqual(len(connection.cursors), 1)

    def test_cli_rejects_missing_guard_before_connect(self):
        with patch("backend.features.brigade_lineage.migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([
                    "--apply", "--confirm", APPLY_CONFIRMATION,
                    "--expected-ready-count", "1",
                ])
        connect.assert_not_called()

    def test_phase_one_commit_is_reported_when_phase_two_guard_drifts(self):
        connection = FakeConnection()
        audited = [classified_ready(41)]
        changed = [classified_ready(42)]
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            return_value=plan(changed, schema(complete=False)),
        ):
            with self.assertRaises(MigrationPhaseError) as raised:
                run_migration(
                    connection,
                    apply=True,
                    expected_ready_count=1,
                    expected_plan_sha256=_plan_sha256(audited),
                )

        self.assertEqual(connection.commit_count, 1)
        self.assertEqual(connection.rollback_count, 1)
        self.assertTrue(raised.exception.snapshot_schema_committed)
        self.assertTrue(raised.exception.retry_safe)
        self.assertIn("plan", str(raised.exception).lower())
        phase_two_sql = " ".join(sql for sql, _ in connection.cursors[1].calls)
        self.assertIn("LOCK TABLE public.brigade_contract_items IN ACCESS EXCLUSIVE MODE", phase_two_sql)
        self.assertNotIn("ADD COLUMN IF NOT EXISTS source_type", phase_two_sql)

    def test_phase_two_cursor_failure_reports_committed_snapshot_phase(self):
        connection = PhaseTwoCursorFailureConnection()
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ):
            with self.assertRaises(MigrationPhaseError) as raised:
                run_migration(connection, True, 0, "0" * 64)

        self.assertTrue(raised.exception.snapshot_schema_committed)
        self.assertTrue(raised.exception.retry_safe)
        self.assertEqual(connection.commit_count, 1)
        self.assertEqual(connection.rollback_count, 1)

    def test_phase_two_commit_failure_never_claims_confirmed_rollback(self):
        connection = UncertainPhaseTwoCommitConnection(update_rowcount=1)
        before = [classified_ready(41)]
        after = [classified_stored(41)]
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            side_effect=[plan(before, schema(complete=False)), plan(after, schema())],
        ):
            with self.assertRaises(MigrationPhaseError) as raised:
                run_migration(connection, True, 1, _plan_sha256(before))

        self.assertFalse(raised.exception.phase_two_rolled_back)
        self.assertTrue(raised.exception.phase_two_outcome_unknown)
        self.assertTrue(raised.exception.retry_safe)
        self.assertEqual(connection.commit_count, 2)

    def test_review_rows_stop_before_bci_ddl_or_update(self):
        connection = FakeConnection()
        review = [classify_lineage_row(ready_row(source_item_index=0))]
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            return_value=plan(review, schema(complete=False)),
        ):
            with self.assertRaisesRegex(MigrationPhaseError, "need review"):
                run_migration(connection, True, 0, _plan_sha256(review))

        phase_two_calls = connection.cursors[1].calls
        self.assertTrue(phase_two_calls[2][0].startswith(
            "LOCK TABLE public.brigade_contract_items IN ACCESS EXCLUSIVE MODE"
        ))
        phase_two_sql = " ".join(sql for sql, _ in phase_two_calls)
        self.assertNotIn("ADD COLUMN IF NOT EXISTS source_type", phase_two_sql)
        self.assertNotIn("UPDATE public.brigade_contract_items", phase_two_sql)

    def test_rowcount_mismatch_rolls_back_only_phase_two(self):
        connection = FakeConnection(update_rowcount=0)
        before = [classified_ready(41)]
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            return_value=plan(before, schema(complete=False)),
        ):
            with self.assertRaisesRegex(MigrationPhaseError, "rowcount"):
                run_migration(connection, True, 1, _plan_sha256(before))

        self.assertEqual(connection.commit_count, 1)
        self.assertEqual(connection.rollback_count, 1)

    def test_success_commits_both_phases_after_strict_postcheck(self):
        connection = FakeConnection(update_rowcount=1)
        before = [classified_ready(41), classified_stored(42, "estimate")]
        after = [classified_stored(41), classified_stored(42, "estimate")]
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            side_effect=[plan(before, schema(complete=False)), plan(after, schema())],
        ):
            result = run_migration(connection, True, 1, _plan_sha256(before))

        self.assertTrue(result["complete"])
        self.assertTrue(result["schemaMigrationComplete"])
        self.assertTrue(result["migrationComplete"])
        self.assertFalse(result["readyForStrictRuntime"])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["preSummary"]["readyLegacy"], 1)
        self.assertEqual(result["summary"]["readyLegacy"], 0)
        self.assertEqual(result["summary"]["storedLegacy"], 1)
        self.assertEqual(connection.commit_count, 2)
        self.assertEqual(connection.rollback_count, 0)
        self.assertEqual(
            connection.session_calls,
            [{
                "readonly": False,
                "autocommit": False,
                "isolation_level": psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED,
            }],
        )
        self.assertTrue(all(cursor.closed for cursor in connection.cursors))

    def test_postcheck_total_row_drift_rolls_back_phase_two(self):
        connection = FakeConnection(update_rowcount=1)
        before = [classified_ready(41)]
        after = [classified_stored(41), classified_stored(42)]
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            side_effect=[plan(before, schema(complete=False)), plan(after, schema())],
        ):
            with self.assertRaisesRegex(MigrationPhaseError, "totalRows"):
                run_migration(connection, True, 1, _plan_sha256(before))

        self.assertEqual(connection.commit_count, 1)
        self.assertEqual(connection.rollback_count, 1)

    def test_already_applied_state_is_idempotent(self):
        connection = FakeConnection()
        stored = [classified_stored(41)]
        current = plan(stored, schema())
        with patch(
            "backend.features.brigade_lineage.migration._assert_snapshot_schema"
        ), patch(
            "backend.features.brigade_lineage.migration.collect_migration_plan",
            side_effect=[current, current],
        ):
            result = run_migration(connection, True, 0, _plan_sha256(stored))

        self.assertTrue(result["complete"])
        self.assertEqual(result["updated"], 0)
        self.assertEqual(connection.commit_count, 2)
        update_sql = " ".join(sql for cursor in connection.cursors for sql, _ in cursor.calls)
        self.assertNotIn("UPDATE public.brigade_contract_items", update_sql)


if __name__ == "__main__":
    unittest.main()
