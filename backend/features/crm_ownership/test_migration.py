import unittest

from .migration import (
    _apply_children,
    _apply_leads,
    _plan_sha256,
    _validate_manual_lead_ids,
    build_report,
    classify_child,
    classify_lead,
    parse_lead_owner,
    run_migration,
)


class CrmOwnershipMigrationTests(unittest.TestCase):
    def projects(self):
        return {
            10: {"id": 10, "company_id": 1},
            20: {"id": 20, "company_id": 2},
        }

    def classify(self, row, manual=None, companies=None):
        return classify_lead(
            row,
            self.projects(),
            set(companies or {1, 2}),
            manual or {},
        )

    def test_project_lead_inherits_exact_project_company(self):
        item = self.classify({"id": 1, "project_id": 10})

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["reason"], "verified_project_parent")
        self.assertEqual((item["proposedCompanyId"], item["proposedProjectId"]), (1, 10))

    def test_standalone_lead_requires_explicit_company_owner(self):
        item = self.classify({"id": 1, "project_id": None})

        self.assertEqual(item["status"], "unresolved")
        self.assertEqual(item["reason"], "manual_company_owner_required")

    def test_manual_company_owner_makes_standalone_lead_ready(self):
        item = self.classify(
            {"id": 1, "project_id": None},
            manual={1: {"companyId": 1}},
        )

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["reason"], "explicit_company_owner")
        self.assertEqual((item["proposedCompanyId"], item["proposedProjectId"]), (1, None))

    def test_manual_company_cannot_override_project_company(self):
        item = self.classify(
            {"id": 1, "project_id": 10},
            manual={1: {"companyId": 2}},
        )

        self.assertEqual(item["status"], "mismatched")
        self.assertEqual(item["reason"], "manual_project_company_mismatch")

    def test_stored_company_owner_is_verified(self):
        item = self.classify(
            {"id": 1, "project_id": None, "stored_company_id": 1},
            manual={1: {"companyId": 1}},
        )

        self.assertEqual(item["status"], "stored")
        self.assertEqual(item["reason"], "stored_owner_verified")

    def test_child_inherits_owner_only_from_verified_lead(self):
        lead = self.classify(
            {"id": 1, "project_id": None},
            manual={1: {"companyId": 1}},
        )
        child = classify_child("crm_lead_tasks", {"id": 2, "lead_id": 1}, {1: lead})

        self.assertEqual(child["status"], "ready")
        self.assertEqual((child["proposedCompanyId"], child["proposedProjectId"]), (1, None))

    def test_child_of_unresolved_lead_is_blocked(self):
        lead = self.classify({"id": 1, "project_id": None})
        child = classify_child("crm_lead_documents", {"id": 2, "lead_id": 1}, {1: lead})

        self.assertEqual(child["status"], "unresolved")
        self.assertEqual(child["reason"], "lead_owner_not_verified")

    def test_stored_child_owner_must_match_lead_owner(self):
        lead = self.classify(
            {"id": 1, "project_id": 10, "stored_company_id": 1},
        )
        child = classify_child(
            "crm_lead_documents",
            {"id": 2, "lead_id": 1, "stored_company_id": 2, "stored_project_id": 20},
            {1: lead},
        )

        self.assertEqual(child["status"], "mismatched")
        self.assertEqual(child["reason"], "stored_owner_mismatch")

    def test_report_blocks_migration_while_standalone_lead_is_unmapped(self):
        report = build_report(
            {"crm_leads": set(), "crm_lead_documents": set(), "crm_lead_tasks": set()},
            [self.classify({"id": 1, "project_id": None})],
        )

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["unresolved"], 1)

    def test_owner_argument_and_plan_hash_are_deterministic(self):
        owner = parse_lead_owner("1:2")
        item = self.classify({"id": 1, "project_id": None}, manual={1: owner})

        self.assertEqual(owner, {"leadId": 1, "companyId": 2})
        self.assertEqual(_plan_sha256([item]), _plan_sha256(list(reversed([item]))))

    def test_owner_argument_rejects_invalid_values(self):
        for value in ("", "1", "x:1", "1:0", "1:2:3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_lead_owner(value)

    def test_manual_owner_for_unknown_lead_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown lead IDs: 99"):
            _validate_manual_lead_ids([{"id": 1}], {99: {"companyId": 1}})

    def test_apply_updates_only_exact_ownerless_rows(self):
        class Cursor:
            def __init__(self):
                self.calls = []
                self.rowcount = 1

            def execute(self, sql, params):
                self.calls.append((" ".join(sql.split()), params))

        cursor = Cursor()
        lead = {
            "recordId": 1,
            "proposedCompanyId": 1,
            "proposedProjectId": None,
        }
        child = {
            "recordId": 2,
            "proposedCompanyId": 1,
            "proposedProjectId": None,
        }

        self.assertEqual(_apply_leads(cursor, [lead]), 1)
        self.assertEqual(_apply_children(cursor, "crm_lead_tasks", "t", [child]), 1)
        self.assertIn("WHERE id=%s AND company_id IS NULL", cursor.calls[0][0])
        self.assertIn(
            "WHERE t.id=owners.id AND t.company_id IS NULL AND t.project_id IS NULL",
            cursor.calls[1][0],
        )

    def test_apply_requires_expected_guards_before_database_access(self):
        class Connection:
            def set_session(self, **_kwargs):
                raise AssertionError("database must not be touched")

        with self.assertRaisesRegex(ValueError, "expected_ready_count"):
            run_migration(Connection(), apply=True)


if __name__ == "__main__":
    unittest.main()
