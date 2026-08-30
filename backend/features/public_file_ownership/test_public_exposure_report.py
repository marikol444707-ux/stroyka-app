import unittest
from unittest.mock import Mock, patch

from . import public_exposure_report as exposure_module
from .public_exposure_report import (
    build_public_exposure_report,
    extract_local_upload_urls,
    load_public_exposure_rows,
    run_public_exposure_report,
)


class PublicUploadExposureReportTests(unittest.TestCase):
    def test_extracts_nested_local_upload_urls_without_query_strings(self):
        value = {
            "photo": "/uploads/company-1/photo.jpg?download=1",
            "attachments": [
                {"url": "/uploads/company-1/document.pdf"},
                "/tenant-files/31/content",
            ],
        }

        self.assertEqual(
            extract_local_upload_urls(value),
            [
                "/uploads/company-1/photo.jpg",
                "/uploads/company-1/document.pdf",
            ],
        )

    def test_extracts_an_exact_legacy_url_containing_spaces(self):
        self.assertEqual(
            extract_local_upload_urls("/uploads/company-1/site photo.jpg"),
            ["/uploads/company-1/site%20photo.jpg"],
        )

    def test_unregistered_reference_blocks_cutover_without_exposing_url(self):
        report = build_public_exposure_report(
            ownership_rows=[
                {
                    "id": 31,
                    "file_url": "/uploads/company-1/known.pdf",
                    "storage_key": None,
                }
            ],
            reference_values=[
                {
                    "table": "supplier_invoices",
                    "column": "file_url",
                    "value": "/uploads/company-1/known.pdf",
                },
                {
                    "table": "warehouse_invoices",
                    "column": "photo_urls",
                    "value": '["/uploads/company-1/unregistered.jpg"]',
                },
            ],
            public_mount_enabled=True,
            storage_backend="local",
            s3_acl="private",
        )

        self.assertFalse(report["dataReadyForProtectedDelivery"])
        self.assertFalse(report["publicExposureClosed"])
        self.assertEqual(report["summary"]["unregisteredUniqueUrls"], 1)
        self.assertIn("unregistered_local_upload_references", report["blockers"])
        self.assertIn("public_uploads_mount_enabled", report["blockers"])
        preview = report["unregisteredPreview"][0]
        self.assertEqual(preview["sources"], ["warehouse_invoices.photo_urls"])
        self.assertEqual(len(preview["urlSha256"]), 64)
        self.assertNotIn("unregistered.jpg", str(report))
        self.assertNotIn("known.pdf", str(report))

    def test_clean_data_can_be_ready_while_public_runtime_remains_open(self):
        report = build_public_exposure_report(
            ownership_rows=[
                {
                    "id": 31,
                    "file_url": "/uploads/company-1/known.pdf",
                    "storage_key": None,
                }
            ],
            reference_values=[
                {
                    "table": "supplier_invoices",
                    "column": "file_url",
                    "value": "/uploads/company-1/known.pdf",
                }
            ],
            public_mount_enabled=True,
            storage_backend="local",
            s3_acl="private",
        )

        self.assertTrue(report["dataReadyForProtectedDelivery"])
        self.assertFalse(report["publicExposureClosed"])
        self.assertEqual(report["blockers"], ["public_uploads_mount_enabled"])

    def test_duplicate_and_malformed_registry_rows_block_data_readiness(self):
        report = build_public_exposure_report(
            ownership_rows=[
                {"id": 31, "file_url": "/uploads/shared.pdf", "storage_key": None},
                {"id": 32, "file_url": "/uploads/shared.pdf", "storage_key": None},
                {"id": 33, "file_url": "/uploads/../secret", "storage_key": None},
            ],
            reference_values=[],
            public_mount_enabled=False,
            storage_backend="local",
            s3_acl="private",
        )

        self.assertFalse(report["dataReadyForProtectedDelivery"])
        self.assertEqual(report["summary"]["duplicateRegisteredLocalUrls"], 1)
        self.assertEqual(report["summary"]["invalidLocalRegistryRows"], 1)
        self.assertIn("duplicate_local_upload_registry", report["blockers"])
        self.assertIn("invalid_local_upload_registry", report["blockers"])

    def test_public_s3_acl_is_a_runtime_blocker_when_s3_is_enabled(self):
        report = build_public_exposure_report(
            ownership_rows=[],
            reference_values=[],
            public_mount_enabled=False,
            storage_backend="s3",
            s3_acl="public-read",
        )

        self.assertTrue(report["dataReadyForProtectedDelivery"])
        self.assertFalse(report["publicExposureClosed"])
        self.assertIn("s3_objects_may_be_public", report["blockers"])

    def test_unverified_owner_scope_blocks_protected_delivery(self):
        report = build_public_exposure_report(
            ownership_rows=[],
            reference_values=[],
            public_mount_enabled=False,
            storage_backend="local",
            s3_acl="private",
            ownership_scope_ready=False,
            ownership_scope_summary={"unresolved": 1, "mismatched": 0},
        )

        self.assertFalse(report["dataReadyForProtectedDelivery"])
        self.assertIn("unverified_file_ownership_scope", report["blockers"])
        self.assertEqual(report["ownershipScope"]["unresolved"], 1)

    def test_truncated_reference_scan_cannot_claim_readiness(self):
        report = build_public_exposure_report(
            ownership_rows=[],
            reference_values=[],
            public_mount_enabled=False,
            storage_backend="local",
            s3_acl="private",
            scan_truncated_sources=["warehouse_invoices.photo_urls"],
        )

        self.assertFalse(report["dataReadyForProtectedDelivery"])
        self.assertIn("reference_scan_truncated", report["blockers"])
        self.assertEqual(
            report["scan"]["truncatedSources"],
            ["warehouse_invoices.photo_urls"],
        )

    def test_loader_scans_url_columns_but_not_generic_payload_or_password_columns(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [{"id": 31, "company_id": 1, "project_id": None,
              "file_url": "/uploads/company-1/known.pdf", "storage_key": ""}],
            [
                {"table_name": "warehouse_invoices", "column_name": "photo_urls",
                 "data_type": "text"},
                {"table_name": "api_errors", "column_name": "payload_json",
                 "data_type": "jsonb"},
                {"table_name": "users", "column_name": "password_hash",
                 "data_type": "character varying"},
            ],
            [{"value": '["/uploads/company-1/known.pdf"]', "occurrences": 2}],
            [{"id": 1}],
            [],
            [],
            [{"id": 31, "company_id": 1, "project_id": None}],
            [],
        ]

        ownership, references, scope_rows, scan = load_public_exposure_rows(cursor)

        self.assertEqual(len(ownership), 1)
        self.assertEqual(references, [{
            "table": "warehouse_invoices",
            "column": "photo_urls",
            "value": '["/uploads/company-1/known.pdf"]',
            "occurrences": 2,
        }])
        self.assertEqual(scope_rows["companies"], [{"id": 1}])
        self.assertEqual(scan["truncatedSources"], [])
        self.assertEqual(cursor.execute.call_count, 8)

    def test_runner_is_read_only_rolls_back_and_reports_no_writes(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)

        with patch.object(
            exposure_module,
            "load_public_exposure_rows",
            return_value=([], [], {
                "companies": [],
                "projects": [],
                "crm_leads": [],
                "file_ownership": [],
                "public_lead_uploads": [],
            }, {"scannedSources": [], "truncatedSources": []}),
        ):
            report = run_public_exposure_report(
                get_db,
                public_mount_enabled=True,
                storage_backend="local",
                s3_acl="private",
            )

        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        connection.rollback.assert_called_once_with()
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
