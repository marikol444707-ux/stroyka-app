"""Employee account edits through authenticated HTTP and isolated PostgreSQL."""
import os
import importlib
import unittest

from backend.features.customer_cabinet import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class StaffAccessPostgresTests(unittest.TestCase):
    api = support.CustomerExtraWorksTests.api
    sql = support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute('ALTER TABLE staff ADD COLUMN IF NOT EXISTS company_scope_verified BOOLEAN NOT NULL DEFAULT FALSE')
                links = importlib.import_module('migrations.versions.0006_user_company_staff_links')
                for sql in (links._ADD_STAFF_LINK, links._ADD_INDEXES, links._ADD_FOREIGN_KEY):
                    cur.execute(sql)
        finally:
            conn.close()

    def seed_staff(self):
        email = self._testMethodName + '@staff.test'
        body = {'name': 'Employee regression', 'email': email,
                'password': 'Original-password-2026', 'systemRole': 'бухгалтер'}
        result = self.api(self.fixture['users']['director'], 'POST', '/staff', body)
        uid = self.sql('SELECT id FROM users WHERE email=%s', (email,))[0][0]
        return result['id'], uid, body

    def test_linked_employee_email_change_keeps_identity_and_original_password(self):
        sid, uid, body = self.seed_staff()
        new_email = 'changed-' + body['email']
        self.api(self.fixture['users']['director'], 'PUT', f'/staff/{sid}',
                 dict(body, email=new_email, password=''))
        self.assertEqual(self.sql('SELECT email FROM users WHERE id=%s', (uid,)), [(new_email,)])
        self.assertEqual(self.sql('SELECT user_id FROM user_company_roles WHERE company_id=2 AND staff_id=%s AND active', (sid,)), [(uid,)])
        login = self.client.post('/login', json={'email': new_email, 'password': body['password']})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(self.client.post('/login', json={'email': body['email'], 'password': body['password']}).status_code, 401)

    def test_linked_employee_password_and_role_reach_login(self):
        sid, uid, body = self.seed_staff()
        password = 'Replacement-password-2026'
        self.api(self.fixture['users']['director'], 'PUT', f'/staff/{sid}',
                 dict(body, password=password, systemRole='сметчик'))
        login = self.client.post('/login', json={'email': body['email'], 'password': password})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(self.sql('SELECT role FROM users WHERE id=%s', (uid,)), [('сметчик',)])
        self.assertEqual(self.sql('SELECT role FROM user_company_roles WHERE user_id=%s AND company_id=2 AND active', (uid,)), [('сметчик',)])
        self.assertEqual(self.client.post('/login', json={'email': body['email'], 'password': body['password']}).status_code, 401)

    def test_shared_employee_password_change_is_rejected_without_partial_staff_write(self):
        sid, uid, body = self.seed_staff()
        self.sql("INSERT INTO user_company_roles(user_id,company_id,role,active) VALUES(%s,3,'бухгалтер',TRUE)", (uid,))
        original = self.sql('SELECT email,password,role FROM users WHERE id=%s', (uid,))
        self.api(self.fixture['users']['director'], 'PUT', f'/staff/{sid}',
                 dict(body, name='Must roll back', password='Forbidden-password', systemRole='сметчик'), expected=409)
        self.assertEqual(self.sql('SELECT email,password,role FROM users WHERE id=%s', (uid,)), original)
        self.assertEqual(self.sql('SELECT name FROM staff WHERE id=%s', (sid,)), [(body['name'],)])
        self.assertEqual(self.sql('SELECT company_id,role FROM user_company_roles WHERE user_id=%s AND active ORDER BY company_id', (uid,)), [(2, 'бухгалтер'), (3, 'бухгалтер')])

    def test_occupied_email_cannot_rebind_staff_or_change_other_user(self):
        sid, uid, body = self.seed_staff()
        other = self.fixture['users']['stranger']['id']
        original = self.sql('SELECT email,password,role FROM users WHERE id=%s', (other,))
        self.api(self.fixture['users']['director'], 'PUT', f'/staff/{sid}',
                 dict(body, email=original[0][0], password='Forbidden-password'), expected=409)
        self.assertEqual(self.sql('SELECT email,password,role FROM users WHERE id=%s', (other,)), original)
        self.assertEqual(self.sql('SELECT user_id FROM user_company_roles WHERE company_id=2 AND staff_id=%s AND active', (sid,)), [(uid,)])
