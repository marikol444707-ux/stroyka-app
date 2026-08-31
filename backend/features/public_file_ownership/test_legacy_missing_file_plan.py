import unittest
from unittest.mock import Mock, patch

from . import legacy_missing_file_plan as plan_module
from .legacy_missing_file_plan import (
    APPLY_CONFIRMATION,
    LegacyMissingFilePlanError,
    build_legacy_missing_file_plan,
    run_legacy_missing_file_plan,
)


class LegacyMissingFilePlanTests(unittest.TestCase):
    def test_missing_scalar_and_json_files_are_planned_without_business_deletes(self):
        report = build_legacy_missing_file_plan(
            records=[
                {
                    "source": "supplier_invoices.photo_url",
                    "recordId": 10,
                    "value": "/uploads/company-1-common-invoices/missing.jpg",
                    "companyId": 1,
                    "dataType": "text",
                },
                {
                    "source": "warehouse_invoices.photo_urls",
                    "recordId": 11,
                    "value": (
                        '["/uploads/company-1-common-invoices/first.jpg",'
                        '"/uploads/company-1-common-invoices/second.jpg"]'
                    ),
                    "companyId": 1,
                    "dataType": "jsonb",
                },
            ],
            ownership_rows=[
                self._missing_registration(41, "missing.jpg"),
                self._missing_registration(42, "first.jpg"),
                self._missing_registration(43, "second.jpg"),
            ],
            projects=[],
            company_ids={1},
            scan={"scannedSources": [
                "supplier_invoices.photo_url",
                "warehouse_invoices.photo_urls",
            ]},
        )

        self.assertTrue(report["readyForCleanup"])
        self.assertEqual(report["summary"]["referenceCount"], 3)
        self.assertEqual(report["summary"]["missingReferenceCount"], 3)
        self.assertEqual(report["summary"]["missingUniqueFileCount"], 3)
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 2)
        self.assertEqual(report["summary"]["businessRecordsToDelete"], 0)
        self.assertEqual(report["summary"]["registryRowsToDelete"], 0)
        self.assertEqual(report["blockers"], [])
        self.assertNotIn("missing.jpg", str(report))
        self.assertNotIn("first.jpg", str(report))

    def test_available_file_is_retained_and_not_planned_for_cleanup(self):
        registration = self._missing_registration(41, "available.jpg")
        registration["storageReady"] = True
        registration.pop("storageReason")

        report = build_legacy_missing_file_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/company-1-common-invoices/available.jpg",
                "companyId": 1,
            }],
            ownership_rows=[registration],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForCleanup"])
        self.assertEqual(report["state"], "clear")
        self.assertEqual(report["summary"]["availableReferenceCount"], 1)
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 0)

    def test_registered_flat_legacy_url_is_accepted_for_missing_cleanup(self):
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/old-flat-photo.jpg",
                "companyId": 1,
            }],
            ownership_rows=[{
                "id": 41,
                "file_url": "/uploads/old-flat-photo.jpg",
                "company_id": 1,
                "project_id": None,
                "context": "legacy_backfill",
                "storageReady": False,
                "storageReason": "local_file_unavailable",
            }],
            projects=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForCleanup"])
        self.assertEqual(report["summary"]["missingReferenceCount"], 1)
        self.assertEqual(report["summary"]["invalidRegistryRows"], 0)
        self.assertEqual(report["blockers"], [])

    def test_embedded_single_legacy_url_is_cleared_from_scalar_photo_field(self):
        url = "/uploads/company-1-common-invoices/missing.jpg"
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "expenses.photo_url",
                "recordId": 10,
                "value": f"legacy-photo:{url}",
                "companyId": 1,
                "ownershipVerified": True,
                "dataType": "text",
            }],
            ownership_rows=[self._missing_registration(41, "missing.jpg")],
            projects=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForCleanup"])
        self.assertEqual(report["summary"]["missingReferenceCount"], 1)
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 1)

    def test_json_scalar_photo_url_is_planned_and_cleared_as_valid_json(self):
        url = "/uploads/company-1-common-invoices/missing.jpg"
        rows = (
            [{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": f'"{url}"',
                "companyId": 1,
                "dataType": "jsonb",
            }],
            [self._missing_registration(41, "missing.jpg")],
            [],
            {1},
            {"scannedSources": ["supplier_invoices.photo_url"]},
        )
        dry = build_legacy_missing_file_plan(*rows)

        self.assertTrue(dry["readyForCleanup"])
        self.assertEqual(dry["summary"]["plannedCellUpdateCount"], 1)

        connection = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = {"id": 10}
        connection.cursor.return_value = cursor

        with patch.object(
            plan_module,
            "load_legacy_reference_cutover_rows",
            return_value=rows,
        ):
            result = run_legacy_missing_file_plan(
                Mock(return_value=connection),
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_update_count=1,
                expected_reference_count=1,
                expected_plan_sha256=dry["planSha256"],
            )

        self.assertEqual(result["updatedCellCount"], 1)
        self.assertEqual(cursor.execute.call_args.args[1][0], '""')

    def test_owner_mismatch_blocks_cleanup(self):
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/company-2-common-invoices/wrong.jpg",
                "companyId": 1,
            }],
            ownership_rows=[{
                **self._missing_registration(41, "wrong.jpg", company_id=2),
                "file_url": "/uploads/company-2-common-invoices/wrong.jpg",
            }],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForCleanup"])
        self.assertIn("reference_owner_mismatch", report["blockers"])
        self.assertEqual(report["summary"]["conflictingReferenceCount"], 1)

    def test_unverified_remote_storage_is_not_treated_as_missing(self):
        registration = self._missing_registration(41, "remote.jpg")
        registration["storageReason"] = "s3_storage_not_verified"

        report = build_legacy_missing_file_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/company-1-common-invoices/remote.jpg",
                "companyId": 1,
            }],
            ownership_rows=[registration],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForCleanup"])
        self.assertIn("file_storage_not_verified", report["blockers"])
        self.assertEqual(report["summary"]["missingReferenceCount"], 0)

    def test_truncated_reference_scan_blocks_cleanup(self):
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "supplier_invoices.photo_url",
                "recordId": 10,
                "value": "/uploads/company-1-common-invoices/missing.jpg",
                "companyId": 1,
            }],
            ownership_rows=[self._missing_registration(41, "missing.jpg")],
            projects=[],
            company_ids={1},
            scan={
                "scannedSources": ["supplier_invoices.photo_url"],
                "truncatedSources": ["supplier_invoices.photo_url"],
            },
        )

        self.assertFalse(report["readyForCleanup"])
        self.assertIn("reference_scan_truncated", report["blockers"])
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 1)

    def test_invalid_photo_collection_blocks_cleanup(self):
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "warehouse_invoices.photo_urls",
                "recordId": 11,
                "value": "not-json /uploads/missing.jpg",
                "companyId": 1,
                "dataType": "text",
            }],
            ownership_rows=[{
                **self._missing_registration(41, "missing.jpg"),
                "file_url": "/uploads/missing.jpg",
            }],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForCleanup"])
        self.assertIn("reference_collection_invalid", report["blockers"])

    def test_duplicate_missing_url_is_removed_from_every_collection_position(self):
        url = "/uploads/company-1-common-invoices/repeated.jpg"
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "warehouse_invoices.photo_urls",
                "recordId": 11,
                "value": f'["{url}","{url}"]',
                "companyId": 1,
                "dataType": "text",
            }],
            ownership_rows=[self._missing_registration(41, "repeated.jpg")],
            projects=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForCleanup"])
        self.assertEqual(report["summary"]["missingReferenceCount"], 2)
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 1)

    def test_absolute_local_url_is_removed_from_photo_collection(self):
        local_url = "/uploads/company-1-common-invoices/missing.jpg"
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "interim_acts.photo_urls",
                "recordId": 1,
                "value": f'["https://stroyka26.pro{local_url}"]',
                "companyId": 1,
                "dataType": "text",
            }],
            ownership_rows=[self._missing_registration(41, "missing.jpg")],
            projects=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForCleanup"])
        self.assertEqual(report["summary"]["missingReferenceCount"], 1)
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 1)

    def test_embedded_single_legacy_url_is_removed_from_collection_item(self):
        local_url = "/uploads/company-1-common-invoices/missing.jpg"
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "interim_acts.photo_urls",
                "recordId": 1,
                "value": f'["Фото: {local_url}"]',
                "companyId": 1,
                "dataType": "text",
            }],
            ownership_rows=[self._missing_registration(41, "missing.jpg")],
            projects=[],
            company_ids={1},
        )

        self.assertTrue(report["readyForCleanup"])
        self.assertEqual(report["summary"]["missingReferenceCount"], 1)
        self.assertEqual(report["summary"]["plannedCellUpdateCount"], 1)

    def test_collection_item_with_multiple_urls_still_blocks_cleanup(self):
        first = "/uploads/company-1-common-invoices/first.jpg"
        second = "/uploads/company-1-common-invoices/second.jpg"
        report = build_legacy_missing_file_plan(
            records=[{
                "source": "interim_acts.photo_urls",
                "recordId": 1,
                "value": f'["first:{first} second:{second}"]',
                "companyId": 1,
                "dataType": "text",
            }],
            ownership_rows=[
                self._missing_registration(41, "first.jpg"),
                self._missing_registration(42, "second.jpg"),
            ],
            projects=[],
            company_ids={1},
        )

        self.assertFalse(report["readyForCleanup"])
        self.assertIn(
            "reference_collection_rewrite_incomplete",
            report["blockers"],
        )

    def test_exact_guarded_apply_clears_only_missing_references(self):
        connection = Mock()
        cursor = Mock()
        cursor.fetchone.side_effect = [{"id": 10}, {"id": 11}]
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._apply_rows()
        dry = build_legacy_missing_file_plan(*rows)

        with patch.object(
            plan_module,
            "load_legacy_reference_cutover_rows",
            return_value=rows,
        ):
            result = run_legacy_missing_file_plan(
                get_db,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_update_count=2,
                expected_reference_count=3,
                expected_plan_sha256=dry["planSha256"],
            )

        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        self.assertEqual(result["updatedCellCount"], 2)
        self.assertEqual(result["removedReferenceCount"], 3)
        self.assertEqual(result["businessRecordsDeleted"], 0)
        self.assertEqual(result["registryRowsDeleted"], 0)
        update_values = [call.args[1][0] for call in cursor.execute.call_args_list]
        self.assertEqual(update_values, ["", "[]"])

    def test_apply_rejects_changed_plan_before_writing(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)
        rows = self._apply_rows()

        with patch.object(
            plan_module,
            "load_legacy_reference_cutover_rows",
            return_value=rows,
        ):
            with self.assertRaisesRegex(
                LegacyMissingFilePlanError,
                "plan_sha256_mismatch",
            ):
                run_legacy_missing_file_plan(
                    get_db,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_update_count=2,
                    expected_reference_count=3,
                    expected_plan_sha256="0" * 64,
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor.execute.assert_not_called()

    def test_runner_is_read_only_and_rolls_back(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        get_db = Mock(return_value=connection)

        with patch.object(
            plan_module,
            "load_legacy_reference_cutover_rows",
            return_value=([], [], [], set(), {
                "scannedSources": [],
                "truncatedSources": [],
            }),
        ):
            report = run_legacy_missing_file_plan(get_db)

        connection.set_session.assert_called_once_with(
            readonly=True,
            autocommit=False,
        )
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)

    @staticmethod
    def _missing_registration(file_id, name, *, company_id=1):
        return {
            "id": file_id,
            "file_url": f"/uploads/company-{company_id}-common-invoices/{name}",
            "company_id": company_id,
            "project_id": None,
            "context": "legacy_backfill",
            "storageReady": False,
            "storageReason": "local_file_unavailable",
        }

    @classmethod
    def _apply_rows(cls):
        scalar = "/uploads/company-1-common-invoices/missing.jpg"
        first = "/uploads/company-1-common-invoices/first.jpg"
        second = "/uploads/company-1-common-invoices/second.jpg"
        return (
            [
                {
                    "source": "supplier_invoices.photo_url",
                    "recordId": 10,
                    "value": scalar,
                    "companyId": 1,
                    "dataType": "text",
                },
                {
                    "source": "warehouse_invoices.photo_urls",
                    "recordId": 11,
                    "value": f'["{first}","{second}"]',
                    "companyId": 1,
                    "dataType": "text",
                },
            ],
            [
                cls._missing_registration(41, "missing.jpg"),
                cls._missing_registration(42, "first.jpg"),
                cls._missing_registration(43, "second.jpg"),
            ],
            [],
            {1},
            {"scannedSources": [
                "supplier_invoices.photo_url",
                "warehouse_invoices.photo_urls",
            ]},
        )


if __name__ == "__main__":
    unittest.main()
