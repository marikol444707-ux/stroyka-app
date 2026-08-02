import unittest
from unittest.mock import Mock, patch

from . import ownership_report as report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


def base_rows():
    return {
        "companies": [{"id": 3}, {"id": 4}],
        "projects": [
            {"id": 11, "company_id": 3, "name": "Object A"},
            {"id": 12, "company_id": 4, "name": "Object B"},
        ],
        "tools": [],
        "tool_history": [],
        "inventory": [],
        "inventory_items": [],
    }


class InventoryOwnershipReportTests(unittest.TestCase):
    def test_exact_project_and_parent_chains_are_verified(self):
        rows = base_rows()
        rows.update({
            "tools": [{"id": 21, "project": "Object A"}],
            "tool_history": [{"id": 22, "tool_id": 21, "project": "Object A"}],
            "inventory": [{"id": 31, "project": "Object A"}],
            "inventory_items": [{"id": 32, "inventory_id": 31}],
        })

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 4, "verified": 4, "unresolved": 0, "ambiguous": 0, "mismatched": 0,
        })
        self.assertEqual(report["readyByCompany"], {"3": 4})

    def test_empty_tool_project_is_not_assigned_from_location_or_master(self):
        rows = base_rows()
        rows["tools"] = [{"id": 21, "project": ""}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "project_owner_missing")

    def test_explicit_company_mapping_only_applies_to_the_named_tool(self):
        rows = base_rows()
        rows["tools"] = [{"id": 21, "project": ""}, {"id": 22, "project": ""}]

        report = build_report_from_rows(rows, {21: 3})

        verified = report["verifiedPreview"]
        self.assertEqual(verified[0]["recordId"], 21)
        self.assertEqual(verified[0]["ownerScope"], "company")
        self.assertEqual(verified[0]["companyId"], 3)
        self.assertEqual(report["needsReview"][0]["recordId"], 22)

    def test_stored_company_wide_tool_is_verified_without_a_manual_mapping(self):
        rows = base_rows()
        rows["tools"] = [{
            "id": 21, "project": "", "stored_owner_scope": "company",
            "stored_company_id": 3, "stored_project_id": None,
        }]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedPreview"][0]["reason"], "stored_company_owner")

    def test_duplicate_project_name_is_ambiguous_without_stored_company(self):
        rows = base_rows()
        rows["projects"].append({"id": 13, "company_id": 4, "name": "Object A"})
        rows["inventory"] = [{"id": 31, "project": "Object A"}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "project_owner_ambiguous")
        self.assertEqual(report["summary"]["ambiguous"], 1)

    def test_history_requires_matching_verified_tool_parent(self):
        rows = base_rows()
        rows["tools"] = [{"id": 21, "project": "Object A"}]
        rows["tool_history"] = [{"id": 22, "tool_id": 21, "project": "Object B"}]

        report = build_report_from_rows(rows)

        history = next(item for item in report["needsReview"] if item["table"] == "tool_history")
        self.assertEqual(history["reason"], "tool_project_mismatch")

    def test_inventory_item_requires_existing_inventory_parent(self):
        rows = base_rows()
        rows["inventory_items"] = [{"id": 32, "inventory_id": 404}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "inventory_parent_not_found")

    def test_loader_reads_only_ids_and_owner_relations(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [], [], [], [],
            [{"id": 3}], [{"id": 11, "company_id": 3, "name": "Object A"}],
            [{"id": 21, "project": "Object A"}], [{"id": 22, "tool_id": 21, "project": "Object A"}],
            [{"id": 31, "project": "Object A"}], [{"id": 32, "inventory_id": 31}],
        ]

        load_ownership_rows(cur)

        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in ("name from tools", "master", "location", "cost", "notes", "material_name", "expected", "actual"):
            self.assertNotIn(forbidden, sql)

    def test_runner_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        get_db = Mock(return_value=conn)

        with patch.object(report_module, "load_ownership_rows", return_value=base_rows()):
            result = run_ownership_report(get_db)

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        conn.close.assert_called_once_with()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
