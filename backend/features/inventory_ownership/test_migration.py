import unittest

from .migration import _base_result, _plan_sha256
from .ownership_report import build_report_from_rows


def base_rows():
    return {
        "companies": [{"id": 1}], "projects": [],
        "tools": [{"id": 1, "project": ""}, {"id": 2, "project": ""}, {"id": 3, "project": ""}],
        "tool_history": [], "inventory": [], "inventory_items": [],
    }


class InventoryOwnershipMigrationTests(unittest.TestCase):
    def test_explicit_company_tools_form_a_deterministic_guarded_plan(self):
        report = build_report_from_rows(base_rows(), {1: 1, 2: 1, 3: 1})
        classified = report["verifiedPreview"] + report["needsReview"]

        digest = _plan_sha256(classified)

        self.assertEqual(len(digest), 64)
        self.assertEqual(report["summary"]["unresolved"], 0)
        self.assertEqual(_plan_sha256(list(reversed(classified))), digest)

    def test_unmapped_tool_blocks_migration(self):
        report = build_report_from_rows(base_rows(), {1: 1, 2: 1})
        classified = report["verifiedPreview"] + report["needsReview"]

        result = _base_result(
            {table: {"owner_scope": False, "company_id": False, "project_id": False}
             for table in ("tools", "tool_history", "inventory", "inventory_items")},
            report, classified, "dry-run",
        )

        self.assertFalse(result["readyForMigration"])
        self.assertEqual(result["readyCount"], 2)
        self.assertEqual(result["reviewCount"], 1)

    def test_stored_company_tools_need_no_backfill_after_schema_apply(self):
        rows = base_rows()
        for row in rows["tools"]:
            row.update({"stored_owner_scope": "company", "stored_company_id": 1, "stored_project_id": None})
        report = build_report_from_rows(rows)
        classified = report["verifiedPreview"] + report["needsReview"]
        schema = {table: {"owner_scope": True, "company_id": True, "project_id": True}
                  for table in ("tools", "tool_history", "inventory", "inventory_items")}

        result = _base_result(schema, report, classified, "apply")

        self.assertTrue(result["readyForStrictRuntime"])
        self.assertEqual(result["readyCount"], 0)


if __name__ == "__main__":
    unittest.main()
