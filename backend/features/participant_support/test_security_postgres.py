"""Support boundary evidence against the real registered HTTP application."""
import os
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from .test_capabilities_postgres import SupportCapabilitiesPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupportSecurityPostgresTests(unittest.TestCase):
    sql, api, seed, failure, report = Base.sql, Base.api, Base.seed, Base.failure, Base.report
    ticket, path, grant, read = Base.ticket, Base.path, Base.grant, Base.read

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)
        # Exercise the authentication guard with these alternative route gates open.
        patch.dict(os.environ, WAREHOUSE_DISTRIBUTION_ENABLED='1', WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED='1',
                   SUPPLIER_PAYMENTS_ENABLED='1', SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED='1').start()

    def test_refusals_are_retained_without_client_company_or_secrets(self):
        actor = self.fixture['users']['support']['id']
        self.api('support', 'GET', '/supplier-invoices?token=private-probe', expected=403,
                 **{'X-Company-Id': '3', 'X-Support-Access': 'private-probe'})
        rows = self.sql('SELECT actor_id,surface,method,status_code,access_id FROM participant_support_denials WHERE actor_id=%s', (actor,))
        self.assertIn((actor, 'business', 'GET', 403, None), rows)
        self.assertNotIn('private-probe', str(self.sql('SELECT * FROM participant_support_denials')))

    def test_refusal_responses_are_not_cached(self):
        token = self.main.create_auth_token(self.fixture['users']['support'], two_factor_passed=True)
        for path in ('/supplier-invoices', '/participant-support/workspace/00000000-0000-4000-8000-000000000999/diagnostic'):
            response = self.client.get(path,headers={'Authorization':'Bearer '+token})
            self.assertIn(response.status_code,(403,404))
            self.assertEqual(response.headers['cache-control'],'private, no-store')

    def test_revoked_access_denial_is_in_exact_ticket_history(self):
        tid = self.ticket()
        grant = self.grant(tid)
        self.api('admin', 'POST', self.path(tid)+'/'+grant['id']+'/revoke', {'reason': 'Synthetic completed investigation'})
        self.read(grant, expected=403)
        history = self.api('admin', 'GET', self.path(tid))['items'][0]
        self.assertEqual(history['denials'][0]['status_code'], 403)
        self.api('admin', 'GET', self.path(tid, 3), expected=404)

    def test_foreign_uuid_does_not_attribute_attempt_to_foreign_company(self):
        grant = self.grant(self.ticket())
        actor = self.fixture['users']['other_support']['id']
        self.read(grant, actor='other_support', expected=404)
        self.assertEqual(self.sql('SELECT access_id,company_id,ticket_id FROM participant_support_denials WHERE actor_id=%s ORDER BY id DESC LIMIT 1', (actor,)), [(None,None,None)])

    def test_actual_route_dependency_inventory(self):
        from fastapi.routing import APIRoute, APIWebSocketRoute
        def calls(dep):
            return {getattr(dep.call, '__name__', '')}.union(*(calls(child) for child in dep.dependencies))
        protected, alternative = [], []
        non_api = []
        for route in self.main.app.routes:
            self.assertNotIsInstance(route, APIWebSocketRoute)
            if isinstance(route, APIRoute):
                names = calls(route.dependant)
                (protected if 'get_current_user' in names else alternative).append((sorted(route.methods), route.path, sorted(names)))
            else:
                non_api.append(route.path)
        self.assertEqual(non_api, ['/openapi.json','/docs','/docs/oauth2-redirect','/redoc'],
                         'New unauthenticated mount or route requires explicit security review')
        self.assertGreater(len(protected), 100)
        expected = json.loads(Path(__file__).with_name('alternative_auth_inventory.json').read_text())
        self.assertEqual([dict(methods=x[0],path=x[1],dependencies=x[2]) for x in alternative], expected,
                         'New alternative authentication surface requires explicit security review')
        # This is an inventory of actual path templates, not requests to public commands.
        print('SUPPORT_ROUTE_INVENTORY protected=%s alternative=%s' % (len(protected),len(alternative)))
        for item in alternative:
            print('SUPPORT_ALTERNATIVE_AUTH', item)

    def test_every_registered_business_operation_refuses_support_before_handler(self):
        from fastapi.routing import APIRoute
        def calls(dep):
            return {getattr(dep.call, '__name__', '')}.union(*(calls(child) for child in dep.dependencies))
        count = 0
        for route in self.main.app.routes:
            if not isinstance(route, APIRoute) or 'get_current_user' not in calls(route.dependant) or route.path.startswith('/participant-support/workspace'):
                continue
            path = re.sub(r'\{[^}]+\}', '1', route.path)
            for method in sorted(route.methods):
                with self.subTest(method=method, path=route.path):
                    # The authentication dependency denies before any business handler.
                    self.api('support', method, path, {} if method not in ('GET','HEAD') else None, expected=403)
                    count += 1
        self.assertGreater(count, 500)
        print('SUPPORT_BUSINESS_DENIALS', count)

    def test_file_job_and_alternative_key_cannot_reuse_grant(self):
        grant = self.grant(self.ticket())
        for path in ('/uploads/synthetic-private.pdf','/tenant-files/1/content','/agent-jobs/1'):
            self.api('support', 'GET', path, expected=403)
        for path, header in (('/workflow/invoice/preview','X-Workflow-Token'),
                             ('/max/outbox/dispatch','X-Max-Bot-Token'),
                             ('/ai-control/run-all','X-AI-Control-Token')):
            if path.startswith('/workflow/'):
                with patch.object(self.main, 'WORKFLOW_TOKEN', 'synthetic-distinct-service-key'):
                    self.api('support','POST',path,{},expected=403, **{header:grant['id']})
            else:
                # MAX has no service key configured in the network-blocked fixture.
                self.api('support','POST',path,{},expected=503 if path.startswith('/max/') else 403, **{header:grant['id']})
        # JEV is disabled without its dedicated deployment key; a support grant
        # or other service token must not activate the internal import route.
        self.api('support','POST','/internal/jev/job-candidates',{},expected=503,
                 **{'X-JEV-Ingest-Key':grant['id']})

    def test_audit_failure_does_not_open_access(self):
        self.sql('ALTER TABLE participant_support_denials RENAME TO participant_support_denials_hidden')
        try:
            self.api('support','GET','/supplier-invoices',expected=403)
            self.api('support','GET','/participant-support/workspace',expected=503)
        finally:
            self.sql('ALTER TABLE participant_support_denials_hidden RENAME TO participant_support_denials')

    def test_append_only_migration_preserves_denials(self):
        import importlib
        import psycopg2
        from types import SimpleNamespace
        self.api('support','GET','/supplier-invoices',expected=403)
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                for query in ('UPDATE participant_support_denials SET status_code=404', 'DELETE FROM participant_support_denials', 'TRUNCATE participant_support_denials'):
                    cur.execute('SAVEPOINT refusal_guard')
                    with self.assertRaises(psycopg2.Error):
                        cur.execute(query)
                    cur.execute('ROLLBACK TO SAVEPOINT refusal_guard')
                migration = importlib.import_module('migrations.versions.0098_participant_support_denials')
                with patch.object(migration, 'op', SimpleNamespace(execute=cur.execute)), self.assertRaises(psycopg2.Error):
                    migration.downgrade()
            conn.rollback()
        finally:
            conn.close()
