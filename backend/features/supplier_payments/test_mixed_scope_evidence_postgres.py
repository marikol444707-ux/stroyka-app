"""Atomic review persistence, no financial opening or cash admission."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi import HTTPException
from .test_mixed_scope_schema_postgres import MixedScopeSchemaTests
from .access import build_payment_access
from .reads import transaction
from .mixed_opening_review import review
from .mixed_scope_evidence import save_review


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class MixedScopeEvidenceTests(unittest.TestCase):
    sql=MixedScopeSchemaTests.sql
    api=MixedScopeSchemaTests.api
    create_offer=MixedScopeSchemaTests.create_offer
    check_contract=MixedScopeSchemaTests.check_contract

    @classmethod
    def setUpClass(cls):
        MixedScopeSchemaTests.setUpClass.__func__(cls)

    def setUp(self):
        from .test_mixed_opening_review_postgres import MixedOpeningReviewTests
        MixedOpeningReviewTests.setUp(self)
        self.actor=self.fixture['users']['accountant']['id']
        self.authorize=build_payment_access(self.main._supplier_payment_access_deps,operation='update')
        self.body=dict(requestId=str(uuid4()),invoiceId=self.invoice,reason='Сверено с первичными документами',
                       evidenceHash=self.preview()['evidenceHash'])

    def preview(self):
        with transaction(dict(get_db=self.main.get_db,authorize_read=self.authorize),2) as cur:
            return review(cur,self.authorize,self.actor,2,self.invoice)

    def save(self,body=None,authorize=None):
        return save_review(self.main.get_db,authorize or self.authorize,self.actor,2,body or self.body)

    def denied(self,action,status):
        with self.assertRaises(HTTPException) as error:action()
        self.assertEqual(error.exception.status_code,status)

    def test_committed_retry_and_concurrent_uuid_save_exactly_one_review_no_cash(self):
        cash=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.save(),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.save(),results[0])
        self.assertFalse(results[0]['openingConfirmed'])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_mixed_scope_reviews WHERE invoice_id=%s',(self.invoice,)),[(1,)])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),cash)
        self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s",(self.invoice,)),[])

    def test_source_change_rejects_old_hash_and_does_not_save(self):
        self.sql('UPDATE supplier_invoices SET paid_amount=51 WHERE id=%s',(self.invoice,))
        self.sql('UPDATE warehouse_invoices SET paid_amount=51 WHERE id=%s',(self.warehouse,))
        self.denied(self.save,409)
        self.assertEqual(self.sql('SELECT id FROM supplier_mixed_scope_reviews WHERE invoice_id=%s',(self.invoice,)),[])
        self.assertNotEqual(self.preview()['evidenceHash'],self.body['evidenceHash'])

    def test_changed_request_and_revoked_package_are_denied_even_on_retry(self):
        self.save()
        self.denied(lambda:self.save(dict(self.body,reason='Другой текст')),409)
        deps=dict(self.main._supplier_payment_access_deps)
        deps['has_package_access']=lambda actor,package:package!='Электрика'
        denied=build_payment_access(deps,operation='update')
        self.denied(lambda:self.save(authorize=denied),403)

    def test_disabled_guard_blocks_new_save_and_retry(self):
        self.save()
        self.sql('ALTER TABLE supplier_mixed_scope_reviews DISABLE TRIGGER supplier_mixed_scope_insert')
        try:
            self.denied(self.save,503)
            self.denied(lambda:self.save(dict(self.body,requestId=str(uuid4()))),503)
        finally:self.sql('ALTER TABLE supplier_mixed_scope_reviews ENABLE TRIGGER supplier_mixed_scope_insert')

    def test_late_commit_failure_rolls_back_review(self):
        self.sql("""CREATE FUNCTION synthetic_review_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic commit failure' USING ERRCODE='23514'; END $$""")
        self.sql('''CREATE CONSTRAINT TRIGGER synthetic_review_failure AFTER INSERT ON supplier_mixed_scope_reviews
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION synthetic_review_commit_failure()''')
        try:
            self.denied(self.save,503)
            self.assertEqual(self.sql('SELECT id FROM supplier_mixed_scope_reviews WHERE invoice_id=%s',(self.invoice,)),[])
        finally:
            self.sql('DROP TRIGGER synthetic_review_failure ON supplier_mixed_scope_reviews')
            self.sql('DROP FUNCTION synthetic_review_commit_failure()')

    def test_http_save_retry_and_revoked_scope_preserve_single_evidence_no_cash(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from .routes import register_supplier_payment_routes
        deps=dict(self.main._supplier_payment_access_deps)
        allowed={'Электрика':True}
        deps['has_package_access']=lambda actor,package:allowed.get(package,True)
        app=FastAPI()
        register_supplier_payment_routes(app,dict(get_db=self.main.get_db,
            get_current_user=lambda: {'id':self.actor},
            authorize_write=build_payment_access(deps,operation='update')))
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        path='/companies/2/supplier-opening-confirmations/package-review'
        with TestClient(app) as client, patch.dict(os.environ,SUPPLIER_PAYMENTS_ENABLED='1',
                SUPPLIER_OPENING_CONFIRMATIONS_ENABLED='1',SUPPLIER_MIXED_OPENING_REVIEW_ENABLED='1'):
            first=client.post(path,json=self.body,headers={'X-Company-Id':'2'})
            self.assertEqual(first.status_code,200,first.text)
            self.assertFalse(first.json()['openingConfirmed'])
            again=client.post(path,json=self.body,headers={'X-Company-Id':'2'})
            self.assertEqual(again.json(),first.json())
            allowed['Электрика']=False
            self.assertEqual(client.post(path,json=self.body,headers={'X-Company-Id':'2'}).status_code,403)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_mixed_scope_reviews WHERE invoice_id=%s',(self.invoice,)),[(1,)])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
