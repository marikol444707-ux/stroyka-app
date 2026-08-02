import unittest

from .routes import (
    _normalize_unit,
    build_packaging_correction_preview,
    build_packaging_dependency_check,
    build_packaging_traceability_status,
    build_packaging_review_snapshot,
    packaging_review_row,
    normalize_review_decision,
    normalize_invoice_packaging_items,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchall(self):
        return self.rows


class MaterialPackagingRulesTest(unittest.TestCase):
    def test_confirmed_cable_rule_converts_to_base_meters(self):
        cursor = FakeCursor([{
            "id": 7, "company_id": 1, "supplier_id": 3,
            "material_key": "кабель tokov ввг пнг a ls 3x2 5", "material_name": "Кабель TOKOV ВВГ-Пнг(A)-LS 3x2.5",
            "document_unit": "уп", "base_unit": "м", "content_quantity": 100,
            "status": "confirmed", "note": "", "created_by": "", "created_at": None, "updated_at": None,
        }])
        rows = normalize_invoice_packaging_items(cursor, [{
            "name": "Кабель TOKOV ВВГ-Пнг(A)-LS 3x2.5", "quantity": 25, "unit": "уп", "price": 1200, "total": 30000,
        }], company_id=1, supplier_id=3)
        item = rows[0]
        self.assertEqual(item["documentQuantity"], 25)
        self.assertEqual(item["documentUnit"], "уп")
        self.assertEqual(item["quantity"], 2500)
        self.assertEqual(item["unit"], "м")
        self.assertEqual(item["price"], 12)
        self.assertEqual(item["total"], 30000)
        self.assertEqual(item["conversionStatus"], "confirmed")

    def test_unknown_packaging_stays_in_document_unit_and_requires_review(self):
        cursor = FakeCursor([])
        source = {"name": "Арматура A500C", "quantity": 4, "unit": "пач", "price": 50000}
        item = normalize_invoice_packaging_items(cursor, [source], company_id=1)[0]
        self.assertEqual(item["quantity"], 4)
        self.assertEqual(item["unit"], "пач")
        self.assertEqual(item["conversionStatus"], "needs_review")
        self.assertEqual(item["conversionReviewReason"], "Не найдено подтвержденное правило содержимого упаковки")

    def test_mixture_and_liquid_containers_require_confirmation(self):
        cursor = FakeCursor([])
        rows = normalize_invoice_packaging_items(cursor, [
            {"name": "Смесь штукатурная", "quantity": 30, "unit": "мешок", "price": 450},
            {"name": "Грунтовка", "quantity": 2, "unit": "канистра", "price": 1800},
        ], company_id=1)
        self.assertEqual([item["conversionStatus"] for item in rows], ["needs_review", "needs_review"])
        self.assertEqual([item["unit"] for item in rows], ["мешок", "канистра"])

    def test_metal_package_normalizes_tonnes_and_profile_rule_normalizes_linear_meters(self):
        cursor = FakeCursor([
            {
                "id": 10, "company_id": 1, "supplier_id": None,
                "material_key": "арматура a500c", "material_name": "Арматура A500C",
                "document_unit": "пачка", "base_unit": "т", "content_quantity": 1.5,
                "status": "confirmed", "note": "", "created_by": "", "created_at": None, "updated_at": None,
            },
            {
                "id": 11, "company_id": 1, "supplier_id": None,
                "material_key": "профиль направляющий", "material_name": "Профиль направляющий",
                "document_unit": "шт", "base_unit": "м", "content_quantity": 3,
                "status": "confirmed", "note": "", "created_by": "", "created_at": None, "updated_at": None,
            },
        ])
        rows = normalize_invoice_packaging_items(cursor, [
            {"name": "Арматура A500C", "quantity": 4, "unit": "пачка", "price": 50000},
            {"name": "Профиль направляющий", "quantity": 12, "unit": "шт", "price": 300},
        ], company_id=1)
        self.assertEqual((rows[0]["quantity"], rows[0]["unit"]), (6, "т"))
        self.assertEqual((rows[1]["quantity"], rows[1]["unit"]), (36, "м"))
        self.assertEqual(_normalize_unit("пог. м"), "м")
        self.assertEqual(_normalize_unit("тонны"), "т")

    def test_direct_non_packaged_item_does_not_enter_packaging_review(self):
        cursor = FakeCursor([])
        source = {"name": "Муфта противопожарная", "quantity": 10, "unit": "шт", "price": 500}
        self.assertEqual(normalize_invoice_packaging_items(cursor, [source], company_id=1), [source])

    def test_historical_correction_preview_never_changes_stock_automatically(self):
        preview = build_packaging_correction_preview(
            {"name": "Кабель", "quantity": 25, "unit": "уп"},
            {"id": 12, "contentQuantity": 100, "baseUnit": "м"},
        )
        self.assertEqual(preview["stored"], {"quantity": 25.0, "unit": "уп"})
        self.assertEqual(preview["proposed"], {"quantity": 2500.0, "unit": "м"})
        self.assertFalse(preview["canApply"])
        self.assertEqual(preview["status"], "preview_only")

    def test_dependency_check_marks_only_possible_post_receipt_movements(self):
        report = build_packaging_dependency_check(
            storage_location="Объект А",
            stored_unit="уп",
            invoice_date="2026-07-10",
            current_balance=8,
            history_rows=[
                {"id": 1, "type": "приход", "quantity": 10, "unit": "уп", "date": "2026-07-10"},
                {"id": 2, "type": "выдача", "quantity": 2, "unit": "уп", "date": "2026-07-11", "issued_to": "Мастер"},
                {"id": 3, "type": "расход", "quantity": 1, "unit": "уп", "date": "2026-07-09"},
            ],
            movement_rows=[
                {"id": 4, "from_location": "Объект А", "to_location": "Склад", "quantity": 1, "unit": "уп", "date": "дата не распознана"},
            ],
        )
        self.assertEqual(report["currentBalance"], {"quantity": 8.0, "unit": "уп"})
        self.assertEqual(report["possibleDependencyCount"], 2)
        self.assertEqual([row["id"] for row in report["possibleHistoryRows"]], [2])
        self.assertEqual([row["id"] for row in report["possibleMovementRows"]], [4])
        self.assertTrue(report["requiresManualReconciliation"])

    def test_traceability_status_never_treats_legacy_name_match_as_invoice_link(self):
        status = build_packaging_traceability_status(
            invoice_id=20,
            item_index=1,
            history_rows=[
                {"id": 3, "type": "приход", "source_invoice_id": None, "source_invoice_line_index": None},
                {"id": 4, "type": "выдача", "source_invoice_id": None, "source_invoice_line_index": None},
            ],
            movement_rows=[],
        )
        self.assertEqual(status["state"], "legacy_unlinked")
        self.assertFalse(status["receiptSourceLinked"])
        self.assertTrue(status["requiresManualReconciliation"])

    def test_traceability_status_marks_linked_receipt_with_untraced_followup(self):
        status = build_packaging_traceability_status(
            invoice_id=20,
            item_index=1,
            history_rows=[
                {"id": 3, "type": "приход", "source_invoice_id": 20, "source_invoice_line_index": 1},
                {"id": 4, "type": "выдача", "source_invoice_id": None, "source_invoice_line_index": None},
            ],
            movement_rows=[],
        )
        self.assertEqual(status["state"], "linked_with_untraced_dependencies")
        self.assertTrue(status["receiptSourceLinked"])
        self.assertEqual(status["untracedDependencyCount"], 1)

    def test_review_snapshot_preserves_evidence_without_a_stock_operation(self):
        preview = build_packaging_correction_preview(
            {"quantity": 2, "unit": "бухта"}, {"id": 14, "contentQuantity": 100, "baseUnit": "м"},
        )
        dependency = build_packaging_dependency_check(
            storage_location="Основной склад", stored_unit="бухта", invoice_date="2026-07-10", current_balance=2,
            history_rows=[], movement_rows=[],
        )
        snapshot = build_packaging_review_snapshot(
            invoice={"id": 20, "number": "ПР-20", "date": "2026-07-10", "supplier_name": "Поставщик"},
            item_index=1, material_name="Кабель", preview=preview, dependency_check=dependency,
            traceability_status={"state": "legacy_unlinked", "requiresManualReconciliation": True},
        )
        self.assertEqual(snapshot["warehouseInvoiceId"], 20)
        self.assertEqual(snapshot["preview"]["status"], "preview_only")
        self.assertTrue(snapshot["dependencyCheck"]["requiresManualReconciliation"])

    def test_packaging_review_row_exposes_only_manual_review_evidence(self):
        row = packaging_review_row({
            "id": 7, "warehouse_invoice_id": 20, "item_index": 1,
            "packaging_rule_id": 14, "status": "reviewed_no_stock_change",
            "review_note": "Сверили документ и остаток вручную.", "reviewed_by": "Директор",
            "reviewed_at": None, "number": "ПР-20", "supplier_name": "Поставщик",
            "snapshot": {"materialName": "Кабель", "traceabilityStatus": {"state": "legacy_unlinked"}},
        })
        self.assertEqual(row["warehouseInvoiceId"], 20)
        self.assertEqual(row["materialName"], "Кабель")
        self.assertEqual(row["traceabilityState"], "legacy_unlinked")
        self.assertEqual(row["status"], "reviewed_no_stock_change")

    def test_review_decision_is_explicit_and_legacy_rows_stay_unclassified(self):
        self.assertEqual(normalize_review_decision("confirmed"), "confirmed")
        self.assertEqual(normalize_review_decision("discrepancy"), "discrepancy")
        self.assertEqual(normalize_review_decision("document_required"), "document_required")
        self.assertIsNone(normalize_review_decision("apply_stock_change"))
        legacy = packaging_review_row({"id": 8, "snapshot": {}})
        self.assertEqual(legacy["decision"], "legacy_unclassified")

    def test_packaging_label_with_its_content_uses_packaging_rule(self):
        cursor = FakeCursor([{
            "id": 9, "company_id": 1, "supplier_id": None,
            "material_key": "кабель ввг 3x1 5", "material_name": "Кабель ВВГ 3x1.5",
            "document_unit": "уп", "base_unit": "м", "content_quantity": 100,
            "status": "confirmed", "note": "", "created_by": "", "created_at": None, "updated_at": None,
        }])
        item = normalize_invoice_packaging_items(cursor, [{
            "name": "Кабель ВВГ 3x1.5", "quantity": 10, "unit": "уп. 100 м",
        }], company_id=1)[0]
        self.assertEqual(item["documentUnit"], "уп. 100 м")
        self.assertEqual(item["quantity"], 1000)
        self.assertEqual(item["unit"], "м")


if __name__ == "__main__":
    unittest.main()
