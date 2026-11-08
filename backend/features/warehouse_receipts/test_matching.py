import copy
from datetime import date
from decimal import Decimal
import unittest

from .matching import resolve_document_match


def fixtures():
    document = {
        "companyId": 2, "documentType": "waybill", "waybillNumber": "накладная № 42/7",
        "waybillDate": "10.08.2026", "supplierInn": "0987654321", "buyerInn": "1234567890",
        "lines": [{"materialName": "Кабель ВВГ", "unit": "м", "quantity": "10.0000"},
                  {"materialName": "Кабель АВВГ", "unit": "м", "quantity": "20"}],
    }
    batch = {
        "id": 31, "companyId": 2, "supplierId": 9, "waybillNumber": "42-7",
        "waybillDate": date(2026, 8, 10),
        "documentParties": {"buyer": {"companyId": 2, "inn": "1234567890"},
                            "supplier": {"supplierId": 9, "inn": "0987654321"}},
        "lines": [{"id": 101 + index, "materialName": line["materialName"], "unit": line["unit"],
                   "shippedQuantity": Decimal(line["quantity"]), "receivedQuantity": 0,
                   "status": "Отгружено", "receivedAt": None, "warehouseInvoiceId": None}
                  for index, line in enumerate(document["lines"])],
    }
    return document, batch


