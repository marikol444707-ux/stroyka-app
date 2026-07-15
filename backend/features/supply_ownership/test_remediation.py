import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import Mock, patch

from . import remediation as remediation_module
from .remediation import (
    APPLY_CONFIRMATION,
    EXPECTED_SOURCE_SHA256,
    _plan_sha256,
    build_cleanup_plan,
    main,
    run_remediation,
)


def production_rows():
    recipients = [
        (1, 7, None), (2, 8, None), (3, 9, None), (5, 11, None),
        (817, 823, None), (819, 825, 30), (820, 826, None),
        (821, 827, None), (823, 829, 32), (825, 831, None),
        (827, 833, 34), (829, 835, None), (831, 837, 36),
        (833, 839, None), (835, 841, 38), (837, 843, None),
        (839, 845, None),
    ]
    offers = [(6, 5), (9, 8), (11, 9), (13, 11), (17, 825), (22, 829), (27, 833), (32, 837)]
    rows = {
        "orphan_recipients": [
            {"id": row_id, "company_id": 1, "request_id": request_id, "max_outbox_id": outbox_id}
            for row_id, request_id, outbox_id in recipients
        ],
        "orphan_offers": [
            {"id": row_id, "company_id": 1, "request_id": request_id}
            for row_id, request_id in offers
        ],
        "supplier_offer_events": [],
        "supplier_invoices": [],
        "supply_deliveries": [],
        "supply_claims": [],
        "supply_history": [],
        "warehouse_invoices": [],
        "messenger_outbox": [
            {
                "id": row_id,
                "company_id": None,
                "request_id": request_id,
                "owner_scope": "legacy",
                "status": "failed",
            }
            for row_id, request_id in ((30, 825), (32, 829), (34, 833), (36, 837), (38, 841))
        ],
    }
    return rows


class SupplyOrphanRemediationTests(unittest.TestCase):
    def test_exact_source_and_legacy_outbox_build_ready_plan(self):
        plan = build_cleanup_plan(production_rows())

        self.assertTrue(plan["readyForCleanup"])
        self.assertEqual(plan["sourceSha256"], EXPECTED_SOURCE_SHA256)
        self.assertEqual(plan["deleteCount"], 25)
        self.assertEqual(plan["deleteByTable"], {
            "supplier_offers": 8,
            "supply_request_recipients": 17,
        })
        self.assertEqual(plan["preservedLegacyOutboxIds"], [30, 32, 34, 36, 38])
        self.assertTrue(plan["legacyOutboxStateVerified"])
        self.assertEqual(plan["blockingReferences"], [])

    def test_changed_source_set_fails_closed(self):
        rows = production_rows()
        rows["orphan_offers"].pop()

        plan = build_cleanup_plan(rows)

        self.assertFalse(plan["readyForCleanup"])
        self.assertIn("source_set_changed", plan["blockers"])

    def test_new_business_reference_blocks_whole_plan(self):
        rows = production_rows()
        rows["supplier_invoices"] = [
            {"id": 901, "company_id": 1, "request_id": 8, "offer_id": 9},
        ]

        plan = build_cleanup_plan(rows)

        self.assertFalse(plan["readyForCleanup"])
        self.assertEqual(plan["blockingReferences"], [
            {"table": "supplier_invoices", "recordIds": [901]},
        ])

    def test_missing_legacy_outbox_blocks_cleanup(self):
        rows = production_rows()
        rows["messenger_outbox"] = rows["messenger_outbox"][:-1]

        plan = build_cleanup_plan(rows)

        self.assertFalse(plan["readyForCleanup"])
        self.assertIn("legacy_outbox_set_changed", plan["blockers"])

    def test_non_terminal_legacy_outbox_blocks_cleanup(self):
        rows = production_rows()
        rows["messenger_outbox"][0]["status"] = "queued"

        plan = build_cleanup_plan(rows)

        self.assertFalse(plan["readyForCleanup"])
        self.assertIn("legacy_outbox_state_changed", plan["blockers"])

    def test_dry_run_is_read_only(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        ready = build_cleanup_plan(production_rows())

        with patch.object(
            remediation_module,
            "collect_cleanup_plan",
            return_value=ready,
        ):
            result = run_remediation(connection)

        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        connection.rollback.assert_called_once_with()
        self.assertEqual(result["writesAttempted"], 0)
        self.assertTrue(result["rolledBack"])

    def test_apply_requires_matching_count_and_sha(self):
        connection = Mock()
        ready = build_cleanup_plan(production_rows())

        with patch.object(
            remediation_module,
            "collect_cleanup_plan",
            return_value=ready,
        ):
            with self.assertRaisesRegex(RuntimeError, "Expected 24"):
                run_remediation(
                    connection,
                    apply=True,
                    expected_delete_count=24,
                    expected_plan_sha256=ready["planSha256"],
                )
        connection.rollback.assert_called()

    def test_apply_deletes_exact_rows_and_preserves_outbox(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        ready = build_cleanup_plan(production_rows())

        with patch.object(
            remediation_module,
            "collect_cleanup_plan",
            return_value=ready,
        ), patch.object(
            remediation_module,
            "_delete_planned_rows",
            return_value={"supplier_offers": 8, "supply_request_recipients": 17},
        ), patch.object(
            remediation_module,
            "_postcheck",
            return_value={"remainingPlannedRows": 0, "preservedLegacyOutboxIds": [30, 32, 34, 36, 38]},
        ):
            result = run_remediation(
                connection,
                apply=True,
                expected_delete_count=25,
                expected_plan_sha256=ready["planSha256"],
            )

        connection.commit.assert_called_once_with()
        self.assertEqual(result["deleted"], 25)
        self.assertEqual(result["preservedLegacyOutboxIds"], [30, 32, 34, 36, 38])

    def test_partial_delete_rolls_back_whole_plan(self):
        connection = Mock()
        cursor = Mock()
        connection.cursor.return_value = cursor
        ready = build_cleanup_plan(production_rows())

        with patch.object(
            remediation_module,
            "collect_cleanup_plan",
            return_value=ready,
        ), patch.object(
            remediation_module,
            "_delete_planned_rows",
            return_value={"supplier_offers": 8, "supply_request_recipients": 16},
        ):
            result = run_remediation(
                connection,
                apply=True,
                expected_delete_count=25,
                expected_plan_sha256=ready["planSha256"],
            )

        self.assertEqual(result["failureReason"], "write_conflict")
        self.assertTrue(result["rolledBack"])
        connection.commit.assert_not_called()

    def test_cli_rejects_apply_without_explicit_confirmation(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main([
                "--apply",
                "--expected-delete-count", "25",
                "--expected-plan-sha256", _plan_sha256([]),
            ])
        self.assertEqual(APPLY_CONFIRMATION, "APPLY_SUPPLY_ORPHAN_CLEANUP")


if __name__ == "__main__":
    unittest.main()
