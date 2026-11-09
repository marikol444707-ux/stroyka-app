"""Durable personal drafts and stock commands against an isolated PostgreSQL."""
import os,importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase, skipUnless
from uuid import uuid4
from fastapi.testclient import TestClient
from .test_postgres_support import Fixture

@skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class DraftPostgresTests(TestCase):
    def setUp(self):
        self.fixture=Fixture();self.addCleanup(self.fixture.close)
        with self.fixture.get_db() as conn,conn.cursor() as cur:
            cur.execute(importlib.import_module('migrations.versions.0111_warehouse_batch_drafts').SCHEMA_SQL)
        conn.close()
        self.client=TestClient(self.fixture.app);self.addCleanup(self.client.close)

    def document(self,quantity='2',**kw):
        return dict(rows=[dict(lotId=1,projectId=1,quantity=quantity)],reason='Draft reason',**kw)

    def save(self,revision=0,document=None,**kw):
        return self.client.put('/warehouse-distributions/draft',json=dict(companyId=2,expectedRevision=revision,
            requestId=str(uuid4()),document=document or self.document()),**kw)

    def test_partial_draft_survives_another_client_without_stock_writes(self):
        before=self.fixture.query('SELECT quantity FROM warehouse_main ORDER BY id')
        result=self.save(document=self.document('2.'));self.assertEqual(result.status_code,200,result.text)
        with TestClient(self.fixture.app) as other:
            saved=other.get('/warehouse-distributions/draft').json()
        self.assertEqual(saved['document']['rows'][0]['quantity'],'2.')
        self.assertEqual(saved['revision'],1)
        self.assertEqual(self.fixture.query('SELECT quantity FROM warehouse_main ORDER BY id'),before)
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_distribution_operations')[0]['n'],0)

    def test_drafts_are_personal_and_company_scoped(self):
        self.assertEqual(self.save().status_code,200)
        for headers in ({'X-Test-Role':'deputy'},{'X-Test-Company':'3'}):
            r=self.client.get('/warehouse-distributions/draft',headers=headers)
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['revision'],0)
        self.assertEqual(self.client.get('/warehouse-distributions/draft',headers={'X-Test-Role':'accountant'}).status_code,403)
        self.assertEqual(self.save(document=dict(rows=[dict(lotId=2,projectId=3,quantity='1')],reason='Foreign')).status_code,404)

    def test_concurrent_saves_refuse_stale_revision(self):
        start=Barrier(2)
        def save(value):
            start.wait();return self.save(document=self.document(value))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['1','3']))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        winner=next(r.json()['document'] for r in results if r.status_code==200)
        self.assertEqual(self.client.get('/warehouse-distributions/draft').json()['document'],winner)

    def test_lost_save_reply_replays_without_overwriting_a_newer_revision(self):
        body=dict(companyId=2,expectedRevision=0,requestId=str(uuid4()),document=self.document())
        first=self.client.put('/warehouse-distributions/draft',json=body)
        self.assertEqual(first.status_code,200,first.text)
        repeat=self.client.put('/warehouse-distributions/draft',json=body)
        self.assertEqual(repeat.json()['revision'],1)
        self.assertEqual(self.save(1,self.document('3')).status_code,200)
        self.assertEqual(self.client.put('/warehouse-distributions/draft',json=body).status_code,409)
        self.assertEqual(self.client.get('/warehouse-distributions/draft').json()['document']['rows'][0]['quantity'],'3')

    def command(self,quantity='2'):
        return dict(companyId=2,requestId=str(uuid4()),reason='Draft reason',rows=[dict(lotId=1,projectId=1,quantity=quantity)])

    def issue(self,body,revision=1):
        return self.client.post('/warehouse-distributions',json=body,headers={'X-Warehouse-Draft-Revision':str(revision)})

    def test_issue_consumes_draft_atomically_and_replay_keeps_new_draft(self):
        self.assertEqual(self.save().status_code,200)
        body=self.command();first=self.issue(body);self.assertEqual(first.status_code,200,first.text)
        saved=self.client.get('/warehouse-distributions/draft').json()
        self.assertEqual(saved['revision'],2);self.assertEqual(saved['document']['rows'][0]['quantity'],'')
        self.assertEqual(saved['lastOperation']['requestId'],body['requestId'])
        self.assertEqual(self.save(2,self.document('1')).status_code,200)
        repeat=self.issue(body);self.assertEqual(repeat.status_code,200,repeat.text)
        self.assertEqual(first.json(),repeat.json())
        self.assertEqual(self.client.get('/warehouse-distributions/draft').json()['revision'],3)
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_distribution_allocations')[0]['n'],1)
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]['available_quantity'],8)

    def test_two_tabs_cannot_issue_one_draft_with_different_request_ids(self):
        self.assertEqual(self.save().status_code,200)
        barrier=Barrier(2)
        def issue(_):barrier.wait();return self.issue(self.command())
        with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(issue,range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_distribution_operations')[0]['n'],1)

    def test_rejected_stock_write_keeps_draft_and_rollback_has_no_partial_movement(self):
        self.assertEqual(self.save(document=self.document('20')).status_code,200)
        self.assertEqual(self.issue(self.command('20')).status_code,409)
        draft=self.client.get('/warehouse-distributions/draft').json()
        self.assertEqual(draft['revision'],1);self.assertEqual(draft['document']['rows'][0]['quantity'],'20')
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_movements')[0]['n'],0)
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_distribution_operations')[0]['n'],0)

    def test_command_must_match_saved_snapshot_and_revoked_membership_cannot_read(self):
        self.assertEqual(self.save().status_code,200)
        self.assertEqual(self.issue(self.command('3')).status_code,409)
        self.assertEqual(self.client.post('/warehouse-distributions',json=self.command(),headers={'X-Warehouse-Draft-Revision':'1','X-Test-Role':'deputy'}).status_code,409)
        self.fixture.query('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=1 RETURNING id')
        self.assertEqual(self.client.get('/warehouse-distributions/draft').status_code,403)
        self.assertEqual(self.save(1).status_code,403)

    def test_missing_migration_fails_explicitly_without_breaking_legacy_issue(self):
        self.fixture.query('DROP TABLE warehouse_batch_drafts')
        response=self.client.get('/warehouse-distributions/draft')
        self.assertEqual(response.status_code,503,response.text)
        self.assertIn('Не закрывайте',response.json()['detail'])
        self.assertEqual(self.save().status_code,503)
        self.assertEqual(self.issue(self.command()).status_code,503)
        legacy=self.client.post('/warehouse-distributions',json=self.command())
        self.assertEqual(legacy.status_code,200,legacy.text)

    def test_same_user_membership_in_two_companies_does_not_mix_drafts(self):
        self.fixture.query("INSERT INTO user_company_roles(user_id,company_id,role) VALUES(1,3,'директор') RETURNING id")
        self.assertEqual(self.save().status_code,200)
        headers={'X-Company-Id':'3','X-Company-Mode':'company'}
        response=self.client.get('/warehouse-distributions/draft',headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual((response.json()['companyId'],response.json()['userId'],response.json()['revision']),(3,1,0))
        body=dict(companyId=3,expectedRevision=0,requestId=str(uuid4()),document=dict(rows=[dict(lotId=2,projectId=3,quantity='1')],reason='Company three'))
        response=self.client.put('/warehouse-distributions/draft',json=body,headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/warehouse-distributions/draft').json()['document'],self.document())
        body.update(expectedRevision=1,requestId=str(uuid4()),document=self.document())
        self.assertEqual(self.client.put('/warehouse-distributions/draft',json=body,headers=headers).status_code,404)

    def test_invalid_revision_or_document_cannot_mutate_saved_draft(self):
        self.assertEqual(self.save().status_code,200)
        before=self.client.get('/warehouse-distributions/draft').json()
        for revision,document in ((True,self.document()),(-1,self.document()),(1,dict(rows=[],reason='Invalid')),
            (1,self.document('\x00')),(1,dict(rows=[dict(lotId=1,projectId=1,quantity='1',cachedBalance=10)],reason='Invalid'))):
            response=self.client.put('/warehouse-distributions/draft',json=dict(companyId=2,expectedRevision=revision,requestId=str(uuid4()),document=document))
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.client.get('/warehouse-distributions/draft').json(),before)
