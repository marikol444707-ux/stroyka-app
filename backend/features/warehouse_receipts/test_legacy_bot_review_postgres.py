"""Review an existing MAX draft without changing its stored owner/destination.

Uses the registered adapters with a synthetic authenticated bot, real employee
lookup and writer. External delivery and bot-token transport are not exercised.
"""
import copy
import json
import os
import unittest

from fastapi import HTTPException

from . import test_bot_admission_regression as bots
from .test_http_support import upload_receipt_document


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1','isolated PostgreSQL opt-in')
class LegacyBotReviewPostgresTests(unittest.TestCase):
    setUpClass=classmethod(bots.BotAdmissionRegressionTests.setUpClass.__func__)
    setUp=bots.BotAdmissionRegressionTests.setUp
    sql=bots.BotAdmissionRegressionTests.sql
    api=bots.BotAdmissionRegressionTests.api
    create_offer=bots.BotAdmissionRegressionTests.create_offer
    check_contract=bots.BotAdmissionRegressionTests.check_contract
    raw_sources=bots.BotAdmissionRegressionTests.raw_sources
    create=bots.BotAdmissionRegressionTests.create
    pay=bots.BotAdmissionRegressionTests.pay
    state=bots.BotAdmissionRegressionTests.state
    receipt_state=bots.BotAdmissionRegressionTests.receipt_state
    invoice_payload=bots.BotAdmissionRegressionTests.invoice_payload

    def prepare(self):
        payload=dict(self.invoice_payload(),maxUserId=self.external_id,maxChatId=self.external_id)
        draft=self.endpoints['/max/warehouse-invoices/preview'](payload,_bot={'role':'synthetic_bot'})
        document=dict(documentType='waybill',waybillNumber=payload['number'],waybillDate=payload['date'],
                      supplierInn='7701234567',buyerInn='7702222222',
                      lines=[dict(materialName=item['name'],quantity=item['quantity'],unit=item['unit']) for item in payload['items']])
        original=upload_receipt_document(self,'director',2,self.fixture['project'],document)
        return payload,dict(draftToken=draft['draftToken'],maxUserId=self.external_id,maxChatId=self.external_id,
                            physicalReceiptConfirmed=True,newDocumentConfirmed=True,
                            receiptDocument=document,originalUrls=[original],syncAccounting=False)

    def confirm(self,data):
        return self.endpoints['/max/warehouse-invoices/confirm'](data,_bot={'role':'synthetic_bot'})

    def test_old_draft_accepts_reviewed_original_and_keeps_source_identity(self):
        payload,data=self.prepare()
        # These fields are deliberately outside the safe patch. An old draft
        # can be completed, but cannot be moved to another actor/company/project.
        forged=dict(companyId=3,project='Foreign project',location='Foreign warehouse',
                    sourceType='other_source',sourceId='other-message',messengerAccountId=9999)
        data['invoiceDraft']={**copy.deepcopy(data),**forged}
        result=self.confirm(data)
        self.assertTrue(result['ok']);self.assertEqual(result['status'],'confirmed')
        saved=self.sql('''SELECT payload_json,warehouse_invoice_id FROM max_invoice_drafts
                         WHERE draft_token=%s''',(data['draftToken'],))[0]
        stored=saved[0] if isinstance(saved[0],dict) else json.loads(saved[0])
        self.assertEqual(stored['companyId'],2)
        self.assertEqual(stored['project'],self.fixture['project'])
        self.assertEqual(stored['sourceId'],payload['sourceId'])
        self.assertNotEqual(stored['sourceType'],'other_source')
        self.assertEqual(stored['originalUrls'],data['originalUrls'])
        self.assertEqual(self.sql('SELECT company_id,project,source_id,photo_urls::jsonb FROM warehouse_invoices WHERE id=%s',
                                 (saved[1],)),[(2,self.fixture['project'],payload['sourceId'],data['originalUrls'])])
        before=self.state()
        self.assertTrue(self.confirm(data)['alreadyConfirmed'])
        self.assertEqual(self.state(),before)

    def test_invalid_review_preserves_old_draft_then_corrected_review_can_commit(self):
        _,data=self.prepare()
        before=self.state()
        invalid={**data,'receiptDocument':{**data['receiptDocument'],'documentType':'payment_invoice'}}
        with self.assertRaises(HTTPException) as rejected:self.confirm(invalid)
        self.assertEqual(rejected.exception.status_code,409)
        self.assertEqual(self.state(),before)
        result=self.confirm(data)
        self.assertTrue(result['ok']);self.assertEqual(result['status'],'confirmed')
