import unittest
from unittest.mock import Mock, patch

from . import s3_reference_cutover as cutover_module
from .s3_reference_cutover import (
    APPLY_CONFIRMATION,
    S3ReferenceCutoverError,
    build_s3_reference_cutover_plan,
    run_s3_reference_cutover,
)


class S3ReferenceCutoverTests(unittest.TestCase):
    def test_registered_s3_references_become_protected_urls(self):
        first = "https://storage.example/uploads/company-1/first.jpg"
        second = "https://storage.example/uploads/company-1/second.pdf"
        report = build_s3_reference_cutover_plan(
            records=[{
                "source": "project_documents.files_json",
                "recordId": 10,
                "value": '{"items":["' + first + '","' + second + '"]}',
                "dataType": "jsonb",
                "companyId": 1,
                "projectId": 7,
            }],
            ownership_rows=[
                {
                    "id": 41,
                    "file_url": first,
                    "storage_key": "uploads/company-1/first.jpg",
                    "company_id": 1,
                    "project_id": 7,
                },
                {
                    "id": 42,
                    "file_url": second,
                    "storage_key": "uploads/company-1/second.pdf",
                    "company_id": 1,
                    "project_id": 7,
                },
            ],
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 2)
        self.assertEqual(report["summary"]["cellUpdateCount"], 1)
        self.assertEqual(report["summary"]["uniqueFileCount"], 2)
        self.assertEqual(report["blockers"], [])
        self.assertNotIn("storage.example", str(report))

    def test_cross_company_reference_blocks_cutover(self):
        url = "https://storage.example/uploads/company-2/wrong.jpg"
        report = build_s3_reference_cutover_plan(
            records=[{
                "source": "company_documents.file_url",
                "recordId": 10,
                "value": url,
                "dataType": "text",
                "companyId": 1,
            }],
            ownership_rows=[{
                "id": 41,
                "file_url": url,
                "storage_key": "uploads/company-2/wrong.jpg",
                "company_id": 2,
                "project_id": None,
            }],
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["conflictingReferences"], 1)
        self.assertIn("reference_owner_mismatch", report["blockers"])

    def test_duplicate_registration_blocks_cutover(self):
        url = "https://storage.example/uploads/company-1/duplicate.jpg"
        report = build_s3_reference_cutover_plan(
            records=[{
                "source": "company_documents.file_url",
                "recordId": 10,
                "value": url,
                "dataType": "text",
                "companyId": 1,
            }],
            ownership_rows=[
                {
                    "id": 41,
                    "file_url": url,
                    "storage_key": "uploads/company-1/duplicate.jpg",
                    "company_id": 1,
                },
                {
                    "id": 42,
                    "file_url": url,
                    "storage_key": "uploads/company-1/duplicate.jpg",
                    "company_id": 1,
                },
            ],
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["conflictingReferences"], 1)
        self.assertIn("file_registration_ambiguous", report["blockers"])

    def test_source_without_provable_owner_blocks_cutover(self):
        url = "https://storage.example/uploads/company-1/unscoped.jpg"
        report = build_s3_reference_cutover_plan(
            records=[{
                "source": "legacy_documents.file_url",
                "recordId": 10,
                "value": url,
                "dataType": "text",
                "companyId": None,
                "projectId": None,
            }],
            ownership_rows=[{
                "id": 41,
                "file_url": url,
                "storage_key": "uploads/company-1/unscoped.jpg",
                "company_id": 1,
                "project_id": None,
            }],
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["unresolvedReferences"], 1)
        self.assertIn("source_owner_missing", report["blockers"])

    def test_unregistered_url_on_storage_host_blocks_cutover(self):
        registered = "https://storage.example/uploads/company-1/registered.jpg"
        missing = "https://storage.example/uploads/company-1/missing.jpg"
        report = build_s3_reference_cutover_plan(
            records=[{
                "source": "company_documents.file_url",
                "recordId": 10,
                "value": missing,
                "dataType": "text",
                "companyId": 1,
            }],
            ownership_rows=[{
                "id": 41,
                "file_url": registered,
                "storage_key": "uploads/company-1/registered.jpg",
                "company_id": 1,
            }],
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["unresolvedReferences"], 1)
        self.assertIn("file_registration_missing", report["blockers"])

    def test_apply_rejects_changed_plan_before_writing(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._single_ready_rows()

        with patch.object(
            cutover_module,
            "load_s3_reference_cutover_rows",
            return_value=rows,
        ):
            with self.assertRaisesRegex(
                S3ReferenceCutoverError,
                "plan_sha256_mismatch",
            ):
                run_s3_reference_cutover(
                    get_db,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_update_count=1,
                    expected_reference_count=1,
                    expected_plan_sha256="0" * 64,
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor.execute.assert_not_called()

    def test_exact_guarded_apply_commits_one_cell_update(self):
        connection = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = {"id": 10}
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._single_ready_rows()
        dry = build_s3_reference_cutover_plan(
            rows[0],
            rows[1],
            rows[2],
            rows[3],
        )

        with patch.object(
            cutover_module,
            "load_s3_reference_cutover_rows",
            return_value=rows,
        ):
            result = run_s3_reference_cutover(
                get_db,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_update_count=1,
                expected_reference_count=1,
                expected_plan_sha256=dry["planSha256"],
            )

        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        self.assertEqual(result["updatedCellCount"], 1)
        self.assertEqual(result["rewrittenReferenceCount"], 1)
        self.assertEqual(result["writesAttempted"], 1)
        self.assertTrue(result["committed"])
        self.assertNotIn("storage.example", str(result))

    @staticmethod
    def _single_ready_rows():
        url = "https://storage.example/uploads/company-1/ready.jpg"
        records = [{
            "source": "company_documents.file_url",
            "recordId": 10,
            "value": url,
            "companyId": 1,
            "projectId": None,
            "dataType": "text",
        }]
        ownership = [{
            "id": 41,
            "file_url": url,
            "storage_key": "uploads/company-1/ready.jpg",
            "company_id": 1,
            "project_id": None,
        }]
        sources = {
            "company_documents.file_url": ("company_documents", "file_url"),
        }
        return records, ownership, sources, {
            "scannedSources": ["company_documents.file_url"],
            "truncatedSources": [],
        }


if __name__ == "__main__":
    unittest.main()
