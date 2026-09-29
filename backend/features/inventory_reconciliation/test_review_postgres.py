"""Independent HTTP regressions for inventory identity and stock conservation."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

from .test_support import InventoryReconciliationPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class InventoryReviewPostgresTests(InventoryReconciliationPostgresSupport, unittest.TestCase):
    def test_invalid_inventory_ids_never_route_to_creation(self):
        before = self.snapshot()
        for inventory_id in (0, -1, 2147483648):
            for method in ("GET", "POST"):
                with self.subTest(inventory_id=inventory_id, method=method):
                    payload = {"requestId": str(uuid4()), "projectId": None} if method == "POST" else None
                    self.api("director", method, f"/inventory/{inventory_id}/reconciliation", payload, expected=400)
                    self.assertEqual(self.snapshot(), before)

    def test_main_lot_shortage_blocks_receipt_cancellation_and_further_overissue(self):
        invoice, lot = self.seed_receipt_lot(3)
        self.create_inventory(main=True, actor="director")
        key = self.material_row()["key"]
        self.count_and_submit("2")
        self.command("approve", actor="director", reason="Verified physical shortage", lotDeductions=[
            {"key": key, "untrackedQuantity": "1", "lots": [{"lotId": lot, "quantity": "2"}]}])
        before = self.snapshot()
        self.api("director", "DELETE", f"/warehouse-invoices/{invoice}", expected=409)
        self.assertEqual(self.snapshot(), before)
        with patch.dict(os.environ, {"WAREHOUSE_DISTRIBUTION_ENABLED": "1"}):
            self.api("director", "POST", "/warehouse-distributions", {
                "companyId": 2, "requestId": str(uuid4()), "reason": "Cannot reuse inventory shortage",
                "rows": [{"lotId": lot, "projectId": self.f["projectId"], "quantity": "2"}],
            }, expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql("SELECT available_quantity FROM warehouse_receipt_lots WHERE id=%s", (lot,)),
                         [(Decimal("1"),)])
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_main WHERE id=%s", (self.main_stock_id,)), [(2,)])

    def test_old_approval_replay_does_not_overwrite_a_later_inventory_adjustment(self):
        self.create_inventory()
        first_path = self.path
        self.count_and_submit("1")
        result, payload = self.command("approve", actor="director", reason="First verified count")
        self.create_inventory()
        self.count_and_submit("3")
        self.command("approve", actor="director", reason="Later verified count")
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", first_path, payload), result)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stock_quantity(), 3)
        self.assertEqual(self.sql("SELECT count(*) FROM inventory_stock_adjustments"), [(2,)])

    def test_competing_approvals_for_one_stock_snapshot_apply_exactly_once(self):
        requests = []
        for actual in ("1", "0"):
            self.create_inventory()
            self.count_and_submit(actual)
            requests.append((self.path, self.command_payload("approve", reason="Competing physical count")))
        barrier = Barrier(2)

        def approve(request):
            barrier.wait(timeout=10)
            return self.request("POST", request[0], request[1], actor="director")

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(approve, requests))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409],
                         [response.text for response in responses])
        self.assertEqual(self.sql("SELECT count(*) FROM inventory_stock_adjustments"), [(1,)])
        self.assertEqual(self.sql("SELECT state,count(*) FROM inventory_reconciliations GROUP BY state ORDER BY state"),
                         [("approved", 1), ("submitted", 1)])
        self.assertIn(self.stock_quantity(), (0, 1))


if __name__ == "__main__":
    unittest.main()
