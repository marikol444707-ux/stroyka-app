import os
import unittest
from ..customer_cabinet import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class CompanyUserTests(unittest.TestCase):
    api=support.CustomerExtraWorksTests.api
    sql=support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)

    def test_directory_and_commands_cannot_target_another_company(self):
        director=self.fixture['users']['director'];foreign=self.fixture['users']['stranger']
        rows=self.api(director,'GET','/users')
        self.assertNotIn(foreign['id'],[row['id'] for row in rows])
        for method,path,body in [('PUT',f"/users/{foreign['id']}",{'name':'Foreign','email':'foreign@example.test','role':'бухгалтер'}),
             ('PUT',f"/users/{foreign['id']}/assigned-projects",{'assignedProjects':[self.fixture['project']]}),
             ('DELETE',f"/users/{foreign['id']}",None),('POST',f"/users/{foreign['id']}/2fa-reset",{})]:
            self.api(director,method,path,body,expected=404)

    def test_new_access_owns_company_and_rejects_platform_role(self):
        director=self.fixture['users']['director']
        body={'name':'Owned accountant','email':'owned-accountant@example.test','password':'local-test-password','role':'бухгалтер'}
        row=self.api(director,'POST','/users',body)
        self.assertEqual(self.sql('SELECT company_id FROM users WHERE id=%s',(row['id'],)),[(2,)])
        self.assertEqual(self.sql('SELECT company_id,role,active FROM user_company_roles WHERE user_id=%s',(row['id'],)),[(2,'бухгалтер',True)])
        self.api(director,'POST','/users',dict(body,email='forbidden@example.test',role='system_owner'),expected=403)

    def test_shared_identity_changes_only_selected_membership(self):
        director=self.fixture['users']['director'];target=self.fixture['users']['accountant'];uid=target['id']
        self.sql("INSERT INTO user_company_roles(user_id,company_id,role,active) VALUES(%s,3,'бухгалтер',TRUE)",(uid,))
        original=self.sql('SELECT name,email,password,role,active FROM users WHERE id=%s',(uid,))[0]
        body={'name':original[0],'email':original[1],'role':'сметчик','password':''}
        self.api(director,'PUT',f'/users/{uid}',body)
        self.assertEqual(self.sql('SELECT name,email,password,role,active FROM users WHERE id=%s',(uid,))[0],original)
        self.assertEqual(self.sql('SELECT role FROM user_company_roles WHERE user_id=%s AND company_id=2 AND active',(uid,)),[('сметчик',)])
        self.api(director,'PUT',f'/users/{uid}',dict(body,password='changed-password'),expected=409)
        self.api(director,'POST',f'/users/{uid}/2fa-reset',{},expected=409)
        self.api(director,'DELETE',f'/users/{uid}')
        self.assertEqual(self.sql('SELECT role,active FROM user_company_roles WHERE user_id=%s AND company_id=3',(uid,)),[('бухгалтер',True)])
        self.assertEqual(self.sql('SELECT active FROM users WHERE id=%s',(uid,)),[(True,)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM user_company_roles WHERE user_id=%s AND company_id=2 AND active',(uid,)),[(0,)])

    def test_platform_and_account_identities_cannot_be_converted_or_reset(self):
        director=self.fixture['users']['director']
        for role in ('system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin','поставщик'):
            uid=self.sql("INSERT INTO users(name,email,password,role,company_id) VALUES('Protected',%s,'hash',%s,2) RETURNING id",(role+'@protected.test',role))[0][0]
            for method,path,body in [('PUT',f'/users/{uid}',{'name':'Changed','email':role+'@protected.test','role':'бухгалтер'}),
                                    ('DELETE',f'/users/{uid}',None),('POST',f'/users/{uid}/2fa-reset',{})]:
                self.api(director,method,path,body,expected=404)
            self.assertNotIn(uid,[r['id'] for r in self.api(director,'GET','/users')])

    def test_assignment_endpoint_cannot_change_role_or_accept_foreign_project(self):
        director=self.fixture['users']['director']
        row=self.api(director,'POST','/users',{'name':'Scoped user','email':'scoped-user@example.test','password':'test-password','role':'бухгалтер'})
        uid=row['id']
        self.api(director,'PUT',f'/users/{uid}/assigned-projects',{'role':'директор'},expected=422)
        foreign='Foreign assignment only'
        self.sql('INSERT INTO projects(company_id,name) VALUES(3,%s)',(foreign,))
        self.api(director,'PUT',f'/users/{uid}/assigned-projects',{'assignedProjects':[foreign]},expected=404)
        self.assertEqual(self.sql('SELECT role FROM user_company_roles WHERE user_id=%s AND active',(uid,)),[('бухгалтер',)])

    def test_failed_audit_rolls_back_new_account_and_membership(self):
        self.sql("""CREATE FUNCTION reject_company_user_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.entity_type='user' THEN RAISE EXCEPTION 'test audit failure'; END IF; RETURN NEW; END $$""")
        self.sql('CREATE TRIGGER reject_company_user_audit BEFORE INSERT ON audit_log FOR EACH ROW EXECUTE FUNCTION reject_company_user_audit()')
        try:
            with self.assertRaises(Exception):
                self.api(self.fixture['users']['director'],'POST','/users',{'name':'Rollback','email':'rollback-user@example.test','password':'test-password','role':'бухгалтер'})
            self.assertEqual(self.sql("SELECT COUNT(*) FROM users WHERE email='rollback-user@example.test'"),[(0,)])
        finally:
            self.sql('DROP TRIGGER reject_company_user_audit ON audit_log')
            self.sql('DROP FUNCTION reject_company_user_audit()')
