import unittest
from unittest.mock import Mock, patch

from . import legacy_registration_plan as plan_module
from .legacy_registration_plan import (
    APPLY_CONFIRMATION,
    LegacyRegistrationPlanError,
    build_legacy_registration_plan,
    load_legacy_registration_rows,
    run_legacy_registration_plan,
)


class LegacyRegistrationPlanTests(unittest.TestCase):
    def test_same_file_with_same_proven_owner_is_one_ready_registration(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "expenses.photo_url",
                    "recordId": 10,
                    "value": "/uploads/shared.jpg",
                    "companyId": 1,
                    "projectId": 7,
                    "projectName": "Объект",
                    "ownershipVerified": True,
                },
                {
                    "source": "own_expenses.photo_url",
                    "recordId": 11,
                    "value": "/uploads/shared.jpg",
                    "companyId": 1,
                    "projectId": 7,
                    "projectName": "Объект",
                    "ownershipVerified": True,
                },
            ],
            projects=[{"id": 7, "company_id": 1, "name": "Объект"}],
            registered_urls=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 2)
        self.assertEqual(report["summary"]["unregisteredUniqueUrls"], 1)
        self.assertEqual(report["summary"]["readyRegistrations"], 1)
        self.assertEqual(report["summary"]["needsReview"], 0)
        self.assertEqual(report["registrationsPreview"][0]["companyId"], 1)
        self.assertEqual(report["registrationsPreview"][0]["projectId"], 7)
        self.assertNotIn("shared.jpg", str(report))

    def test_conflicting_owners_for_same_file_block_apply(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "supplier_invoices.photo_url",
                    "recordId": 10,
                    "value": "/uploads/shared.jpg",
                    "companyId": 1,
                    "projectId": 7,
                },
                {
                    "source": "supplier_invoices.photo_url",
                    "recordId": 11,
                    "value": "/uploads/shared.jpg",
                    "companyId": 2,
                    "projectId": 8,
                },
            ],
            projects=[
                {"id": 7, "company_id": 1, "name": "Первый"},
                {"id": 8, "company_id": 2, "name": "Второй"},
            ],
            registered_urls=[],
            company_ids={1, 2},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["conflicting"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "owner_conflict")
        self.assertNotIn("shared.jpg", str(report))

    def test_unverified_legacy_accounting_owner_blocks_apply(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "expenses.photo_url",
                    "recordId": 10,
                    "value": "/uploads/expense.jpg",
                    "companyId": 1,
                    "ownershipVerified": False,
                }
            ],
            projects=[],
            registered_urls=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(
            report["needsReview"][0]["reason"],
            "source_owner_not_verified",
        )

    def test_ambiguous_project_name_blocks_apply_instead_of_guessing(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "room_works.photo_url",
                    "recordId": 10,
                    "value": "/uploads/room.jpg",
                    "projectName": "Одинаковое имя",
                }
            ],
            projects=[
                {"id": 7, "company_id": 1, "name": "Одинаковое имя"},
                {"id": 8, "company_id": 2, "name": "Одинаковое имя"},
            ],
            registered_urls=[],
            company_ids={1, 2},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_name_ambiguous")

    def test_registered_file_is_not_planned_again(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "warehouse_invoices.photo_url",
                    "recordId": 10,
                    "value": "/uploads/known.jpg",
                    "companyId": 1,
                }
            ],
            projects=[],
            registered_urls=["/uploads/known.jpg"],
            company_ids={1},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["alreadyRegisteredUniqueUrls"], 1)
        self.assertEqual(report["summary"]["readyRegistrations"], 0)

    def test_unknown_company_blocks_company_scoped_registration(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "supplier_invoices.photo_url",
                    "recordId": 10,
                    "value": "/uploads/orphan.jpg",
                    "companyId": 404,
                }
            ],
            projects=[],
            registered_urls=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["needsReview"][0]["reason"], "company_not_found")

    def test_company_only_legacy_row_is_not_assumed_in_multitenant_database(self):
        report = build_legacy_registration_plan(
            records=[
                {
                    "source": "supplier_invoices.photo_url",
                    "recordId": 10,
                    "value": "/uploads/company-only.jpg",
                    "companyId": 1,
                }
            ],
            projects=[],
            registered_urls=[],
            company_ids={1, 2},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(
            report["needsReview"][0]["reason"],
            "company_scope_not_provable",
        )

    def test_loader_uses_only_static_sources_and_available_owner_columns(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [
                {"table_name": "expenses", "column_name": name}
                for name in (
                    "id", "photo_url", "company_id", "project_id", "project",
                    "company_scope_verified",
                )
            ],
            [{"id": 7, "company_id": 1, "name": "Объект"}],
            [{"id": 1}],
            [{"file_url": "/uploads/known.jpg"}],
            [
                {
                    "record_id": 10,
                    "value": "/uploads/expense.jpg",
                    "company_id": 1,
                    "project_id": 7,
                    "project_name": "Объект",
                    "ownership_verified": True,
                }
            ],
        ]

        records, projects, registered, company_ids = load_legacy_registration_rows(cursor)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "expenses.photo_url")
        self.assertEqual(projects[0]["id"], 7)
        self.assertEqual(registered, ["/uploads/known.jpg"])
        self.assertEqual(company_ids, {1})
        self.assertEqual(cursor.execute.call_count, 5)

    def test_runner_is_read_only_and_rolls_back(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)

        with patch.object(
            plan_module,
            "load_legacy_registration_rows",
            return_value=([], [], [], set()),
        ):
            report = run_legacy_registration_plan(get_db)

        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        connection.rollback.assert_called_once_with()
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)

    def test_apply_requires_exact_confirmation_and_plan_guards(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        records = [{
            "source": "supplier_invoices.photo_url",
            "recordId": 10,
            "value": "/uploads/ready.jpg",
            "companyId": 1,
        }]
        dry = build_legacy_registration_plan(records, [], [], {1})

        with patch.object(
            plan_module,
            "load_legacy_registration_rows",
            return_value=(records, [], [], {1}),
        ):
            with self.assertRaises(LegacyRegistrationPlanError):
                run_legacy_registration_plan(
                    get_db,
                    apply=True,
                    confirm="wrong",
                    expected_ready_count=1,
                    expected_plan_sha256=dry["planSha256"],
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor.execute.assert_not_called()

    def test_apply_rejects_changed_plan_sha_before_writing(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        records = [{
            "source": "supplier_invoices.photo_url",
            "recordId": 10,
            "value": "/uploads/ready.jpg",
            "companyId": 1,
        }]

        with patch.object(
            plan_module,
            "load_legacy_registration_rows",
            return_value=(records, [], [], {1}),
        ):
            with self.assertRaisesRegex(
                LegacyRegistrationPlanError,
                "plan_sha256_mismatch",
            ):
                run_legacy_registration_plan(
                    get_db,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_ready_count=1,
                    expected_plan_sha256="0" * 64,
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor.execute.assert_not_called()

    def test_apply_registers_exact_guarded_plan_and_commits(self):
        connection = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = {"id": 44}
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        records = [{
            "source": "supplier_invoices.photo_url",
            "recordId": 10,
            "value": "/uploads/ready.jpg",
            "companyId": 1,
        }]
        dry = build_legacy_registration_plan(records, [], [], {1})

        with patch.object(
            plan_module,
            "load_legacy_registration_rows",
            return_value=(records, [], [], {1}),
        ):
            result = run_legacy_registration_plan(
                get_db,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_ready_count=1,
                expected_plan_sha256=dry["planSha256"],
            )

        connection.set_session.assert_called_once_with(autocommit=False)
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        self.assertEqual(cursor.execute.call_count, 1)
        sql_text = str(cursor.execute.call_args.args[0])
        self.assertIn("INSERT INTO file_ownership", sql_text)
        self.assertEqual(result["writesAttempted"], 1)
        self.assertTrue(result["committed"])
        self.assertFalse(result["rolledBack"])
        self.assertEqual(result["appliedPlanSha256"], dry["planSha256"])
        self.assertNotIn("ready.jpg", str(result))


if __name__ == "__main__":
    unittest.main()
