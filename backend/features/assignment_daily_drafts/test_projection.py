import copy
import math
import unittest
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

from backend.features.assignment_daily_drafts.projection import (
    MAX_DAILY_WORK_ROWS,
    AssignmentDailyDraftContractError,
    AssignmentDailyDraftScope,
    build_daily_work_draft,
)


def _row(**overrides):
    row = {
        "id": 7,
        "company_id": 1,
        "project_id": 10,
        "date": "2026-08-21",
        "status": "Подтверждено",
        "description": "Монтаж кабеля",
        "unit": "м",
        "quantity": Decimal("2.500"),
        "master_id": 31,
        "master_name": "Иван Петров",
        "work_package": "Слаботочка",
        "total": 999999,
        "photo_url": "PRIVATE_PHOTO_MARKER",
        "materials_used": "PRIVATE_MATERIAL_MARKER",
        "comment": "PRIVATE_COMMENT_MARKER",
    }
    row.update(overrides)
    return row


class AssignmentDailyDraftProjectionTests(unittest.TestCase):
    def setUp(self):
        self.scope = AssignmentDailyDraftScope(1, 10, "2026-08-21")

    def test_scope_is_exact_immutable_and_canonical(self):
        self.assertEqual(
            (self.scope.company_id, self.scope.project_id, self.scope.date),
            (1, 10, "2026-08-21"),
        )
        with self.assertRaises(FrozenInstanceError):
            self.scope.project_id = 11

        invalid = (
            (True, 10, "2026-08-21"),
            (0, 10, "2026-08-21"),
            (1, False, "2026-08-21"),
            (1, 10, "21.08.2026"),
            (1, 10, "2026-02-30"),
            (1, 10, "2026-8-21"),
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(AssignmentDailyDraftContractError) as raised:
                    AssignmentDailyDraftScope(*values)
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_daily_draft_input_invalid",),
                )

    def test_ready_draft_uses_only_confirmed_rows_and_detaches_safe_fields(self):
        rows = [
            _row(id=9, quantity=1.25, work_package=""),
            _row(id=3, quantity=Decimal("4.000"), master_id=None),
            _row(id=4, status="На проверке", description="PRIVATE_PENDING"),
        ]
        original = copy.deepcopy(rows)

        draft = build_daily_work_draft(self.scope, rows)

        self.assertEqual(draft.state, "ready")
        self.assertEqual([item.source_id for item in draft.items], [3, 9])
        self.assertEqual([item.quantity for item in draft.items], ["4", "1.25"])
        self.assertEqual(draft.items[0].responsible_id, None)
        self.assertEqual(draft.items[0].responsible_name, "Иван Петров")
        self.assertEqual(draft.items[1].work_package, "Основная")
        self.assertEqual(draft.summary.confirmed_rows, 2)
        self.assertEqual(draft.summary.work_packages, 2)
        self.assertEqual(draft.summary.responsible_people, 1)
        self.assertEqual(draft.review_codes, ())
        self.assertEqual(rows, original)

        allowed = {
            "source_id", "description", "unit", "quantity", "responsible_id",
            "responsible_name", "work_package", "status",
        }
        self.assertEqual({field.name for field in fields(draft.items[0])}, allowed)
        serialized = repr(draft)
        for marker in (
            "PRIVATE_PHOTO_MARKER", "PRIVATE_MATERIAL_MARKER",
            "PRIVATE_COMMENT_MARKER", "PRIVATE_PENDING", "999999",
        ):
            self.assertNotIn(marker, serialized)
        with self.assertRaises(FrozenInstanceError):
            draft.items[0].description = "changed"

        rows[0]["description"] = "changed"
        self.assertEqual(draft.items[1].description, "Монтаж кабеля")

    def test_no_confirmed_rows_returns_clear(self):
        draft = build_daily_work_draft(
            self.scope,
            [_row(status="На проверке"), _row(id=8, status="Отклонено")],
        )

        self.assertEqual(draft.state, "clear")
        self.assertEqual(draft.items, ())
        self.assertEqual(draft.summary.confirmed_rows, 0)
        self.assertEqual(draft.review_codes, ())

    def test_owner_or_date_drift_fails_closed_without_source_content(self):
        for row in (
            _row(company_id=2, description="PRIVATE_FOREIGN"),
            _row(project_id=11, description="PRIVATE_PROJECT"),
            _row(date="2026-08-20", description="PRIVATE_DATE"),
        ):
            with self.subTest(row=row):
                with self.assertRaises(AssignmentDailyDraftContractError) as raised:
                    build_daily_work_draft(self.scope, [row])
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_daily_draft_input_invalid",),
                )
                self.assertNotIn("PRIVATE_", repr(raised.exception))

    def test_invalid_or_duplicate_confirmed_rows_withhold_all_items(self):
        invalid_rows = (
            [_row(id=7), _row(id=7, description="PRIVATE_DUPLICATE")],
            [_row(description="")],
            [_row(unit="x" * 129)],
            [_row(quantity=0)],
            [_row(quantity=math.inf)],
            [_row(quantity=True)],
            [_row(quantity=Decimal("1E+1000"))],
            [_row(master_id=None, master_name="")],
            [_row(work_package="x" * 1025)],
        )
        for rows in invalid_rows:
            with self.subTest(rows=rows):
                draft = build_daily_work_draft(self.scope, rows)
                self.assertEqual(draft.state, "review_required")
                self.assertEqual(draft.items, ())
                self.assertEqual(draft.summary.confirmed_rows, 0)
                self.assertEqual(len(draft.review_codes), 1)
                self.assertIn(
                    draft.review_codes[0],
                    ("daily_work_source_duplicate", "daily_work_source_invalid"),
                )
                self.assertNotIn("PRIVATE_", repr(draft))

    def test_scan_limit_withholds_rows_and_is_inclusive(self):
        accepted = [
            _row(id=index + 1, master_id=index + 1, master_name=f"M{index + 1}")
            for index in range(MAX_DAILY_WORK_ROWS)
        ]
        exact = build_daily_work_draft(self.scope, accepted)
        self.assertEqual(exact.state, "ready")
        self.assertEqual(len(exact.items), MAX_DAILY_WORK_ROWS)

        overflow = build_daily_work_draft(
            self.scope,
            accepted + [_row(id=MAX_DAILY_WORK_ROWS + 1, description="PRIVATE_LIMIT")],
        )
        self.assertEqual(overflow.state, "review_required")
        self.assertEqual(overflow.items, ())
        self.assertEqual(overflow.review_codes, ("daily_work_scan_limit_exceeded",))
        self.assertNotIn("PRIVATE_LIMIT", repr(overflow))

    def test_text_caps_are_measured_in_utf8_bytes(self):
        exact = build_daily_work_draft(self.scope, [_row(
            description="я" * 2048,
            unit="я" * 64,
            master_name="я" * 256,
            work_package="я" * 512,
        )])
        self.assertEqual(exact.state, "ready")

        overflow_rows = (
            _row(description="я" * 2049),
            _row(unit="я" * 65),
            _row(master_name="я" * 257),
            _row(work_package="я" * 513),
        )
        for row in overflow_rows:
            with self.subTest(field=row):
                rejected = build_daily_work_draft(self.scope, [row])
                self.assertEqual(rejected.state, "review_required")
                self.assertEqual(rejected.items, ())
                self.assertEqual(
                    rejected.review_codes,
                    ("daily_work_source_invalid",),
                )


if __name__ == "__main__":
    unittest.main()
