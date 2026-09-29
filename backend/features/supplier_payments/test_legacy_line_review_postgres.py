"""Real original review -> prepayment -> VAT partial receipts; disposable DB only."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from . import test_receipt_vat_postgres as vat
from . import test_invoice_line_creation_postgres as invoices
from .test_cancellations_postgres import migration
from .legacy_line_routes import register_legacy_line_review_routes


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class LegacyLineReviewPostgresTests(unittest.TestCase):
    sql=vat.ReceiptVatTests.sql
    api=vat.ReceiptVatTests.api
    create_offer=vat.ReceiptVatTests.create_offer
    check_contract=vat.ReceiptVatTests.check_contract
    raw_sources=vat.ReceiptVatTests.raw_sources
    ship=vat.ReceiptVatTests.ship
    receive=vat.ReceiptVatTests.receive
    pay=vat.ReceiptVatTests.pay

    @classmethod
    def setUpClass(cls):
        vat.ReceiptVatTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0062_supplier_legacy_contract_binding.py')
                migration(cur,'0063_supplier_legacy_line_reviews.py')
        finally:conn.close()
        register_legacy_line_review_routes(cls.main.app,cls.main.supplier_deal_dependencies)

    def setUp(self):
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        flags=patch.dict(os.environ,SUPPLIER_PAYMENTS_ENABLED='1',SUPPLIER_PARTIAL_RECEIPTS_ENABLED='1',
            SUPPLIER_UNPAID_RECEIPTS_ENABLED='1',SUPPLIER_VAT_RECEIPTS_ENABLED='1',
            OWNED_DELIVERY_SOURCES_ENABLED='1',OWNED_DELIVERY_QUALITY_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)
        self.sql('UPDATE supplier_offers SET vat_included=TRUE WHERE id=%s',(self.offer_id,))
        self.invoice=self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,offer_id,request_id,
            project_name,work_package,status,amount,vat_amount,paid_amount,contract_version_id)
            SELECT company_id,supplier_id,id,request_id,%s,%s,'На утверждении',200,34,0,%s
            FROM supplier_offers WHERE id=%s RETURNING id''',
            (self.fixture['project'],self.fixture['workPackage'],self.contract_id,self.offer_id))[0][0]
        token=self.main.create_auth_token(self.fixture['users']['director'],two_factor_passed=True)
        upload=self.client.post('/upload-photo',files={'file':('original.txt',b'Synthetic original: 2 units, gross 200, VAT 34.','text/plain')},
            data={'context':'supplier-invoice'},headers={'Authorization':'Bearer '+token,'X-Company-Id':'2','X-Company-Mode':'company'})
        self.assertEqual(upload.status_code,200,upload.text)
        self.review_path=f'/supplier-invoices/{self.invoice}/legacy-line-review'
        preview=self.api('director','GET',self.review_path)
        self.body=dict(requestId=str(uuid4()),contractVersionId=self.contract_id,sourceFileId=upload.json()['fileId'],
            expectedAmount='200.00',vatAmount='34.00',reason='Synthetic original review',confirmed=True,
            lines=[dict({k:v for k,v in row.items() if k!='lineNo'},vatAmount='34.00') for row in preview['lines']])

    def review(self,body=None,actor='director',expected=200):
        return self.api(actor,'POST',self.review_path,self.body if body is None else body,expected=expected)

    def test_prepayment_partial_receipts_and_replay_preserve_money_tax_and_birth(self):
        before=self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s',(self.invoice,))
        saved=self.review();self.assertFalse(saved['replayed'])
        self.assertTrue(self.review()['replayed'])
        self.assertEqual(before,self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s',(self.invoice,)))
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        self.pay('200.00')
        cash=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        warehouses=[]
        for _ in range(2):
            delivery=self.ship();accepted=self.receive(delivery);warehouses.append(accepted['invoiceId'])
            self.assertTrue(self.receive(delivery)['alreadyReceived'])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),cash)
        self.assertEqual(self.sql('SELECT total_base,total_vat,total_with_vat,supplier_invoice_id FROM warehouse_invoices WHERE id=ANY(%s)',(warehouses,)),[(83,17,100,None)]*2)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(200,)])
        self.assertTrue(self.review()['replayed'])

    def test_foreign_actor_and_supplier_cannot_review(self):
        self.review(actor='stranger',expected=403);self.review(actor='supplier',expected=403)
        self.assertEqual(self.sql('SELECT id FROM supplier_legacy_line_reviews WHERE invoice_id=%s',(self.invoice,)),[])

    def test_changed_amount_tax_or_confirmation_never_creates_evidence(self):
        for body in (dict(self.body,expectedAmount='201.00'),dict(self.body,vatAmount='33.00')):
            rejection=self.review(body,expected=409)
            self.assertEqual(rejection['detail']['code'],'legacy_line_review_not_saved')
        self.review(dict(self.body,confirmed=False),expected=422)
        self.assertEqual(self.sql('SELECT id FROM supplier_invoice_line_specs WHERE invoice_id=%s',(self.invoice,)),[])

    def test_paid_and_approved_invoices_are_not_retrofitted(self):
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        self.review(expected=409)
        self.pay('20.00');self.review(expected=409)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(20,)])

    def test_replay_cannot_change_original_payload(self):
        self.review()
        self.review(dict(self.body,reason='Other'),expected=409)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_legacy_line_reviews WHERE invoice_id=%s',(self.invoice,)),[(1,)])

    def test_original_birth_writer_still_rejects_old_invoice(self):
        from psycopg2 import Error
        with self.assertRaises(Error):
            self.sql("INSERT INTO supplier_invoice_line_specs(company_id,invoice_id,row_count,amount,source_payload) VALUES(2,%s,1,200,'{}')",(self.invoice,))

    def test_sealed_review_and_invoice_identity_are_immutable(self):
        self.review()
        from psycopg2 import Error
        for query in ('DELETE FROM supplier_legacy_line_reviews WHERE invoice_id=%s',
                      "UPDATE supplier_legacy_line_reviews SET reason='Other' WHERE invoice_id=%s",
                      'UPDATE supplier_invoices SET vat_amount=0 WHERE id=%s'):
            with self.assertRaises(Error):self.sql(query,(self.invoice,))

    def test_review_cannot_commit_without_sealed_lines(self):
        from psycopg2 import Error
        from psycopg2.extras import Json
        payload=dict(provenance='legacy_original_review',amount='200.00',vatAmount='34.00',
                     lines=[dict(self.body['lines'][0],lineNo=1)])
        with self.assertRaises(Error):
            self.sql('''INSERT INTO supplier_legacy_line_reviews(invoice_id,company_id,request_id,
                source_file_id,actor_id,reason,command_json,reviewed_payload)
                VALUES(%s,2,%s,%s,%s,'orphan',%s,%s)''',
                (self.invoice,str(uuid4()),self.body['sourceFileId'],self.fixture['users']['director']['id'],Json(self.body),Json(payload)))
        self.assertEqual(self.sql('SELECT id FROM supplier_legacy_line_reviews WHERE invoice_id=%s',(self.invoice,)),[])

    def test_foreign_original_is_denied_without_blocking_a_corrected_review(self):
        self.sql('UPDATE file_ownership SET company_id=3 WHERE id=%s',(self.body['sourceFileId'],))
        error=self.review(expected=403)
        self.assertEqual(error['detail']['code'],'legacy_line_review_not_saved')
        self.assertEqual(self.sql('SELECT id FROM supplier_legacy_line_reviews WHERE invoice_id=%s',(self.invoice,)),[])
        self.sql('UPDATE file_ownership SET company_id=2 WHERE id=%s',(self.body['sourceFileId'],))
        self.assertFalse(self.review()['replayed'])

    def test_new_invoice_birth_path_still_works_after_upgrade(self):
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        created=invoices.InvoiceLineCreationPostgresTests.create(self)
        self.assertEqual(self.sql('''SELECT s.legacy_review_id,s.source_identity=i.line_spec_insert_identity,
            s.creation_xid=i.line_spec_insert_xid FROM supplier_invoice_line_specs s
            JOIN supplier_invoices i ON i.id=s.invoice_id WHERE i.id=%s''',(created['id'],)),[(None,True,True)])
