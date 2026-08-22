import copy
import json
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

import psycopg2.extras

from backend.features.assignment_daily_drafts.snapshot import (
    AssignmentDailySnapshotError,
    AssignmentDailySnapshotRequest,
    collect_assignment_daily_snapshot,
    run_assignment_daily_snapshot,
)


def _sections():
    return [
        {
            "name": "Кабельные системы",
            "items": [
                {
                    "name": "Монтаж кабеля",
                    "unit": "м",
                    "quantity": "10",
                    "itemType": "work",
                    "priceWork": 100,
                    "priceMaterial": 0,
                    "estimateItemKey": "work-1",
                },
                {
                    "name": "Кабель",
                    "unit": "м",
                    "quantity": "20",
                    "itemType": "material",
                    "priceWork": 0,
                    "priceMaterial": 50,
                    "estimateItemKey": "material-1",
                },
            ],
        }
    ]


def _context_row(**overrides):
    active = json.dumps(_sections(), ensure_ascii=False)
    version = json.dumps(_sections(), ensure_ascii=False, separators=(",", ":"))
    row = {
        "estimate_id": 80,
        "company_id": 1,
        "project_id": 10,
        "project_name": "Школа",
        "project_name_count": 1,
        "estimate_version_id": 4,
        "estimate_status": "Активная",
        "is_template": False,
        "work_package": "Слаботочка",
        "active_sections_json": active,
        "version_sections_json": version,
        "field_active_sections_json_bytes": len(active.encode("utf-8")),
        "field_version_sections_json_bytes": len(version.encode("utf-8")),
        "query_json_bytes": len(active.encode("utf-8")) + len(version.encode("utf-8")),
        "row_count": 1,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    }
    row.update(overrides)
    if "active_sections_json" in overrides:
        value = row["active_sections_json"]
        row["field_active_sections_json_bytes"] = (
            len(value.encode("utf-8")) if value is not None else 0
        )
    if "version_sections_json" in overrides:
        value = row["version_sections_json"]
        row["field_version_sections_json_bytes"] = (
            len(value.encode("utf-8")) if value is not None else 0
        )
    if (
        "active_sections_json" in overrides
        or "version_sections_json" in overrides
    ):
        row["query_json_bytes"] = (
            row["field_active_sections_json_bytes"]
            + row["field_version_sections_json_bytes"]
        )
    return row


def _assignment_row(**overrides):
    row = {
        "company_id": 1,
        "project_id": 10,
        "estimate_id": 80,
        "estimate_version_id": 4,
        "work_package": "Слаботочка",
        "source_type": "estimate",
        "section_index": 0,
        "item_index": 0,
        "item_key": "work-1",
        "assigned_quantity": Decimal("4"),
        "field_item_key_bytes": 6,
        "field_assigned_quantity_bytes": 1,
        "row_count": 1,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    }
    row.update(overrides)
    row.setdefault(
        "query_text_bytes",
        row["field_item_key_bytes"] + row["field_assigned_quantity_bytes"],
    )
    return row


def _daily_row(**overrides):
    row = {
        "id": 7,
        "company_id": 1,
        "project_id": 10,
        "date": "2026-08-21",
        "status": "Подтверждено",
        "description": "Монтаж кабеля",
        "unit": "м",
        "quantity": Decimal("2.5"),
        "master_id": 31,
        "master_name": "Иван Петров",
        "work_package": "Слаботочка",
        "row_count": 1,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    }
    for field in (
        "description", "unit", "quantity", "master_name", "work_package",
    ):
        value = row[field]
        row["field_" + field + "_bytes"] = len(str(value).encode("utf-8"))
    row["query_text_bytes"] = sum(
        row["field_" + field + "_bytes"]
        for field in (
            "description", "unit", "quantity", "master_name", "work_package",
        )
    )
    row.update(overrides)
    return row


def _repeat_query_rows(rows, total_field, field_names):
    total = sum(
        row["field_" + field + "_bytes"]
        for row in rows
        for field in field_names
    )
    for row in rows:
        row["row_count"] = len(rows)
        row[total_field] = total
        row["cardinality_limit_exceeded"] = True
        row["payload_limit_exceeded"] = False
        for field in field_names:
            row[field] = None
    return rows


