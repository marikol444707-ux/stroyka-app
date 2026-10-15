"""Read-only, typed organization projections against isolated PostgreSQL/auth."""
import os
import unittest
import importlib
import time
from statistics import median
from unittest.mock import patch

from . import test_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class OrganizationDirectoryPostgresTests(unittest.TestCase):
    sql, api = support.ParticipantSupportPostgresTests.sql, support.ParticipantSupportPostgresTests.api

    @classmethod
    def setUpClass(cls):
        support.ParticipantSupportPostgresTests.setUpClass.__func__(cls)

    def person(self, name, company=2, role='мастер', account=None, active=True):
        uid = self.sql("INSERT INTO users(name,role,active) VALUES(%s,'директор',TRUE) RETURNING id", (name,))[0][0]
        mid = self.sql('''INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active)
            VALUES(%s,%s,%s,%s,%s) RETURNING id''', (uid,company,account,role,active))[0][0]
        return uid,mid

    def invite(self, role='мастер', company=2, account=1, **fields):
        iid = self.sql('''INSERT INTO invite_codes(code,role,company_id,platform_account_id,used,expires_at)
            VALUES(%s,%s,%s,%s,%s,NOW()+INTERVAL '1 day') RETURNING id''',
            ('SECRET-'+os.urandom(5).hex(),role,company,account,fields.get('used',False)))[0][0]
        return iid

    def test_memberships_exact_context_no_global_role_or_staff_id_substitution(self):
        uid,mid = self.person('Directory scope-case shared person')
        self.sql("INSERT INTO user_company_roles(user_id,company_id,role) VALUES(%s,3,'бухгалтер')", (uid,))
        self.person('Directory scope-case foreign secret person',3)
        self.person('Directory scope-case bad account person',2,account=999)
        self.sql("INSERT INTO users(name,company_id,role,active) VALUES('Directory scope-case legacy only',2,'директор',TRUE)")
        self.sql("INSERT INTO staff(id,name,company_id) VALUES(%s,'STAFF NAME MUST NOT REPLACE USER',2)",(uid,))
        self.sql('UPDATE user_company_roles SET staff_id=%s WHERE id=%s',(uid,mid))
        before = self.sql('SELECT to_jsonb(m) FROM user_company_roles m ORDER BY id')
        rows = self.api('admin','GET','/system/companies/2/participant-memberships?search=scope-case')['items']
        self.assertEqual([r['membershipId'] for r in rows],[mid])
        self.assertEqual(rows[0]['userId'],uid)
        self.assertEqual(rows[0]['role'],'мастер')
        self.assertEqual(rows[0]['status'],'active')
        self.assertEqual(rows[0]['activeRoleCount'],1)
        self.assertNotIn('staffId',rows[0])
        self.assertNotIn('email',rows[0])
        self.assertEqual(before,self.sql('SELECT to_jsonb(m) FROM user_company_roles m ORDER BY id'))
        other = self.api('admin','GET','/system/companies/3/participant-memberships?search=shared')['items']
        self.assertEqual(other[0]['role'],'бухгалтер')

    def test_conflicts_revocation_and_disabled_identity_are_facts_not_effective_grants(self):
        uid,mid = self.person('Directory conflict person')
        self.sql("INSERT INTO user_company_roles(user_id,company_id,role) VALUES(%s,2,'прораб')", (uid,))
        rows = self.api('admin','GET','/system/companies/2/participant-memberships?search=conflict')['items']
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['status']=='review' and r['activeRoleCount']==2 for r in rows))
        filtered=self.api('admin','GET','/system/companies/2/participant-memberships?search=conflict&status=active')['items']
        self.assertEqual(filtered,[])
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE id=%s',(mid,))
        rows = self.api('admin','GET','/system/companies/2/participant-memberships?search=conflict')['items']
        self.assertEqual({r['status'] for r in rows},{'active','inactive'})
        filtered=self.api('admin','GET','/system/companies/2/participant-memberships?search=conflict&status=inactive')['items']
        self.assertEqual([r['membershipId'] for r in filtered],[mid])
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(uid,))
        rows = self.api('admin','GET','/system/companies/2/participant-memberships?search=conflict')['items']
        self.assertEqual({r['status'] for r in rows},{'disabled','inactive'})
        self.person('Directory invalid role',role='system_owner')
        rows = self.api('admin','GET','/system/companies/2/participant-memberships?search=invalid')['items']
        self.assertEqual(rows[0]['status'],'review')

    def test_invites_verified_purpose_scope_status_and_no_secrets(self):
        pending = self.invite()
        used = self.invite(used=True)
        expired = self.invite()
        self.sql("UPDATE invite_codes SET expires_at=NOW()-INTERVAL '1 day' WHERE id=%s",(expired,))
        unknown = self.invite(account=None)
        self.sql('UPDATE invite_codes SET expires_at=NULL WHERE id=%s',(unknown,))
        self.invite(company=3)
        self.invite(account=999)
        supplier = self.invite('поставщик')
        self.sql('''INSERT INTO supplier_invite_companies(invite_id,company_id,platform_account_id,created_by_user_id)
            VALUES(%s,2,1,%s)''',(supplier,self.fixture['users']['director']['id']))
        self.invite('поставщик')  # no binding: legacy/unknown, never an employee invite
        self.invite('system_owner')
        before = self.sql('SELECT to_jsonb(i) FROM invite_codes i ORDER BY id')
        rows = self.api('admin','GET','/system/companies/2/participant-invitations?limit=100')['items']
        selected = {r['inviteId']:r for r in rows}
        self.assertEqual(set(selected),{pending,used,expired,unknown,supplier})
        self.assertEqual(selected[pending]['status'],'pending')
        self.assertEqual(selected[used]['status'],'used')
        self.assertEqual(selected[expired]['status'],'expired')
        self.assertEqual(selected[unknown]['status'],'review')
        self.assertEqual(selected[supplier]['purpose'],'supplier_registration')
        self.assertEqual(selected[pending]['purpose'],'company_membership')
        self.assertNotIn('SECRET-',str(rows))
        self.assertTrue(all(set(r)=={'inviteId','purpose','role','status','createdAt','expiresAt'} for r in rows))
        self.assertEqual(before,self.sql('SELECT to_jsonb(i) FROM invite_codes i ORDER BY id'))

    def test_supplier_invite_inconsistent_binding_never_becomes_company_invite(self):
        iid = self.invite('мастер')
        self.sql('''INSERT INTO supplier_invite_companies(invite_id,company_id,platform_account_id,created_by_user_id)
            VALUES(%s,3,1,%s)''',(iid,self.fixture['users']['director']['id']))
        for cid in (2,3):
            rows = self.api('admin','GET',f'/system/companies/{cid}/participant-invitations?limit=100')['items']
            self.assertNotIn(iid,[r['inviteId'] for r in rows])

    def test_team_invitation_excluded_and_each_read_rechecks_admin(self):
        self.sql(importlib.import_module('migrations.versions.0038_supplier_customer_team').SCHEMA_SQL)
        iid=self.invite('мастер')  # damaged team record must still never become buyer employment
        sid=self.fixture['supplierId']
        self.sql('''INSERT INTO supplier_team_invites(invite_id,supplier_id,created_by_user_id,issuer_user_epoch)
            VALUES(%s,%s,%s,0)''',(iid,sid,self.fixture['users']['supplier']['id']))
        rows=self.api('admin','GET','/system/companies/2/participant-invitations?limit=100')['items']
        self.assertNotIn(iid,[r['inviteId'] for r in rows])
        self.fixture['users']['directory_support']=dict(id=self.sql("INSERT INTO users(name,role,active) VALUES('Synthetic directory support','platform_support',TRUE) RETURNING id")[0][0],role='platform_support')
        for endpoint in ('participant-memberships','participant-invitations'):
            path='/system/companies/2/'+endpoint
            self.api('directory_support','GET',path,expected=403)
            self.sql('UPDATE users SET active=FALSE WHERE id=%s',(self.fixture['users']['admin']['id'],))
            try:self.api('admin','GET',path,expected=403)
            finally:self.sql('UPDATE users SET active=TRUE WHERE id=%s',(self.fixture['users']['admin']['id'],))

    def measure_directory_latency(self):
        for endpoint in ('participant-memberships','participant-invitations'):
            values=[]
            for _ in range(20):
                start=time.perf_counter()
                self.api('admin','GET','/system/companies/249/'+endpoint+'?limit=25')
                values.append((time.perf_counter()-start)*1000)
            values.sort()
            print('ORGANIZATION_DIRECTORY_BASELINE endpoint=%s synthetic=50_companies/106_memberships/106_invites samples=20 median_ms=%.2f p95_ms=%.2f' % (endpoint,median(values),values[18]))

    def test_50_organizations_two_accounts_search_pagination_and_guards(self):
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(199,'Synthetic directory account','pro','active')")
        uid,_ = self.person('Directory many-company person')
        for cid in range(200,250):
            aid=1 if cid<225 else 199
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,%s,%s,TRUE,'pro')",(cid,'Synthetic directory company '+str(cid),aid))
            self.sql("INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role) VALUES(%s,%s,%s,'мастер')",(uid,cid,aid))
            self.invite(company=cid,account=aid)
        for cid in (200,249):
            rows = self.api('admin','GET',f'/system/companies/{cid}/participant-memberships')['items']
            self.assertEqual([r['userId'] for r in rows],[uid])
            self.assertEqual(len(self.api('admin','GET',f'/system/companies/{cid}/participant-invitations')['items']),1)
        for n in range(105):
            self.person('Directory paginated '+str(n),249,account=199)
            self.invite(company=249,account=199)
        for endpoint,query,key in (('participant-memberships','search=paginated&','membershipId'),('participant-invitations','','inviteId')):
            path=f'/system/companies/249/{endpoint}?{query}limit=25'
            one=self.api('admin','GET',path)
            two=self.api('admin','GET',path+'&offset=25')
            self.assertTrue(one['hasMore'])
            self.assertEqual(len(one['items']),25)
            self.assertFalse({r[key] for r in one['items']} & {r[key] for r in two['items']})
            self.api('director','GET',path,expected=403)
            self.api('admin','GET',path.replace('/249/','/999999/'),expected=404)
            self.api('admin','GET',path+'&status=unknown',expected=422)
            self.api('admin','GET',path+'&limit=101',expected=422)
            with patch.dict(os.environ,PARTICIPANT_SUPPORT_ENABLED='0'):
                self.api('admin','GET',path,expected=503)
            self.api('admin','POST',path,{},expected=405)
        self.measure_directory_latency()
