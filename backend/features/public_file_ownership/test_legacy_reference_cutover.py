import unittest
from unittest.mock import Mock, patch

from . import legacy_reference_cutover as cutover_module
from .legacy_reference_cutover import (
    APPLY_CONFIRMATION,
    LegacyReferenceCutoverError,
    build_legacy_reference_cutover_plan,
    run_legacy_reference_cutover,
)


class LegacyReferenceCutoverTests(unittest.TestCase):
    def test_rewrite_handles_spaced_scalar_and_nested_json_urls(self):
        spaced = "/uploads/company-1-common-invoices/site%20photo.jpg"
        nested = "/uploads/company-1-common-invoices/nested.pdf"
        replacements = {
            spaced: "/tenant-files/41/content",
            nested: "/tenant-files/42/content",
        }

        rewritten_scalar, scalar_count = cutover_module._rewrite_value(
            "/uploads/company-1-common-invoices/site photo.jpg",
            replacements,
        )
        rewritten_json, json_count = cutover_module._rewrite_value(
            '{"items":[{"url":"/uploads/company-1-common-invoices/nested.pdf"}]}',
            replacements,
        )

        self.assertEqual(rewritten_scalar, "/tenant-files/41/content")
        self.assertEqual(scalar_count, 1)
        self.assertEqual(
            rewritten_json,
            '{"items":[{"url":"/tenant-files/42/content"}]}',
        )
        self.assertEqual(json_count, 1)

    def test_registered_json_references_become_protected_urls(self):
        report = build_legacy_reference_cutover_plan(
            records=[{
                "source": "warehouse_invoices.photo_urls",
                "recordId": 10,
                "value": (
                    '["/uploads/company-1-common-invoices/invoices/first.jpg", '
                    '"/uploads/company-1-common-invoices/invoices/second.jpg"]'
                ),
                "companyId": 1,
            }],
            ownership_rows=[
                {
                    "id": 41,
                    "file_url": "/uploads/company-1-common-invoices/invoices/first.jpg",
                    "company_id": 1,
                    "project_id": None,
                    "context": "legacy_backfill",
                },
                {
                    "id": 42,
                    "file_url": "/uploads/company-1-common-invoices/invoices/second.jpg",
                    "company_id": 1,
                    "project_id": None,
                    "context": "legacy_backfill",
                },
            ],
            projects=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["referenceCount"], 2)
        self.assertEqual(report["summary"]["cellUpdateCount"], 1)
        self.assertEqual(report["summary"]["uniqueFileCount"], 2)
        self.assertEqual(report["summary"]["registryContextUpdateCount"], 2)
        self.assertEqual(report["blockers"], [])
        self.assertNotIn("first.jpg", str(report))
        self.assertNotIn("second.jpg", str(report))

    def test_missing_registration_blocks_cutover(self):
        report = build_legacy_reference_cutover_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/missing.jpg",
                "companyId": 1,
            }],
            ownership_rows=[],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["unresolvedReferences"], 1)
        self.assertIn("file_registration_missing", report["blockers"])

    def test_cross_company_registration_blocks_cutover(self):
        report = build_legacy_reference_cutover_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/company-2-common-invoices/invoices/wrong-owner.jpg",
                "companyId": 1,
            }],
            ownership_rows=[{
                "id": 41,
                "file_url": "/uploads/company-2-common-invoices/invoices/wrong-owner.jpg",
                "company_id": 2,
                "project_id": None,
                "context": "invoices",
            }],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["conflictingReferences"], 1)
        self.assertIn("reference_owner_mismatch", report["blockers"])

    def test_file_outside_registered_tenant_namespace_blocks_cutover(self):
        report = build_legacy_reference_cutover_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/legacy/unscoped.jpg",
                "companyId": 1,
            }],
            ownership_rows=[{
                "id": 41,
                "file_url": "/uploads/legacy/unscoped.jpg",
                "company_id": 1,
                "project_id": None,
                "context": "legacy_backfill",
            }],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["invalidStorageRows"], 1)
        self.assertIn("invalid_file_storage_namespace", report["blockers"])

    def test_missing_physical_file_blocks_cutover(self):
        rows = self._single_ready_rows()
        rows[1][0]["storageReady"] = False
        rows[1][0]["storageReason"] = "local_file_missing"

        report = build_legacy_reference_cutover_plan(*rows)

        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["summary"]["unavailableStorageRows"], 1)
        self.assertIn("file_storage_unavailable", report["blockers"])

    def test_unreferenced_invalid_registration_does_not_expand_cutover_scope(self):
        rows = self._single_ready_rows()
        rows[1].append({
            "id": 99,
            "file_url": "/uploads/legacy/unrelated.jpg",
            "company_id": 1,
            "project_id": None,
            "context": "legacy_backfill",
            "storageReady": False,
        })

        report = build_legacy_reference_cutover_plan(*rows)

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["uniqueFileCount"], 1)
        self.assertEqual(report["summary"]["unavailableStorageRows"], 0)
        self.assertEqual(report["summary"]["registryContextUpdateCount"], 1)

    def test_apply_rejects_changed_plan_before_writing(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._single_ready_rows()

        with patch.object(
            cutover_module,
            "load_legacy_reference_cutover_rows",
            return_value=rows,
        ):
            with self.assertRaisesRegex(
                LegacyReferenceCutoverError,
                "plan_sha256_mismatch",
            ):
                run_legacy_reference_cutover(
                    get_db,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_update_count=1,
                    expected_reference_count=1,
                    expected_context_update_count=1,
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
        dry = build_legacy_reference_cutover_plan(*rows)

        with patch.object(
            cutover_module,
            "load_legacy_reference_cutover_rows",
            return_value=rows,
        ):
            result = run_legacy_reference_cutover(
                get_db,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_update_count=1,
                expected_reference_count=1,
                expected_context_update_count=1,
                expected_plan_sha256=dry["planSha256"],
            )

        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        self.assertEqual(result["updatedCellCount"], 1)
        self.assertEqual(result["rewrittenReferenceCount"], 1)
        self.assertEqual(result["updatedRegistryContextCount"], 1)
        self.assertEqual(result["writesAttempted"], 2)
        self.assertTrue(result["committed"])
        self.assertNotIn("ready.jpg", str(result))

    @staticmethod
    def _single_ready_rows():
        records = [{
            "source": "supplier_invoices.photo_url",
            "recordId": 10,
            "value": "/uploads/company-1-common-invoices/invoices/ready.jpg",
            "companyId": 1,
            "dataType": "text",
        }]
        ownership = [{
            "id": 41,
            "file_url": "/uploads/company-1-common-invoices/invoices/ready.jpg",
            "company_id": 1,
            "project_id": None,
            "context": "legacy_backfill",
        }]
        return records, ownership, [], {1}, {
            "scannedSources": ["supplier_invoices.photo_url"],
        }


if __name__ == "__main__":
    unittest.main()
