"""Real authenticated HTTP and SQL; fresh isolated UTF8 database required per run."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Explicit isolated PostgreSQL opt-in required')
class MaterialCompanyPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def sql(self, statement, params=()):
        conn = self.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(statement, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def setUp(self):
        self.uid = self.fixture['users']['director']['id']
        self.sql('DELETE FROM materials')
        self.sql('DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3', (self.uid,))
        self.sql("UPDATE user_company_roles SET role='директор',active=TRUE WHERE user_id=%s AND company_id=2", (self.uid,))
        self.sql('UPDATE companies SET active=TRUE WHERE id IN (2,3)')
        self.ids = {}
        for company in (2, 3):
            self.ids[company] = self.sql("""INSERT INTO materials
                (company_id,name,project,unit,quantity,price,work_package)
                VALUES(%s,'Shared material',%s,'шт',7,13,'Основная') RETURNING id""",
                (company, self.fixture['project']))[0][0]

    def api(self, method='GET', path='/materials', payload=None, expected=200, **headers):
        token = self.main.create_auth_token(self.fixture['users']['director'], two_factor_passed=True)
        response = self.client.request(method, path, json=payload, headers={
            'Authorization': 'Bearer ' + token, **headers})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def add_membership(self, role):
        from psycopg2.extras import Json
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
            role,assigned_projects,assigned_packages,active,is_default)
            VALUES(%s,3,1,%s,%s,%s,TRUE,FALSE)""",
            (self.uid, role, Json([self.fixture['project']]), Json(['Основная'])))

    def test_read_isolates_same_name_projects_and_search(self):
        rows = self.api(**{'X-Company-Id': '2'})
        self.assertEqual([r['id'] for r in rows], [self.ids[2]])
        self.assertEqual(rows[0]['companyId'], 2)
        self.assertEqual(self.api(path='/materials?search=missing', **{'X-Company-Id': '2'}), [])
        self.api(expected=403, **{'X-Company-Id': '3'})

    def test_create_and_update_selected_company_not_default(self):
        self.add_membership('директор')
        row = self.api('POST', payload={'name': 'New', 'quantity': 5, 'companyId': 3}, **{'X-Company-Id': '3'})
        self.assertEqual(row['companyId'], 3)
        self.assertEqual(self.sql("SELECT company_id,user_id FROM audit_log WHERE entity_type='material' AND entity_id=%s", (row['id'],)), [(3, self.uid)])
        self.api('PUT', '/materials/' + str(row['id']), {'name': 'Updated', 'quantity': 6, 'companyId': 3}, **{'X-Company-Id': '3'})
        self.assertEqual(self.sql('SELECT company_id,name,quantity FROM materials WHERE id=%s', (row['id'],)), [(3, 'Updated', 6)])

    def test_foreign_id_not_found_and_unchanged(self):
        before = self.sql('SELECT * FROM materials ORDER BY id')
        self.api('PUT', '/materials/' + str(self.ids[3]), {'name': 'Foreign'}, expected=404, **{'X-Company-Id': '2'})
        self.assertEqual(self.sql('SELECT * FROM materials ORDER BY id'), before)

    def test_claim_mismatch_and_all_company_writes_rejected(self):
        before = self.sql('SELECT * FROM materials ORDER BY id')
        self.api('POST', payload={'name': 'Mismatch', 'companyId': 3}, expected=409, **{'X-Company-Id': '2'})
        self.api('POST', payload={'name': 'Aggregate'}, expected=400, **{'X-Company-Mode': 'all_companies'})
        for value in (True, 0, -1, '3'):
            self.api('POST', payload={'name': 'Invalid', 'companyId': value}, expected=422)
        self.assertEqual(self.sql('SELECT * FROM materials ORDER BY id'), before)

    def test_effective_role_controls_writes_and_aggregate_masking(self):
        self.add_membership('мастер')
        self.api('POST', payload={'name': 'Denied'}, expected=403, **{'X-Company-Id': '3'})
        self.api('PUT', '/materials/' + str(self.ids[3]), {'name': 'Denied'}, expected=403, **{'X-Company-Id': '3'})
        rows = self.api(**{'X-Company-Mode': 'all_companies'})
        by_company = {row['companyId']: row for row in rows}
        self.assertEqual(set(by_company), {2, 3})
        self.assertEqual(by_company[2]['quantity'], 7)
        self.assertEqual((by_company[3]['quantity'], by_company[3]['price']), (0, 0))
        pages = [self.api(path='/materials?limit=1&offset=' + str(i), **{'X-Company-Mode': 'all_companies'}) for i in (0, 1)]
        self.assertEqual([page[0]['id'] for page in pages], [row['id'] for row in rows])

    def test_revoked_membership_cannot_fall_back_to_legacy_profile(self):
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (self.uid,))
        self.api(expected=403)
        self.api('POST', payload={'name': 'Denied'}, expected=403)
        self.api('PUT', '/materials/' + str(self.ids[2]), {'name': 'Denied'}, expected=403)

    def test_inactive_company_is_denied(self):
        self.sql('UPDATE companies SET active=FALSE WHERE id=2')
        self.api(expected=403, **{'X-Company-Id': '2'})

    def test_missing_membership_cannot_use_legacy_profile(self):
        # Restore this fixture membership afterwards for subsequent test cases.
        self.sql('UPDATE user_company_roles SET company_id=3 WHERE user_id=%s AND company_id=2', (self.uid,))
        self.addCleanup(self.sql, 'UPDATE user_company_roles SET company_id=2 WHERE user_id=%s AND company_id=3', (self.uid,))
        self.api(expected=403, **{'X-Company-Id': '2'})

    def test_selected_membership_project_and_package_assignments(self):
        from psycopg2.extras import Json
        self.add_membership('мастер')
        self.assertEqual(len(self.api(**{'X-Company-Id': '3'})), 1)
        self.sql('UPDATE user_company_roles SET assigned_packages=%s WHERE user_id=%s AND company_id=3', (Json(['Other']), self.uid))
        self.assertEqual(self.api(**{'X-Company-Id': '3'}), [])
        self.assertEqual([row['companyId'] for row in self.api(**{'X-Company-Mode': 'all_companies'})], [2])
        self.sql('UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=3', (Json([]), self.uid))
        self.assertEqual(self.api(**{'X-Company-Id': '3'}), [])
        self.assertEqual([row['companyId'] for row in self.api(**{'X-Company-Mode': 'all_companies'})], [2])

    def test_cleared_default_membership_cannot_inherit_legacy_project(self):
        from psycopg2.extras import Json
        self.addCleanup(self.sql, 'UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=2',
                        (Json([self.fixture['project']]), self.uid))
        self.sql("""UPDATE user_company_roles SET role='мастер',assigned_projects='[]'
            WHERE user_id=%s AND company_id=2""", (self.uid,))
        # The authenticated profile still names the old object, but membership
        # assignments are the only authority for this directory.
        self.assertEqual(self.sql('SELECT project_name FROM users WHERE id=%s', (self.uid,)),
                         [(self.fixture['project'],)])
        self.assertEqual(self.api(**{'X-Company-Id': '2'}), [])

    def test_empty_membership_role_cannot_inherit_director_profile(self):
        self.sql("UPDATE user_company_roles SET role='' WHERE user_id=%s AND company_id=2", (self.uid,))
        before = self.sql('SELECT * FROM materials ORDER BY id')
        self.api(expected=403, **{'X-Company-Id': '2'})
        self.api('POST', payload={'name': 'Denied'}, expected=403, **{'X-Company-Id': '2'})
        self.api('PUT', '/materials/' + str(self.ids[2]),
                 {'name': 'Denied', 'quantity': 7, 'project': self.fixture['project']},
                 expected=403, **{'X-Company-Id': '2'})
        self.assertEqual(self.sql('SELECT * FROM materials ORDER BY id'), before)

    def test_aggregate_omits_membership_without_role(self):
        self.add_membership('директор')
        self.sql("UPDATE user_company_roles SET role='' WHERE user_id=%s AND company_id=2", (self.uid,))
        self.assertEqual([row['companyId'] for row in self.api(**{'X-Company-Mode': 'all_companies'})], [3])

    def pending_authorization_change(self, method, path, payload, statement, params):
        before = self.sql('SELECT * FROM materials ORDER BY id')
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute(statement, params)
            with ThreadPoolExecutor(max_workers=1) as pool:
                request = pool.submit(self.api, method, path, payload, expected=403,
                                      **{'X-Company-Id': '2'})
                try:
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline and not request.done():
                        if self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND pid<>pg_backend_pid()
                              AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM %% FOR SHARE'"""):
                            break
                        time.sleep(.02)
                finally:
                    blocker.commit()
                request.result(timeout=15)
            self.assertEqual(self.sql('SELECT * FROM materials ORDER BY id'), before)
        finally:
            blocker.rollback()
            blocker.close()

    def test_pending_membership_revocation_is_rechecked_before_create(self):
        self.pending_authorization_change('POST', '/materials', {'name': 'Denied'},
            'UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.uid,))

    def test_pending_membership_role_change_is_rechecked_before_update(self):
        self.pending_authorization_change('PUT', '/materials/' + str(self.ids[2]),
            {'name': 'Denied', 'quantity': 7, 'project': self.fixture['project']},
            "UPDATE user_company_roles SET role='мастер' WHERE user_id=%s AND company_id=2", (self.uid,))

    def test_pending_company_deactivation_is_rechecked_before_create(self):
        self.pending_authorization_change('POST', '/materials', {'name': 'Denied'},
            'UPDATE companies SET active=FALSE WHERE id=2', ())

    def test_object_quantity_requires_documents(self):
        before = self.sql('SELECT * FROM materials ORDER BY id')
        self.api('PUT', '/materials/' + str(self.ids[2]),
                 {'name': 'Shared material', 'project': self.fixture['project'], 'quantity': 8}, expected=400)
        self.assertEqual(self.sql('SELECT * FROM materials ORDER BY id'), before)
