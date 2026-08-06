import unittest
from decimal import Decimal

from backend.features.estimate_row_transfer.plan import (
    build_reviewed_plan,
    normalize_draft_payload,
)
from backend.features.estimate_row_transfer.storage import (
    approve_plan,
    find_plan_id_by_hash,
    insert_draft,
    load_stored_plan,
)
from backend.features.estimate_row_transfer.test_plan import (
    assignment_mapping,
    assignment_report,
)


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.current = None
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        self.current = self.results.pop(0) if self.results else None

    def fetchone(self):
        return self.current

    def fetchall(self):
        return list(self.current or [])


def reviewed_plan():
    entries = normalize_draft_payload({
        "reconciliationId": 9,
        "entries": [assignment_mapping()],
    })["entries"]
    return build_reviewed_plan(assignment_report(), entries)


def header_row(plan, **overrides):
    row = {
        "id": 5,
        "company_id": plan["companyId"],
        "project_id": plan["projectId"],
        "work_package": plan["workPackage"],
        "smeta_type": plan["smetaType"],
        "reconciliation_id": plan["reconciliationId"],
        "base_estimate_id": plan["baseEstimateId"],
        "target_estimate_id": plan["targetEstimateId"],
        "target_estimate_version_id": plan["targetSnapshot"]["estimateVersionId"],
        "base_sections_sha256": plan["baseSnapshot"]["sectionsSha256"],
        "target_sections_sha256": plan["targetSnapshot"]["sectionsSha256"],
        "base_snapshot_row_count": plan["baseSnapshot"]["rowCount"],
        "target_snapshot_row_count": plan["targetSnapshot"]["rowCount"],
        "plan_sha256": plan["planSha256"],
        "approved_plan_sha256": None,
        "status": "draft",
        "created_by_user_id": 12,
        "created_by_name": "Сметчик",
        "created_by_role": "сметчик",
        "approved_by_user_id": None,
        "approved_by_name": None,
        "approved_by_role": None,
        "approved_at": None,
        "created_at": "2026-08-06 10:00:00+03",
        "updated_at": "2026-08-06 10:00:00+03",
    }
    row.update(overrides)
    return row


def entry_row(plan):
    entry = plan["entries"][0]
    return {
        "id": 8,
        "plan_id": 5,
        "company_id": plan["companyId"],
        "project_id": plan["projectId"],
        "source_kind": entry["sourceKind"],
        "source_id": entry["sourceId"],
        "source_parent_id": entry["sourceParentId"],
        "request_item_index": None,
        "source_estimate_id": entry["source"]["estimateId"],
        "source_estimate_version_id": entry["source"]["estimateVersionId"],
        "source_section_index": entry["source"]["sectionIndex"],
        "source_item_index": entry["source"]["itemIndex"],
        "source_item_key": entry["source"]["itemKey"],
        "source_sections_sha256": entry["source"]["sectionsSha256"],
        "target_estimate_id": entry["target"]["estimateId"],
        "target_estimate_version_id": entry["target"]["estimateVersionId"],
        "target_section_index": entry["target"]["sectionIndex"],
        "target_item_index": entry["target"]["itemIndex"],
        "target_item_key": entry["target"]["itemKey"],
        "target_sections_sha256": entry["target"]["sectionsSha256"],
        "source_total_quantity": Decimal(entry["sourceTotalQuantity"]),
        "source_protected_quantity": Decimal(entry["sourceProtectedQuantity"]),
        "source_available_quantity": Decimal(entry["sourceAvailableQuantity"]),
        "quantity": Decimal(entry["quantity"]),
        "created_at": "2026-08-06 10:00:00+03",
    }


class EstimateRowTransferStorageTests(unittest.TestCase):
    def test_insert_draft_writes_only_plan_and_entry_tables(self):
        plan = reviewed_plan()
        cursor = FakeCursor([{"id": 5}])
        actor = {"id": 12, "name": "Сметчик", "role": "сметчик"}

        plan_id = insert_draft(cursor, plan, actor)

        self.assertEqual(plan_id, 5)
        self.assertEqual(len(cursor.calls), 2)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("INSERT INTO public.estimate_row_transfer_plans", sql)
        self.assertIn("INSERT INTO public.estimate_row_transfer_entries", sql)
        self.assertNotIn("brigade_contract_items", sql)
        self.assertNotIn("supply_requests", sql)

    def test_load_reconstructs_the_exact_hashed_plan_inside_company(self):
        plan = reviewed_plan()
        cursor = FakeCursor([header_row(plan), [entry_row(plan)]])

        stored = load_stored_plan(cursor, 5, 1, for_update=True)

        self.assertEqual(stored["canonicalPlan"], plan)
        self.assertEqual(stored["status"], "draft")
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertTrue(cursor.calls[0][0].endswith("FOR UPDATE"))
        self.assertEqual(cursor.calls[0][1], (5, 1))

    def test_hash_lookup_and_approval_are_guarded_by_stored_owner_and_hash(self):
        plan = reviewed_plan()
        cursor = FakeCursor([{"id": 5}, {"id": 5}])

        found = find_plan_id_by_hash(cursor, 1, 9, plan["planSha256"])
        approved = approve_plan(
            cursor,
            plan_id=5,
            company_id=1,
            expected_plan_sha256=plan["planSha256"],
            actor={"id": 2, "name": "Директор", "role": "директор"},
        )

        self.assertEqual(found, 5)
        self.assertTrue(approved)
        approval_sql, approval_params = cursor.calls[1]
        self.assertIn("status='draft'", approval_sql)
        self.assertIn("plan_sha256=%s", approval_sql)
        self.assertIn(plan["planSha256"], approval_params)


if __name__ == "__main__":
    unittest.main()
