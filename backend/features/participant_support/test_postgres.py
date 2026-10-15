"""Synthetic authenticated PostgreSQL evidence → ticket → organization admin."""
import os
import unittest
import time
from statistics import median
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from ..invite_codes import test_supplier_registration_postgres as base
from .schema import SCHEMA_SQL


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ParticipantSupportPostgresTests(unittest.TestCase):
    sql = base.SupplierRegistrationPostgresTests.sql
    api = base.SupplierRegistrationPostgresTests.api

    @classmethod
    def setUpClass(cls):
        base.SupplierRegistrationPostgresTests.setUpClass.__func__(cls)
        cls.sql(cls,SCHEMA_SQL)
        cls.addClassCleanup(patch.stopall)
        patch.dict(os.environ,PARTICIPANT_SUPPORT_ENABLED='1').start()
        admin_id = cls.sql(cls,"INSERT INTO users(name,email,password,role,active) VALUES('Synthetic platform admin','admin@local.invalid','unused','system_owner',TRUE) RETURNING id")[0][0]
        cls.fixture['users']['admin'] = dict(id=admin_id,role='system_owner',name='Synthetic platform admin')

    def seed(self, owned=False, shared=False):
        sid = self.sql('INSERT INTO suppliers(name,user_id) VALUES(%s,%s) RETURNING id',
                       ('Synthetic supplier',self.fixture['users']['supplier']['id'] if owned else None))[0][0]
        self.sql("INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id,source_type,source_detail) VALUES(2,1,%s,'warehouse_invoice','Synthetic receipt')", (sid,))
        if shared:
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(3,1,%s)',(sid,))
        return sid

    def failure(self,sid,code):
        before = self.sql('SELECT count(*) FROM invite_codes')
        response = self.client.post('/invite-codes',json={'role':'поставщик','supplierId':sid,'expiresInDays':1},headers={
            'Authorization':'Bearer '+self.main.create_auth_token(self.fixture['users']['director'],two_factor_passed=True),
            'X-Company-Id':'2','X-Company-Mode':'company'})
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(response.headers['x-access-reason'],code)
        self.assertEqual(self.sql('SELECT count(*) FROM invite_codes'),before)
        return response.headers['x-access-diagnostic']

    def report(self,evidence,**extra):
        return self.api('director','POST','/participant-support/tickets',
                        {'diagnosticId':evidence,'comment':'Please connect existing account'},**{'X-Company-Id':'2',**extra})

    def test_00_empty_migration_downgrade_and_replay(self):
        import importlib
        from types import SimpleNamespace
        migration=importlib.import_module('migrations.versions.0094_participant_access_support')
        self.assertEqual(self.sql('SELECT count(*) FROM participant_access_diagnostics'),[(0,)])
        conn=self.main.get_db()
        try:
            conn.autocommit=False
            with conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade()
                cur.execute("SELECT to_regclass('public.participant_access_tickets')")
                self.assertIsNone(cur.fetchone()[0])
                migration.upgrade()
                migration.upgrade()
            conn.commit()
        finally:conn.close()
        self.assertEqual(self.sql('SELECT count(*) FROM participant_access_tickets'),[(0,)])

    def test_distinct_refusals_survive_rollback_no_business_mutation(self):
        for owned,shared,code in ((True,False,'SUPPLIER_ACCOUNT_EXISTS'),(False,True,'SUPPLIER_SHARED_CARD')):
            sid = self.seed(owned,shared)
            before = self.sql('SELECT to_jsonb(s) FROM suppliers s WHERE id=%s',(sid,))
            evidence = self.failure(sid,code)
            self.assertEqual(self.sql('SELECT to_jsonb(s) FROM suppliers s WHERE id=%s',(sid,)),before)
            self.assertEqual(self.sql('SELECT count(*) FROM participant_access_tickets WHERE diagnostic_id=%s',(evidence,)),[(0,)])
            ticket = self.report(evidence)
            self.assertEqual(self.report(evidence)['id'],ticket['id'])
            card = self.api('admin','GET',f"/system/companies/2/participant-tickets/{ticket['id']}")
            self.assertEqual(card['context']['sourceType'],'warehouse_invoice')
            self.assertNotIn('sourceDetail',card['context'])
            self.assertEqual(card['reason_code'],code)
            self.assertEqual(card['context']['action'],'create_supplier_invite')
            self.assertEqual(len(card['history']),1)

    def test_forgery_other_actor_other_company_and_revocation(self):
        evidence = self.failure(self.seed(True),'SUPPLIER_ACCOUNT_EXISTS')
        self.api('stranger','POST','/participant-support/tickets',{'diagnosticId':evidence,'comment':'Synthetic problem'},expected=404,**{'X-Company-Id':'3'})
        self.api('director','POST','/participant-support/tickets',{'diagnosticId':evidence,'comment':'Synthetic problem','companyId':3},expected=422,**{'X-Company-Id':'2'})
        self.api('director','GET','/system/companies/2/participants',expected=403)
        self.api('admin','GET','/system/companies/999999/participants',expected=404)
        director_id = self.fixture['users']['director']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(director_id,))
        try:
            self.report(evidence,expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(director_id,))

    def test_status_version_closure_and_reporter_result(self):
        ticket = self.report(self.failure(self.seed(True),'SUPPLIER_ACCOUNT_EXISTS'))
        path = f"/system/companies/2/participant-tickets/{ticket['id']}"
        for invalid in ([],{},None,42):
            self.api('admin','PATCH',path,{'status':invalid,'expectedVersion':1},expected=422)
        self.api('admin','PATCH',path,{'status':'closed','expectedVersion':1,'result':'Verified scenario','verified':True},expected=409)
        self.api('admin','PATCH',path,{'status':'in_progress','expectedVersion':1})
        self.api('admin','PATCH',path,{'status':'resolved','expectedVersion':1,'result':'Verified scenario'},expected=409)
        self.api('admin','PATCH',path,{'status':'resolved','expectedVersion':2,'result':'Connection reviewed'})
        self.api('admin','PATCH',path,{'status':'closed','expectedVersion':3,'result':'Scenario verified'},expected=422)
        self.api('admin','PATCH',path,{'status':'closed','expectedVersion':3,'result':'Scenario verified','verified':True})
        mine = self.api('director','GET','/participant-support/tickets',**{'X-Company-Id':'2'})
        item = next(row for row in mine['items'] if row['id']==ticket['id'])
        self.assertEqual(item['result'],'Scenario verified')
        self.assertNotIn('context',item)
        own=self.api('director','GET',f"/participant-support/tickets/{ticket['id']}",**{'X-Company-Id':'2'})
        self.assertEqual(own['result'],'Scenario verified')
        self.api('stranger','GET',f"/participant-support/tickets/{ticket['id']}",expected=404,**{'X-Company-Id':'3'})
        self.api('admin','GET',path.replace('/2/','/3/'),expected=404)

    def test_fifty_organizations_separate_accounts_search_and_pagination(self):
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(99,'Synthetic independent account','pro','active') ON CONFLICT DO NOTHING")
        sid = self.seed(True)
        for cid in range(100,150):
            account = 1 if cid<125 else 99
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,%s,%s,TRUE,'pro')",(cid,'Synthetic organization '+str(cid),account))
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)',(cid,account,sid))
        for cid in (100,149):
            rows = self.api('admin','GET',f'/system/companies/{cid}/participants')['items']
            self.assertEqual([row['id'] for row in rows],[sid])
            self.assertNotIn('user_id',rows[0])
            self.assertNotIn('bank',rows[0])
            self.assertNotIn('source_detail',rows[0])
        for n in range(110):
            other = self.sql("INSERT INTO suppliers(name) VALUES(%s) RETURNING id",('Synthetic page '+str(n),))[0][0]
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(149,99,%s)',(other,))
        first = self.api('admin','GET','/system/companies/149/participants?search=Synthetic%20page&limit=25')
        second = self.api('admin','GET','/system/companies/149/participants?search=Synthetic%20page&limit=25&offset=25')
        self.assertTrue(first['hasMore'])
        self.assertFalse({r['id'] for r in first['items']} & {r['id'] for r in second['items']})
        self.api('director','GET','/suppliers',expected=403,**{'X-Company-Id':'149'})
        timings=[]
        for _ in range(20):
            start=time.perf_counter()
            self.api('admin','GET','/system/companies/149/participants?search=Synthetic%20page&limit=25')
            timings.append((time.perf_counter()-start)*1000)
        timings.sort()
        print('SUPPORT_REGISTRY_BASELINE synthetic=50_organizations/111_catalog_rows samples=20 median_ms=%.2f p95_ms=%.2f' % (median(timings),timings[18]))

    def test_disabled_feature_and_expired_evidence(self):
        evidence = self.failure(self.seed(True),'SUPPLIER_ACCOUNT_EXISTS')
        self.sql("UPDATE participant_access_diagnostics SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(evidence,))
        self.report(evidence,expected=409)
        with patch.dict(os.environ,PARTICIPANT_SUPPORT_ENABLED='0'):
            self.report(evidence,expected=503)
            self.api('admin','GET','/system/companies/2/participants',expected=503)

    def test_evidence_storage_failure_preserves_original_refusal(self):
        sid=self.seed(True)
        with patch('backend.features.participant_support.service.record_failure',side_effect=RuntimeError('must not expose request or credentials')):
            result=self.api('director','POST','/invite-codes',{'role':'поставщик','supplierId':sid},expected=409,**{'X-Company-Id':'2'})
        self.assertEqual(result['reasonCode'],'SUPPLIER_ACCOUNT_EXISTS')
        self.assertIsNone(result['diagnosticId'])
        self.assertNotIn('credentials',str(result))

    def test_concurrent_report_has_one_ticket_one_event(self):
        evidence=self.failure(self.seed(True),'SUPPLIER_ACCOUNT_EXISTS')
        token=self.main.create_auth_token(self.fixture['users']['director'],two_factor_passed=True)
        from fastapi.testclient import TestClient
        def send(_):
            with TestClient(self.main.app) as client:
                return client.post('/participant-support/tickets',json={'diagnosticId':evidence,'comment':'Synthetic concurrent help'},
                    headers={'Authorization':'Bearer '+token,'X-Company-Id':'2'})
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies=list(pool.map(send,range(4)))
        self.assertEqual([r.status_code for r in replies],[200]*4)
        ids={r.json()['id'] for r in replies}
        self.assertEqual(len(ids),1)
        self.assertEqual(self.sql('SELECT count(*) FROM participant_access_ticket_events WHERE ticket_id=%s',(ids.pop(),)),[(1,)])

    def test_cross_company_diagnostic_rate_limit_is_atomic(self):
        from fastapi.testclient import TestClient
        from uuid import uuid4
        uid=self.sql("INSERT INTO users(name,email,password,role,active) VALUES('Synthetic limit actor','limit@local.invalid','unused','директор',TRUE) RETURNING id")[0][0]
        actor=dict(id=uid,role='директор',name='Synthetic limit actor')
        sid=self.seed(True)
        # Two company locks cannot protect a reporter-wide limit; race at 19/20.
        for _ in range(19):
            self.sql("""INSERT INTO participant_access_diagnostics(id,company_id,platform_account_id,reporter_id,participant_type,participant_id,reason_code,context,expires_at)
                VALUES(%s,2,1,%s,'supplier',%s,'SUPPLIER_ACCOUNT_EXISTS','{}',NOW()-INTERVAL '1 second')""",(str(uuid4()),uid,sid))
        for cid in (2000,2001):
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,'Synthetic rate limit',1,TRUE,'pro')",(cid,))
            self.sql("INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active) VALUES(%s,%s,1,'директор',TRUE)",(uid,cid))
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,1,%s)',(cid,sid))
        token=self.main.create_auth_token(actor,two_factor_passed=True)
        def send(cid):
            with TestClient(self.main.app) as client:
                return client.post('/invite-codes',json={'role':'поставщик','supplierId':sid},headers={
                    'Authorization':'Bearer '+token,'X-Company-Id':str(cid),'X-Company-Mode':'company'})
        with ThreadPoolExecutor(max_workers=2) as pool:replies=list(pool.map(send,(2000,2001)))
        self.assertEqual([r.status_code for r in replies],[409,409])
        self.assertEqual(sum(bool(r.json()['diagnosticId']) for r in replies),1)
        self.assertEqual(self.sql('SELECT count(*) FROM participant_access_diagnostics WHERE reporter_id=%s AND company_id IN (2000,2001)',(uid,)),[(1,)])

    def test_database_guards_and_migration_repeat_downgrade_refusal(self):
        import importlib
        import psycopg2
        from types import SimpleNamespace
        evidence=self.failure(self.seed(True),'SUPPLIER_ACCOUNT_EXISTS')
        ticket=self.report(evidence)
        self.sql(SCHEMA_SQL)
        for statement,params in (
            ('UPDATE participant_access_tickets SET company_id=3 WHERE id=%s',(ticket['id'],)),
            ("UPDATE participant_access_diagnostics SET context='{}' WHERE id=%s",(evidence,)),
            ('DELETE FROM participant_access_ticket_events WHERE ticket_id=%s',(ticket['id'],)),
        ):
            conn=self.main.get_db()
            try:
                conn.autocommit=False
                with conn.cursor() as cur:
                    with self.assertRaises(psycopg2.Error):cur.execute(statement,params)
                conn.rollback()
            finally:conn.close()
        migration=importlib.import_module('migrations.versions.0094_participant_access_support')
        conn=self.main.get_db()
        try:
            conn.autocommit=False
            with conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                with self.assertRaises(psycopg2.Error):migration.downgrade()
            conn.rollback()
        finally:conn.close()
        self.assertEqual(self.sql('SELECT id FROM participant_access_tickets WHERE id=%s',(ticket['id'],)),[(ticket['id'],)])

    def test_support_session_never_grants_pilot_authority_and_admin_revocation(self):
        uid=self.sql("INSERT INTO users(name,email,password,role,active) VALUES('Synthetic support','support@local.invalid','unused','platform_support',TRUE) RETURNING id")[0][0]
        self.fixture['users']['support']=dict(id=uid,role='platform_support',name='Synthetic support')
        self.sql("INSERT INTO platform_support_sessions(company_id,platform_account_id,reason,scope,status,expires_at) VALUES(2,1,'Synthetic expired support','read_only','active',NOW()-INTERVAL '1 second')")
        self.api('support','GET','/system/companies/2/participants',expected=403)
        self.api('support','POST','/participant-support/tickets',{'diagnosticId':'not-valid','comment':'Synthetic'},expected=422)
        admin_id=self.fixture['users']['admin']['id']
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(admin_id,))
        try:self.api('admin','GET','/system/companies/2/participants',expected=403)
        finally:self.sql('UPDATE users SET active=TRUE WHERE id=%s',(admin_id,))
