"""Real authenticated editor API and inherited storage checks; fresh Unix-only DB."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
from unittest.mock import patch

from backend.features.material_aliases import test_scoped_postgres as support


class OwnedAliasHttpPostgresTests(support.ScopedAliasPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flag = patch.dict(os.environ, {'COMPANY_MATERIAL_ALIASES_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def api(self, method='GET', path='/company-material-aliases?companyId=2', data=None,
            actor='director', expected=200, **headers):
        token = self.main.create_auth_token(self.fixture['users'][actor], two_factor_passed=True)
        response = self.client.request(method, path, json=data, headers={'Authorization': 'Bearer '+token, **headers})
        self.assertEqual(response.status_code, expected, response.text)
        if expected < 300:
            self.assertEqual(response.headers.get('cache-control'), 'private, no-store')
        return response.json()

    def create(self, **changes):
        return self.api('POST', '/company-material-aliases',
            dict(companyId=2, aliasName='Brand', canonicalName='Cement', expectedAliasId=None, **changes), expected=201)

    def test_http_create_replace_conflict_deactivate_and_history(self):
        first = self.create()
        payload = dict(companyId=2, aliasName='Brand', canonicalName='Updated', expectedAliasId=first['id'])
        newer = self.api('POST', '/company-material-aliases', payload, expected=201)
        self.assertEqual(newer['previousId'], first['id'])
        self.assertNotEqual(newer['id'], first['id'])
        self.assertEqual(newer['createdById'], self.fixture['users']['director']['id'])
        self.api('POST', '/company-material-aliases', payload, expected=409)
        self.api('POST', '/company-material-aliases', {**payload, 'expectedAliasId': None}, expected=409)
        self.assertEqual([row['id'] for row in self.api()['items']], [newer['id']])
        self.api('DELETE', '/company-material-aliases/'+first['id']+'?companyId=2')
        self.assertEqual(self.api()['items'][0]['id'], newer['id'])
        self.api('DELETE', '/company-material-aliases/'+newer['id']+'?companyId=2')
        self.assertEqual(self.api()['items'], [])
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(2,)])

    def test_http_foreign_id_and_project_rejected(self):
        own = self.create()
        self.api('DELETE', '/company-material-aliases/'+own['id']+'?companyId=3', actor='stranger', expected=404)
        self.api('POST', '/company-material-aliases', dict(companyId=3, projectId=self.fixture['projectId'],
            aliasName='Brand', canonicalName='Foreign', expectedAliasId=None), actor='stranger', expected=404)
        self.assertEqual(self.api()['items'][0]['id'], own['id'])
        self.assertEqual(self.api(path='/company-material-aliases?companyId=3', actor='stranger')['items'], [])

    def test_http_project_scope_and_pagination(self):
        company = self.create()
        project = self.create(projectId=self.fixture['projectId'])
        self.assertEqual([r['id'] for r in self.api()['items']], [company['id']])
        path = '/company-material-aliases?companyId=2&projectId='+str(self.fixture['projectId'])
        self.assertEqual([r['id'] for r in self.api(path=path)['items']], [project['id'], company['id']])
        self.assertEqual([r['id'] for r in self.api(path=path+'&limit=1&offset=1')['items']], [company['id']])
        self.api(path=path+'&limit=501', expected=422)

    def test_http_header_conflict_aggregate_and_revoked_membership(self):
        self.api(expected=409, **{'X-Company-Id': '3'})
        self.api(expected=400, **{'X-Company-Mode': 'all_companies'})
        uid = self.fixture['users']['director']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (uid,))
        self.addCleanup(self.sql, 'UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (uid,))
        self.api(expected=403)
        self.api('POST', '/company-material-aliases', dict(companyId=2, aliasName='Brand',
            canonicalName='Denied', expectedAliasId=None), expected=403)

    def test_http_effective_role_not_profile_role(self):
        uid = self.fixture['users']['director']['id']
        self.sql("UPDATE user_company_roles SET role='мастер' WHERE user_id=%s AND company_id=2", (uid,))
        self.addCleanup(self.sql, "UPDATE user_company_roles SET role='директор' WHERE user_id=%s AND company_id=2", (uid,))
        self.api('POST', '/company-material-aliases', dict(companyId=2, aliasName='Brand',
            canonicalName='Denied', expectedAliasId=None), expected=403)

    def wait_for_membership_lock(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if self.sql("""SELECT pid FROM pg_stat_activity WHERE datname=current_database()
                AND pid<>pg_backend_pid() AND wait_event_type='Lock'
                AND query LIKE %s""", ('SELECT id FROM user_company_roles%',)):
                return
            time.sleep(.02)
        self.fail('Alias operation did not serialize with the pending membership change')

    def test_pending_membership_revocation_is_rechecked_before_save(self):
        uid = self.fixture['users']['director']['id']
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (uid,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                request = pool.submit(self.api, 'POST', '/company-material-aliases',
                    dict(companyId=2, aliasName='Revoked', canonicalName='Denied', expectedAliasId=None), expected=403)
                try:
                    self.wait_for_membership_lock()
                finally:
                    blocker.commit()
                request.result(timeout=15)
            self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(0,)])
        finally:
            blocker.rollback(); blocker.close()
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (uid,))

    def test_cleared_member_projects_cannot_inherit_legacy_profile_assignment(self):
        uid = self.fixture['users']['foreman']['id']
        old_user = self.sql('SELECT project_name FROM users WHERE id=%s', (uid,))[0][0]
        old_projects = self.sql('SELECT assigned_projects FROM user_company_roles WHERE user_id=%s AND company_id=2', (uid,))[0][0]
        self.sql('UPDATE users SET project_name=%s WHERE id=%s', (self.fixture['project'], uid))
        self.sql("UPDATE user_company_roles SET assigned_projects='[]' WHERE user_id=%s AND company_id=2", (uid,))
        try:
            self.api(path='/company-material-aliases?companyId=2&projectId='+str(self.fixture['projectId']), actor='foreman', expected=403)
        finally:
            from psycopg2.extras import Json
            self.sql('UPDATE users SET project_name=%s WHERE id=%s', (old_user, uid))
            self.sql('UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=2', (Json(old_projects), uid))

    def test_http_concurrent_edit_only_one_wins(self):
        from fastapi.testclient import TestClient
        from threading import Barrier
        first = self.create()
        barrier = Barrier(2)
        token = self.main.create_auth_token(self.fixture['users']['director'], two_factor_passed=True)
        def edit(name):
            with TestClient(self.main.app) as client:
                barrier.wait(timeout=5)
                return client.post('/company-material-aliases', headers={'Authorization': 'Bearer '+token},
                    json=dict(companyId=2, aliasName='Brand', canonicalName=name, expectedAliasId=first['id']))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(edit, ['A', 'B']))
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409], [r.text for r in responses])
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(2,)])
        self.assertEqual(len(self.api()['items']), 1)

    def test_http_late_failure_rolls_back_and_does_not_expose_internal_error(self):
        from backend.features.material_aliases import owned_routes
        first = self.create()
        original = owned_routes.save_alias
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('sensitive SQL failure')
        with patch.object(owned_routes, 'save_alias', side_effect=fail):
            result = self.api('POST', '/company-material-aliases', dict(companyId=2, aliasName='Brand',
                canonicalName='Lost', expectedAliasId=first['id']), expected=503)
        self.assertNotIn('sensitive', str(result))
        self.assertEqual(self.api()['items'][0]['id'], first['id'])
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(1,)])

    def test_http_project_assignment_cannot_be_bypassed(self):
        project = self.sql("INSERT INTO projects(company_id,name) VALUES(2,'UNASSIGNED ALIAS HTTP') RETURNING id")[0][0]
        self.api(path='/company-material-aliases?companyId=2&projectId='+str(project), actor='foreman', expected=403)
        self.api('POST', '/company-material-aliases', dict(companyId=2, projectId=project,
            aliasName='Hidden brand', canonicalName='Hidden target', expectedAliasId=None), actor='foreman', expected=403)
        own = self.create(projectId=project)
        self.api('DELETE', '/company-material-aliases/'+own['id']+'?companyId=2', actor='foreman', expected=403)
        self.assertEqual(self.api(actor='foreman')['items'], [])

    def test_http_nondefault_company_membership_is_used(self):
        uid = self.fixture['users']['director']['id']
        membership = self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
            role,active,is_default) VALUES(%s,3,1,'директор',TRUE,FALSE) RETURNING id""", (uid,))[0][0]
        self.addCleanup(self.sql, 'DELETE FROM user_company_roles WHERE id=%s', (membership,))
        result = self.api('POST', '/company-material-aliases', dict(companyId=3, aliasName='Brand',
            canonicalName='Company three', expectedAliasId=None), expected=201, **{'X-Company-Id': '3'})
        self.assertEqual(result['companyId'], 3)
        self.assertEqual(self.api()['items'], [])
        rows = self.api(path='/company-material-aliases?companyId=3', **{'X-Company-Id': '3'})['items']
        self.assertEqual([r['id'] for r in rows], [result['id']])

    def test_http_requires_auth_and_does_not_reinterpret_legacy_urls(self):
        self.assertEqual(self.client.get('/company-material-aliases?companyId=2').status_code, 401)
        owned = self.create()
        number = owned['id'][4:]
        self.api('DELETE', '/material-aliases/'+number, expected=503)
        self.api('DELETE', '/company-material-aliases/'+number+'?companyId=2', expected=422)
        self.assertEqual(self.api()['items'][0]['id'], owned['id'])

    def test_http_revision_changes_after_replace_and_deactivate(self):
        initial = self.api()['revision']
        first = self.create()
        created = self.api()['revision']
        self.assertNotEqual(initial, created)
        self.assertEqual(self.api()['revision'], created)
        second = self.api('POST', '/company-material-aliases', dict(companyId=2,
            aliasName='Brand', canonicalName='Changed', expectedAliasId=first['id']), expected=201)
        replaced = self.api()['revision']
        self.assertNotEqual(created, replaced)
        self.api('DELETE', '/company-material-aliases/'+second['id']+'?companyId=2')
        self.assertNotEqual(replaced, self.api()['revision'])
