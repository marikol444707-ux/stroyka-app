import unittest

from fastapi import HTTPException

from .document_bindings import contract_version_id, select_invoice_contract, select_shipment_contract


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def execute(self, *args):
        pass

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class DocumentBindingPolicyTests(unittest.TestCase):
    def test_id_is_strict_and_feature_is_not_silently_ignored(self):
        self.assertIsNone(contract_version_id({}, False))
        for value in (True, 0, -1, '7', 7.0, None):
            with self.subTest(value=value), self.assertRaises(HTTPException) as error:
                contract_version_id({'contractVersionId': value}, True)
            self.assertEqual(error.exception.status_code, 422)
        with self.assertRaises(HTTPException) as error:
            contract_version_id({'contractVersionId': 7}, False)
        self.assertEqual(error.exception.status_code, 409)

    def test_legacy_offer_without_contract_can_remain_unbound(self):
        self.assertIsNone(select_invoice_contract(Cursor([None]), 40, None))

    def test_existing_contract_requires_explicit_choice(self):
        with self.assertRaises(HTTPException) as error:
            select_invoice_contract(Cursor([{'id': 7}]), 40, None)
        self.assertEqual(error.exception.status_code, 409)

    def test_current_contract_must_match_current_party_version(self):
        for row, supplied in (({'id': 8}, 7), ({'id': 7, 'party_version': 1, 'current_party_version': 2}, 7)):
            with self.subTest(row=row), self.assertRaises(HTTPException) as error:
                select_invoice_contract(Cursor([row, {'id': 7}]), 40, supplied)
            self.assertEqual(error.exception.status_code, 409)

    def test_matching_version_is_returned_without_client_requisites(self):
        row = {'id': 7, 'party_version': 2, 'current_party_version': 2,
               'snapshot_json': {'paymentTerms': 'Постоплата 100%'}}
        self.assertEqual(select_invoice_contract(Cursor([row]), 40, 7), row)

    def test_foreign_invoice_contract_is_denied(self):
        with self.assertRaises(HTTPException) as error:
            select_invoice_contract(Cursor([{'id': 8}, None]), 40, 7)
        self.assertEqual(error.exception.status_code, 403)

    def test_shipment_inherits_old_invoice_contract_not_latest(self):
        row = {'id': 7, 'party_version': 1}
        self.assertEqual(select_shipment_contract(Cursor([row]), 40, {'contract_version_id': 7}, None), row)

    def test_shipment_rejects_different_contract_missing_snapshot_and_unbound_invoice(self):
        for rows, invoice, requested in (([], {'contract_version_id': 7}, 8),
                                         ([None], {'contract_version_id': 7}, None),
                                         ([{'id': 7}], {}, None)):
            with self.subTest(invoice=invoice, requested=requested), self.assertRaises(HTTPException) as error:
                select_shipment_contract(Cursor(rows), 40, invoice, requested)
            self.assertEqual(error.exception.status_code, 409)

    def test_legacy_shipment_remains_unbound_without_any_contract(self):
        self.assertIsNone(select_shipment_contract(Cursor([None]), 40, {}, None))
