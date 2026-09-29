import os
import unittest
from unittest.mock import patch
from uuid import uuid4
import psycopg2.extras
from fastapi import FastAPI
from fastapi.testclient import TestClient
from . import test_contract_postgres as fixture
from .supplier_originals import register_supplier_originals
from .automatic_reuse import build_automatic_reuse
from .test_contracts import payload

@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS')=='1','local PostgreSQL opt-in')
class SupplierOriginalsTest(unittest.TestCase):
    setUp_parties=fixture.ContractPostgresTest.setUp_parties
    put=fixture.ContractPostgresTest.put
    review=fixture.ContractPostgresTest.review

    def setUp(self):
        fixture.ContractPostgresTest.setUp(self)
        with self.conn.cursor() as cur:
            for sql in fixture.statements('upgrade','0067_supplier_contract_originals.py'):
                cur.execute(sql.replace('public.','pg_temp.'))
            cur.execute('CREATE TEMP TABLE company_supplier_links (company_id INTEGER,supplier_id INTEGER,platform_account_id INTEGER)')
            cur.execute('INSERT INTO company_supplier_links VALUES (12,5,7)')
            cur.execute('CREATE TEMP TABLE supplier_invoices (offer_id INTEGER)')
            cur.execute('CREATE TEMP TABLE supply_deliveries (offer_id INTEGER)')
        app=FastAPI();register_supplier_originals(app,self.deps);self.client=TestClient(app)
        self.path='/companies/12/suppliers/5/contracts'
        self.body={'requestId':str(uuid4()),'sourceFileId':31,'number':'Supplier-original','date':'2026-09-15',
            'buyer':payload()['buyer'],'supplier':payload()['supplier'],'paymentTerms':'After receipt',
            'applicability':{'scope':'company','projectId':None,'term':'open_ended','startsOn':'2020-01-01','endsOn':None},'reviewConfirmed':True}
        self.conn.commit()

    def save(self,**changes):return self.client.post(self.path,json={**self.body,**changes})

    def test_original_without_offer_is_listed_and_reused_in_new_offer(self):
        response=self.save();self.assertEqual(response.status_code,200,response.text)
        saved=response.json();self.assertIsNone(saved['offerId'])
        listed=self.client.get(self.path);self.assertEqual(listed.status_code,200,listed.text)
        self.assertEqual(listed.json()['items'][0]['id'],saved['id'])
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("INSERT INTO supplier_offers VALUES (41,12,20,5,'Утверждено')")
            result=build_automatic_reuse(self.deps)(cur,41,self.user)
            self.assertIsNotNone(result)
            cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s',(result,))
            reused=cur.fetchone();self.assertEqual(reused['source_file_id'],31)
            self.assertEqual(reused['snapshot_json']['reusedFrom']['contractId'],saved['id'])
            cur.execute('SELECT COUNT(*) AS n FROM file_ownership');self.assertEqual(cur.fetchone()['n'],5)

    def test_exact_retry_does_not_create_duplicate(self):
        first=self.save();self.assertEqual(first.status_code,200,first.text)
        second=self.save();self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(first.json()['id'],second.json()['id'])
        self.assertEqual(self.save(number='changed').status_code,409)

    def test_foreign_company_file_and_header_denied(self):
        self.assertEqual(self.save(sourceFileId=32).status_code,403)
        self.assertEqual(self.client.post(self.path,json=self.body,headers={'X-Company-Id':'99'}).status_code,409)
        self.assertEqual(self.client.get('/companies/99/suppliers/5/contracts').status_code,404)

    def test_addendum_retains_original_and_old_snapshot(self):
        first=self.save().json()
        with self.conn.cursor() as cur:cur.execute('INSERT INTO file_ownership (id,company_id) VALUES (36,12)')
        self.conn.commit()
        second=self.save(requestId=str(uuid4()),revisesContractId=first['id'],addendum={'sourceFileId':36,'number':'A1','date':'2026-09-20'})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json()['sourceFileId'],31)
        self.assertEqual(second.json()['snapshot']['addenda'][0]['sourceFileId'],36)
        with self.conn.cursor() as cur:
            cur.execute('SELECT snapshot_json FROM supplier_contract_versions WHERE id=%s',(first['id'],))
            self.assertNotIn('addenda',cur.fetchone()[0])
        stale=self.save(requestId=str(uuid4()),revisesContractId=first['id'])
        self.assertEqual(stale.status_code,422,stale.text)

    def test_review_and_identity_required(self):
        self.assertEqual(self.save(reviewConfirmed=False).status_code,422)
        self.assertEqual(self.save(buyer={**self.body['buyer'],'inn':'7700000000'}).status_code,409)
        self.assertEqual(self.save(sourceFileId=35).status_code,422)

    def test_recognition_is_authorized_read_only(self):
        source_text='Buyer INN 7701234567 Supplier INN 7709876543'
        with patch('backend.features.supplier_deal_parties.supplier_originals.read_contract_text',return_value=(source_text,'a'*64)) as read:
            result=self.client.post(self.path+'/recognize',json={'sourceFileId':31})
            self.assertEqual(result.status_code,200,result.text)
            self.assertFalse(result.json()['reviewConfirmed'])
            denied=self.client.post(self.path+'/recognize',json={'sourceFileId':32})
            self.assertEqual(denied.status_code,403)
            self.assertEqual(read.call_count,1)
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_contract_versions');self.assertEqual(cur.fetchone()[0],0)

    def test_standalone_download_checks_manager_assignment(self):
        # Reuse the established real supplier team fixture, but not its invoice table.
        with self.conn.cursor() as cur:cur.execute('DROP TABLE supplier_invoices')
        fixture.ContractPostgresTest.publication_scope(self)
        first=self.save();self.assertEqual(first.status_code,200,first.text)
        from ..supplier_access.contract_files import supplier_contract_file_visible
        with self.conn.cursor() as cur:
            user={'id':14,'role':'поставщик'}
            row={'id':31,'company_id':12,'project_id':None}
            self.assertTrue(supplier_contract_file_visible(cur,user,row,[5]))
            cur.execute('DELETE FROM supplier_customer_assignments')
            self.assertFalse(supplier_contract_file_visible(cur,user,row,[5]))
            self.assertTrue(supplier_contract_file_visible(cur,{'id':13,'role':'поставщик'},row,[5]))

    def test_cabinet_lists_only_addressed_contracts_and_rechecks_assignment(self):
        with self.conn.cursor() as cur:cur.execute('DROP TABLE supplier_invoices')
        fixture.ContractPostgresTest.publication_scope(self)
        saved=self.save().json()
        self.assertEqual(self.client.get('/supplier-cabinet/contracts').status_code,403)
        self.user={'id':14,'role':'поставщик'}
        response=self.client.get('/supplier-cabinet/contracts')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers['cache-control'],'private, no-store')
        item=response.json()['items'][0]
        self.assertEqual(item['id'],saved['id'])
        self.assertEqual(item['companyId'],12)
        self.assertNotIn('snapshot',item)
        self.assertEqual(self.client.get('/supplier-cabinet/contracts?before='+str(saved['id'])).json()['items'],[])
        with self.conn.cursor() as cur:cur.execute('DELETE FROM supplier_customer_assignments')
        self.assertEqual(self.client.get('/supplier-cabinet/contracts').json()['items'],[])
        self.user={'id':13,'role':'поставщик'}
        self.assertEqual(len(self.client.get('/supplier-cabinet/contracts').json()['items']),1)
        self.user={'id':15,'role':'поставщик'}
        self.assertEqual(self.client.get('/supplier-cabinet/contracts').json()['items'],[])

    def test_cabinet_reused_contract_is_not_duplicated_and_file_revocation_hides_it(self):
        with self.conn.cursor() as cur:cur.execute('DROP TABLE supplier_invoices')
        fixture.ContractPostgresTest.publication_scope(self)
        saved=self.save().json()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("INSERT INTO supplier_offers VALUES (41,12,20,5,'Утверждено')")
            reused=build_automatic_reuse(self.deps)(cur,41,self.user)
            self.assertIsNotNone(reused)
        self.conn.commit()
        self.user={'id':14,'role':'поставщик'}
        response=self.client.get('/supplier-cabinet/contracts')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([x['id'] for x in response.json()['items']],[reused])
        with self.conn.cursor() as cur:cur.execute("UPDATE file_ownership SET deletion_status='deleted' WHERE id=31")
        self.assertEqual(self.client.get('/supplier-cabinet/contracts').json()['items'],[])

    def test_company_archive_includes_standalone_original(self):
        saved=self.save().json()
        from ..counterparty_documents.routes import SOURCES
        with self.conn.cursor() as cur:
            cur.execute('SELECT d.id FROM supplier_contract_versions d WHERE d.company_id=%s AND '+SOURCES['contract'][5],(12,))
            self.assertIn((saved['id'],),cur.fetchall())
            cur.execute('SELECT d.id FROM supplier_contract_versions d WHERE d.company_id=%s AND '+SOURCES['contract'][5],(99,))
            self.assertEqual(cur.fetchall(),[])

    def test_migration_downgrade_refuses_saved_original(self):
        self.save()
        import psycopg2
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.RaiseException):
                cur.execute(fixture.statements('downgrade','0067_supplier_contract_originals.py')[0].replace('public.','pg_temp.'))
