"""Inventory lifecycle and stock conservation through real HTTP/PostgreSQL."""
from decimal import Decimal
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from .test_support import InventoryReconciliationPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class InventoryReconciliationPostgresTests(InventoryReconciliationPostgresSupport, unittest.TestCase):
    def test_snapshot_uses_exact_company_project_stock_and_keeps_zero_and_blank(self):
        zero_id = self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
            VALUES(2,'Synthetic zero','шт',0,%s,'Основная') RETURNING id""", (self.f["project"],))[0][0]
        self.create_inventory()
        view = self.detail("foreman")
        self.assertEqual(view["inventory"]["state"], "draft")
        self.assertEqual(view["inventory"]["status"], "Черновик")
        self.assertTrue(view["canCount"])
        self.assertFalse(view["canDecide"])
        self.assertEqual(len(view["rows"]), 2, "Main stock, foreign-company stock and issued personal stock are excluded")
        row = self.material_row(view)
        self.assertEqual(Decimal(str(row["expected"])), 2)
        self.assertIsNone(row["actual"])
        zero = next(r for r in view["rows"] if r["name"] == "Synthetic zero")
        self.assertEqual(Decimal(str(zero["expected"])), 0)
        self.assertIsNone(zero["actual"])
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE id=%s", (zero_id,)), [(0,)])
        self.assertEqual(self.balance(), dict(issued=2, used=0, returned=0, available=2))

    def test_create_retry_preserves_same_snapshot_and_rejects_uuid_with_changed_body(self):
        result, payload = self.create_inventory()
        before = self.snapshot()
        replay = self.api("foreman", "POST", "/inventory/reconciliation", payload)
        self.assertEqual(replay, result)
        self.assertEqual(self.snapshot(), before)
        self.api("foreman", "POST", "/inventory/reconciliation", {**payload, "notes": "Different request"}, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_blank_is_not_zero_and_every_discrepancy_requires_a_reason(self):
        self.create_inventory()
        row = self.material_row()
        self.command("save", counts=[{"key": row["key"], "actual": ""}])
        self.unchanged_command(self.command_payload("submit"), actor="foreman", expected=400)
        self.command("save", counts=[{"key": row["key"], "actual": "0"}])
        self.assertEqual(Decimal(str(self.material_row()["actual"])), 0)
        self.unchanged_command(self.command_payload("submit"), actor="foreman", expected=400)
        self.command("save", counts=[{"key": row["key"], "actual": "0", "reason": "Empty location verified"}])
        self.command("submit")
        self.assertEqual(self.detail()["inventory"]["state"], "submitted")
        self.assertEqual(self.stock_quantity(), 2, "Submitting facts alone never adjusts stock")

    def test_saving_again_replaces_fact_in_one_snapshot_row_and_stale_save_cannot_overwrite(self):
        self.create_inventory()
        key = self.material_row()["key"]
        stale = self.command_payload("save", counts=[{"key": key, "actual": "0", "reason": "Old draft"}])
        self.command("save", counts=[{"key": key, "actual": "1", "reason": "First count"}])
        self.unchanged_command(stale, actor="foreman")
        self.command("save", counts=[{"key": key, "actual": "1.5", "reason": "Recount"}])
        rows = self.detail()["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(Decimal(str(rows[0]["actual"])), Decimal("1.5"))
        self.assertEqual(Decimal(str(rows[0]["difference"])), Decimal("-0.5"))
        self.assertEqual(self.stock_quantity(), 2)

    def test_count_cannot_forge_snapshot_fields_duplicate_keys_or_nonfinite_quantity(self):
        self.create_inventory()
        key = self.material_row()["key"]
        base = {"key": key, "actual": "1", "reason": "Observed shortage"}
        invalid = [
            [{**base, "expected": 999, "difference": 0, "name": "Forged", "unit": "т"}],
            [base, base], [{**base, "key": "unknown-stock-row"}],
            [{**base, "actual": "NaN"}], [{**base, "actual": "Infinity"}],
            [{**base, "actual": "-1"}], [{**base, "actual": "0.0000001"}],
        ]
        for counts in invalid:
            with self.subTest(counts=counts):
                self.unchanged_command(self.command_payload("save", counts=counts), actor="foreman", expected=400)

    def test_project_approval_adjusts_once_with_history_without_touching_personal_or_finances(self):
        self.create_inventory()
        self.count_and_submit("1.25")
        before_personal = self.balance()
        before_finance = self.sql("SELECT row_to_json(t)::text FROM brigade_contracts t ORDER BY id")
        before_history = self.sql("SELECT COUNT(*) FROM warehouse_history")[0][0]
        result, payload = self.command("approve", actor="director", reason="Verified actual stock")
        self.assertEqual(self.stock_quantity(), 1.25)
        self.assertEqual(self.balance(), before_personal)
        self.assertEqual(self.sql("SELECT row_to_json(t)::text FROM brigade_contracts t ORDER BY id"), before_finance)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM warehouse_history"), [(before_history + 1,)])
        self.assertEqual(self.sql("SELECT before_quantity,after_quantity,stock_id FROM inventory_stock_adjustments"),
                         [(2, Decimal("1.25"), self.stock_id)])
        view = self.detail()
        self.assertEqual(view["inventory"]["state"], "approved")
        self.assertEqual(Decimal(str(self.material_row(view)["expected"])), 2)
        self.assertEqual(Decimal(str(self.material_row(view)["actual"])), Decimal("1.25"))
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.path, payload), result)
        self.assertEqual(self.snapshot(), before)
        self.unchanged_command(self.command_payload("save", counts=[]), actor="foreman")
        self.unchanged_command(self.command_payload("cancel", reason="Undo approved result"))

    def test_changed_stock_rejects_approval_without_losing_submitted_facts(self):
        self.create_inventory()
        self.count_and_submit("1")
        self.api("worker", "POST", "/material-transfers/return", self.payload(1))
        self.assertEqual(self.stock_quantity(), 3)
        self.unchanged_command(self.command_payload("approve", reason="Stale count"))
        self.assertEqual(self.detail()["inventory"]["state"], "submitted")
        self.assertEqual(Decimal(str(self.material_row()["actual"])), 1)

    def test_approval_failure_rolls_back_material_history_and_ledgers_then_retry_succeeds(self):
        self.create_inventory()
        self.count_and_submit("1")
        payload = self.command_payload("approve", reason="Verified shortage")
        self.sql("""CREATE FUNCTION inventory_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic inventory adjustment failure'; END $$""")
        self.sql("""CREATE TRIGGER inventory_test_failure AFTER INSERT ON inventory_stock_adjustments
            FOR EACH ROW EXECUTE FUNCTION inventory_test_failure()""")
        before = self.snapshot()
        try:
            response = self.request("POST", self.path, payload, actor="director")
            self.assertEqual(response.status_code, 500, response.text)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql("DROP TRIGGER inventory_test_failure ON inventory_stock_adjustments")
            self.sql("DROP FUNCTION inventory_test_failure()")
        self.api("director", "POST", self.path, payload)
        self.assertEqual(self.stock_quantity(), 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM inventory_stock_adjustments"), [(1,)])

    def test_main_shortage_requires_exact_explicit_lot_and_untracked_allocation(self):
        invoice, lot = self.seed_receipt_lot(3)
        original_receipt = self.sql("SELECT row_to_json(t)::text FROM warehouse_invoices t WHERE id=%s", (invoice,))
        self.create_inventory(main=True, actor="director")
        key = self.material_row()["key"]
        self.assertEqual(Decimal(str(self.material_row()["untrackedQuantity"])), 2)
        self.count_and_submit("2")
        for allocations, status in (([], 400), ([{"key": key, "untrackedQuantity": 2, "lots": []}], 400),
                                    ([{"key": key, "untrackedQuantity": 3, "lots": []}], 409)):
            with self.subTest(allocations=allocations):
                self.unchanged_command(self.command_payload("approve", reason="Counted main stock",
                    lotDeductions=allocations), expected=status)
        self.command("approve", actor="director", reason="Counted main stock", lotDeductions=[
            {"key": key, "untrackedQuantity": 1, "lots": [{"lotId": lot, "quantity": 2}]}])
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_main WHERE id=%s", (self.main_stock_id,)), [(2,)])
        self.assertEqual(self.sql("SELECT received_quantity,available_quantity FROM warehouse_receipt_lots WHERE id=%s", (lot,)), [(3, 1)])
        self.assertEqual(self.sql("SELECT row_to_json(t)::text FROM warehouse_invoices t WHERE id=%s", (invoice,)), original_receipt)
        self.assertEqual(self.stock_quantity(), 2, "Main warehouse recount cannot adjust project stock")

    def test_main_surplus_is_untracked_adjustment_without_fabricating_receipt_or_lot(self):
        self.create_inventory(main=True, actor="director")
        self.count_and_submit("6.5")
        self.command("approve", actor="director", reason="Found surplus")
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_main WHERE id=%s", (self.main_stock_id,)), [(6.5,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM warehouse_invoices"), [(0,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM warehouse_receipt_lots"), [(0,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM inventory_stock_adjustments"), [(1,)])

    def test_tool_discrepancy_is_recorded_without_custody_or_fine_mutation(self):
        self.create_inventory(main=True, actor="director")
        view = self.detail()
        tools = [r for r in view["rows"] if r["kind"] == "tool"]
        self.assertEqual(len(tools), 1)
        before = [(table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
                  for table in ("tools", "tool_history", "tool_custody_events", "tool_incidents", "tool_fine_allocations")]
        counts = [{"key": r["key"], **({"condition": "missing", "reason": "Tool not found during count"}
            if r["kind"] == "tool" else {"actual": r["expected"]})} for r in view["rows"]]
        self.command("save", counts=counts)
        self.command("submit")
        self.command("approve", actor="director", reason="Refer missing tool to custody investigation")
        after = [(table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1")) for table, _ in before]
        self.assertEqual(after, before)
        self.assertEqual(next(r for r in self.detail()["rows"] if r["kind"] == "tool")["condition"], "missing")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM inventory_stock_adjustments"), [(0,)])

    def test_changed_tool_version_makes_main_snapshot_stale(self):
        self.create_inventory(main=True, actor="director")
        self.count_and_submit("5")
        self.issue_tool()
        self.unchanged_command(self.command_payload("approve", reason="Old tool presence"))

    def test_director_can_return_for_recount_and_cancel_with_reason_without_stock_changes(self):
        self.create_inventory()
        self.count_and_submit("1")
        self.unchanged_command(self.command_payload("return", reason=""), expected=400)
        self.command("return", actor="director", reason="Count again with second observer")
        self.assertEqual(self.detail()["inventory"]["state"], "draft")
        self.assertEqual(Decimal(str(self.material_row()["actual"])), 1)
        self.command("cancel", actor="director", reason="New inventory required")
        self.assertEqual(self.detail()["inventory"]["state"], "cancelled")
        self.assertEqual(self.stock_quantity(), 2)
        self.unchanged_command(self.command_payload("save", counts=[]), actor="foreman")

    def test_roles_foreign_company_and_secondary_context_cannot_decide_or_read_private_count(self):
        self.create_inventory()
        self.count_and_submit("1")
        for actor in ("foreman", "worker", "accountant"):
            with self.subTest(actor=actor):
                self.unchanged_command(self.command_payload("approve", reason="No director authority"), actor=actor, expected=403)
        before = self.snapshot()
        self.api("stranger", "GET", self.path, expected=404)
        self.api("stranger", "POST", "/inventory/reconciliation", {
            "requestId": str(uuid4()), "projectId": self.f["projectId"]}, expected=404)
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default)
            VALUES(%s,3,1,'бухгалтер',TRUE,FALSE)""", (self.f["users"]["director"]["id"],))
        self.addCleanup(self.sql, "DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3",
                        (self.f["users"]["director"]["id"],))
        self.api("director", "POST", "/inventory/reconciliation", {"requestId": str(uuid4()), "projectId": None},
                 expected=403, **{"X-Company-Id": "3", "X-Company-Mode": "company"})
        self.assertEqual(self.snapshot(), before)

    def test_new_inventory_legacy_writes_are_blocked_even_when_feature_disabled(self):
        self.create_inventory()
        legacy = f"/inventory/{self.inventory_id}"
        item = {"inventoryId": self.inventory_id, "materialName": self.f["materialName"], "unit": self.f["unit"],
                "expected": 999, "actual": 8, "difference": 0}
        before = self.snapshot()
        for flag in ("1", "0"):
            with self.subTest(flag=flag), patch.dict(os.environ, {"INVENTORY_RECONCILIATION_ENABLED": flag}):
                for method, path, payload in (("PUT", legacy, {"status": "Fake"}), ("DELETE", legacy, None),
                                               ("POST", legacy + "/items", item), ("POST", "/inventory-items", item)):
                    self.api("director", method, path, payload, expected=409)
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
