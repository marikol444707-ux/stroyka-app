"""Real bot adapters and writer must preserve refusals and MAX drafts.

The existing isolated PostgreSQL fixture has no real bot secrets. Invoke the
registered endpoint functions with an already authenticated synthetic bot; the
employee lookup, company authorization, writer and transactions remain real.
Bot-token transport and external messenger delivery are outside this test.
"""
import os
import unittest
from uuid import uuid4

from fastapi import HTTPException

from . import test_document_admission_regression as admission
from ..messenger.schema import ensure_messenger_schema


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'isolated PostgreSQL opt-in')
class BotAdmissionRegressionTests(unittest.TestCase):
    # Share preparation only; importing a TestCase base would rediscover its
    # five independent admission tests and inflate this adapter suite's count.
    setUpClass = classmethod(admission.DocumentAdmissionRegressionTests.setUpClass.__func__)
    sql = admission.DocumentAdmissionRegressionTests.sql
    api = admission.DocumentAdmissionRegressionTests.api
    create_offer = admission.DocumentAdmissionRegressionTests.create_offer
    check_contract = admission.DocumentAdmissionRegressionTests.check_contract
    raw_sources = admission.DocumentAdmissionRegressionTests.raw_sources
    create = admission.DocumentAdmissionRegressionTests.create
    pay = admission.DocumentAdmissionRegressionTests.pay
    receipt_state = admission.DocumentAdmissionRegressionTests.receipt_state

    def setUp(self):
        admission.DocumentAdmissionRegressionTests.setUp(self)
        ensure_messenger_schema(self.main.get_db)
        self.endpoints = {route.path: route.endpoint for route in self.main.app.routes
                          if hasattr(route, 'endpoint')}
        self.external_id = 'admission-' + uuid4().hex
        user = self.fixture['users']['director']
        self.sql("""INSERT INTO messenger_accounts
            (provider,user_id,external_user_id,chat_id,enabled)
            VALUES ('max',%s,%s,%s,TRUE)""",
            (user['id'], self.external_id, self.external_id))
        # Fixture init_db predates the staff ownership migration. This column
        # matches the real adapter's required, explicitly verified ownership.
        self.sql('ALTER TABLE staff ADD COLUMN IF NOT EXISTS company_scope_verified BOOLEAN NOT NULL DEFAULT FALSE')
        self.sql("""INSERT INTO staff(name,role,project,company_id,
            company_scope_verified,telegram_id,telegram_chat_id)
            VALUES (%s,%s,%s,2,TRUE,%s,%s)""",
            (user['name'], user['role'], self.fixture['project'],
             self.external_id, self.external_id))

    def invoice_payload(self):
        return dict(companyId=2, project=self.fixture['project'],
            supplierId=self.fixture['supplierId'], supplierName='Synthetic bot supplier',
            number='BOT-' + uuid4().hex, date='2026-09-28',
            sourceId='bot-message-' + uuid4().hex, vat='Без НДС',
            totalBase=100, totalVat=0, totalWithVat=100,
            items=[dict(name=self.fixture['materialName'], unit='шт',
                        quantity=1, price=100, total=100,
                        workPackage=self.fixture['workPackage'])])

    def state(self):
        return {**self.receipt_state(), **{
            table: self.sql('SELECT to_jsonb(t) FROM ' + table +
                            ' t ORDER BY to_jsonb(t)::text')
            for table in ('max_invoice_drafts', 'messenger_outbox')}}

    def assert_admission_refused(self, path, payload):
        with self.assertRaises(HTTPException) as rejected:
            self.endpoints[path](payload, _bot={'role': 'synthetic_bot'})
        self.assertIn(rejected.exception.status_code, (400, 409))
        self.assertTrue(any(word in str(rejected.exception.detail).lower()
                            for word in ('приём', 'оригинал')),
                        rejected.exception.detail)

    def test_telegram_refusal_and_retry_never_claim_success_or_post(self):
        payload = dict(self.invoice_payload(), telegramId=self.external_id)
        before = self.state()
        for _ in range(2):
            self.assert_admission_refused('/telegram/warehouse-invoices', payload)
            self.assertEqual(self.state(), before)

    def test_max_direct_refusal_and_retry_never_claim_success_or_post(self):
        payload = dict(self.invoice_payload(), maxUserId=self.external_id,
                       maxChatId=self.external_id)
        before = self.state()
        for _ in range(2):
            self.assert_admission_refused('/max/warehouse-invoices', payload)
            self.assertEqual(self.state(), before)

    def test_max_confirm_refusal_keeps_saved_draft_and_never_enqueues_success(self):
        payload = dict(self.invoice_payload(), maxUserId=self.external_id,
                       maxChatId=self.external_id)
        draft = self.endpoints['/max/warehouse-invoices/preview'](
            payload, _bot={'role': 'synthetic_bot'})
        token = draft['draftToken']
        self.assertEqual(self.sql('SELECT status,warehouse_invoice_id FROM max_invoice_drafts WHERE draft_token=%s',
                                  (token,)), [('draft', None)])
        before = self.state()
        for _ in range(2):
            self.assert_admission_refused('/max/warehouse-invoices/confirm',
                dict(draftToken=token, maxUserId=self.external_id,
                     maxChatId=self.external_id))
            self.assertEqual(self.state(), before)

    def test_max_admission_conflict_is_not_misreported_as_an_existing_receipt(self):
        # A source/message ID is not proof that a refused document is the same
        # physical receipt. Admission returns 409 for a payment invoice; an
        # unrelated receipt appearing meanwhile must not turn this into success.
        payload = dict(self.invoice_payload(), maxUserId=self.external_id,
                       maxChatId=self.external_id, physicalReceiptConfirmed=True,
                       newDocumentConfirmed=True,
                       receiptDocument={'documentType': 'invoice'}, originalUrls=[])
        draft = self.endpoints['/max/warehouse-invoices/preview'](
            payload, _bot={'role': 'synthetic_bot'})
        self.sql("""INSERT INTO warehouse_invoices
            (company_id,number,project,location,source_type,source_id,items)
            VALUES (2,'PREEXISTING-OTHER-DOCUMENT',%s,%s,'max_project_invoice',%s,'[]')""",
            (self.fixture['project'], self.fixture['project'], payload['sourceId']))
        before = self.state()
        self.assert_admission_refused('/max/warehouse-invoices/confirm',
            dict(draftToken=draft['draftToken'], maxUserId=self.external_id,
                 maxChatId=self.external_id))
        self.assertEqual(self.state(), before)

    def test_max_preview_does_not_disclose_foreign_receipt_with_same_source_id(self):
        payload = dict(self.invoice_payload(), maxUserId=self.external_id,
                       maxChatId=self.external_id)
        foreign_id = self.sql("""INSERT INTO warehouse_invoices
            (company_id,number,project,location,source_type,source_id,items)
            VALUES (3,'FOREIGN-PRIVATE-DOCUMENT','Foreign private project',
                    'Foreign private location','max_project_invoice',%s,'[]')
            RETURNING id""", (payload['sourceId'],))[0][0]
        before = self.receipt_state()
        result = self.endpoints['/max/warehouse-invoices/preview'](
            payload, _bot={'role': 'synthetic_bot'})
        self.assertNotEqual(result.get('warehouseInvoiceId'), foreign_id, result)
        self.assertEqual(result.get('status'), 'draft', result)
        self.assertIsNone(result.get('warehouseInvoiceId'), result)
        self.assertIsNone(result.get('supplierInvoiceId'), result)
        self.assertNotIn('Foreign private', str(result))
        self.assertEqual(self.receipt_state(), before)
        self.assertEqual(self.sql('''SELECT status,warehouse_invoice_id
            FROM max_invoice_drafts WHERE draft_token=%s''',
            (result['draftToken'],)), [('draft', None)])
        # Preview may enqueue its review card, never a receipt confirmation.
        self.assertEqual(self.sql('''SELECT count(*) FROM messenger_outbox
            WHERE external_user_id=%s AND event_type='max_invoice_confirmed' ''',
            (self.external_id,)), [(0,)])
