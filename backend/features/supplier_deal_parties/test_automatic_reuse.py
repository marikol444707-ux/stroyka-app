import os
import unittest
import psycopg2.extras
from . import test_contract_postgres as fixture
from .automatic_reuse import build_automatic_reuse
from .test_contracts import payload


@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS')=='1','local PostgreSQL opt-in')
class AutomaticReuseTest(unittest.TestCase):
    setUp_parties=fixture.ContractPostgresTest.setUp_parties
    put=fixture.ContractPostgresTest.put
    review=fixture.ContractPostgresTest.review

    def setUp(self):
        fixture.ContractPostgresTest.setUp(self)
        self.scope={'scope':'company','term':'open_ended','startsOn':'2020-01-01','projectId':None,'endsOn':None}
        with self.conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE supplier_invoices (offer_id INTEGER)')
            cur.execute('CREATE TEMP TABLE supply_deliveries (offer_id INTEGER)')
            cur.execute('UPDATE supplier_deal_parties SET payer_company_id=12 WHERE offer_id=40')
            cur.execute("INSERT INTO supplier_offers VALUES (41,12,20,5,'Утверждено')")
        response=self.review(payer=payload()['buyer'],applicability=self.scope)
        self.assertEqual(response.status_code,200,response.text)
        self.source=response.json()
        self.reuse=build_automatic_reuse(self.deps)

    def apply(self,**kw):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            return self.reuse(cur,41,self.user,**kw)

    def test_approval_reuses_once_preserving_original_and_review(self):
        contract_id=self.apply()
        self.assertIsNotNone(contract_id)
        self.assertIsNone(self.apply())
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s',(contract_id,))
            saved=cur.fetchone()
            self.assertEqual(saved['source_file_id'],31)
            self.assertEqual(saved['snapshot_json']['buyer'],self.source['snapshot']['buyer'])
            self.assertEqual(saved['snapshot_json']['reusedFrom']['contractId'],self.source['id'])
            self.assertEqual(str(saved['reviewed_at']),self.source['reviewedAt'])
            cur.execute('SELECT COUNT(*) AS n FROM file_ownership');self.assertEqual(cur.fetchone()['n'],5)
            cur.execute('SELECT * FROM supplier_deal_parties WHERE offer_id=41')
            parties=cur.fetchone();self.assertEqual(parties['buyer_company_id'],parties['payer_company_id'])

    def test_ambiguous_does_not_pick_or_create_parties(self):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO supplier_offers VALUES (42,12,20,5,'Утверждено')")
            cur.execute('''INSERT INTO supplier_deal_parties
                (offer_id,company_id,request_id,supplier_id,buyer_company_id,payer_company_id,version,reason,created_by_id,created_by)
                VALUES (42,12,20,5,12,12,1,'test',8,'Test')''')
        response=self.contract_client.post('/supplier-offers/42/contracts',json={**payload(),'payer':payload()['buyer'],'sourceFileId':35,'applicability':{'scope':'project','projectId':44,'term':'open_ended','startsOn':'2020-01-01'}})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(self.apply())
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_deal_parties WHERE offer_id=41');self.assertEqual(cur.fetchone()[0],0)

    def test_changed_profile_requires_review(self):
        with self.conn.cursor() as cur:
            cur.execute('ALTER TABLE suppliers ADD COLUMN account TEXT')
            cur.execute("UPDATE suppliers SET account='40702810000000000001'")
        self.assertIsNone(self.apply())

    def test_archived_or_expired_not_used(self):
        with self.conn.cursor() as cur:cur.execute('UPDATE supplier_contract_registry SET archived=TRUE')
        self.assertIsNone(self.apply())
        with self.conn.cursor() as cur:
            cur.execute('UPDATE supplier_contract_registry SET archived=FALSE')
            cur.execute('''UPDATE supplier_contract_versions SET snapshot_json=jsonb_set(snapshot_json,'{applicability}',
                '{"scope":"company","projectId":null,"term":"fixed","startsOn":"2020-01-01","endsOn":"2020-02-01"}'::jsonb)''')
        self.assertIsNone(self.apply())

    def test_foreign_header_cannot_attach(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):self.apply(header_id='99')

    def test_addendum_is_preserved_and_unavailable_file_blocks(self):
        with self.conn.cursor() as cur:cur.execute('INSERT INTO file_ownership (id,company_id) VALUES (36,12)')
        response=self.review(payer=payload()['buyer'],applicability=self.scope,expectedVersion=1,revisesContractId=self.source['id'],addendum={'sourceFileId':36,'number':'1','date':'2026-09-20'})
        self.assertEqual(response.status_code,200,response.text)
        with self.conn.cursor() as cur:cur.execute("UPDATE file_ownership SET deletion_status='deleting' WHERE id=36")
        self.assertIsNone(self.apply())
        with self.conn.cursor() as cur:cur.execute("UPDATE file_ownership SET deletion_status='active' WHERE id=36")
        contract_id=self.apply();self.assertIsNotNone(contract_id)
        with self.conn.cursor() as cur:
            cur.execute('SELECT snapshot_json FROM supplier_contract_versions WHERE id=%s',(contract_id,))
            self.assertEqual(cur.fetchone()[0]['addenda'][0]['sourceFileId'],36)

    def test_issued_invoice_prevents_automatic_change(self):
        with self.conn.cursor() as cur:cur.execute('INSERT INTO supplier_invoices VALUES (41)')
        self.assertIsNone(self.apply())

    def test_reused_contract_can_bind_invoice_without_another_review(self):
        from .document_bindings import select_invoice_contract
        contract_id=self.apply()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            chosen=select_invoice_contract(cur,41,contract_id)
            self.assertEqual(chosen['id'],contract_id)
            self.assertEqual(chosen['snapshot_json']['paymentTerms'],self.source['snapshot']['paymentTerms'])

    def test_different_supplier_not_reused(self):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO suppliers VALUES (6,'7709876544','Другой поставщик')")
            cur.execute('UPDATE supplier_offers SET supplier_id=6 WHERE id=41')
        self.assertIsNone(self.apply())

    def test_selection_api_reads_without_writes_and_retries_safely(self):
        path='/supplier-offers/41/saved-contracts'
        options=self.contract_client.get(path)
        self.assertEqual(options.status_code,200,options.text)
        self.assertEqual([x['id'] for x in options.json()['items']],[self.source['id']])
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_contract_versions WHERE offer_id=41')
            self.assertEqual(cur.fetchone()[0],0)
        body={'contractId':self.source['id']}
        first=self.contract_client.post(path,json=body)
        self.assertEqual(first.status_code,200,first.text)
        second=self.contract_client.post(path,json=body)
        self.assertEqual(second.json(),first.json())
        self.assertEqual(self.contract_client.post(path,json={'contractId':99999}).status_code,409)

    def test_selection_revalidates_profile_and_owner(self):
        path='/supplier-offers/41/saved-contracts'
        body={'contractId':self.source['id']}
        self.assertEqual(self.contract_client.post(path,json=body,headers={'X-Company-Id':'99'}).status_code,409)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE suppliers SET name='Changed profile'")
        self.conn.commit()
        self.assertEqual(self.contract_client.post(path,json=body).status_code,409)

    def test_explicit_choice_resolves_ambiguity(self):
        self.test_ambiguous_does_not_pick_or_create_parties()
        self.conn.commit()
        path='/supplier-offers/41/saved-contracts'
        self.assertEqual(len(self.contract_client.get(path).json()['items']),2)
        selected=self.contract_client.post(path,json={'contractId':self.source['id']})
        self.assertEqual(selected.status_code,200,selected.text)
        self.assertEqual(selected.json()['sourceContractId'],self.source['id'])
