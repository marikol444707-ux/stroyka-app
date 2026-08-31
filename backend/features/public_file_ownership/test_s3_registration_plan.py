import unittest
from unittest.mock import Mock, patch

from . import s3_registration_plan as plan_module
from .s3_registration_plan import (
    APPLY_CONFIRMATION,
    S3RegistrationPlanError,
    build_s3_registration_plan,
    run_s3_registration_plan,
)


class S3RegistrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.registered = [{
            "id": 1,
            "company_id": 1,
            "project_id": 7,
            "file_url": "https://storage.example/uploads/company-1-project-7-expense/expense/known.jpg",
            "storage_key": "uploads/company-1-project-7-expense/expense/known.jpg",
        }]
        self.projects = [{"id": 7, "company_id": 1}]

    def test_same_file_in_expense_and_parent_becomes_one_registration(self):
        key = "uploads/company-1-project-7-expense/expense/shared.jpg"
        url = "https://storage.example/" + key
        report = build_s3_registration_plan(
            records=[
                self._record("expenses.photo_url", 10, url),
                self._record("own_expenses.photo_url", 11, url),
            ],
            ownership_rows=self.registered,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys={key},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 2)
        self.assertEqual(report["summary"]["uniqueFileCount"], 1)
        self.assertEqual(report["summary"]["readyRegistrations"], 1)
        self.assertEqual(report["summary"]["verifiedObjects"], 1)
        self.assertNotIn("storage.example", str(report))
        self.assertNotIn("shared.jpg", str(report))

    def test_comma_separated_legacy_urls_become_individual_registrations(self):
        first_key = "uploads/company-1-project-7-expense/expense/first.jpg"
        second_key = "uploads/company-1-project-7-expense/expense/second.jpg"
        first_url = "https://storage.example/" + first_key
        second_url = "https://storage.example/" + second_key

        report = build_s3_registration_plan(
            records=[
                self._record(
                    "expenses.photo_url",
                    10,
                    first_url + "," + second_url,
                ),
            ],
            ownership_rows=self.registered,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys={first_key, second_key},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 2)
        self.assertEqual(report["summary"]["uniqueFileCount"], 2)
        self.assertEqual(report["summary"]["readyRegistrations"], 2)
        self.assertEqual(report["summary"]["verifiedObjects"], 2)

    def test_unverified_accounting_owner_blocks_registration(self):
        key = "uploads/company-1-project-7-expense/expense/unverified.jpg"
        url = "https://storage.example/" + key
        record = self._record("expenses.photo_url", 10, url)
        record["ownershipVerified"] = False

        report = build_s3_registration_plan(
            records=[record],
            ownership_rows=self.registered,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys={key},
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("source_owner_not_verified", report["blockers"])

    def test_owner_conflict_for_same_url_blocks_registration(self):
        key = "uploads/company-1-project-7-expense/expense/conflict.jpg"
        url = "https://storage.example/" + key
        report = build_s3_registration_plan(
            records=[
                self._record("expenses.photo_url", 10, url),
                {
                    **self._record("own_expenses.photo_url", 11, url),
                    "companyId": 2,
                    "projectId": 8,
                },
            ],
            ownership_rows=self.registered,
            projects=[*self.projects, {"id": 8, "company_id": 2}],
            company_ids={1, 2},
            verified_storage_keys={key},
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("owner_conflict", report["blockers"])

    def test_unknown_storage_url_shape_is_not_accepted(self):
        report = build_s3_registration_plan(
            records=[self._record(
                "expenses.photo_url",
                10,
                "https://other.example/uploads/company-1-project-7-expense/expense/file.jpg",
            )],
            ownership_rows=self.registered,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys=set(),
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("storage_url_not_recognized", report["blockers"])

    def test_missing_object_blocks_registration(self):
        url = "https://storage.example/uploads/company-1-project-7-expense/expense/missing.jpg"
        report = build_s3_registration_plan(
            records=[self._record("expenses.photo_url", 10, url)],
            ownership_rows=self.registered,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys=set(),
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("storage_object_not_verified", report["blockers"])

    def test_existing_storage_key_is_not_registered_twice(self):
        key = "uploads/company-1-project-7-expense/expense/known.jpg"
        ownership_rows = [
            *self.registered,
            {
                "id": 2,
                "company_id": 1,
                "project_id": 7,
                "file_url": "https://cdn.example/uploads/company-1-project-7-expense/expense/layout.jpg",
                "storage_key": "uploads/company-1-project-7-expense/expense/layout.jpg",
            },
        ]
        report = build_s3_registration_plan(
            records=[self._record(
                "expenses.photo_url",
                10,
                "https://cdn.example/" + key,
            )],
            ownership_rows=ownership_rows,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys={key},
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("storage_key_already_registered", report["blockers"])

    def test_storage_namespace_for_another_company_is_rejected(self):
        key = "uploads/company-2-project-7-expense/expense/wrong.jpg"
        report = build_s3_registration_plan(
            records=[self._record(
                "expenses.photo_url",
                10,
                "https://storage.example/" + key,
            )],
            ownership_rows=self.registered,
            projects=self.projects,
            company_ids={1},
            verified_storage_keys={key},
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("storage_key_owner_mismatch", report["blockers"])

    def test_runner_is_read_only_and_verifies_each_unique_object_once(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._runner_rows()
        verifier = Mock(return_value=True)

        with patch.object(plan_module, "load_s3_registration_rows", return_value=rows):
            report = run_s3_registration_plan(
                get_db,
                verify_storage_key=verifier,
            )

        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        verifier.assert_called_once_with(
            "uploads/company-1-project-7-expense/expense/ready.jpg"
        )
        self.assertTrue(report["readyForApply"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)

    def test_apply_rejects_wrong_plan_hash_before_lock_or_insert(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._runner_rows()

        with patch.object(plan_module, "load_s3_registration_rows", return_value=rows):
            with self.assertRaisesRegex(S3RegistrationPlanError, "plan_sha256_mismatch"):
                run_s3_registration_plan(
                    get_db,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_ready_count=1,
                    expected_plan_sha256="0" * 64,
                    verify_storage_key=lambda _key: True,
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor.execute.assert_not_called()

    def test_storage_verifier_failure_is_not_silently_treated_as_missing(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)

        with patch.object(
            plan_module,
            "load_s3_registration_rows",
            return_value=self._runner_rows(),
        ):
            with self.assertRaisesRegex(RuntimeError, "verification service failed"):
                run_s3_registration_plan(
                    get_db,
                    verify_storage_key=Mock(
                        side_effect=RuntimeError("verification service failed")
                    ),
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_exact_guarded_apply_registers_one_file(self):
        connection = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = {"id": 44}
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._runner_rows()
        dry = build_s3_registration_plan(
            *rows,
            verified_storage_keys={
                "uploads/company-1-project-7-expense/expense/ready.jpg"
            },
        )

        with patch.object(plan_module, "load_s3_registration_rows", return_value=rows):
            result = run_s3_registration_plan(
                get_db,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_ready_count=1,
                expected_plan_sha256=dry["planSha256"],
                verify_storage_key=lambda _key: True,
            )

        connection.commit.assert_called_once_with()
        self.assertTrue(result["committed"])
        self.assertEqual(result["registeredCount"], 1)
        self.assertEqual(result["writesAttempted"], 1)
        self.assertNotIn("storage.example", str(result))
        insert_calls = [
            call for call in cursor.execute.call_args_list
            if "INSERT INTO public.file_ownership" in str(call.args[0])
        ]
        self.assertEqual(len(insert_calls), 1)

    def _runner_rows(self):
        key = "uploads/company-1-project-7-expense/expense/ready.jpg"
        return (
            [self._record("expenses.photo_url", 10, "https://storage.example/" + key)],
            self.registered,
            self.projects,
            {1},
        )

    @staticmethod
    def _record(source, record_id, url):
        return {
            "source": source,
            "recordId": record_id,
            "value": url,
            "companyId": 1,
            "projectId": 7,
            "ownershipVerified": True,
        }


if __name__ == "__main__":
    unittest.main()
