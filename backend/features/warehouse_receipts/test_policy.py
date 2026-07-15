import unittest

from .policy import (
    WarehouseReceiptPolicyError,
    resolve_warehouse_receipt_policy,
    warehouse_invoice_accounting_required,
)


class WarehouseReceiptPolicyTests(unittest.TestCase):
    def test_director_can_receive_main_stock_without_supplier_or_accounting(self):
        policy = resolve_warehouse_receipt_policy(
            {"inventoryOnly": True, "warehouseTarget": "main"},
            target_project="",
            role="директор",
        )

        self.assertTrue(policy["inventoryOnly"])
        self.assertFalse(policy["accountingRequired"])
        self.assertEqual(policy["selectedAction"], "receive_stock_without_supplier")

    def test_deputy_can_receive_main_stock_without_supplier(self):
        policy = resolve_warehouse_receipt_policy(
            {"inventoryOnly": True},
            target_project="",
            role="зам_директора",
        )

        self.assertTrue(policy["inventoryOnly"])

    def test_storekeeper_cannot_use_supplierless_main_receipt(self):
        with self.assertRaisesRegex(WarehouseReceiptPolicyError, "директору или заместителю") as error:
            resolve_warehouse_receipt_policy(
                {"inventoryOnly": True},
                target_project="",
                role="кладовщик",
            )

        self.assertEqual(error.exception.status_code, 403)

    def test_supplierless_main_receipt_requires_explicit_inventory_mode(self):
        with self.assertRaisesRegex(WarehouseReceiptPolicyError, "Без поставщика и оплаты"):
            resolve_warehouse_receipt_policy(
                {},
                target_project="",
                role="директор",
            )

    def test_inventory_mode_rejects_supplier_identity(self):
        with self.assertRaisesRegex(WarehouseReceiptPolicyError, "нельзя указывать поставщика"):
            resolve_warehouse_receipt_policy(
                {"inventoryOnly": True, "supplierName": "ООО Поставка"},
                target_project="",
                role="директор",
            )

    def test_inventory_mode_rejects_supplier_invoice_link(self):
        with self.assertRaisesRegex(WarehouseReceiptPolicyError, "документ к оплате"):
            resolve_warehouse_receipt_policy(
                {"inventoryOnly": True, "supplierInvoiceId": 15},
                target_project="",
                role="директор",
            )

    def test_inventory_mode_is_only_for_main_warehouse(self):
        with self.assertRaisesRegex(WarehouseReceiptPolicyError, "только для основного склада"):
            resolve_warehouse_receipt_policy(
                {"inventoryOnly": True},
                target_project="Объект 1",
                role="директор",
            )

    def test_inventory_mode_rejects_object_warehouse_target_without_project(self):
        with self.assertRaisesRegex(WarehouseReceiptPolicyError, "только для основного склада"):
            resolve_warehouse_receipt_policy(
                {"inventoryOnly": True, "warehouseTarget": "object"},
                target_project="",
                role="директор",
            )

    def test_supplier_document_keeps_accounting_chain(self):
        policy = resolve_warehouse_receipt_policy(
            {"supplierId": 15, "supplierName": "ООО Поставка"},
            target_project="",
            role="кладовщик",
        )

        self.assertFalse(policy["inventoryOnly"])
        self.assertTrue(policy["accountingRequired"])
        self.assertEqual(policy["selectedAction"], "receive_to_warehouse")

    def test_linked_supplier_invoice_is_valid_accounting_identity(self):
        policy = resolve_warehouse_receipt_policy(
            {"supplierInvoiceId": 15, "warehouseTarget": "main"},
            target_project="",
            role="бухгалтер",
        )

        self.assertTrue(policy["hasSupplier"])
        self.assertTrue(policy["accountingRequired"])

    def test_legacy_main_receipt_without_supplier_is_not_payable_even_if_bad_link_exists(self):
        self.assertFalse(warehouse_invoice_accounting_required({
            "location": "Основной склад",
            "warehouse_target": "main",
            "supplier_id": None,
            "supplier_name": "",
            "supplier_invoice_id": 15,
        }))

    def test_explicit_inventory_action_wins_over_stale_supplier_text(self):
        self.assertFalse(warehouse_invoice_accounting_required({
            "warehouse_target": "main",
            "selected_action": "receive_stock_without_supplier",
            "supplier_name": "Старое ошибочное значение",
        }))


if __name__ == "__main__":
    unittest.main()
