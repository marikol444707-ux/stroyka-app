"""Authenticated supplier team boundaries on disposable PostgreSQL, no external traffic."""
import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from backend.features.supplier_offers import test_response_postgres as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class TeamPolicyPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.SupplierResponsePostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {'SUPPLIER_TEAM_ENABLED': '1'})
        flag.start(); cls.addClassCleanup(flag.stop)
        SCHEMA_SQL = importlib.import_module('migrations.versions.0035_supplier_team_policy').SCHEMA_SQL
        conn = cls.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
                cur.execute("INSERT INTO users(name,email,role,active) VALUES('TEAM manager','manager@local.invalid','поставщик',TRUE) RETURNING id,name,email,role,active")
                row = cur.fetchone()
                cls.manager = dict(zip(('id','name','email','role','active'), row))
                cls.fixture['users']['manager'] = cls.manager
                cur.execute("INSERT INTO supplier_team_members(supplier_id,user_id,role) VALUES(%s,%s,'manager') RETURNING id", (cls.fixture['supplierId'], cls.manager['id']))
                cls.member_id = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()

    api = support.SupplierResponsePostgresTests.api
    sql = support.SupplierResponsePostgresTests.sql
    quote = support.SupplierResponsePostgresTests.quote

    def setUp(self):
        self.sql("UPDATE supplier_team_members SET active=TRUE,role='manager' WHERE id=%s", (self.member_id,))
        self.sql("UPDATE users SET active=TRUE,role='поставщик' WHERE id=%s", (self.manager['id'],))
        self.sql('DELETE FROM supplier_offer_assignments')

    def assign(self, offer):
        self.sql('INSERT INTO supplier_offer_assignments(offer_id,supplier_id,member_id) VALUES(%s,%s,%s)',
                 (offer['id'], self.fixture['supplierId'], self.member_id))

    def test_manager_only_assigned_reads_response_and_revocation(self):
        a, path, body = self.quote()
        b, other, other_body = self.quote()
        self.assertEqual(self.api('manager', 'GET', '/supplier-offers'), [])
        self.assertEqual(self.api('manager', 'GET', '/supply-requests'), [])
        self.api('manager', 'PUT', path, body, expected=403)
        self.assign(a)
        self.assertEqual([r['id'] for r in self.api('manager','GET','/supplier-offers', **{'X-Company-Id':'3'})], [a['id']])
        self.assertEqual([r['id'] for r in self.api('manager','GET','/supply-requests')], [a['requestId']])
        self.api('manager','PUT',other,other_body,expected=403)
        self.api('manager','PUT',path,body)
        self.api('stranger_supplier','PUT',path,body,expected=403)
        self.sql('UPDATE supplier_team_members SET active=FALSE WHERE id=%s', (self.member_id,))
        self.assertEqual(self.api('manager','GET','/supplier-offers'), [])
        self.assertEqual(self.api('manager','GET','/supply-requests'), [])
        self.api('manager','PUT',path,body,expected=403)

    def test_leader_all_manager_only_assigned_documents_and_shipping(self):
        a,path,body=self.quote()
        self.api('supplier','PUT',path,body)
        self.api('director','PUT',path,{'action':'select'})
        invoice_body={'invoiceNumber':'TEAM-'+str(a['id']),'invoiceDate':'2026-09-20','amount':100}
        self.api('manager','POST',path+'/create-invoice',invoice_body,expected=403)
        self.api('manager','POST',path+'/ship',{'shippedQuantity':1},expected=403)
        self.assertEqual(self.api('manager','GET','/supplier-invoices'),[])
        self.assign(a)
        invoice = self.api('manager','POST',path+'/create-invoice',invoice_body)
        self.assertIn(invoice['id'],[r['id'] for r in self.api('manager','GET','/supplier-invoices')])
        self.api('manager','POST',path+'/ship',{'shippedQuantity':1,'waybillNumber':'TEAM-'+str(a['id'])})
        self.assertEqual([r['offerId'] for r in self.api('manager','GET','/supply-deliveries')],[a['id']])
        self.sql('DELETE FROM supplier_offer_assignments WHERE offer_id=%s',(a['id'],))
        self.api('manager','POST',path+'/ship',{'shippedQuantity':1,'waybillNumber':'TEAM-'+str(a['id'])},expected=403)
        self.assertEqual(self.api('manager','GET','/supply-deliveries'),[])
        self.assertEqual(self.api('manager','GET','/supplier-invoices'),[])
        self.sql("UPDATE supplier_team_members SET role='leader' WHERE id=%s",(self.member_id,))
        self.assertIn(a['id'],[r['id'] for r in self.api('manager','GET','/supplier-offers')])
        self.assertIn(invoice['id'],[r['id'] for r in self.api('manager','GET','/supplier-invoices')])

    def test_inactive_actor_and_wrong_supplier_assignment_fail_closed(self):
        a,path,body=self.quote();self.assign(a)
        self.sql("UPDATE users SET role='снабженец' WHERE id=%s",(self.manager['id'],))
        from backend.features.supplier_team.policy import access_ids, lock_offer_access
        conn=self.main.get_db()
        try:
            with conn.cursor() as cur:
                self.assertEqual(access_ids(cur,self.manager),[])
                with self.assertRaises(Exception):lock_offer_access(cur,a['id'],self.manager['id'])
        finally:conn.close()
        self.sql("UPDATE users SET role='поставщик',active=FALSE WHERE id=%s",(self.manager['id'],))
        # Authentication itself must reject disabled users before any team authorization.
        token=self.main.create_auth_token(self.manager,two_factor_passed=True)
        response=self.client.get('/supplier-offers',headers={'Authorization':'Bearer '+token})
        self.assertIn(response.status_code,(401,403))
        self.sql('DELETE FROM supplier_offer_assignments')
        other_supplier=self.sql('SELECT id FROM suppliers WHERE user_id=%s',(self.fixture['users']['stranger_supplier']['id'],))[0][0]
        with self.assertRaises(Exception):
            self.sql('INSERT INTO supplier_offer_assignments(offer_id,supplier_id,member_id) VALUES(%s,%s,%s)',(a['id'],other_supplier,self.member_id))

    def test_migration_is_idempotent_and_preserves_memberships(self):
        migration=importlib.import_module('migrations.versions.0035_supplier_team_policy')
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn.cursor() as cur:
                with patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                    migration.upgrade();migration.upgrade()
                    with self.assertRaisesRegex(Exception,'Cannot discard recorded'):
                        migration.downgrade()
        finally:conn.rollback();conn.close()

    def test_revocation_waits_for_authorized_transaction(self):
        from backend.features.supplier_team.policy import lock_offer_access
        import psycopg2
        a,_,_=self.quote();self.assign(a)
        first=self.main.get_db();first.autocommit=False
        second=self.main.get_db();second.autocommit=False
        try:
            with first.cursor() as cur:
                lock_offer_access(cur,a['id'],self.manager['id'])
            with second.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    cur.execute('UPDATE supplier_team_members SET active=FALSE WHERE id=%s',(self.member_id,))
            second.rollback();first.rollback()
            with second.cursor() as cur:
                cur.execute('UPDATE supplier_team_members SET active=FALSE WHERE id=%s',(self.member_id,))
            second.commit()
            with first.cursor() as cur:
                with self.assertRaisesRegex(Exception,'403'):
                    lock_offer_access(cur,a['id'],self.manager['id'])
        finally:first.rollback();first.close();second.close()

    def test_owner_keeps_legacy_request_without_offer_and_manager_cannot_create_one(self):
        a,path,body=self.quote()
        self.sql('DELETE FROM supplier_offers WHERE id=%s',(a['id'],))
        self.assertIn(a['requestId'],[r['id'] for r in self.api('supplier','GET','/supply-requests')])
        self.assertEqual(self.api('manager','GET','/supply-requests'),[])
        self.api('manager','POST','/supplier-offers',{'requestId':a['requestId'],'supplierId':self.fixture['supplierId'],'pricePerUnit':100,'totalPrice':100},expected=403)
        self.sql("UPDATE supplier_team_members SET role='leader' WHERE id=%s",(self.member_id,))
        self.assertIn(a['requestId'],[r['id'] for r in self.api('manager','GET','/supply-requests')])

    def test_unlinked_invoice_requires_leader_and_assignment_does_not_survive_withdrawn_recipient(self):
        a,path,body=self.quote();self.assign(a)
        invoice_id=self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,invoice_number,amount,status) VALUES(%s,%s,'TEAM direct',1,'К оплате') RETURNING id",(self.fixture['companyId'],self.fixture['supplierId']))[0][0]
        self.assertNotIn(invoice_id,[r['id'] for r in self.api('manager','GET','/supplier-invoices')])
        self.sql("UPDATE supplier_team_members SET role='leader' WHERE id=%s",(self.member_id,))
        self.assertIn(invoice_id,[r['id'] for r in self.api('manager','GET','/supplier-invoices')])
        self.sql("UPDATE supplier_team_members SET role='manager' WHERE id=%s",(self.member_id,))
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s',(a['requestId'],))
        self.assertNotIn(a['id'],[r['id'] for r in self.api('manager','GET','/supplier-offers')])
        self.api('manager','PUT',path,body,expected=403)

    def test_invoice_cannot_mix_assigned_offer_with_another_supplier_identity(self):
        a,_,_=self.quote();self.assign(a)
        other=self.sql('SELECT id FROM suppliers WHERE user_id=%s',(self.fixture['users']['stranger_supplier']['id'],))[0][0]
        self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role) VALUES(%s,%s,'manager') ON CONFLICT(supplier_id,user_id) DO UPDATE SET active=TRUE",(other,self.manager['id']))
        bad=self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,offer_id,request_id,invoice_number) VALUES(%s,%s,%s,%s,'TEAM invalid identity') RETURNING id",(self.fixture['companyId'],other,a['id'],a['requestId']))[0][0]
        self.assertNotIn(bad,[r['id'] for r in self.api('manager','GET','/supplier-invoices')])