class _Cursor:
    def __init__(self, result_sets, events=None):
        self.result_sets = list(result_sets)
        self.calls = []
        self.current = []
        self.closed = False
        self.events = events

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.events is not None:
            self.events.append("execute")
        self.current = self.result_sets.pop(0) if self.result_sets else []

    def fetchall(self):
        return copy.deepcopy(self.current)

    def close(self):
        self.closed = True
        if self.events is not None:
            self.events.append("cursor_close")


class _FailingCursor(_Cursor):
    def __init__(self, result_sets, events, fail_at):
        super().__init__(result_sets, events)
        self.fail_at = fail_at

    def execute(self, sql, params=()):
        super().execute(sql, params)
        if len(self.calls) == self.fail_at:
            raise RuntimeError("PRIVATE_DATABASE_DETAIL")


class _Connection:
    def __init__(self, cursor, events):
        self._cursor = cursor
        self.events = events
        self.session = None
        self.cursor_kwargs = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.events.append("set_session")
        self.session = kwargs

    def cursor(self, **kwargs):
        self.events.append("cursor")
        self.cursor_kwargs = kwargs
        return self._cursor

    def rollback(self):
        self.events.append("rollback")
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.events.append("connection_close")
        self.closed = True


class AssignmentDailySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.request = AssignmentDailySnapshotRequest(
            1, 10, "2026-08-21", 80, 4, "Слаботочка",
        )

    def test_request_is_exact_immutable_and_private(self):
        self.assertEqual(
            (
                self.request.company_id, self.request.project_id,
                self.request.date, self.request.estimate_id,
                self.request.estimate_version_id, self.request.work_package,
            ),
            (1, 10, "2026-08-21", 80, 4, "Слаботочка"),
        )
        with self.assertRaises(FrozenInstanceError):
            self.request.project_id = 11
        for values in (
            (True, 10, "2026-08-21", 80, 4, "Слаботочка"),
            (1, 0, "2026-08-21", 80, 4, "Слаботочка"),
            (1, 10, "21.08.2026", 80, 4, "Слаботочка"),
            (1, 10, "2026-08-21", 0, 4, "Слаботочка"),
            (1, 10, "2026-08-21", 80, False, "Слаботочка"),
            (1, 10, "2026-08-21", 80, 4, ""),
        ):
            with self.subTest(values=values):
                with self.assertRaises(AssignmentDailySnapshotError) as raised:
                    AssignmentDailySnapshotRequest(*values)
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_daily_snapshot_input_invalid",),
                )

    def test_collects_one_detached_ready_snapshot_from_three_bounded_selects(self):
        result_sets = [[_context_row()], [_assignment_row()], [_daily_row()]]
        original = copy.deepcopy(result_sets)
        cursor = _Cursor(result_sets)

        snapshot = collect_assignment_daily_snapshot(cursor, self.request)

        self.assertEqual(snapshot.state, "ready")
        self.assertEqual(snapshot.review_codes, ())
        self.assertEqual(snapshot.assignment_draft.state, "ready")
        self.assertEqual(snapshot.assignment_draft.items[0].available_quantity, "6")
        self.assertIsNone(snapshot.assignment_draft.items[0].assignee)
        self.assertEqual(snapshot.daily_work_draft.state, "ready")
        self.assertEqual(snapshot.daily_work_draft.items[0].quantity, "2.5")
        self.assertEqual(result_sets, original)
        self.assertEqual(len(cursor.calls), 3)
        for sql, _params in cursor.calls:
            upper = sql.upper().lstrip()
            self.assertTrue(upper.startswith("SELECT "))
            self.assertIn("LIMIT %S", upper)
            self.assertIn("MATERIALIZED", upper)
            for forbidden in (
                "INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE ",
                "FOR UPDATE", "FOR SHARE",
            ):
                self.assertNotIn(forbidden, upper)
        self.assertIn("E.COMPANY_ID=%S", cursor.calls[0][0].upper())
        self.assertIn("E.PROJECT_ID=%S", cursor.calls[0][0].upper())
        self.assertIn("BC.COMPANY_ID=%S", cursor.calls[1][0].upper())
        self.assertIn("BC.PROJECT_ID=%S", cursor.calls[1][0].upper())
        self.assertIn("COALESCE(BC.STATUS,'') NOT IN", cursor.calls[1][0].upper())
        self.assertIn("COALESCE(BCI.STATUS,'') NOT IN", cursor.calls[1][0].upper())
        self.assertIn("WJ.COMPANY_ID=%S", cursor.calls[2][0].upper())
        self.assertIn("P.ID=%S", cursor.calls[2][0].upper())
        self.assertIn("WJ.STATUS='ПОДТВЕРЖДЕНО'", cursor.calls[2][0].upper())

    def test_stale_version_or_ambiguous_project_fails_closed_without_payload(self):
        stale = _context_row(version_sections_json=json.dumps([
            {"name": "PRIVATE_STALE", "items": []},
        ]))
        ambiguous = _context_row(project_name_count=2)
        for row, code in (
            (stale, "assignment_snapshot_version_stale"),
            (ambiguous, "assignment_snapshot_project_ambiguous"),
        ):
            with self.subTest(code=code):
                cursor = _Cursor([[row], [], []])
                snapshot = collect_assignment_daily_snapshot(cursor, self.request)
                self.assertEqual(snapshot.state, "review_required")
                self.assertEqual(snapshot.review_codes, (code,))
                self.assertEqual(snapshot.assignment_draft.items, ())
                self.assertEqual(snapshot.daily_work_draft.items, ())
                self.assertNotIn("PRIVATE_STALE", repr(snapshot))
                self.assertEqual(len(cursor.calls), 1)

    def test_empty_source_is_review_only_and_stops_after_context(self):
        cursor = _Cursor([[]])

        snapshot = collect_assignment_daily_snapshot(cursor, self.request)

        self.assertEqual(snapshot.state, "review_required")
        self.assertEqual(
            snapshot.review_codes,
            ("assignment_snapshot_source_not_found",),
        )
        self.assertEqual(snapshot.assignment_draft.items, ())
        self.assertEqual(snapshot.daily_work_draft.items, ())
        self.assertEqual(len(cursor.calls), 1)

    def test_cardinality_or_payload_gate_stops_before_dependent_reads(self):
        cardinality_rows = _repeat_query_rows(
            [_context_row(), _context_row()],
            "query_json_bytes",
            ("active_sections_json", "version_sections_json"),
        )
        overflow_row = _context_row()
        overflow_row["active_sections_json"] = None
        overflow_row["version_sections_json"] = None
        overflow_row["field_active_sections_json_bytes"] = 4 * 1024 * 1024 + 1
        overflow_row["query_json_bytes"] = (
            overflow_row["field_active_sections_json_bytes"]
            + overflow_row["field_version_sections_json_bytes"]
        )
        overflow_row["payload_limit_exceeded"] = True
        cases = (
            (
                cardinality_rows,
                "assignment_snapshot_source_ambiguous",
            ),
            (
                [overflow_row],
                "assignment_snapshot_payload_too_large",
            ),
        )
        for rows, code in cases:
            with self.subTest(code=code):
                cursor = _Cursor([rows])
                snapshot = collect_assignment_daily_snapshot(cursor, self.request)
                self.assertEqual(snapshot.state, "review_required")
                self.assertEqual(snapshot.review_codes, (code,))
                self.assertEqual(len(cursor.calls), 1)

    def test_forged_metadata_or_raw_gate_leak_is_fixed_contract_failure(self):
        forged_flag = _context_row(payload_limit_exceeded=True)
        leaked = _context_row()
        leaked["field_active_sections_json_bytes"] = 4 * 1024 * 1024 + 1
        leaked["query_json_bytes"] = (
            leaked["field_active_sections_json_bytes"]
            + leaked["field_version_sections_json_bytes"]
        )
        leaked["payload_limit_exceeded"] = True
        for row in (forged_flag, leaked):
            with self.subTest(row=row):
                cursor = _Cursor([[row]])
                with self.assertRaises(AssignmentDailySnapshotError) as raised:
                    collect_assignment_daily_snapshot(cursor, self.request)
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_daily_snapshot_contract_invalid",),
                )
                self.assertNotIn("PRIVATE", repr(raised.exception))
                self.assertEqual(len(cursor.calls), 1)

    def test_foreign_or_orphan_assignment_lineage_stops_before_daily_read(self):
        rows = (
            _assignment_row(company_id=2, item_key="PRIVATE_FOREIGN"),
            _assignment_row(section_index=9, item_key="PRIVATE_ORPHAN"),
        )
        for assignment in rows:
            with self.subTest(assignment=assignment):
                assignment["field_item_key_bytes"] = len(
                    assignment["item_key"].encode("utf-8")
                )
                assignment["query_text_bytes"] = (
                    assignment["field_item_key_bytes"]
                    + assignment["field_assigned_quantity_bytes"]
                )
                cursor = _Cursor([[_context_row()], [assignment]])
                snapshot = collect_assignment_daily_snapshot(cursor, self.request)
                self.assertEqual(snapshot.state, "review_required")
                self.assertEqual(
                    snapshot.review_codes,
                    ("assignment_snapshot_lineage_invalid",),
                )
                self.assertNotIn("PRIVATE_", repr(snapshot))
                self.assertEqual(len(cursor.calls), 2)

    def test_oversized_snapshot_number_is_rejected_before_decimal_conversion(self):
        sections = _sections()
        sections[0]["items"][0]["quantity"] = "9" * 129
        active = json.dumps(sections, ensure_ascii=False)
        version = json.dumps(sections, ensure_ascii=False, separators=(",", ":"))
        cursor = _Cursor([[
            _context_row(
                active_sections_json=active,
                version_sections_json=version,
            ),
        ], [], []])

        snapshot = collect_assignment_daily_snapshot(cursor, self.request)

        self.assertEqual(snapshot.state, "review_required")
        self.assertIn("assignment_source_invalid", snapshot.review_codes)
        self.assertNotIn("9" * 65, repr(snapshot))

    def test_assignment_or_daily_overflow_is_query_wide_and_non_leaking(self):
        assignment = _repeat_query_rows(
            [_assignment_row(section_index=index) for index in range(101)],
            "query_text_bytes",
            ("item_key", "assigned_quantity"),
        )
        daily = _repeat_query_rows(
            [_daily_row(id=index + 1) for index in range(101)],
            "query_text_bytes",
            ("description", "unit", "quantity", "master_name", "work_package"),
        )
        for result_sets, code, call_count in (
            (
                [[_context_row()], assignment],
                "assignment_draft_scan_limit_exceeded",
                2,
            ),
            (
                [[_context_row()], [], daily],
                "daily_work_scan_limit_exceeded",
                3,
            ),
        ):
            with self.subTest(code=code):
                cursor = _Cursor(result_sets)
                snapshot = collect_assignment_daily_snapshot(cursor, self.request)
                self.assertEqual(snapshot.state, "review_required")
                self.assertIn(code, snapshot.review_codes)
                self.assertEqual(len(cursor.calls), call_count)
                self.assertNotIn("PRIVATE_", repr(snapshot))

    def test_runner_uses_one_read_only_snapshot_and_rolls_back_before_return(self):
        events = []
        cursor = _Cursor([
            [], [_context_row()], [_assignment_row()], [_daily_row()],
        ], events)
        connection = _Connection(cursor, events)

        def get_db():
            events.append("get_db")
            return connection

        snapshot = run_assignment_daily_snapshot(get_db, self.request)

        self.assertEqual(snapshot.state, "ready")
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.cursor_kwargs, {
            "cursor_factory": psycopg2.extras.RealDictCursor,
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        self.assertEqual(events, [
            "get_db", "set_session", "cursor", "execute", "execute",
            "execute", "execute", "rollback", "cursor_close",
            "connection_close",
        ])
        settings_sql, settings_params = cursor.calls[0]
        self.assertEqual(settings_sql.count("pg_catalog.set_config(%s, %s, true)"), 4)
        self.assertEqual(settings_params, (
            "statement_timeout", "30000",
            "lock_timeout", "1000",
            "idle_in_transaction_session_timeout", "30000",
            "search_path", "pg_catalog,public",
        ))

    def test_runner_maps_read_failure_and_still_rolls_back_and_closes(self):
        events = []
        cursor = _FailingCursor([[], []], events, fail_at=2)
        connection = _Connection(cursor, events)

        with self.assertRaises(AssignmentDailySnapshotError) as raised:
            run_assignment_daily_snapshot(lambda: connection, self.request)

        self.assertEqual(
            raised.exception.args,
            ("assignment_daily_snapshot_read_failed",),
        )
        self.assertNotIn("PRIVATE_DATABASE_DETAIL", repr(raised.exception))
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        self.assertEqual(connection.commits, 0)


if __name__ == "__main__":
    unittest.main()
