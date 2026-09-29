"""Limits apply to every account-admission path inside company transactions."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from ..customer_cabinet import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1','isolated PostgreSQL required')
class CompanyLimitsTests(unittest.TestCase):
    api=support.CustomerExtraWorksTests.api
    sql=support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        conn.autocommit=False
        try:
            with conn.cursor() as cur:
                from ..crm_ownership.migration import _ensure_schema
                _ensure_schema(cur)
                cur.execute('ALTER TABLE staff ADD COLUMN IF NOT EXISTS company_scope_verified BOOLEAN NOT NULL DEFAULT FALSE')
            conn.commit()
        finally:conn.close()

    def test_concurrent_project_creation_respects_single_remaining_slot(self):
        current=self.sql('SELECT COUNT(*) FROM projects WHERE company_id=2 AND NOT COALESCE(archived,FALSE)')[0][0]
        self.sql('UPDATE companies SET max_projects=%s WHERE id=2',(current+1,))
        director=self.fixture['users']['director']
        token=self.main.create_auth_token(director,two_factor_passed=True)
        def create(n):
            return self.client.post('/projects',json={'name':f'Limited project {n}'},headers={'Authorization':'Bearer '+token,'X-Company-Id':'2','X-Company-Mode':'company'}).status_code
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(create,[1,2])),[200,409])
            self.assertEqual(self.sql('SELECT COUNT(*) FROM projects WHERE company_id=2 AND NOT COALESCE(archived,FALSE)')[0][0],current+1)
        finally:self.sql('UPDATE companies SET max_projects=NULL WHERE id=2')

    def test_user_and_registration_limits_leave_no_partial_records(self):
        director=self.fixture['users']['director']
        self.sql('UPDATE companies SET max_users=1 WHERE id=2')
        try:
            self.api(director,'POST','/users',{'name':'Over limit','email':'over-limit@company.test','password':'test-password','role':'бухгалтер'},expected=409)
            self.api(director,'POST','/staff',{'name':'Over limit staff','email':'over-limit-staff@company.test','password':'test-password','systemRole':'бухгалтер'},expected=409)
            self.assertEqual(self.sql("SELECT COUNT(*) FROM staff WHERE name='Over limit staff'"),[(0,)])
            self.sql("INSERT INTO invite_codes(code,role,company_id) VALUES('LIMITINVITETEST','бухгалтер',2)")
            response=self.client.post('/register',json={'code':'LIMITINVITETEST','name':'Over limit','email':'over-limit-register@company.test','password':'test-password'})
            self.assertEqual(response.status_code,409,response.text)
            self.assertEqual(self.sql("SELECT COUNT(*) FROM users WHERE email LIKE 'over-limit%%'")[0][0],0)
            self.assertEqual(self.sql("SELECT used FROM invite_codes WHERE code='LIMITINVITETEST'"),[(False,)])
        finally:self.sql('UPDATE companies SET max_users=NULL WHERE id=2')

    def test_crm_cannot_bypass_project_limit(self):
        director=self.fixture['users']['director']
        self.sql('UPDATE companies SET max_projects=1 WHERE id=2')
        lead=self.sql("INSERT INTO crm_leads(name,company_id) VALUES('Limit lead',2) RETURNING id")[0][0]
        try:
            self.api(director,'POST',f'/crm/leads/{lead}/create-project',{},expected=409)
            self.assertEqual(self.sql('SELECT project_id FROM crm_leads WHERE id=%s',(lead,)),[(None,)])
            self.assertEqual(self.sql("SELECT COUNT(*) FROM projects WHERE name='Limit lead'"),[(0,)])
        finally:self.sql('UPDATE companies SET max_projects=NULL WHERE id=2')

    def test_max_registration_uses_same_limit_and_exact_membership(self):
        from unittest.mock import patch
        from backend.features.messenger import routes
        self.sql("INSERT INTO invite_codes(code,role,company_id,project_name) VALUES('MAXLIMITTEST','заказчик',2,%s)",(self.fixture['project'],))
        body={'code':'MAXLIMITTEST','name':'MAX customer','email':'max-limit@company.test','password':'test-password'}
        with patch.object(routes,'_validate_max_init_data',return_value={'user':{'id':'test-max-company-user'},'chat':{}}), patch.object(routes,'_validate_max_contact',return_value={}):
            self.sql('UPDATE companies SET max_users=1 WHERE id=2')
            try:
                response=self.client.post('/max/register',json=body)
                self.assertEqual(response.status_code,409,response.text)
                self.assertEqual(self.sql("SELECT used FROM invite_codes WHERE code='MAXLIMITTEST'"),[(False,)])
                self.assertEqual(self.sql("SELECT COUNT(*) FROM users WHERE email='max-limit@company.test'"),[(0,)])
            finally:self.sql('UPDATE companies SET max_users=NULL WHERE id=2')
            response=self.client.post('/max/register',json=body)
            self.assertEqual(response.status_code,200,response.text)
            uid=response.json()['user']['id']
            self.assertEqual(self.sql('SELECT company_id,project_id FROM users WHERE id=%s',(uid,)),[(2,self.fixture['projectId'])])
            self.assertEqual(self.sql('SELECT company_id,role,active FROM user_company_roles WHERE user_id=%s',(uid,)),[(2,'заказчик',True)])
            self.assertEqual(self.client.post('/max/register',json=body).status_code,400)
