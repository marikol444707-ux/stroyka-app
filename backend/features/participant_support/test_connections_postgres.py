"""Owner consent connects a cabinet to one buyer; it never claims receipt history."""
import importlib
import os
import uuid
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from types import SimpleNamespace
from psycopg2.errors import RaiseException, ForeignKeyViolation

from . import test_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupplierConnectionsPostgresTests(unittest.TestCase):
    sql, api = support.ParticipantSupportPostgresTests.sql, support.ParticipantSupportPostgresTests.api

    @classmethod
    def setUpClass(cls):
        support.ParticipantSupportPostgresTests.setUpClass.__func__(cls)
        cls.sql(cls, importlib.import_module('migrations.versions.0038_supplier_customer_team').SCHEMA_SQL)
        cls.sql(cls, importlib.import_module('migrations.versions.0095_supplier_buyer_connections').SCHEMA_SQL)
        patch.dict(os.environ, PARTICIPANT_CONNECTIONS_ENABLED='1').start()

    def pair(self, company=2, account=1):
        inn = '77'+str(uuid.uuid4().int % 10**8).zfill(8)
        source = self.sql('INSERT INTO suppliers(name,inn) VALUES(%s,%s) RETURNING id', ('Synthetic receipt card', inn))[0][0]
        target = self.sql('INSERT INTO suppliers(name,inn,user_id) VALUES(%s,%s,%s) RETURNING id',
                          ('Synthetic existing cabinet', inn, self.fixture['users']['supplier']['id']))[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)', (company,account,source))
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(3,1,%s)', (target,))
        return source,target

    def path(self, source, company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests'

    def propose(self, source, target, company=2, **kwargs):
        version = self.sql('SELECT version FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s', (company,source))[0][0]
        body = dict(targetSupplierId=target, expectedSourceVersion=version, requestId=str(uuid.uuid4()), confirmed=True)
        body.update(kwargs.pop('body', {}))
        return self.api('admin','POST',self.path(source,company),body,**kwargs)

    def decide(self, request, action='accept', actor='supplier', **kwargs):
        return self.api(actor,'POST',f"/supplier/connection-requests/{request['id']}/{action}", {'expectedVersion':1,'confirmed':True},**kwargs)

    def test_00_empty_migration_replay_and_downgrade(self):
        migration=importlib.import_module('migrations.versions.0095_supplier_buyer_connections')
        conn=self.main.get_db()
        try:
            with conn,conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade();migration.upgrade();migration.upgrade()
        finally:conn.close()
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_buyer_connection_requests'),[(0,)])

    def test_01_consent_adds_only_exact_relationship_and_preserves_history(self):
        source,target = self.pair()
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,200,50),(3,%s,999,0)', (source,target))
        before = {table:self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id') for table in ('suppliers','supplier_invoices','users','invite_codes')}
        request = self.propose(source,target)
        self.assertEqual(request['status'],'pending')
        self.assertEqual(self.sql('SELECT id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[])
        inbox = self.api('supplier','GET','/supplier/connection-requests')
        item = next(r for r in inbox['items'] if r['id']==request['id'])
        self.assertEqual(item['companyId'],2)
        self.assertNotIn('amount',str(item)); self.assertNotIn('ownerUserId',str(item))
        result = self.decide(request)
        self.assertEqual(result['status'],'accepted')
        self.assertEqual(self.decide(request),result)
        self.assertEqual(self.sql('SELECT supplier_id,platform_account_id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[(target,1)])
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.sql('SELECT count(*) FROM user_company_roles WHERE user_id=%s AND company_id=2',(self.fixture['users']['supplier']['id'],)),[(0,)])
        for table,rows in before.items(): self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))
        visibility = self.api('admin','GET',f'/system/companies/2/participants/{target}/connection-preview')
        self.assertEqual(visibility['currentVisibility'],{'invoices':0,'offers':0})
        old=self.api('admin','GET',f'/system/companies/2/participants/{source}/connection-preview')
        self.assertEqual(old['scenario'],'merge_cards')
        self.assertNotIn('OWNER_VERIFICATION_REQUIRED',[b['code'] for b in old['blockers']])
        self.assertIn('HISTORICAL_ACCESS_REVIEW_REQUIRED',[b['code'] for b in old['blockers']])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_buyer_connection_accepted' AND company_id=2 AND entity_id=%s",(target,)),[(1,)])

    def test_wrong_user_ids_flags_and_forged_payload_never_grant(self):
        source,target = self.pair()
        request = self.propose(source,target)
        self.decide(request,actor='director',expected=403)
        other = self.sql("INSERT INTO users(name,email,password,role,active) VALUES('Synthetic wrong supplier',%s,'unused','поставщик',TRUE) RETURNING id",('synthetic-'+str(uuid.uuid4())+'@local.invalid',))[0][0]
        self.fixture['users']['other_supplier']=dict(id=other,role='поставщик',name='Synthetic wrong supplier')
        self.decide(request,actor='other_supplier',expected=404)
        self.assertNotIn(request['id'],[r['id'] for r in self.api('other_supplier','GET','/supplier/connection-requests')['items']])
        self.api('admin','GET',self.path(source,3),expected=404)
        self.propose(source,target,body={'ownerUserId':other},expected=422)
        self.propose(source,target,body={'expectedSourceVersion':True},expected=422)
        self.propose(source,target,body={'confirmed':False},expected=422)
        with patch.dict(os.environ,PARTICIPANT_CONNECTIONS_ENABLED='0'):
            self.decide(request,expected=503)
        self.assertEqual(self.sql('SELECT id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[])

    def test_revoke_decline_expiry_and_role_epoch_invalidate_open_requests(self):
        source,target = self.pair(); request=self.propose(source,target)
        revoked=self.api('admin','POST',self.path(source)+f"/{request['id']}/revoke",{'expectedVersion':1,'confirmed':True})
        self.assertEqual(revoked['status'],'revoked'); self.decide(request,expected=409)
        source,target=self.pair(); request=self.propose(source,target)
        self.assertEqual(self.decide(request,'decline')['status'],'declined'); self.decide(request,expected=409)
        source,target=self.pair(); request=self.propose(source,target)
        self.sql("""ALTER TABLE supplier_buyer_connection_requests DISABLE TRIGGER supplier_buyer_connection_immutable;
            UPDATE supplier_buyer_connection_requests SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s;
            ALTER TABLE supplier_buyer_connection_requests ENABLE TRIGGER supplier_buyer_connection_immutable""",(request['id'],))
        self.decide(request,expected=409)
        for actor in ('supplier','admin'):
            source,target=self.pair(); request=self.propose(source,target)
            uid=self.fixture['users'][actor]['id']
            self.sql('UPDATE users SET active=FALSE WHERE id=%s',(uid,)); self.sql('UPDATE users SET active=TRUE WHERE id=%s',(uid,))
            self.decide(request,expected=409)
            self.assertEqual(self.sql('SELECT id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[])

    def test_drift_owner_change_legal_conflict_and_disabled_buyer_block(self):
        mutations=[('UPDATE company_supplier_links SET version=version+1 WHERE supplier_id=%s',lambda s,t:s),
                   ("UPDATE suppliers SET inn='7700000999' WHERE id=%s",lambda s,t:t),
                   ('UPDATE suppliers SET user_id=NULL WHERE id=%s',lambda s,t:t)]
        for sql,which in mutations:
            source,target=self.pair(); request=self.propose(source,target)
            self.sql(sql,(which(source,target),)); self.decide(request,expected=403 if 'user_id' in sql else 409)
        source,target=self.pair(); request=self.propose(source,target)
        self.sql('UPDATE companies SET active=FALSE WHERE id=2')
        try: self.decide(request,expected=409)
        finally:self.sql('UPDATE companies SET active=TRUE WHERE id=2')
        source,target=self.pair()
        self.sql("UPDATE suppliers SET ogrn='1100000000001' WHERE id=%s",(source,))
        self.sql("UPDATE suppliers SET ogrn='1100000000002' WHERE id=%s",(target,))
        self.propose(source,target,expected=409)

    def test_replay_and_parallel_acceptance_are_atomic(self):
        source,target=self.pair(); key=str(uuid.uuid4())
        request=self.propose(source,target,body={'requestId':key})
        self.assertEqual(self.propose(source,target,body={'requestId':key})['id'],request['id'])
        self.propose(source,target,body={'requestId':key,'expectedSourceVersion':2},expected=409)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.decide(request),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql('SELECT count(*) FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[(1,)])

    def test_owner_reassignment_then_restore_does_not_revive_consent(self):
        source,target=self.pair(); request=self.propose(source,target)
        self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s',(target,))
        self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(self.fixture['users']['supplier']['id'],target))
        self.decide(request,expected=409)
        self.assertNotIn(request['id'],[r['id'] for r in self.api('supplier','GET','/supplier/connection-requests')['items']])
        self.assertEqual(self.sql('SELECT id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[])

    def test_expiry_while_waiting_for_company_lock_cannot_grant(self):
        source,target=self.pair(); request=self.propose(source,target)
        # Synthetic fixture clock only; public commands cannot rewrite deadlines.
        self.sql("""ALTER TABLE supplier_buyer_connection_requests DISABLE TRIGGER supplier_buyer_connection_immutable;
            UPDATE supplier_buyer_connection_requests SET expires_at=clock_timestamp()+INTERVAL '3 seconds' WHERE id=%s;
            ALTER TABLE supplier_buyer_connection_requests ENABLE TRIGGER supplier_buyer_connection_immutable""",(request['id'],))
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn.cursor() as cur:cur.execute('SELECT id FROM companies WHERE id=2 FOR UPDATE')
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(lambda:self.decide(request,expected=409))
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    waiting=self.sql("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query LIKE 'SELECT id,name,platform_account_id,active FROM companies%%'")[0][0]
                    if waiting:break
                    time.sleep(.02)
                self.assertGreater(waiting,0,'Acceptance did not reach the company lock')
                while time.monotonic()<deadline:
                    if self.sql('SELECT expires_at<=clock_timestamp() FROM supplier_buyer_connection_requests WHERE id=%s',(request['id'],))[0][0]:break
                    time.sleep(.02)
                conn.rollback()
                future.result(timeout=10)
        finally:conn.rollback();conn.close()
        self.assertEqual(self.sql('SELECT id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[])

    def test_simultaneous_requests_and_audit_failure_do_not_leave_partial_grant(self):
        source,target=self.pair(); key=str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.propose(source,target,body={'requestId':key}),range(2)))
        self.assertEqual(results[0]['id'],results[1]['id'])
        with patch('backend.features.participant_support.connections.audit',side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaisesRegex(RuntimeError,'Synthetic audit failure'):self.decide(results[0])
        self.assertEqual(self.sql('SELECT id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[])
        self.assertEqual(self.sql('SELECT status FROM supplier_buyer_connection_requests WHERE id=%s',(results[0]['id'],)),[('pending',)])
        self.assertEqual(self.decide(results[0])['status'],'accepted')

    def test_team_leader_is_not_primary_owner_and_database_evidence_cannot_be_rewritten(self):
        source,target=self.pair(); request=self.propose(source,target)
        uid=self.sql("INSERT INTO users(name,email,password,role,active) VALUES('Synthetic delegated leader',%s,'unused','поставщик',TRUE) RETURNING id",(str(uuid.uuid4())+'@local.invalid',))[0][0]
        self.fixture['users']['delegated']=dict(id=uid,name='Synthetic delegated leader',role='поставщик')
        self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role,active) VALUES(%s,%s,'leader',TRUE)",(target,uid))
        self.assertNotIn(request['id'],[r['id'] for r in self.api('delegated','GET','/supplier/connection-requests')['items']])
        self.decide(request,actor='delegated',expected=404)
        with self.assertRaises(RaiseException):self.sql('UPDATE supplier_buyer_connection_requests SET company_id=3 WHERE id=%s',(request['id'],))
        with self.assertRaises(RaiseException):self.sql('DELETE FROM supplier_buyer_connection_requests WHERE id=%s',(request['id'],))
        with self.assertRaises(ForeignKeyViolation):
            self.sql("""INSERT INTO supplier_buyer_connection_requests
                (id,company_id,platform_account_id,source_supplier_id,target_supplier_id,source_version,
                owner_user_id,owner_epoch,target_owner_epoch,created_by_user_id,issuer_epoch,operation_key,evidence)
                SELECT %s,3,999,source_supplier_id,target_supplier_id,source_version,owner_user_id,owner_epoch,
                target_owner_epoch,created_by_user_id,issuer_epoch,%s,evidence FROM supplier_buyer_connection_requests WHERE id=%s""",
                (str(uuid.uuid4()),str(uuid.uuid4()),request['id']))
        migration=importlib.import_module('migrations.versions.0095_supplier_buyer_connections')
        conn=self.main.get_db()
        try:
            with self.assertRaises(RaiseException),conn,conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade()
        finally:conn.close()

    def test_fifty_buyers_two_accounts_reuse_same_cabinet(self):
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(198,'Synthetic connection buyers','pro','active')")
        source,target=self.pair()
        before=self.sql('SELECT count(*) FROM users'),self.sql('SELECT count(*) FROM suppliers')
        for cid in range(600,650):
            account=1 if cid<625 else 198
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,'Synthetic consent buyer',%s,TRUE,'pro')",(cid,account))
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)',(cid,account,source))
            # Source sharedness is a merge blocker, not a reason to hand over history.
            request=self.propose(source,target,cid)
            self.assertEqual(self.decide(request)['status'],'accepted')
        self.assertEqual(before,(self.sql('SELECT count(*) FROM users'),self.sql('SELECT count(*) FROM suppliers')))
        self.assertEqual(self.sql('SELECT count(*) FROM company_supplier_links WHERE supplier_id=%s AND company_id>=600',(target,)),[(50,)])
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
