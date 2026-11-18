"""Personal return drafts, competing writers and stock conservation on disposable PostgreSQL."""
import os, importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase, skipUnless
from uuid import uuid4
from fastapi.testclient import TestClient
from .test_postgres_support import Fixture

@skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class ReturnDraftPostgresTests(TestCase):
    def setUp(self):
        self.fixture=Fixture();self.addCleanup(self.fixture.close)
        with self.fixture.get_db() as conn,conn.cursor() as cur:
            cur.execute(importlib.import_module('migrations.versions.0112_warehouse_return_drafts').SCHEMA_SQL)
        conn.close()
        self.client=TestClient(self.fixture.app);self.addCleanup(self.client.close)
        response=self.client.post('/warehouse-distributions',json=dict(companyId=2,requestId=str(uuid4()),reason='Seed issue',rows=[dict(lotId=1,projectId=1,quantity='4')]))
        self.assertEqual(response.status_code,200,response.text)
        self.allocation=response.json()['items'][0]['id']
    def document(self,quantity='1'):
        return dict(allocationId=self.allocation,quantity=quantity,reason='Physical return')
    def save(self,revision=0,document=None,**kwargs):
        return self.client.put('/warehouse-distributions/return-draft',json=dict(companyId=2,expectedRevision=revision,requestId=str(uuid4()),document=document or self.document()),**kwargs)
    def command(self,quantity='1'):
        return dict(companyId=2,requestId=str(uuid4()),reason='Physical return',quantity=quantity)
    def perform(self,body,revision=1,allocation=None,**kwargs):
        return self.client.post(f'/warehouse-distributions/{allocation or self.allocation}/returns',json=body,headers={'X-Warehouse-Return-Draft-Revision':str(revision),**kwargs})
    def facts(self):
        return {table:self.fixture.query('SELECT * FROM '+table+' ORDER BY id') for table in ('warehouse_main','materials','warehouse_receipt_lots','warehouse_movements','warehouse_distribution_operations','warehouse_distribution_returns','warehouse_distribution_allocations')}
    def test_partial_return_restores_on_another_device_without_stock_changes(self):
        before=self.facts();response=self.save(document=self.document('1.'))
        self.assertEqual(response.status_code,200,response.text)
        with TestClient(self.fixture.app) as device:result=device.get('/warehouse-distributions/return-draft').json()
        self.assertEqual(result['document'],self.document('1.'));self.assertEqual(result['source']['id'],self.allocation)
        self.assertEqual(self.facts(),before)
    def test_concurrent_saves_keep_one_revision(self):
        barrier=Barrier(2)
        def write(value):barrier.wait();return self.save(document=self.document(value))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,['1','2']))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        winner=next(r.json()['document'] for r in results if r.status_code==200)
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').json()['document'],winner)
    def test_success_consumes_draft_and_replay_preserves_next_draft(self):
        self.assertEqual(self.save().status_code,200)
        body=self.command();response=self.perform(body);self.assertEqual(response.status_code,200,response.text)
        draft=self.client.get('/warehouse-distributions/return-draft').json()
        self.assertEqual(draft['revision'],2);self.assertIsNone(draft['document']['allocationId'])
        self.assertEqual(draft['lastOperation']['requestId'],body['requestId'])
        self.assertEqual(self.save(2,self.document('2')).status_code,200)
        before=self.facts();self.assertEqual(self.perform(body).json(),response.json());self.assertEqual(self.facts(),before)
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').json()['document'],self.document('2'))
    def test_two_returns_with_different_request_ids_consume_once(self):
        self.assertEqual(self.save().status_code,200);barrier=Barrier(2)
        def run(_):barrier.wait();return self.perform(self.command())
        with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(run,range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_distribution_returns')[0]['n'],1)
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]['available_quantity'],7)
        row=self.fixture.query('SELECT * FROM warehouse_distribution_allocations WHERE id=%s',(self.allocation,))[0]
        self.assertEqual((row['lot_id'],row['receipt_id'],row['project_id'],row['returned_quantity']),(1,1,1,1))
    def test_stock_failure_keeps_draft_and_all_business_tables(self):
        self.assertEqual(self.save(document=self.document('9')).status_code,200);before=self.facts()
        response=self.perform(self.command('9'));self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.facts(),before)
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').json()['document'],self.document('9'))
    def test_return_must_match_snapshot_and_allocation(self):
        self.assertEqual(self.save().status_code,200);before=self.facts()
        self.assertEqual(self.perform(self.command('2')).status_code,409)
        self.assertEqual(self.perform(self.command(),allocation=self.allocation+50).status_code,409)
        self.assertEqual(self.facts(),before)
    def test_personal_and_company_scope_with_same_user_in_two_companies(self):
        self.assertEqual(self.save().status_code,200)
        self.fixture.query("INSERT INTO user_company_roles(user_id,company_id,role) VALUES(1,3,'директор') RETURNING id")
        for headers in ({'X-Test-Role':'deputy'},{'X-Company-Id':'3','X-Company-Mode':'company'}):
            response=self.client.get('/warehouse-distributions/return-draft',headers=headers)
            self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['revision'],0)
            self.assertIsNone(response.json()['source'])
        foreign=self.client.put('/warehouse-distributions/return-draft',headers={'X-Company-Id':'3','X-Company-Mode':'company'},json=dict(companyId=3,expectedRevision=0,requestId=str(uuid4()),document=self.document()))
        self.assertEqual(foreign.status_code,404,foreign.text)
        self.assertEqual(self.perform(self.command(),**{'X-Test-Role':'deputy'}).status_code,409)
    def test_revoked_membership_cannot_read_save_or_replay(self):
        self.assertEqual(self.save().status_code,200);body=self.command();self.assertEqual(self.perform(body).status_code,200)
        self.fixture.query('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=1 RETURNING id')
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').status_code,403)
        self.assertEqual(self.save(2).status_code,403);self.assertEqual(self.perform(body).status_code,403)
    def test_lost_save_reply_replays_but_never_overwrites_later_revision(self):
        body=dict(companyId=2,expectedRevision=0,requestId=str(uuid4()),document=self.document())
        self.assertEqual(self.client.put('/warehouse-distributions/return-draft',json=body).status_code,200)
        self.assertEqual(self.client.put('/warehouse-distributions/return-draft',json=body).json()['revision'],1)
        self.assertEqual(self.save(1,self.document('2')).status_code,200)
        self.assertEqual(self.client.put('/warehouse-distributions/return-draft',json=body).status_code,409)
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').json()['document'],self.document('2'))
    def test_missing_migration_and_old_client_behavior_are_explicit(self):
        self.fixture.query('DROP TABLE warehouse_return_drafts')
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').status_code,503)
        self.assertEqual(self.perform(self.command()).status_code,503)
        response=self.client.post(f'/warehouse-distributions/{self.allocation}/returns',json=self.command())
        self.assertEqual(response.status_code,200,response.text)
    def test_reader_and_invalid_inputs_cannot_save(self):
        self.assertEqual(self.save(headers={'X-Test-Role':'accountant'}).status_code,403)
        self.assertEqual(self.save(document={**self.document(),'confirmed':True}).status_code,422)
        self.assertEqual(self.save(True).status_code,422)
        self.assertEqual(self.save(document=self.document('\x00')).status_code,422)
        self.assertEqual(self.save(document=dict(allocationId=None,quantity='1',reason='No allocation')).status_code,422)
        self.assertEqual(self.client.get('/warehouse-distributions/return-draft').json()['revision'],0)
