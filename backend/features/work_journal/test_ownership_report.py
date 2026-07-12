import unittest

from backend.features.work_journal.ownership_report import (
    build_work_journal_ownership_report,
    classify_work_journal,
)


def owned_row(**overrides):
    row = {
        "journal_id": 11,
        "stored_company_id": 4,
        "project_count": 1,
        "project_id": 14,
        "project_company_id": 4,
        "estimate_id": 100,
        "estimate_exists": True,
        "estimate_company_id": 4,
        "estimate_project_id": 14,
        "unexpected_work_id": None,
        "unexpected_work_exists": False,
        "unexpected_company_id": None,
        "unexpected_project_id": None,
        "contract_item_id": None,
        "contract_item_exists": False,
        "contract_company_id": None,
        "contract_project_id": None,
    }
    row.update(overrides)
    return row


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)


class WorkJournalOwnershipReportTests(unittest.TestCase):
    def test_matching_project_and_parent_are_verified(self):
        result = classify_work_journal(owned_row())
        self.assertEqual(result["status"], "verified")
        self.assertEqual((result["companyId"], result["projectId"]), (4, 14))

    def test_legacy_default_company_becomes_safe_backfill_candidate(self):
        result = classify_work_journal(owned_row(stored_company_id=1))
        self.assertEqual(result["status"], "needs_backfill")
        self.assertEqual(result["reason"], "stored_company_mismatch")
        self.assertEqual(result["companyId"], 4)

    def test_ambiguous_project_name_requires_review(self):
        result = classify_work_journal(owned_row(project_count=2))
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["reason"], "project_name_ambiguous")

    def test_conflicting_explicit_parent_requires_review(self):
        result = classify_work_journal(owned_row(
            unexpected_work_id=88,
            unexpected_work_exists=True,
            unexpected_company_id=8,
            unexpected_project_id=80,
        ))
        self.assertEqual(result["status"], "mismatched")
        self.assertEqual(result["reason"], "unexpected_work_owner_mismatch")

    def test_report_uses_one_read_only_query_and_hides_business_content(self):
        cursor = FakeCursor([owned_row(), owned_row(journal_id=12, project_count=0)])
        report = build_work_journal_ownership_report(cursor)
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["summary"], {
            "totalRows": 2,
            "verified": 1,
            "needsBackfill": 0,
            "unresolved": 1,
            "mismatched": 0,
        })
        self.assertEqual(report["needsReview"], [{
            "journalId": 12,
            "status": "unresolved",
            "reason": "project_not_found",
        }])
        self.assertEqual(len(cursor.calls), 1)
        self.assertTrue(cursor.calls[0][0].startswith("SELECT"))
        self.assertNotIn("description", str(report))


if __name__ == "__main__":
    unittest.main()
