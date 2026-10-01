import hashlib
import json
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from backend.features.supplier_offers.delivery_document import (
    delivery_document_projection,
    load_delivery_document_projections,
)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class DeliveryDocumentProjectionTests(unittest.TestCase):
    def setUp(self):
        self.requester = {
            "version": 1, "requestId": 31, "companyId": 2,
            "companyName": "ООО Покупатель", "companyEmail": "office@buyer.test",
            "companyPhone": "+7 900", "contactUserId": 14,
            "contactName": "Иван Петров", "contactEmail": "ivan@buyer.test",
            "contactPhone": "+7 911", "projectId": 8, "projectName": "Лицей",
            "deliveryAddress": "Кисловодск, ул. Школьная, 4",
            "frozenAt": "2026-10-01T10:00:00Z",
        }
        party = {key: "" for key in (
            "fullName", "shortName", "inn", "kpp", "ogrn", "legalAddress",
            "actualAddress", "phone", "email",
        )}
        self.offer = {
            "version": 1, "offerId": 17, "requestId": 31, "companyId": 2,
            "supplierId": 9,
            "buyer": {**party, "fullName": "ООО Покупатель", "inn": "1234567890"},
            "supplier": {**party, "fullName": "ООО Поставщик", "inn": "0987654321"},
            "supplierContact": {"userId": 7, "name": "Анна", "email": "anna@supplier.test", "phone": "+7 922"},
            "frozenAt": "2026-10-01T11:00:00Z",
        }
        self.contract = {
            "number": "Д-7", "date": "2026-09-20",
            "buyer": {"companyId": 2, "fullName": "ООО Покупатель по договору", "inn": "1234567890", "kpp": "123456789"},
            "payer": {"companyId": 2, "fullName": "ООО Покупатель по договору", "inn": "1234567890", "kpp": "123456789"},
            "supplier": {"supplierId": 9, "fullName": "ООО Поставщик по договору", "inn": "0987654321", "kpp": "987654321", "legalAddress": "Москва"},
            "paymentTerms": "Постоплата",
        }

    def project(self, **overrides):
        values = dict(
            delivery_id=51, request_id=31, offer_id=17, company_id=2, supplier_id=9, project_name="Лицей",
            requester_snapshot=self.requester, offer_snapshot=self.offer,
            contract_version_id=21, source_supplier_invoice_id=44,
            contract_snapshot=self.contract, contract_snapshot_hash=digest(self.contract),
            contract_company_id=2, contract_offer_id=17,
            source_invoice_company_id=2, source_invoice_supplier_id=9,
            source_invoice_request_id=31, source_invoice_offer_id=17,
            source_invoice_contract_version_id=21,
        )
        values.update(overrides)
        return delivery_document_projection(**values)

    def test_uses_exact_contract_parties_and_frozen_delivery_destination(self):
        result = self.project()
        self.assertEqual(result["buyer"]["fullName"], "ООО Покупатель по договору")
        self.assertEqual(result["supplier"]["fullName"], "ООО Поставщик по договору")
        self.assertEqual(result["consignee"]["deliveryAddress"], "Кисловодск, ул. Школьная, 4")
        self.assertEqual(result["consignee"]["contactName"], "Иван Петров")
        self.assertEqual(result["contract"], {"versionId": 21, "number": "Д-7", "date": "2026-09-20", "snapshotHash": digest(self.contract)})
        self.assertEqual(result["sourceInvoiceId"], 44)
        self.assertFalse(result["reviewRequired"])

    def test_profile_changes_do_not_replace_frozen_values(self):
        result = self.project(current_company_name="Новое имя", current_delivery_address="Новый адрес")
        self.assertEqual(result["buyer"]["fullName"], "ООО Покупатель по договору")
        self.assertEqual(result["consignee"]["deliveryAddress"], "Кисловодск, ул. Школьная, 4")

    def test_without_contract_uses_frozen_quotation_parties(self):
        result = self.project(contract_version_id=None, source_supplier_invoice_id=None,
                              contract_snapshot=None, contract_snapshot_hash=None)
        self.assertEqual(result["buyer"]["fullName"], "ООО Покупатель")
        self.assertEqual(result["supplier"]["fullName"], "ООО Поставщик")
        self.assertIsNone(result["contract"])

    def test_rejects_contract_hash_or_scope_substitution(self):
        for overrides in ({"contract_snapshot_hash": "0" * 64}, {"supplier_id": 10}, {"company_id": 3},
                          {"contract_company_id": 3}, {"contract_offer_id": 18},
                          {"source_invoice_company_id": 3}, {"source_invoice_supplier_id": 10},
                          {"source_invoice_request_id": 32}, {"source_invoice_offer_id": 18},
                          {"source_invoice_contract_version_id": 22}):
            with self.subTest(overrides=overrides), self.assertRaises(HTTPException) as raised:
                self.project(**overrides)
            self.assertEqual(raised.exception.status_code, 409)

    def test_legacy_row_without_snapshots_is_marked_for_review(self):
        result = delivery_document_projection(
            delivery_id=51, request_id=31, offer_id=17, company_id=2, supplier_id=9, project_name="Лицей",
            requester_snapshot=None, offer_snapshot=None, contract_version_id=None,
            source_supplier_invoice_id=None, contract_snapshot=None, contract_snapshot_hash=None,
        )
        self.assertTrue(result["reviewRequired"])
        self.assertEqual(result["reviewReason"], "Историческая поставка без сохранённых реквизитов")

    def test_legacy_deal_with_bound_contract_remains_visible_without_live_fallback(self):
        result = self.project(requester_snapshot=None)
        self.assertTrue(result["reviewRequired"])
        self.assertNotIn("buyer", result)
        self.assertNotIn("supplier", result)

    def test_read_list_marks_corrupt_chain_but_strict_document_issue_blocks_it(self):
        row = {
            "delivery_id": 51, "request_id": 31, "offer_id": 17,
            "company_id": 2, "supplier_id": 9, "project": "Лицей",
            "requester_snapshot_json": self.requester, "party_snapshot_json": self.offer,
            "contract_version_id": 21, "source_supplier_invoice_id": 44,
        }
        contract = {
            "id": 21, "company_id": 2, "offer_id": 17,
            "snapshot_json": self.contract, "snapshot_hash": "0" * 64,
        }
        invoice = {
            "id": 44, "company_id": 2, "supplier_id": 9, "request_id": 31,
            "offer_id": 17, "contract_version_id": 21,
        }
        cursor = Mock()
        cursor.fetchall.side_effect = [[row], [contract], [invoice], [row], [contract], [invoice]]
        visible = load_delivery_document_projections(cursor, [51], strict=False)
        self.assertTrue(visible[51]["reviewRequired"])
        self.assertEqual(visible[51]["reviewReason"], "Связи документов поставки требуют сверки")
        with self.assertRaises(HTTPException):
            load_delivery_document_projections(cursor, [51], strict=True)


if __name__ == "__main__":
    unittest.main()
