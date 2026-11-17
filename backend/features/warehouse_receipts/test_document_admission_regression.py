"""Legacy clients must not bypass document-backed receipt admission.

Real authenticated HTTP and disposable PostgreSQL. Reuse fixture preparation,
not its test cases or receipt helper: these requests deliberately target the old
write URL even after the supported receipt workflow has changed.
"""
import os
import unittest
from uuid import uuid4

from fastapi import HTTPException

from ..supplier_payments import test_partial_receipt_runtime_postgres as partial


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'isolated PostgreSQL opt-in')
class DocumentAdmissionRegressionTests(unittest.TestCase):
    setUpClass = classmethod(partial.PartialReceiptRuntimeTests.setUpClass.__func__)
    setUp = partial.PartialReceiptRuntimeTests.setUp
    sql = partial.PartialReceiptRuntimeTests.sql
    api = partial.PartialReceiptRuntimeTests.api
    create_offer = partial.PartialReceiptRuntimeTests.create_offer
    check_contract = partial.PartialReceiptRuntimeTests.check_contract
    raw_sources = partial.PartialReceiptRuntimeTests.raw_sources
    create = partial.PartialReceiptRuntimeTests.create
    pay = partial.PartialReceiptRuntimeTests.pay
    ship = partial.PartialReceiptRuntimeTests.ship

    def receipt_state(self):
        return {table: self.sql('SELECT to_jsonb(t) FROM ' + table +
                                ' t ORDER BY to_jsonb(t)::text') for table in (
            'supply_deliveries', 'warehouse_invoices', 'warehouse_history',
            'materials', 'material_inspection_journal', 'supplier_invoices',
            'project_payments', 'supply_claims', 'supply_history',
            'supplier_receipt_line_proofs', 'supplier_receipt_exceptions',
            'supplier_payment_operations')}

    def legacy_receive(self, actor, delivery, payload):
        user = self.fixture['users'][actor]
        token = self.main.create_auth_token(user, two_factor_passed=True)
        return self.client.put(f'/supply-deliveries/{delivery}/receive', json=payload,
            headers={'Authorization': 'Bearer ' + token,
                     'X-Company-Id': str(user['company_id']),
                     'X-Company-Mode': 'company'})

    def reject_legacy_without_changes(self, payload):
        delivery = self.ship()
        before = self.receipt_state()
        response = self.legacy_receive('foreman', delivery, payload)
        self.assertEqual(response.status_code, 409, response.text)
        detail = response.json().get('detail', '')
        self.assertIsInstance(detail, str)
        self.assertIn('оригинал', detail.lower())
        self.assertIn('накладн', detail.lower())
        self.assertEqual(self.receipt_state(), before)
        # A queued request from an old tab must remain a refusal on repetition,
        # never become a successful new write or invent a receipt on retry.
        again = self.legacy_receive('foreman', delivery, payload)
        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(self.receipt_state(), before)

    def test_old_tab_cannot_post_stock_without_a_verified_original(self):
        self.reject_legacy_without_changes({
            'receivedQuantity': 1, 'qualityStatus': 'Принято',
            'receivedBy': 'Synthetic legacy receiver'})

    def test_asserting_physical_confirmation_does_not_replace_an_original(self):
        self.reject_legacy_without_changes({
            'receivedQuantity': 1, 'qualityStatus': 'Принято',
            'physicalReceiptConfirmed': True, 'originalUrls': []})

    def test_missing_actual_quantity_cannot_silently_create_a_zero_receipt_claim(self):
        self.reject_legacy_without_changes({'qualityStatus': 'Недостача'})

    def test_foreign_company_cannot_change_or_discover_the_receipt(self):
        delivery = self.ship()
        before = self.receipt_state()
        payload = {'receivedQuantity': 1, 'physicalReceiptConfirmed': True}
        response = self.legacy_receive('stranger', delivery, payload)
        # Retirement may return the same generic 409 for every authenticated
        # caller. Resource authorization may instead retain its ordinary 403.
        self.assertIn(response.status_code, (403, 409), response.text)
        self.assertNotIn('delivery', response.json())
        self.assertNotIn('invoiceId', response.json())
        self.assertEqual(self.receipt_state(), before)

    def test_shared_bot_writer_cannot_post_without_document_admission(self):
        # Telegram/MAX route adapters call this same writer directly. Making
        # admission opt-in on only the public HTTP endpoint leaves that route
        # around it open. Exercise the real writer with its default arguments.
        payload = {
            'companyId': 2, 'project': self.fixture['project'],
            'location': self.fixture['project'], 'warehouseTarget': 'object',
            'supplierId': self.fixture['supplierId'],
            'supplierName': 'SUPPLY CHAIN legal supplier',
            'number': 'ADMISSION-' + uuid4().hex, 'date': '2026-09-28',
            'vat': 'Без НДС', 'totalBase': 100, 'totalVat': 0,
            'totalWithVat': 100, 'acceptedBy': 'Synthetic bot receiver',
            'items': [{'name': self.fixture['materialName'], 'unit': 'шт',
                       'quantity': 1, 'price': 100, 'total': 100,
                       'workPackage': self.fixture['workPackage']}],
        }
        before = self.receipt_state()
        with self.assertRaises(HTTPException) as rejected:
            self.main._create_warehouse_invoice_record(
                payload, self.fixture['users']['director'],
                x_company_id='2', x_company_mode='company')
        self.assertIn(rejected.exception.status_code, (400, 409))
        self.assertTrue(any(word in str(rejected.exception.detail).lower()
                            for word in ('приём', 'оригинал')),
                        rejected.exception.detail)
        self.assertEqual(self.receipt_state(), before)
