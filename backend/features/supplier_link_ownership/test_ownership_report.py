import unittest
from unittest.mock import Mock, patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


def base_rows():
    return {
        "platform_accounts": [{"id": 7}],
        "companies": [{"id": 3, "platform_account_id": 7}],
        "suppliers": [{"id": 11}],
        "company_supplier_links": [],
    }


class SupplierLinkOwnershipReportTests(unittest.TestCase):
    def test_company_and_global_supplier_parents_are_verified(self):
        rows = base_rows()
        rows["company_supplier_links"] = [
            {"id": 21, "company_id": 3, "supplier_id": 11, "platform_account_id": None}
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 1,
            "verified": 1,
            "unresolved": 0,
            "mismatched": 0,
        })
        self.assertEqual(report["readyByCompany"], {"3": 1})

    def test_matching_stored_platform_account_is_verified(self):
        rows = base_rows()
        rows["company_supplier_links"] = [
            {"id": 21, "company_id": 3, "supplier_id": 11, "platform_account_id": 7}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["verifiedPreview"][0]["reason"], "verified_company_supplier_account")

    def test_missing_company_is_unresolved(self):
        rows = base_rows()
        rows["company_supplier_links"] = [
            {"id": 21, "company_id": 404, "supplier_id": 11, "platform_account_id": None}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "company_not_found")
        self.assertEqual(report["summary"]["unresolved"], 1)

    def test_missing_supplier_is_unresolved(self):
        rows = base_rows()
        rows["company_supplier_links"] = [
            {"id": 21, "company_id": 3, "supplier_id": 404, "platform_account_id": None}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "supplier_not_found")

    def test_stored_platform_account_must_match_company(self):
        rows = base_rows()
        rows["platform_accounts"].append({"id": 8})
        rows["company_supplier_links"] = [
            {"id": 21, "company_id": 3, "supplier_id": 11, "platform_account_id": 8}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "platform_account_mismatch")
        self.assertEqual(report["summary"]["mismatched"], 1)

    def test_loader_reads_only_ids_and_owner_relations(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [{"id": 7}],
            [{"id": 3, "platform_account_id": 7}],
            [{"id": 11}],
            [{"id": 21, "company_id": 3, "supplier_id": 11, "platform_account_id": 7}],
        ]

        rows = load_ownership_rows(cur)

        self.assertEqual(rows["company_supplier_links"][0]["company_id"], 3)
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in (
            "contract", "rating", "category", "source", "status", "name", "phone",
            "email", "inn", "kpp", "ogrn", "address",
        ):
            self.assertNotIn(forbidden, sql)

    def test_runner_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        get_db = Mock(return_value=conn)

        with patch.object(
            ownership_report_module,
            "load_ownership_rows",
            return_value=base_rows(),
        ):
            result = run_ownership_report(get_db)

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        conn.close.assert_called_once_with()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
