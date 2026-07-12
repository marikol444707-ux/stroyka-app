import unittest

from .migration import (
    _apply_ready,
    _plan_sha256,
    _validate_manual_channel_ids,
    build_report,
    classify_channel,
    parse_channel_owner,
    run_migration,
)


class MessengerChannelOwnershipMigrationTests(unittest.TestCase):
    def projects(self):
        return {
            "by_id": {
                10: {"id": 10, "company_id": 1, "name": "Объект A"},
                20: {"id": 20, "company_id": 2, "name": "Объект B"},
            },
            "by_name": {
                "Объект A": [{"id": 10, "company_id": 1, "name": "Объект A"}],
                "Объект B": [{"id": 20, "company_id": 2, "name": "Объект B"}],
            },
        }

    def classify(self, row, manual=None, companies=None):
        projects = self.projects()
        return classify_channel(
            row,
            projects["by_id"],
            projects["by_name"],
            set(companies or {1, 2}),
            manual or {},
        )

    def test_unique_project_name_is_ready(self):
        result = self.classify({"id": 1, "project_name": "Объект A"})

        self.assertEqual(result["status"], "ready")
        self.assertEqual((result["proposedCompanyId"], result["proposedProjectId"]), (1, 10))

    def test_company_level_channel_without_manual_owner_requires_review(self):
        result = self.classify({"id": 2, "project_name": "", "channel_type": "internal"})

        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["reason"], "manual_company_owner_required")

    def test_manual_company_owner_makes_company_channel_ready(self):
        result = self.classify(
            {"id": 3, "project_name": "", "channel_type": "internal"},
            manual={3: {"companyId": 1, "projectId": None}},
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["reason"], "explicit_company_owner")
        self.assertEqual((result["proposedCompanyId"], result["proposedProjectId"]), (1, None))

    def test_manual_project_must_belong_to_manual_company(self):
        result = self.classify(
            {"id": 4, "project_name": "Объект A"},
            manual={4: {"companyId": 2, "projectId": 10}},
        )

        self.assertEqual(result["status"], "mismatched")
        self.assertEqual(result["reason"], "manual_project_company_mismatch")

    def test_stored_owner_is_verified(self):
        result = self.classify(
            {"id": 5, "project_name": "Объект A", "stored_company_id": 1, "stored_project_id": 10},
        )

        self.assertEqual(result["status"], "stored")
        self.assertEqual(result["reason"], "stored_owner_verified")

    def test_stored_project_accepts_equivalent_company_only_mapping(self):
        result = self.classify(
            {"id": 6, "project_name": "Объект A", "stored_company_id": 1, "stored_project_id": 10},
            manual={6: {"companyId": 1, "projectId": None}},
        )

        self.assertEqual(result["status"], "stored")
        self.assertEqual(result["reason"], "stored_owner_verified")

    def test_report_blocks_apply_when_review_rows_exist(self):
        classified = [
            self.classify({"id": 1, "project_name": "Объект A"}),
            self.classify({"id": 2, "project_name": ""}),
        ]

        report = build_report(set(), classified)

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["ready"], 1)
        self.assertEqual(report["summary"]["unresolved"], 1)

    def test_owner_argument_and_plan_hash_are_deterministic(self):
        owner = parse_channel_owner("17:1")
        classified = [self.classify({"id": 17, "project_name": ""}, manual={17: owner})]

        self.assertEqual(owner, {"channelId": 17, "companyId": 1, "projectId": None})
        self.assertEqual(_plan_sha256(classified), _plan_sha256(list(reversed(classified))))

    def test_owner_argument_rejects_invalid_values(self):
        for value in ("", "17", "x:1", "17:0", "17:1:0", "17:1:2:3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_channel_owner(value)

    def test_manual_owner_for_unknown_channel_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown channel IDs: 99"):
            _validate_manual_channel_ids([{"id": 1}], {99: {"companyId": 1, "projectId": None}})

    def test_apply_updates_only_exact_unowned_channel(self):
        class Cursor:
            def __init__(self):
                self.calls = []
                self.rowcount = 1

            def execute(self, sql, params):
                self.calls.append((" ".join(sql.split()), params))

        cursor = Cursor()
        updated = _apply_ready(cursor, [{"channelId": 17, "proposedCompanyId": 1, "proposedProjectId": None}])

        self.assertEqual(updated, 1)
        self.assertEqual(cursor.calls[0][1], (1, None, 17))
        self.assertIn("WHERE id=%s AND company_id IS NULL AND project_id IS NULL", cursor.calls[0][0])

    def test_apply_requires_expected_count_and_sha_before_database_access(self):
        class Connection:
            def set_session(self, **_kwargs):
                raise AssertionError("database must not be touched")

        with self.assertRaisesRegex(ValueError, "expected_ready_count"):
            run_migration(Connection(), apply=True)


if __name__ == "__main__":
    unittest.main()
