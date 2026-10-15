"""Read-only financial basis for an exact accepted buyer connection."""
import os
import unittest
from unittest.mock import patch

from .test_quote_corrections_postgres import SupplierQuoteCorrectionsPostgresTests as Fixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierCorrectionFinancialsPostgresTests(unittest.TestCase):
    sql,api,connection,received,rfq=Fixture.sql,Fixture.api,Fixture.connection,Fixture.received,Fixture.rfq
    raw=Fixture.raw

    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass.__func__(cls)

    def path(self,source,request,company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{request}/correction-preview'

    def review(self,source,request,category='invoices',company=2):
        return self.api('admin','GET',self.path(source,request,company)+'?category='+category)

    def invoice(self,target,company=2,offer=None,request=None):
        return self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,offer_id,request_id,amount,paid_amount)
            VALUES(%s,%s,%s,%s,0,0) RETURNING id''',(company,target,offer,request))[0][0]

    def test_source_paid_invoice_does_not_imply_target_issued_documents_or_disclose_money(self):
        source,target,connection=self.connection()
        invoice=self.invoice(source)
        self.sql('UPDATE supplier_invoices SET amount=200,paid_amount=50 WHERE id=%s',(invoice,))
        foreign=self.invoice(target,company=3)
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in
            ('suppliers','users','company_supplier_links','supplier_invoices','supplier_buyer_connection_requests','audit_log')}
        result=self.review(source,connection)
        self.assertEqual(result['financialReview']['state'],'clear')
        self.assertEqual(result['financialReview']['source']['invoices'],1)
        self.assertEqual(result['financialReview']['connected']['invoices'],0)
        self.assertEqual(result['items'][0]['context']['supplierCard'],'source')
        self.assertNotIn(foreign,[r['id'] for r in result['items']])
        for key in ('paid_amount','amount','snapshot','file_url','email','password','200.00','50.00'):
            self.assertNotIn(key,str(result))
        for t,rows in before.items():self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id'))

    def test_zero_invoice_and_unpaid_delivery_require_document_review_with_exact_parent_ids(self):
        source,target,connection=self.connection();request,_,offer,_=self.received(target)
        invoice=self.invoice(target,offer=offer,request=request)
        self.sql('''INSERT INTO supply_deliveries(company_id,supplier_id,offer_id,request_id)
            VALUES(2,%s,%s,%s)''',(target,offer,request))
        self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id) VALUES(2,%s,%s)',(target,invoice))
        result=self.review(source,connection)
        self.assertEqual(result['financialReview']['state'],'review_required')
        self.assertEqual({k:result['financialReview']['connected'][k] for k in ('invoices','deliveries','receipts')},
            dict(invoices=1,deliveries=1,receipts=1))
        self.assertEqual(result['items'][0]['context'],dict(supplierCard='connected',requestId=request,offerId=offer,linksConfirmed=True))
        self.assertFalse(result['canApply'])
        self.api('admin','POST',self.path(source,connection),{},expected=405)

    def test_awarded_order_is_detected_without_invoice_and_offer_history_preserved(self):
        source,target,connection=self.connection();request,_,offer,_=self.received(target)
        self.sql("UPDATE supplier_offers SET status='Утверждено' WHERE id=%s",(offer,))
        before=self.sql('SELECT to_jsonb(t) FROM supplier_offers t WHERE id=%s',(offer,))
        result=self.review(source,connection,'offers')
        self.assertEqual(result['financialReview']['connected']['orders'],1)
        self.assertEqual(result['financialReview']['state'],'review_required')
        self.assertEqual(result['items'][0]['context'],dict(supplierCard='connected',requestId=request,offerId=offer,linksConfirmed=True))
        self.assertEqual(before,self.sql('SELECT to_jsonb(t) FROM supplier_offers t WHERE id=%s',(offer,)))

    def test_foreign_or_different_supplier_parent_is_not_disclosed_as_valid_chain(self):
        for foreign_company in (True,False):
            source,target,connection=self.connection();_,_,offer,_=self.received(target,company=3 if foreign_company else 2)
            request=self.rfq(target,company=3 if foreign_company else 2)[0]
            invoice=self.invoice(target if foreign_company else source,offer=offer,request=request)
            item=next(r for r in self.review(source,connection)['items'] if r['id']==invoice)
            self.assertEqual(item['context']['linksConfirmed'],False)
            self.assertIsNone(item['context']['offerId'])
            if foreign_company:self.assertIsNone(item['context']['requestId'])

    def test_missing_registry_is_unknown_and_role_company_scope_still_enforced(self):
        source,_,connection=self.connection()
        self.sql('ALTER TABLE supply_deliveries RENAME TO financial_test_deliveries')
        try:
            result=self.review(source,connection)
            self.assertEqual(result['financialReview']['state'],'needs_check')
            self.assertIsNone(result['financialReview']['connected']['deliveries'])
        finally:self.sql('ALTER TABLE financial_test_deliveries RENAME TO supply_deliveries')
        self.api('admin','GET',self.path(source,connection,3),expected=404)
        for actor in ('supplier','director'):
            self.api(actor,'GET',self.path(source,connection),expected=403)

    def test_receipt_request_context_and_page_do_not_mix_suppliers(self):
        source,target,connection=self.connection();request,_,_=self.rfq(target)
        receipt=self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,supply_request_id)
            VALUES(2,%s,%s) RETURNING id''',(target,request))[0][0]
        result=self.review(source,connection,'receipts')
        self.assertEqual(result['items'][0]['id'],receipt)
        self.assertEqual(result['items'][0]['context'],dict(supplierCard='connected',requestId=request,offerId=None,linksConfirmed=True))
        self.assertEqual(result['financialReview']['connected']['receipts'],1)

    def test_invoice_without_request_uses_only_a_verified_offer_parent_and_page_is_bounded(self):
        source,target,connection=self.connection();request,_,offer,_=self.received(target)
        first=self.invoice(target,offer=offer)
        self.invoice(source)
        result=self.api('admin','GET',self.path(source,connection)+'?limit=1')
        self.assertTrue(result['hasMore'])
        self.assertEqual([r['id'] for r in result['items']],[first])
        self.assertEqual(result['items'][0]['context']['requestId'],request)
        self.sql('UPDATE supply_requests SET company_id=3 WHERE id=%s',(request,))
        result=self.review(source,connection)
        context=next(r['context'] for r in result['items'] if r['id']==first)
        self.assertFalse(context['linksConfirmed'])
        self.assertIsNone(context['requestId']);self.assertIsNone(context['offerId'])

    def test_awarded_positions_with_pending_status_and_missing_status_column_are_not_clear(self):
        source,target,connection=self.connection();_,_,offer=self.rfq(target)
        self.sql('ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS awarded_items_json TEXT')
        self.sql('UPDATE supplier_offers SET awarded_items_json=%s WHERE id=%s',('[{"requestPosition":0}]',offer))
        self.assertEqual(self.review(source,connection)['financialReview']['connected']['orders'],1)
        self.sql('ALTER TABLE supplier_offers RENAME COLUMN status TO financial_test_status')
        try:
            result=self.review(source,connection)
            self.assertEqual(result['financialReview']['state'],'needs_check')
            self.assertIsNone(result['financialReview']['connected']['orders'])
        finally:self.sql('ALTER TABLE supplier_offers RENAME COLUMN financial_test_status TO status')

    def test_financial_inspection_runs_in_database_read_only_transaction(self):
        from psycopg2.errors import ReadOnlySqlTransaction
        source,target,connection=self.connection()
        before=self.sql('SELECT to_jsonb(t) FROM company_supplier_links t ORDER BY id')
        def writer(cur,*args):
            cur.execute("UPDATE company_supplier_links SET status='Неактивный' WHERE company_id=2 AND supplier_id=%s",(target,))
        with patch('backend.features.participant_support.correction_preview.inspect',side_effect=writer):
            with self.assertRaises(ReadOnlySqlTransaction):self.review(source,connection)
        self.assertEqual(before,self.sql('SELECT to_jsonb(t) FROM company_supplier_links t ORDER BY id'))
