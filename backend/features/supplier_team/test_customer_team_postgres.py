"""Customer responsibility and manager onboarding through authenticated HTTP."""
import importlib
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from backend.features.supplier_team import test_policy_postgres as support

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Requires isolated PostgreSQL')
class CustomerTeamPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.TeamPolicyPostgresTests.setUpClass.__func__(cls)
        flag=patch.dict(os.environ,{'SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED':'1'})
        flag.start();cls.addClassCleanup(flag.stop)
        conn=cls.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(importlib.import_module('migrations.versions.0036_supplier_invite_company').SCHEMA_SQL)
                cur.execute(importlib.import_module('migrations.versions.0038_supplier_customer_team').SCHEMA_SQL)
            conn.commit()
        finally:conn.close()
    api=support.TeamPolicyPostgresTests.api
    sql=support.TeamPolicyPostgresTests.sql
    quote=support.TeamPolicyPostgresTests.quote

    def setUp(self):
        self.sql('DELETE FROM supplier_customer_assignments')
        self.sql("UPDATE supplier_team_members SET active=TRUE,role='manager' WHERE id=%s",(self.member_id,))

    def command(self,action,actor='supplier',expected=200,**fields):
        return self.api(actor,'POST',f"/supplier-team/{self.fixture['supplierId']}/commands",
                        dict(action=action,requestId=str(uuid4()),**fields),expected=expected)

    def test_current_future_and_revoked_access(self):
        offer,path,body=self.quote()
        self.assertEqual(self.api('manager','GET','/supplier-offers'),[])
        assignment=self.command('assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0)
        self.api('manager','PUT',path,body)
        newer,newpath,newbody=self.quote()
        self.api('manager','PUT',newpath,newbody)
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=None,version=assignment['version'])
        self.api('manager','PUT',path,body,expected=403)
        self.api('manager','PUT',newpath,newbody,expected=403)
        self.assertEqual(self.api('manager','GET','/supplier-offers'),[])

    def test_assignment_cannot_create_recipient_access_or_cross_supplier(self):
        offer,path,body=self.quote()
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s',(offer['requestId'],))
        self.api('manager','PUT',path,body,expected=403)
        self.command('assign_customer',actor='manager',companyId=self.fixture['companyId'],memberId=self.member_id,version=1,expected=403)
        self.command('assign_customer',actor='stranger_supplier',companyId=self.fixture['companyId'],memberId=self.member_id,version=1,expected=403)
        self.command('assign_customer',companyId=999999,memberId=self.member_id,version=0,expected=403)

    def test_disable_reenable_does_not_restore_customer_access(self):
        self.quote()
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0)
        version=self.sql('SELECT version FROM supplier_team_members WHERE id=%s',(self.member_id,))[0][0]
        off=self.command('member_active',memberId=self.member_id,version=version,active=False)
        self.assertIn(self.fixture['companyId'],off['releasedCompanyIds'])
        self.command('member_active',memberId=self.member_id,version=off['version'],active=True)
        self.assertEqual(self.api('manager','GET','/supplier-offers'),[])
        context=self.api('manager','GET','/supplier-team')
        self.assertEqual(context[0]['id'],self.fixture['supplierId'])
        self.assertEqual(context[0]['role'],'manager')

    def test_parallel_assignment_and_retry(self):
        self.quote()
        payload=dict(action='assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0,requestId=str(uuid4()))
        path=f"/supplier-team/{self.fixture['supplierId']}/commands"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.api('supplier','POST',path,payload),range(2)))
        self.assertEqual(results[0],results[1])
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=None,version=0,expected=409)

    def signup(self,invite):
        return self.client.post('/register',json={'code':invite['code'],'name':'Test manager','email':str(uuid4())+'@local.invalid','password':'Local-Test-Password-739!',
                                                 'companyId':3,'supplierId':999,'companyName':'Do not create company'})

    def test_invite_joins_existing_supplier_and_is_not_buyer_invite(self):
        invite=self.command('invite_manager')
        public=self.client.get('/invite-codes/'+invite['code']+'/info').json()
        self.assertTrue(public['supplierTeam'])
        ids=[r['id'] for r in self.api('director','GET','/invite-codes')]
        self.assertNotIn(invite['id'],ids)
        self.api('director','DELETE','/invite-codes/'+str(invite['id']),expected=403)
        before=self.sql('SELECT COUNT(*) FROM suppliers')[0][0]
        response=self.signup(invite)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM suppliers')[0][0],before)
        self.assertEqual(self.sql('''SELECT u.company_id,u.platform_account_id,m.role FROM supplier_team_members m
            JOIN users u ON u.id=m.user_id WHERE u.name='Test manager' ORDER BY u.id DESC LIMIT 1'''),[(None,None,'manager')])
        self.assertEqual(self.signup(invite).status_code,400)

    def test_revoked_expired_and_disabled_rollout_invite_rejected(self):
        invite=self.command('invite_manager');self.command('revoke_invite',inviteId=invite['id'])
        self.assertEqual(self.signup(invite).status_code,400)
        invite=self.command('invite_manager')
        self.sql("UPDATE invite_codes SET expires_at=NOW()-INTERVAL '1 day' WHERE id=%s",(invite['id'],))
        self.assertEqual(self.signup(invite).status_code,400)
        invite=self.command('invite_manager')
        with patch.dict(os.environ,{'SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED':'0'}):
            self.assertEqual(self.signup(invite).status_code,404)
            self.assertFalse(self.client.get('/invite-codes/'+invite['code']+'/info').json()['valid'])
            self.assertNotIn(invite['id'],[r['id'] for r in self.api('director','GET','/invite-codes')])

    def test_issuer_membership_version_prevents_invitation_revival(self):
        self.sql("UPDATE supplier_team_members SET role='leader' WHERE id=%s",(self.member_id,))
        invite=self.command('invite_manager',actor='manager')
        self.sql('UPDATE supplier_team_members SET active=FALSE,version=version+1 WHERE id=%s',(self.member_id,))
        self.sql('UPDATE supplier_team_members SET active=TRUE,version=version+1 WHERE id=%s',(self.member_id,))
        self.assertEqual(self.signup(invite).status_code,400)

    def test_owner_disable_reenable_does_not_revive_invite(self):
        invite=self.command('invite_manager')
        owner=self.fixture['users']['supplier']['id']
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(owner,))
        self.sql('UPDATE users SET active=TRUE WHERE id=%s',(owner,))
        self.assertEqual(self.signup(invite).status_code,400)

    def test_assigned_customer_without_request_is_visible(self):
        self.command('assign_customer',companyId=3,memberId=self.member_id,version=0)
        self.assertIn(3,[r['id'] for r in self.api('manager','GET','/supplier-team/customers')])
        self.command('assign_customer',companyId=3,memberId=None,version=1)
        self.assertEqual(self.api('manager','GET','/supplier-team/customers'),[])

    def test_invoice_shipment_and_replay_revoked_after_reassignment(self):
        offer,path,body=self.quote()
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0)
        self.api('manager','PUT',path,body)
        self.api('director','PUT',path,{'action':'select'})
        invoice={'invoiceNumber':'TEAM-CUSTOMER-'+str(offer['id']),'invoiceDate':'2026-09-20','amount':100}
        self.api('manager','POST',path+'/create-invoice',invoice)
        shipment={'shippedQuantity':1,'requestId':str(uuid4()),'waybillNumber':'TEAM-CUSTOMER-'+str(offer['id'])}
        self.api('manager','POST',path+'/ship',shipment)
        other_user=self.fixture['users']['stranger_supplier']['id']
        new_member=self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role) VALUES(%s,%s,'manager') RETURNING id",(self.fixture['supplierId'],other_user))[0][0]
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=new_member,version=1)
        self.assertEqual(self.api('manager','GET','/supplier-invoices'),[])
        self.assertEqual(self.api('manager','GET','/supply-deliveries'),[])
        self.api('manager','POST',path+'/create-invoice',invoice,expected=403)
        self.api('manager','POST',path+'/ship',shipment,expected=403)
        self.assertIn(offer['id'],[r['id'] for r in self.api('stranger_supplier','GET','/supplier-offers')])

    def test_reassignment_waits_for_authorized_mutation(self):
        from backend.features.supplier_team.policy import lock_offer_access
        from psycopg2.errors import LockNotAvailable
        offer,_,_=self.quote()
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0)
        first=self.main.get_db();first.autocommit=False
        second=self.main.get_db();second.autocommit=False
        try:
            with first.cursor() as cur:lock_offer_access(cur,offer['id'],self.manager['id'])
            with second.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(LockNotAvailable):
                    cur.execute('SELECT id FROM suppliers WHERE id=%s FOR UPDATE',(self.fixture['supplierId'],))
        finally:
            second.rollback();second.close();first.rollback();first.close()
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=None,version=1)
