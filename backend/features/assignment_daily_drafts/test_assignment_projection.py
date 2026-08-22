import copy
import math
import unittest
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

from backend.features.assignment_daily_drafts.assignment_projection import (
    MAX_ASSIGNMENT_DRAFT_ROWS,
    AssignmentDraftContractError,
    AssignmentDraftScope,
    build_assignment_draft,
)


def _row(**overrides):
    row = {
        "company_id": 1,
        "project_id": 10,
        "estimate_id": 80,
        "estimate_version_id": 4,
        "estimate_status": "Активная",
        "is_template": False,
        "work_package": "Слаботочка",
        "source_type": "estimate",
        "lineage_count": 1,
        "section_index": 0,
        "item_index": 0,
        "item_key": "80:0:0",
        "section_name": "Кабельные системы",
        "item_name": "Монтаж кабеля",
        "unit": "м",
        "quantity": Decimal("10.000"),
        "assigned_quantity": Decimal("4.000"),
        "itemType": "work",
        "priceWork": 12345,
        "priceMaterial": 0,
        "contractor": "PRIVATE_CONTRACTOR",
        "comment": "PRIVATE_COMMENT",
    }
    row.update(overrides)
    return row


class AssignmentDraftProjectionTests(unittest.TestCase):
    def setUp(self):
        self.scope = AssignmentDraftScope(1, 10, 80, 4, "Слаботочка")

    def test_scope_is_exact_and_immutable(self):
        self.assertEqual(
            (
                self.scope.company_id,
                self.scope.project_id,
                self.scope.estimate_id,
                self.scope.estimate_version_id,
                self.scope.work_package,
            ),
            (1, 10, 80, 4, "Слаботочка"),
        )
        with self.assertRaises(FrozenInstanceError):
            self.scope.estimate_id = 81

        invalid = (
            (True, 10, 80, 4, "Слаботочка"),
            (1, 0, 80, 4, "Слаботочка"),
            (1, 10, 0, 4, "Слаботочка"),
            (1, 10, 80, False, "Слаботочка"),
            (1, 10, 80, 4, ""),
            (1, 10, 80, 4, "я" * 513),
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(AssignmentDraftContractError) as raised:
                    AssignmentDraftScope(*values)
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_draft_input_invalid",),
                )

    def test_ready_draft_subtracts_assignments_and_never_guesses_assignee(self):
        rows = [
            _row(section_index=1, item_index=0, item_key="80:1:0"),
            _row(
                section_index=0,
                item_index=1,
                item_key="80:0:1",
                quantity=3,
                assigned_quantity=0,
            ),
            _row(
                section_index=0,
                item_index=2,
                item_key="80:0:2",
                quantity=2,
                assigned_quantity=2,
            ),
            _row(
                section_index=0,
                item_index=3,
                item_key="80:0:3",
                itemType="material",
                item_name="PRIVATE_MATERIAL_ROW",
            ),
        ]
        original = copy.deepcopy(rows)

        draft = build_assignment_draft(self.scope, rows)

        self.assertEqual(draft.state, "ready")
        self.assertEqual(
            [(item.section_index, item.item_index) for item in draft.items],
            [(0, 1), (1, 0)],
        )
        self.assertEqual(
            [item.available_quantity for item in draft.items],
            ["3", "6"],
        )
        self.assertEqual(draft.items[1].estimate_quantity, "10")
        self.assertEqual(draft.items[1].assigned_quantity, "4")
        self.assertTrue(all(item.assignee is None for item in draft.items))
        self.assertEqual(draft.summary.source_work_rows, 3)
        self.assertEqual(draft.summary.available_rows, 2)
        self.assertEqual(draft.summary.fully_assigned_rows, 1)
        self.assertEqual(draft.review_codes, ())
        self.assertEqual(rows, original)

        allowed = {
            "source_estimate_id", "source_estimate_version_id",
            "section_index", "item_index", "item_key", "section_name",
            "item_name", "unit", "estimate_quantity", "assigned_quantity",
            "available_quantity", "work_package", "assignee",
        }
        self.assertEqual({field.name for field in fields(draft.items[0])}, allowed)
        for marker in (
            "12345", "PRIVATE_CONTRACTOR", "PRIVATE_COMMENT",
            "PRIVATE_MATERIAL_ROW",
        ):
            self.assertNotIn(marker, repr(draft))
        with self.assertRaises(FrozenInstanceError):
            draft.items[0].assignee = "someone"
        rows[1]["item_name"] = "changed"
        self.assertEqual(draft.items[0].item_name, "Монтаж кабеля")

    def test_fully_assigned_or_material_rows_return_clear(self):
        draft = build_assignment_draft(self.scope, [
            _row(quantity=2, assigned_quantity=2),
            _row(
                section_index=0,
                item_index=1,
                item_key="80:0:1",
                itemType="material",
            ),
        ])
        self.assertEqual(draft.state, "clear")
        self.assertEqual(draft.items, ())
        self.assertEqual(draft.summary.source_work_rows, 1)
        self.assertEqual(draft.summary.fully_assigned_rows, 1)

    def test_foreign_inactive_or_template_source_fails_closed(self):
        rows = (
            _row(company_id=2, item_name="PRIVATE_FOREIGN"),
            _row(project_id=11, item_name="PRIVATE_PROJECT"),
            _row(estimate_id=81, item_name="PRIVATE_ESTIMATE"),
            _row(estimate_version_id=5, item_name="PRIVATE_VERSION"),
            _row(estimate_status="Черновик", item_name="PRIVATE_STATUS"),
            _row(is_template=True, item_name="PRIVATE_TEMPLATE"),
            _row(work_package="Основная", item_name="PRIVATE_PACKAGE"),
        )
        for row in rows:
            with self.subTest(row=row):
                with self.assertRaises(AssignmentDraftContractError) as raised:
                    build_assignment_draft(self.scope, [row])
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_draft_input_invalid",),
                )
                self.assertNotIn("PRIVATE_", repr(raised.exception))

    def test_lineage_duplicate_and_balance_defects_withhold_all_items(self):
        cases = (
            ([_row(lineage_count=0)], "assignment_lineage_invalid"),
            ([_row(lineage_count=2)], "assignment_lineage_invalid"),
            ([_row(source_type="manual")], "assignment_lineage_invalid"),
            (
                [_row(), _row(section_index=1, item_index=1, item_key="80:0:0")],
                "assignment_source_duplicate",
            ),
            (
                [_row(), _row(item_key="80:1:1")],
                "assignment_source_duplicate",
            ),
            (
                [_row(), _row(itemType="material", item_name="PRIVATE_DUPLICATE")],
                "assignment_source_duplicate",
            ),
            ([_row(quantity=3, assigned_quantity=4)], "assignment_balance_invalid"),
            ([_row(quantity=math.inf)], "assignment_source_invalid"),
            ([_row(assigned_quantity=-1)], "assignment_balance_invalid"),
        )
        for rows, reason in cases:
            with self.subTest(reason=reason):
                draft = build_assignment_draft(self.scope, rows)
                self.assertEqual(draft.state, "review_required")
                self.assertEqual(draft.items, ())
                self.assertEqual(draft.review_codes, (reason,))
                self.assertNotIn("PRIVATE_", repr(draft))

    def test_scan_limit_is_inclusive_and_query_wide(self):
        accepted = [
            _row(
                section_index=index,
                item_index=0,
                item_key=f"80:{index}:0",
            )
            for index in range(MAX_ASSIGNMENT_DRAFT_ROWS)
        ]
        exact = build_assignment_draft(self.scope, accepted)
        self.assertEqual(exact.state, "ready")
        self.assertEqual(len(exact.items), MAX_ASSIGNMENT_DRAFT_ROWS)

        overflow = build_assignment_draft(
            self.scope,
            accepted + [_row(
                section_index=MAX_ASSIGNMENT_DRAFT_ROWS,
                item_key="PRIVATE_LIMIT",
            )],
        )
        self.assertEqual(overflow.state, "review_required")
        self.assertEqual(overflow.items, ())
        self.assertEqual(
            overflow.review_codes,
            ("assignment_draft_scan_limit_exceeded",),
        )
        self.assertNotIn("PRIVATE_LIMIT", repr(overflow))

    def test_utf8_field_caps_are_exact(self):
        exact = build_assignment_draft(self.scope, [_row(
            item_key="я" * 256,
            section_name="я" * 512,
            item_name="я" * 2048,
            unit="я" * 64,
        )])
        self.assertEqual(exact.state, "ready")

        overflow_rows = (
            _row(item_key="я" * 257),
            _row(section_name="я" * 513),
            _row(item_name="я" * 2049),
            _row(unit="я" * 65),
        )
        for row in overflow_rows:
            with self.subTest(row=row):
                rejected = build_assignment_draft(self.scope, [row])
                self.assertEqual(rejected.state, "review_required")
                self.assertEqual(
                    rejected.review_codes,
                    ("assignment_source_invalid",),
                )


if __name__ == "__main__":
    unittest.main()
