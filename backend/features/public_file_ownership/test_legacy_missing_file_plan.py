import unittest
from unittest.mock import Mock, patch

from . import legacy_missing_file_plan as plan_module
from .legacy_missing_file_plan import (
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


if __name__ == "__main__":
    unittest.main()
