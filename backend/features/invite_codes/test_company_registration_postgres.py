"""Company invitations bind membership and assignments without guessed ownership."""
import os
import importlib
import unittest
from ..customer_cabinet import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class CompanyInvitationTests(unittest.TestCase):
    api = support.CustomerExtraWorksTests.api
    sql = support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(importlib.import_module('migrations.versions.0036_supplier_invite_company').SCHEMA_SQL)
        finally:
            conn.close()

    def test_company_is_server_bound_and_other_company_invite_is_private(self):
        director = self.fixture['users']['director']
        self.api(director, 'POST', '/invite-codes', {'role':'бухгалтер', 'companyId':3}, expected=403)
        invite = self.api(director, 'POST', '/invite-codes', {'role':'бухгалтер'})
        self.assertEqual(invite['company_id'], 2)
        foreign = self.sql("INSERT INTO invite_codes(code,role,company_id) VALUES('FOREIGNCOMPANYTEST','бухгалтер',3) RETURNING id")[0][0]
        self.assertNotIn(foreign, [r['id'] for r in self.api(director, 'GET', '/invite-codes')])
        self.api(director, 'DELETE', f'/invite-codes/{foreign}', expected=403)
        self.api(director, 'POST', '/invite-codes', {'role':'system_owner'}, expected=403)

    def test_register_creates_explicit_membership_and_code_is_single_use(self):
        director = self.fixture['users']['director']
        invite = self.api(director, 'POST', '/invite-codes', {'role':'директор'})
        body = {'code':invite['code'], 'name':'New director', 'email':'new-director@company.test', 'password':'test-password'}
        response = self.client.post('/register', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.sql("SELECT m.company_id,m.role,m.active FROM user_company_roles m JOIN users u ON u.id=m.user_id WHERE u.email=%s", (body['email'],)), [(2,'директор',True)])
        self.assertEqual(self.client.post('/register', json=dict(body,email='replay@company.test')).status_code,400)

    def test_project_is_resolved_inside_invitation_company_and_expired_code_rejected(self):
        director = self.fixture['users']['director']
        self.sql('INSERT INTO projects(company_id,name) VALUES(3,%s)',(self.fixture['project'],))
        invite = self.api(director,'POST','/invite-codes',{'role':'заказчик','projectId':self.fixture['projectId']})
        body = {'code':invite['code'],'name':'Customer','email':'new-customer@company.test','password':'test-password'}
        response = self.client.post('/register',json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.sql('SELECT company_id,project_id FROM users WHERE email=%s',(body['email'],)),[(2,self.fixture['projectId'])])
        expired = self.api(director,'POST','/invite-codes',{'role':'бухгалтер'})
        self.sql("UPDATE invite_codes SET expires_at=NOW()-INTERVAL '1 day' WHERE id=%s",(expired['id'],))
        self.assertEqual(self.client.post('/register',json=dict(body,code=expired['code'],email='expired@company.test')).status_code,400)
        foreign = self.sql("INSERT INTO projects(company_id,name) VALUES(3,'Foreign invite project') RETURNING id")[0][0]
        self.api(director,'POST','/invite-codes',{'role':'заказчик','projectId':foreign},expected=404)

    def test_unowned_legacy_invitation_cannot_guess_company_from_name(self):
        name = self.sql('SELECT name FROM companies WHERE id=2')[0][0]
        self.sql("INSERT INTO invite_codes(code,role,preset_name) VALUES('UNOWNEDCOMPANYTEST','директор',%s)",(name,))
        response=self.client.post('/register',json={'code':'UNOWNEDCOMPANYTEST','name':'Legacy','email':'legacy@company.test','password':'test-password'})
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM users WHERE email='legacy@company.test'"),[(0,)])

    def test_platform_onboarding_director_employee_and_project_chain(self):
        self.sql("SELECT setval(pg_get_serial_sequence('companies','id'),(SELECT MAX(id) FROM companies))")
        self.sql("SELECT setval(pg_get_serial_sequence('platform_accounts','id'),(SELECT MAX(id) FROM platform_accounts))")
        uid=self.sql("INSERT INTO users(name,email,password,role) VALUES('Platform test','platform-onboarding@local.test','unused','system_owner') RETURNING id")[0][0]
        operator={'id':uid,'role':'system_owner','name':'Platform test','email':'platform-onboarding@local.test'}
        created=self.api(operator,'POST','/system/companies',{'name':'Isolated onboarding company','inn':'7707083893','contactName':'Director','contactEmail':'onboarding-director@local.test','plan':'demo'})
        cid=created['id']
        body={'code':created['inviteCode'],'name':'Director','email':'onboarding-director@local.test','password':'test-password'}
        response=self.client.post('/register',json=body)
        self.assertEqual(response.status_code,200,response.text)
        uid=self.sql('SELECT id FROM users WHERE email=%s',(body['email'],))[0][0]
        director={'id':uid,'role':'директор','name':'Director','email':body['email'],'companyId':cid}
        self.assertEqual(self.sql('SELECT company_id,role FROM user_company_roles WHERE user_id=%s AND active',(uid,)),[(cid,'директор')])
        project=self.api(director,'POST','/projects',{'name':'First onboarding project'},company=cid)
        employee=self.api(director,'POST','/users',{'name':'Accountant','email':'onboarding-accountant@local.test','password':'test-password','role':'бухгалтер'},company=cid)
        self.assertEqual(employee['companyId'],cid)
        own=self.api(director,'GET','/projects',company=cid)
        self.assertEqual([row['id'] for row in own],[project['id']])
        self.api(director,'GET','/users',company=2,expected=403)
