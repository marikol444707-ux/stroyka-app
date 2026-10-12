"""Real signed actors and isolated PostgreSQL, without business writes or sends."""
import importlib
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from .test_postgres import ParticipantSupportPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupportCapabilitiesPostgresTests(unittest.TestCase):
    sql, api, seed, failure, report = Base.sql, Base.api, Base.seed, Base.failure, Base.report

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)
        cls.sql(cls, importlib.import_module('migrations.versions.0038_supplier_customer_team').SCHEMA_SQL)
        patch.dict(os.environ, PARTICIPANT_SUPPORT_ACCESS_ENABLED='1').start()
        for key in ('support', 'other_support'):
            uid = cls.sql(cls, "INSERT INTO users(name,role,active) VALUES(%s,'platform_support',TRUE) RETURNING id", (key,))[0][0]
            cls.fixture['users'][key] = dict(id=uid, role='platform_support', name=key)
        schema = importlib.import_module('backend.features.participant_support.capability_schema')
        cls.sql(cls, schema.SCHEMA_SQL)
        cls.sql(cls, importlib.import_module('backend.features.participant_support.security_schema').SCHEMA_SQL)

    def ticket(self):
        return self.report(self.failure(self.seed(True), 'SUPPLIER_ACCOUNT_EXISTS'))['id']

    def path(self, ticket, company=2):
        return f'/system/companies/{company}/participant-tickets/{ticket}/support-access'

    def grant(self, ticket, **changes):
        return self.api('admin', 'POST', self.path(ticket), dict(
            assigneeId=self.fixture['users']['support']['id'], expiresInMinutes=60,
            action='diagnostic.read', reason='Inspect invitation refusal', **changes))

    def read(self, grant, actor='support', expected=200, **changes):
        return self.api(actor, 'GET', '/participant-support/workspace/' + grant['id'] + '/diagnostic',
                        expected=expected, **changes)

    def test_00_empty_migration_downgrade_and_replay(self):
        from types import SimpleNamespace
        migration = importlib.import_module('migrations.versions.0097_participant_support_access')
        security_migration = importlib.import_module('migrations.versions.0098_participant_support_denials')
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur, patch.object(migration, 'op', SimpleNamespace(execute=cur.execute)), patch.object(security_migration, 'op', SimpleNamespace(execute=cur.execute)):
                self.assertEqual(self.sql('SELECT count(*) FROM participant_support_access'), [(0,)])
                security_migration.downgrade()
                migration.downgrade()
                cur.execute("SELECT to_regclass('public.participant_support_access')")
                self.assertIsNone(cur.fetchone()[0])
                migration.upgrade()
                migration.upgrade()
                security_migration.upgrade()
                security_migration.upgrade()
            conn.commit()
        finally:
            conn.close()

    def test_scoped_diagnostic_and_audit_no_business_mutation(self):
        tid = self.ticket()
        before = self.sql('SELECT count(*) FROM invite_codes'), self.sql('SELECT count(*) FROM supplier_invoices')
        grant = self.grant(tid)
        card = self.read(grant)
        self.assertEqual(card['ticketId'], tid)
        self.assertEqual(card['companyId'], 2)
        self.assertNotIn('reporter_id', card)
        self.assertNotIn('email', str(card))
        self.assertNotIn('sourceDetail', card['context'])
        audit = self.api('admin', 'GET', self.path(tid))
        self.assertEqual([e['action'] for e in audit['items'][0]['history']], ['granted', 'diagnostic.read'])
        self.assertEqual((self.sql('SELECT count(*) FROM invite_codes'), self.sql('SELECT count(*) FROM supplier_invoices')), before)

    def test_other_actor_cannot_use_or_discover_grant(self):
        grant = self.grant(self.ticket())
        self.read(grant, 'other_support', 404)
        self.read(grant, 'director', 403)
        self.read(grant, 'admin', 403)
        self.assertEqual(self.api('other_support', 'GET', '/participant-support/workspace')['items'], [])

    def test_company_and_action_forgery_do_not_expand_access(self):
        tid = self.ticket()
        grant = self.grant(tid)
        self.api('admin', 'GET', self.path(tid, 3), expected=404)
        self.api('admin', 'POST', self.path(tid, 3), dict(assigneeId=self.fixture['users']['support']['id'], action='diagnostic.read', expiresInMinutes=60, reason='Synthetic reason'), expected=404)
        for path in ('/system/companies/2/participants', '/system/companies/3/participant-tickets',
                     '/supplier-invoices', '/tenant-files/999999', '/tenant-files/999999/content', '/agent-jobs', '/pricelists', '/system/support-sessions'):
            self.api('support', 'GET', path, expected=403, **{'X-Support-Access': grant['id'], 'X-Company-Id': '2'})
        self.api('support', 'POST', '/participant-support/workspace/' + grant['id'] + '/diagnostic', {}, expected=405)
        self.read(grant, **{'X-Company-Id': '3'})  # Headers cannot replace the server-owned scope.

    def test_unknown_action_and_payload_are_rejected(self):
        tid = self.ticket()
        for extra in ({'action': 'payment.write'}, {'companyId': 3}, {'expiresInMinutes': 1441},
                      {'expiresInMinutes': True}, {'assigneeId': self.fixture['users']['director']['id']}):
            body = dict(assigneeId=self.fixture['users']['support']['id'], expiresInMinutes=60,
                        action='diagnostic.read', reason='Synthetic reason')
            body.update(extra)
            self.api('admin', 'POST', self.path(tid), body, expected=422)

    def test_revoke_is_final_and_idempotent_with_use_history(self):
        tid = self.ticket()
        grant = self.grant(tid)
        self.read(grant)
        path = self.path(tid) + '/' + grant['id'] + '/revoke'
        self.api('admin', 'POST', path, {'reason': 'Investigation is complete'})
        self.api('admin', 'POST', path, {'reason': 'Investigation is complete'})
        self.read(grant, expected=403)
        self.assertNotIn(grant['id'], [item['id'] for item in self.api('support', 'GET', '/participant-support/workspace')['items']])
        history = self.api('admin', 'GET', self.path(tid))['items'][0]['history']
        self.assertEqual([e['action'] for e in history], ['granted', 'diagnostic.read', 'revoked'])

    def test_ticket_change_invalidates_old_access_and_reissue_revokes_it(self):
        tid = self.ticket()
        grant = self.grant(tid)
        self.api('admin', 'PATCH', self.path(tid).replace('/support-access', ''), {'status': 'in_progress', 'expectedVersion': 1})
        self.read(grant, expected=403)
        fresh = self.grant(tid)
        self.assertNotEqual(fresh['id'], grant['id'])
        self.read(fresh)
        self.read(grant, expected=403)

    def test_actor_and_issuer_aba_never_reactivate_old_access(self):
        for actor in ('support', 'admin'):
            grant = self.grant(self.ticket())
            uid = self.fixture['users'][actor]['id']
            self.sql('UPDATE users SET active=FALSE WHERE id=%s', (uid,))
            self.read(grant, expected=403)
            self.sql('UPDATE users SET active=TRUE WHERE id=%s', (uid,))
            self.read(grant, expected=403)

    def test_expired_grant_and_old_session_label_grant_no_authority(self):
        grant = self.grant(self.ticket())
        self.sql("INSERT INTO platform_support_sessions(company_id,platform_account_id,reason,scope,status,expires_at) VALUES(2,1,'Legacy label','manage','active',NOW()+INTERVAL '1 day')")
        self.sql('''INSERT INTO participant_support_access
            (id,company_id,platform_account_id,ticket_id,ticket_version,assignee_id,assignee_epoch,issuer_id,issuer_epoch,action,reason,created_at,expires_at)
            SELECT '00000000-0000-4000-8000-000000000001',company_id,platform_account_id,ticket_id,ticket_version,assignee_id,assignee_epoch,issuer_id,issuer_epoch,action,reason,NOW()-INTERVAL '2 minutes',NOW()-INTERVAL '1 second'
            FROM participant_support_access WHERE id=%s''', (grant['id'],))
        self.read({'id': '00000000-0000-4000-8000-000000000001'}, expected=403)
        self.api('support', 'GET', self.path(grant['ticketId']), expected=403)

    def test_disabled_feature_and_missing_schema_fail_closed(self):
        grant = self.grant(self.ticket())
        with patch.dict(os.environ, PARTICIPANT_SUPPORT_ACCESS_ENABLED='0'):
            self.read(grant, expected=503)
        self.sql('ALTER TABLE participant_support_access RENAME TO participant_support_access_hidden')
        try:
            self.read(grant, expected=503)
        finally:
            self.sql('ALTER TABLE participant_support_access_hidden RENAME TO participant_support_access')

    def test_empty_migration_replay_and_filled_downgrade_preserve_history(self):
        import psycopg2
        from types import SimpleNamespace
        self.grant(self.ticket())
        migration = importlib.import_module('migrations.versions.0097_participant_support_access')
        # This test uses a transaction/savepoint so earlier synthetic grants remain.
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur, patch.object(migration, 'op', SimpleNamespace(execute=cur.execute)):
                migration.upgrade()
                cur.execute('SAVEPOINT downgrade_attempt')
                with self.assertRaises(psycopg2.Error):
                    migration.downgrade()
                cur.execute('ROLLBACK TO SAVEPOINT downgrade_attempt')
                cur.execute('SELECT count(*) FROM participant_support_access_events')
                self.assertGreater(cur.fetchone()[0], 0)
            conn.rollback()
        finally:
            conn.close()

    def test_database_rejects_scope_rebinding_and_audit_tampering(self):
        import psycopg2
        grant = self.grant(self.ticket())
        for query, args in (
            ('UPDATE participant_support_access SET company_id=3 WHERE id=%s', (grant['id'],)),
            ("UPDATE participant_support_access SET expires_at=expires_at+INTERVAL '1 minute' WHERE id=%s", (grant['id'],)),
            ('DELETE FROM participant_support_access WHERE id=%s', (grant['id'],)),
            ('DELETE FROM participant_support_access_events WHERE access_id=%s', (grant['id'],)),
            ('UPDATE participant_support_access_events SET actor_id=%s WHERE access_id=%s', (self.fixture['users']['admin']['id'], grant['id'])),
        ):
            conn = self.main.get_db()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    with self.assertRaises(psycopg2.Error):
                        cur.execute(query, args)
                conn.rollback()
            finally:
                conn.close()
        self.read(grant)

    def test_cookie_session_uses_the_same_boundary_and_revocation(self):
        tid = self.ticket()
        grant = self.grant(tid)
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                token = self.main._create_auth_session(cur, self.fixture['users']['support'], None, True)
            conn.commit()
        finally:
            conn.close()
        self.client.cookies.set(self.main.AUTH_SESSION_COOKIE_NAME, token)
        try:
            response = self.client.get('/participant-support/workspace/' + grant['id'] + '/diagnostic')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.headers['cache-control'], 'private, no-store')
            self.assertEqual(self.client.get('/pricelists').status_code, 403)
            self.api('admin', 'POST', self.path(tid)+'/'+grant['id']+'/revoke', {'reason':'Cookie access revoked'})
            self.assertEqual(self.client.get('/participant-support/workspace/' + grant['id'] + '/diagnostic').status_code, 403)
        finally:
            self.client.cookies.clear()

    def test_missing_auth_and_disabled_company_return_no_diagnostic(self):
        grant = self.grant(self.ticket())
        self.assertEqual(self.client.get('/participant-support/workspace/' + grant['id'] + '/diagnostic').status_code, 401)
        self.sql('UPDATE companies SET active=FALSE WHERE id=2')
        try:
            self.read(grant, expected=404)
            self.assertNotIn(grant['id'], [item['id'] for item in self.api('support','GET','/participant-support/workspace')['items']])
        finally:
            self.sql('UPDATE companies SET active=TRUE WHERE id=2')

    def test_reader_and_revoker_serialize_without_post_revoke_uses(self):
        tid = self.ticket()
        grant = self.grant(tid)
        gate = Barrier(7)
        token = self.main.create_auth_token(self.fixture['users']['support'], two_factor_passed=True)
        path = '/participant-support/workspace/' + grant['id'] + '/diagnostic'
        def read():
            gate.wait(timeout=10)
            return self.client.get(path, headers={'Authorization':'Bearer '+token}).status_code
        def revoke():
            gate.wait(timeout=10)
            return self.api('admin','POST',self.path(tid)+'/'+grant['id']+'/revoke',{'reason':'Concurrent access revoked'})
        with ThreadPoolExecutor(max_workers=7) as pool:
            readers = [pool.submit(read) for _ in range(6)]
            revoker = pool.submit(revoke)
            revoker.result(timeout=15)
            codes = [reader.result(timeout=15) for reader in readers]
        self.assertTrue(all(code in (200,403) for code in codes), codes)
        self.read(grant, expected=403)
        self.assertEqual(self.sql("SELECT count(*) FROM participant_support_access_events e JOIN participant_support_access g ON g.id=e.access_id WHERE g.id=%s AND e.action='diagnostic.read' AND e.created_at>g.revoked_at",(grant['id'],)), [(0,)])

    def test_role_aba_invalidates_grant_after_returning_to_support(self):
        grant = self.grant(self.ticket())
        uid = self.fixture['users']['support']['id']
        self.sql("UPDATE users SET role='мастер' WHERE id=%s", (uid,))
        try:
            self.read(grant, expected=403)
        finally:
            self.sql("UPDATE users SET role='platform_support' WHERE id=%s", (uid,))
        self.read(grant, expected=403)

    def test_closed_ticket_and_support_mutations_are_rejected(self):
        tid = self.ticket()
        grant = self.grant(tid)
        path = self.path(tid).replace('/support-access','')
        for version, status in ((1,'in_progress'),(2,'resolved'),(3,'closed')):
            self.api('admin','PATCH',path,dict(status=status,expectedVersion=version,result='Original scenario checked',verified=True))
        self.read(grant, expected=403)
        self.api('admin','POST',self.path(tid),dict(assigneeId=self.fixture['users']['support']['id'],action='diagnostic.read',expiresInMinutes=60,reason='Synthetic reason'),expected=409)
        self.api('support','PATCH',path,dict(status='in_progress',expectedVersion=4),expected=403)
        self.api('support','POST',self.path(tid)+'/'+grant['id']+'/revoke',{'reason':'Synthetic revoke'},expected=403)
        self.api('admin','PATCH',path,dict(status='in_progress',expectedVersion=4))
        self.read(grant, expected=403)
