"""Profile membership SQL against a disposable, socket-only PostgreSQL database."""
import os
import unittest

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.features.company_context.service import effective_company_actors
from backend.features.supplier_access.test_postgres_chain_support import connection_settings, _assert_empty_database
from .access import authorized_profile_users
from .routes import register_master_profiles_module


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class ProfileMembershipPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = connection_settings(os.environ)
        conn = psycopg2.connect(**cls.settings)
        try:
            _assert_empty_database(conn, cls.settings)
            with conn, conn.cursor() as cur:
                cur.execute('''CREATE TABLE users(id INTEGER PRIMARY KEY,company_id INTEGER,active BOOLEAN,
                    assigned_projects JSONB,project_name TEXT);
                    CREATE TABLE user_company_roles(id SERIAL PRIMARY KEY,user_id INTEGER,company_id INTEGER,
                    active BOOLEAN,assigned_projects JSONB)''')
                for user_id, company, active, projects, project in (
                    (1, 2, True, '["Alpha"]', ''), (42, 2, True, '["Alpha"]', ''),
                    (43, 2, True, '["Beta"]', ''), (44, 2, True, '[]', 'Alpha'),
                    (45, 2, True, '[]', ''), (46, 2, True, '["Alpha"]', ''),
                    (47, 2, True, '["Alpha"]', ''), (48, 2, False, '["Alpha"]', ''),
                    (49, 3, True, '["Alpha"]', 'Alpha'), (99, 3, True, '["Alpha"]', ''),
                ):
                    cur.execute('INSERT INTO users VALUES(%s,%s,%s,%s,%s)',
                                (user_id, company, active, projects, project))
                cur.execute('''INSERT INTO user_company_roles(user_id,company_id,active,assigned_projects) VALUES
                    (42,2,TRUE,'["Alpha"]'),(43,2,TRUE,'["Beta"]'),(46,2,FALSE,'["Alpha"]'),
                    (47,3,TRUE,'["Alpha"]'),(48,2,TRUE,'["Alpha"]'),(49,2,TRUE,'["Beta"]')''')
                cur.execute('''CREATE TABLE master_profiles(id SERIAL PRIMARY KEY,user_id INTEGER UNIQUE,
                    full_name TEXT,passport TEXT,inn TEXT,contract_type TEXT,bank_account TEXT,bank_name TEXT,
                    phone TEXT,specialization TEXT,ogrnip TEXT,kpp TEXT,ogrn TEXT,legal_address TEXT,
                    bank_bik TEXT,bank_corr TEXT,signatory_name TEXT,signatory_position TEXT,signatory_basis TEXT,
                    profile_completed BOOLEAN DEFAULT TRUE);
                    INSERT INTO master_profiles(user_id,full_name,passport,bank_account)
                    SELECT id,'Synthetic profile '||id,'Synthetic passport '||id,'Synthetic bank '||id FROM users''')
        finally:
            conn.close()

    def setUp(self):
        self.conn = psycopg2.connect(**self.settings)
        self.addCleanup(self.conn.close)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)

    def allowed(self, role='прораб', company=2):
        context = {'mode': 'company', 'companyId': company, 'effectiveRole': role,
                   'assignedProjects': ['Alpha'], 'active': True}
        deps = {'resolve_work_company_context': lambda *args, **kwargs: context,
                'effective_company_actors': effective_company_actors}
        user = {'id': 1, 'company_id': 3, 'role': 'директор', 'assigned_projects': ['Beta']}
        return authorized_profile_users(self.cur, user, deps, manager_roles=('директор', 'бухгалтер'),
                                        project_roles=('прораб',), company_id=str(company), company_mode='company')

    def client(self, role):
        def connect():
            conn = psycopg2.connect(**self.settings)
            conn.autocommit = True
            return conn
        context = {'mode': 'company', 'companyId': 2, 'effectiveRole': role,
                   'assignedProjects': ['Alpha'], 'active': True}
        user = {'id': 1, 'company_id': 3, 'role': 'директор', 'assigned_projects': ['Beta']}
        app = FastAPI()
        register_master_profiles_module(app, {
            'get_db': connect, 'get_current_user': lambda: user,
            'resolve_work_company_context': lambda *args, **kwargs: context,
            'effective_company_actors': effective_company_actors,
            'finance_roles': ('директор', 'бухгалтер'), 'worker_execution_roles': ('мастер',),
            'user_project_names': lambda actor: actor.get('assigned_projects', []),
        })
        return TestClient(app, headers={'X-Company-Id': '2', 'X-Company-Mode': 'company'})

    def test_http_selected_membership_limits_list_detail_and_sensitive_fields(self):
        with self.client('прораб') as client:
            response = client.get('/master-profiles')
            self.assertEqual(response.status_code, 200, response.text)
            rows = {row['userId']: row for row in response.json()}
            self.assertEqual(set(rows), {1, 42, 44})
            self.assertIn('passport', rows[1])
            self.assertNotIn('passport', rows[42])
            self.assertNotIn('bankAccount', rows[42])
            detail = client.get('/master-profile/42')
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertNotIn('passport', detail.json())
            self.assertEqual(client.get('/master-profile/99').status_code, 403)

    def test_http_foreign_or_peer_write_denial_preserves_profiles(self):
        self.cur.execute('SELECT to_jsonb(p) AS row FROM master_profiles p ORDER BY id')
        before = self.cur.fetchall()
        for role, target in (('прораб', 42), ('прораб', 99), ('директор', 99)):
            with self.subTest(role=role, target=target), self.client(role) as client:
                response = client.post('/master-profile', json={'userId': target, 'fullName': 'Forbidden change'})
                self.assertEqual(response.status_code, 403, response.text)
        self.cur.execute('SELECT to_jsonb(p) AS row FROM master_profiles p ORDER BY id')
        self.assertEqual(self.cur.fetchall(), before)

    def test_http_own_profile_and_company_director_changes_are_persisted(self):
        for role, target in (('прораб', 1), ('директор', 42)):
            with self.subTest(role=role, target=target), self.client(role) as client:
                name = 'Allowed change ' + str(target)
                response = client.post('/master-profile', json={'userId': target, 'fullName': name})
                self.assertEqual(response.status_code, 200, response.text)
                self.cur.execute('SELECT full_name FROM master_profiles WHERE user_id=%s', (target,))
                self.assertEqual(self.cur.fetchone()['full_name'], name)

    def test_foreman_cannot_use_foreign_legacy_or_inactive_membership(self):
        self.assertEqual(self.allowed(), {1: True, 42: False, 44: False})

    def test_director_stays_within_selected_company_and_active_users(self):
        self.assertEqual(self.allowed('директор'),
                         {1: True, 42: True, 43: True, 44: True, 45: True, 49: True})

    def test_revoked_membership_does_not_fall_back_to_legacy_company(self):
        self.assertIn(42, self.allowed())
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=42 AND company_id=2')
        self.assertNotIn(42, self.allowed())
        self.assertNotIn(42, self.allowed('директор'))

    def test_switching_selected_company_changes_peer_access(self):
        # User 49's membership in company 2 supersedes the legacy company 3 field.
        self.assertEqual(self.allowed(company=3), {1: True, 47: False, 99: False})
