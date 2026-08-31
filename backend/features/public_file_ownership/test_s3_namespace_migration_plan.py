import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote

from . import s3_namespace_migration_plan as plan_module
from .s3_namespace_migration_plan import (
    _prepare_s3_namespace_migration_plan,
    build_s3_namespace_migration_plan,
    run_s3_namespace_migration_plan,
)


class S3NamespaceMigrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.ownership_rows = [{
            "id": 1,
            "company_id": 1,
            "project_id": 7,
            "file_url": (
                "https://storage.example/uploads/"
                "company-1-project-7-expenses/expenses/known.jpg"
            ),
            "storage_key": (
                "uploads/company-1-project-7-expenses/expenses/known.jpg"
            ),
        }]
        self.projects = [{
            "id": 7,
            "company_id": 1,
            "name": "Кисловодск Лицей 4",
        }]

    def test_legacy_project_path_gets_deterministic_canonical_destination(self):
        source_key = (
            "uploads/Кисловодск-Лицей-4/own-expenses/own-expenses/"
            "2026/08/14/photo.jpg"
        )
        url = "https://storage.example/" + quote(source_key, safe="/")

        first = self._build([self._record("own_expenses.photo_url", 8, url)], {source_key})
        second = self._build([self._record("own_expenses.photo_url", 8, url)], {source_key})

        self.assertTrue(first["readyForApply"])
        self.assertEqual(first["summary"]["readyObjectCopies"], 1)
        self.assertEqual(first["summary"]["affectedCells"], 1)
        self.assertEqual(first["planSha256"], second["planSha256"])
        preview = first["migrationsPreview"][0]
        self.assertEqual(preview["companyId"], 1)
        self.assertEqual(preview["projectId"], 7)
        self.assertEqual(preview["context"], "own-expenses")
        self.assertNotIn("storage.example", str(first))
        self.assertNotIn("Кисловодск", str(first))
        self.assertNotIn("photo.jpg", str(first))

    def test_shared_photo_is_copied_once_but_rewrites_two_cells(self):
        source_key = (
            "uploads/Кисловодск-Лицей-4/own-expenses/2026/08/shared.jpg"
        )
        url = "https://storage.example/" + quote(source_key, safe="/")
        report = self._build(
            [
                self._record("expenses.photo_url", 26, url),
                self._record("own_expenses.photo_url", 7, url),
            ],
            {source_key},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["readyObjectCopies"], 1)
        self.assertEqual(report["summary"]["affectedCells"], 2)
        self.assertEqual(
            report["migrationsPreview"][0]["sources"],
            ["expenses.photo_url", "own_expenses.photo_url"],
        )

    def test_protected_tenant_route_is_not_treated_as_an_s3_object(self):
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                "/tenant-files/812/content",
            )],
            set(),
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 0)
        self.assertEqual(report["summary"]["readyObjectCopies"], 0)
        self.assertEqual(report["blockers"], [])

    def test_list_of_protected_tenant_routes_is_a_clear_post_migration_state(self):
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                '["/tenant-files/812/content", "/tenant-files/913/content"]',
            )],
            set(),
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 0)
        self.assertEqual(report["blockers"], [])

    def test_legacy_embedded_protected_routes_are_a_clear_post_migration_state(self):
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                (
                    "'/tenant-files/812/content', "
                    "'/tenant-files/913/content'"
                ),
            )],
            set(),
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 0)
        self.assertEqual(report["blockers"], [])

    def test_malformed_protected_route_is_still_reported(self):
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                "/tenant-files/812/content unexpected",
            )],
            set(),
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("storage_url_not_recognized", report["blockers"])

    def test_project_slug_mismatch_blocks_migration(self):
        source_key = "uploads/Другой-объект/manual-expenses/file.jpg"
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                "https://storage.example/" + quote(source_key, safe="/"),
            )],
            {source_key},
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("legacy_project_name_mismatch", report["blockers"])

    def test_unverified_source_object_blocks_migration(self):
        source_key = "uploads/Кисловодск-Лицей-4/manual-expenses/file.jpg"
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                "https://storage.example/" + quote(source_key, safe="/"),
            )],
            set(),
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("source_object_not_verified", report["blockers"])

    def test_canonical_or_cross_tenant_source_is_never_migrated(self):
        source_key = (
            "uploads/company-2-project-7-expenses/expenses/foreign.jpg"
        )
        report = self._build(
            [self._record(
                "expenses.photo_url",
                49,
                "https://storage.example/" + quote(source_key, safe="/"),
            )],
            {source_key},
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("source_namespace_not_legacy", report["blockers"])

    def test_runner_is_read_only_and_verifies_each_source_once(self):
        source_key = "uploads/Кисловодск-Лицей-4/manual-expenses/file.jpg"
        rows = (
            [self._record(
                "expenses.photo_url",
                49,
                "https://storage.example/" + quote(source_key, safe="/"),
            )],
            self.ownership_rows,
            self.projects,
            {1},
        )
        connection = Mock()
        connection.cursor.return_value = Mock()
        get_db = Mock(return_value=connection)
        verifier = Mock(return_value=True)

        with patch.object(plan_module, "load_s3_registration_rows", return_value=rows):
            report = run_s3_namespace_migration_plan(
                get_db,
                verify_storage_key=verifier,
            )

        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        verifier.assert_called_once_with(source_key)
        self.assertTrue(report["readyForApply"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)

    def test_destination_keeps_the_exact_recognized_storage_base(self):
        source_key = "uploads/Кисловодск-Лицей-4/manual-expenses/file.jpg"
        source_url = "https://second.example/" + quote(source_key, safe="/")
        second_registry_row = {
            **self.ownership_rows[0],
            "id": 2,
            "file_url": (
                "https://second.example/uploads/"
                "company-1-project-7-expenses/expenses/known.jpg"
            ),
        }

        _report, migrations = _prepare_s3_namespace_migration_plan(
            records=[self._record("expenses.photo_url", 49, source_url)],
            ownership_rows=[*self.ownership_rows, second_registry_row],
            projects=self.projects,
            company_ids={1},
            verified_source_keys={source_key},
            storage_prefixes=("uploads",),
        )

        self.assertEqual(len(migrations), 1)
        self.assertTrue(migrations[0]["destinationUrl"].startswith("https://second.example/"))

    def test_verification_failure_rolls_back_and_propagates(self):
        source_key = "uploads/Кисловодск-Лицей-4/manual-expenses/file.jpg"
        rows = (
            [self._record(
                "expenses.photo_url",
                49,
                "https://storage.example/" + quote(source_key, safe="/"),
            )],
            self.ownership_rows,
            self.projects,
            {1},
        )
        connection = Mock()
        connection.cursor.return_value = Mock()

        with patch.object(plan_module, "load_s3_registration_rows", return_value=rows):
            with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
                run_s3_namespace_migration_plan(
                    Mock(return_value=connection),
                    verify_storage_key=Mock(
                        side_effect=RuntimeError("storage unavailable")
                    ),
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_runner_does_not_open_a_nonlegacy_or_cross_tenant_key(self):
        source_key = (
            "uploads/company-2-project-7-expenses/expenses/foreign.jpg"
        )
        rows = (
            [self._record(
                "expenses.photo_url",
                49,
                "https://storage.example/" + source_key,
            )],
            self.ownership_rows,
            self.projects,
            {1},
        )
        connection = Mock()
        connection.cursor.return_value = Mock()
        verifier = Mock(return_value=True)

        with patch.object(plan_module, "load_s3_registration_rows", return_value=rows):
            report = run_s3_namespace_migration_plan(
                Mock(return_value=connection),
                verify_storage_key=verifier,
            )

        verifier.assert_not_called()
        self.assertFalse(report["readyForApply"])
        self.assertIn("source_namespace_not_legacy", report["blockers"])

    def _build(self, records, verified):
        return build_s3_namespace_migration_plan(
            records=records,
            ownership_rows=self.ownership_rows,
            projects=self.projects,
            company_ids={1},
            verified_source_keys=verified,
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