class DocumentMatchingTests(unittest.TestCase):
    def resolve(self, document=None, batch=None):
        default_document, default_batch = fixtures()
        return resolve_document_match(document or default_document, [batch or default_batch])

    def assert_no_ids(self, result):
        for key in ("batchId", "companyId", "supplierId", "lineIds", "warehouseInvoiceIds"):
            self.assertNotIn(key, result)
        self.assertFalse(result["postingAllowed"])

    def test_exact_match_normalizes_number_date_whitespace_and_case(self):
        document, batch = fixtures()
        document["lines"][0]["materialName"] = " КАБЕЛЬ   ввг "
        result = self.resolve(document, batch)
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["lineIds"], [101, 102])
        self.assertEqual(result["receiptState"], "unreceived")
        self.assertFalse(result["postingAllowed"])

    def test_reordered_lines_preserve_document_order(self):
        document, batch = fixtures()
        document["lines"].reverse()
        self.assertEqual(self.resolve(document, batch)["lineIds"], [102, 101])

    def test_cross_company_never_matches_or_exposes_ids(self):
        document, batch = fixtures()
        batch["companyId"] = 3
        result = self.resolve(document, batch)
        self.assertEqual(result["status"], "no_match")
        self.assert_no_ids(result)

    def test_frozen_buyer_company_must_agree_with_scope(self):
        document, batch = fixtures()
        batch["documentParties"]["buyer"]["companyId"] = 3
        result = self.resolve(document, batch)
        self.assertEqual(result["status"], "review")
        self.assert_no_ids(result)

    def test_each_legal_inn_must_match(self):
        for field in ("supplierInn", "buyerInn"):
            with self.subTest(field=field):
                document, batch = fixtures()
                document[field] = "9999999999"
                self.assertEqual(self.resolve(document, batch)["status"], "no_match")

    def test_names_do_not_replace_legal_identity(self):
        document, batch = fixtures()
        del document["supplierInn"]
        document["supplierName"] = "Known Supplier"
        self.assertEqual(self.resolve(document, batch)["status"], "review")
        document, batch = fixtures()
        del batch["documentParties"]["supplier"]["inn"]
        self.assertEqual(self.resolve(document, batch)["status"], "review")

    def test_duplicate_batch_is_ambiguous_even_when_lines_differ(self):
        document, batch = fixtures()
        second = copy.deepcopy(batch)
        second["id"] = 32
        second["lines"][0]["shippedQuantity"] = 100
        result = resolve_document_match(document, [batch, second])
        self.assertEqual(result["status"], "ambiguous")
        self.assert_no_ids(result)
        self.assertEqual(result['candidateBatchIds'], [31, 32])

    def test_explicit_selection_requires_true_and_complete_legal_header(self):
        document, batch = fixtures()
        second = copy.deepcopy(batch)
        second['id'] = 32
        for confirmation in (False, None, 1, 'true'):
            result = resolve_document_match(document, [batch, second], selected_batch_id=32,
                                            explicit_selection_confirmed=confirmation)
            self.assertEqual(result['reasons'], ['explicit_selection_required'])
            self.assert_no_ids(result)
        result = resolve_document_match(document, [batch, second], selected_batch_id=32,
                                        explicit_selection_confirmed=True)
        self.assertEqual(result['batchId'], 32)
        for selected in (999, True, {}, 0):
            with self.subTest(selected=selected):
                result = resolve_document_match(document, [batch, second], selected_batch_id=selected,
                                                explicit_selection_confirmed=True)
                self.assertEqual(result['status'], 'review')
                self.assert_no_ids(result)

    def test_selection_cannot_override_wrong_legal_parties_header_or_company(self):
        for field, value in (('companyId', 3), ('waybillNumber', 'other'), ('waybillDate', '2026-08-11')):
            document, batch = fixtures()
            foreign = copy.deepcopy(batch)
            foreign.update(id=32, **{field: value})
            result = resolve_document_match(document, [batch, foreign], selected_batch_id=32,
                                            explicit_selection_confirmed=True)
            self.assertEqual(result['reasons'], ['selected_batch_not_eligible'])
        document, batch = fixtures()
        foreign = copy.deepcopy(batch)
        foreign['id'] = 32
        foreign['documentParties']['supplier']['inn'] = '9999999999'
        result = resolve_document_match(document, [batch, foreign], selected_batch_id=32,
                                        explicit_selection_confirmed=True)
        self.assertEqual(result['reasons'], ['selected_batch_not_eligible'])

    def test_selection_never_overrides_full_line_and_quantity_validation(self):
        document, batch = fixtures()
        second = copy.deepcopy(batch)
        second['id'] = 32
        for change in ('quantity', 'unit', 'missing'):
            candidate = copy.deepcopy(second)
            if change == 'missing':
                candidate['lines'].pop()
            else:
                candidate['lines'][0]['shippedQuantity' if change == 'quantity' else 'unit'] = 99 if change == 'quantity' else 'шт'
            result = resolve_document_match(document, [batch, candidate], selected_batch_id=32,
                                            explicit_selection_confirmed=True)
            self.assertEqual(result['status'], 'review')
            self.assert_no_ids(result)

    def test_other_received_batch_blocks_selection_even_across_invoice_sources(self):
        document, received = fixtures()
        received['sourceSupplierInvoiceId'] = 10
        unreceived = copy.deepcopy(received)
        unreceived.update(id=32, sourceSupplierInvoiceId=11)
        for marker in ({'receivedQuantity': 1}, {'receivedAt': '2026-08-10'},
                       {'warehouseInvoiceId': 55}, {'status': 'Принято'}, {'status': 'Проблема'}):
            original = copy.deepcopy(received)
            original['lines'][0].update(marker)
            for source in (None, 11):
                result = resolve_document_match(document, [original, unreceived], selected_batch_id=32,
                    explicit_selection_confirmed=True, source_supplier_invoice_id=source)
                self.assertEqual(result['reasons'], ['another_batch_already_received'])
                self.assert_no_ids(result)
            result = resolve_document_match(document, [original, unreceived], source_supplier_invoice_id=11)
            self.assertEqual(result['reasons'], ['another_batch_already_received'])

    def test_source_selection_cannot_override_batch_source(self):
        document, batch = fixtures()
        batch['sourceSupplierInvoiceId'] = 10
        result = resolve_document_match(document, [batch], selected_batch_id=31,
            explicit_selection_confirmed=True, source_supplier_invoice_id=11)
        self.assertEqual(result['reasons'], ['selected_batch_not_eligible'])

    def test_duplicate_line_identity_on_either_side_requires_review(self):
        for side in ("document", "batch"):
            document, batch = fixtures()
            lines = document["lines"] if side == "document" else batch["lines"]
            duplicate = copy.deepcopy(lines[0])
            duplicate["id"] = 999
            lines.append(duplicate)
            result = self.resolve(document, batch)
            self.assertEqual(result["reasons"], ["duplicate_line_identity"])
            self.assert_no_ids(result)

    def test_quantity_unit_full_name_and_missing_line_require_review(self):
        for field, value in (("quantity", 11), ("unit", "шт"), ("materialName", "Кабель")):
            document, batch = fixtures()
            document["lines"][0][field] = value
            self.assertEqual(self.resolve(document, batch)["status"], "review")
        document, batch = fixtures()
        document["lines"].pop()
        self.assertEqual(self.resolve(document, batch)["status"], "review")

    def test_payment_and_unknown_document_types_require_review(self):
        for value in ("payment_invoice", "supplier_invoice", "invoice", None, {}, ""):
            document, batch = fixtures()
            document["documentType"] = value
            self.assertEqual(self.resolve(document, batch)["status"], "review")

    def test_generated_scan_number_and_invalid_dates_do_not_match(self):
        for field, value in (("waybillNumber", "SCAN-20260826-1430"),
                             ("waybillDate", "2026-99-10"), ("waybillDate", "2026-08-10garbage")):
            document, batch = fixtures()
            document[field] = value
            batch[field] = value
            self.assertEqual(self.resolve(document, batch)["status"], "review")

    def test_invalid_quantities_fail_closed_on_both_sides(self):
        for value in (0, -1, True, None, "NaN", "Infinity", float("inf"), "1e1", "10.00000", {}, []):
            for side in ("document", "batch"):
                with self.subTest(value=value, side=side):
                    document, batch = fixtures()
                    target = document if side == "document" else batch
                    target["lines"][0]["quantity" if side == "document" else "shippedQuantity"] = value
                    result = self.resolve(document, batch)
                    self.assertEqual(result["status"], "review")
                    self.assert_no_ids(result)

    def test_existing_receipt_requires_all_lines_accepted_and_linked(self):
        document, batch = fixtures()
        for line in batch["lines"]:
            line.update(receivedQuantity=line["shippedQuantity"], status="Принято",
                        receivedAt="2026-08-10", warehouseInvoiceId=55)
        result = self.resolve(document, batch)
        self.assertEqual(result["receiptState"], "existing")
        self.assertEqual(result["warehouseInvoiceIds"], [55])
        self.assertFalse(result["postingAllowed"])

    def test_partial_receipt_including_partial_quantity(self):
        document, batch = fixtures()
        batch["lines"][0].update(receivedQuantity=2, status="Проблема", warehouseInvoiceId=55)
        result = self.resolve(document, batch)
        self.assertEqual(result["receiptState"], "partial")
        self.assertEqual(result["warehouseInvoiceIds"], [55])

    def test_receipt_marker_without_quantity_blocks_unreceived_state(self):
        document, batch = fixtures()
        batch["lines"][0]["receivedAt"] = "2026-08-10"
        self.assertEqual(self.resolve(document, batch)["receiptState"], "partial")

    def test_invalid_received_quantity_and_reference_require_review(self):
        for field, value in (("receivedQuantity", 999), ("receivedQuantity", "NaN"),
                             ("warehouseInvoiceId", True), ("warehouseInvoiceId", "invalid")):
            document, batch = fixtures()
            batch["lines"][0][field] = value
            result = self.resolve(document, batch)
            self.assertEqual(result["status"], "review")
            self.assert_no_ids(result)

    def test_malformed_containers_and_ids_do_not_raise_or_match(self):
        document, batch = fixtures()
        for value in (None, [], "bad", 1):
            self.assertEqual(resolve_document_match(value, [batch])["status"], "review")
            if value != []:
                self.assertEqual(resolve_document_match(document, value)["status"], "review")
        for field, value in (("lines", None), ("documentParties", []), ("companyId", True),
                             ("supplierId", 0), ("id", -1)):
            malformed = copy.deepcopy(batch)
            malformed[field] = value
            self.assertEqual(self.resolve(document, malformed)["status"], "review")

    def test_mutation_free_and_empty_candidates(self):
        document, batch = fixtures()
        before = copy.deepcopy((document, batch))
        self.resolve(document, batch)
        self.assertEqual((document, batch), before)
        self.assertEqual(resolve_document_match(document, [])["status"], "no_match")


if __name__ == "__main__":
    unittest.main()
