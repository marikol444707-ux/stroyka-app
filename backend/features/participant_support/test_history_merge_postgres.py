"""Historical access requires a fresh exact plan, never a global reassignment."""
import importlib
import os
import unittest
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from .test_history_preview_postgres import SupplierHistoryPreviewPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierHistoryMergePostgresTests(unittest.TestCase):
    sql,api,pair=Base.sql,Base.api,Base.pair

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)
        cls.sql(cls,importlib.import_module('migrations.versions.0038_supplier_customer_team').SCHEMA_SQL)
        cls.sql(cls,importlib.import_module('migrations.versions.0095_supplier_buyer_connections').SCHEMA_SQL)
        patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1',SUPPLIER_TEAM_ENABLED='1').start()
        migration=importlib.import_module('migrations.versions.0096_supplier_history_merge_plans')
        cls.sql(cls,migration.SCHEMA_SQL)

    def path(self,source,company=2):
        return f'/system/companies/{company}/participants/{source}/history-merge-plans'

    def review(self,source,target,**kwargs):
        return self.api('admin','POST',self.path(source,kwargs.pop('company',2)),{'targetSupplierId':target},**kwargs)

    def confirm(self,source,plan,**kwargs):
        return self.api(kwargs.pop('actor','admin'),'POST',self.path(source,kwargs.pop('company',2))+f"/{plan['id']}/confirm",
            dict(confirmed=True,reason='Проверено юрлицо и принадлежность старых документов'),**kwargs)

    def seed(self):
        source,target=self.pair()
        invoice=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,200,50) RETURNING id',(source,))[0][0]
        return source,target,invoice

    def test_00_empty_migration_replay_downgrade_and_immutable_evidence(self):
        migration=importlib.import_module('migrations.versions.0096_supplier_history_merge_plans')
        conn=self.main.get_db()
        try:
            with conn,conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade();migration.upgrade();migration.upgrade()
        finally:conn.close()
        source,target,_=self.seed();plan=self.review(source,target)
        from psycopg2.errors import RaiseException
        for query in ('DELETE FROM supplier_history_merge_plans WHERE id=%s',
                      "UPDATE supplier_history_merge_plans SET manifest='{}' WHERE id=%s"):
            with self.assertRaises(RaiseException):self.sql(query,(plan['id'],))
        conn=self.main.get_db()
        try:
            with self.assertRaises(RaiseException),conn,conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade()
        finally:conn.close()

    def test_plan_confirm_and_retry_keep_originals_and_one_audit(self):
        source,target,invoice=self.seed()
        before=self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s',(invoice,))
        plan=self.review(source,target)
        self.assertEqual(plan['newAccess']['invoices'],[invoice])
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        result=self.confirm(source,plan)
        self.assertTrue(result['ok'])
        self.assertEqual(result,self.confirm(source,plan))
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s',(invoice,)),before)
        owner=self.fixture['users']['supplier']['id']
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(owner,)])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_history_merged' AND entity_id=%s",(source,)),[(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_team_members WHERE supplier_id=%s',(source,)),[(0,)])
        self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s',(source,))
        self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(owner,source))
        self.confirm(source,plan,expected=409)

    def test_changed_history_and_owner_epoch_invalidate_plan(self):
        for change in ('invoice','owner'):
            source,target,invoice=self.seed();plan=self.review(source,target)
            if change=='invoice':self.sql('UPDATE supplier_invoices SET paid_amount=60 WHERE id=%s',(invoice,))
            else:
                self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s',(target,))
                self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(self.fixture['users']['supplier']['id'],target))
            self.confirm(source,plan,expected=409)
            self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_foreign_or_shared_source_and_legacy_command_cannot_grant(self):
        source,target,invoice=self.seed()
        self.api('director','POST',self.path(source),{'targetSupplierId':target},expected=403)
        self.api('admin','POST',self.path(source,3),{'targetSupplierId':target},expected=404)
        self.api('director','POST',f'/suppliers/{target}/merge',dict(companyId=2,sourceId=source,sourceVersion=1,targetVersion=1,confirmed=True),expected=409,**{'X-Company-Id':'2'})
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(3,1,%s)',(source,))
        self.review(source,target,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_expiry_flag_forgery_and_fresh_role_fail_closed(self):
        source,target,invoice=self.seed();plan=self.review(source,target)
        self.api('admin','POST',self.path(source)+f"/{uuid.uuid4()}/confirm",dict(confirmed=True,reason='Проверено юрлицо'),expected=404)
        self.api('admin','POST',self.path(source)+f"/{plan['id']}/confirm",dict(confirmed=False,reason='Проверено юрлицо'),expected=422)
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='0'):self.confirm(source,plan,expected=503)
        admin=self.fixture['users']['admin']['id']
        self.sql('UPDATE users SET supplier_team_epoch=supplier_team_epoch+1 WHERE id=%s',(admin,))
        self.confirm(source,plan,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_expired_plan_cannot_grant_history(self):
        source,target,_=self.seed()
        with patch('backend.features.participant_support.history_merge.PLAN_TTL_SECONDS',0.1):plan=self.review(source,target)
        time.sleep(0.15);self.confirm(source,plan,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_exact_file_rights_include_photo_arrays_without_foreign_or_unrelated_files(self):
        source,target,invoice=self.seed()
        files=[]
        for company in (2,2,3):
            files.append(self.sql('INSERT INTO file_ownership(company_id,file_url,context) VALUES(%s,%s,\'documents\') RETURNING id',
                          (company,f'/uploads/company-{company}-common-documents/'+str(uuid.uuid4())+'.pdf'))[0][0])
        wi=self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,photo_urls,supplier_invoice_id) VALUES(2,%s,%s,%s) RETURNING id',
                    (source,__import__('json').dumps([f'/tenant-files/{files[0]}/content',f'/tenant-files/{files[2]}/content']),invoice))[0][0]
        plan=self.review(source,target)
        self.assertEqual(plan['newAccess']['files'],[files[0]])
        self.assertNotIn(files[1],plan['newAccess']['files'])
        self.assertNotIn(files[2],plan['newAccess']['files'])
        self.confirm(source,plan)
        from ..document_access.supplier_files import authorize_read
        from psycopg2.extras import RealDictCursor
        conn=self.main.get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                owner=self.fixture['users']['supplier']
                for fid,expected in ((files[0],True),(files[1],False),(files[2],False)):
                    cur.execute('SELECT * FROM file_ownership WHERE id=%s',(fid,));row=cur.fetchone()
                    if expected:self.assertEqual(authorize_read(cur,owner,row)['id'],owner['id'])
                    else:
                        from fastapi import HTTPException
                        with self.assertRaises(HTTPException):authorize_read(cur,owner,row)
        finally:conn.close()
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s',(wi,)),[(invoice,)])
        self.api('supplier','GET',f'/tenant-files/{files[0]}')
        self.api('supplier','GET',f'/tenant-files/{files[1]}',expected=403)
        self.api('supplier','GET',f'/tenant-files/{files[2]}',expected=403)

    def test_invalid_storage_namespace_cannot_be_promised_or_granted(self):
        source,target,invoice=self.seed()
        fid=self.sql("INSERT INTO file_ownership(company_id,file_url,context) VALUES(2,%s,'documents') RETURNING id",
                     ('/uploads/another-company/'+str(uuid.uuid4())+'.pdf',))[0][0]
        self.sql('UPDATE supplier_invoices SET file_url=%s WHERE id=%s',(f'/tenant-files/{fid}/content',invoice))
        self.review(source,target,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_delivery_and_coherent_claim_photos_use_the_original_chain(self):
        source,target,_=self.seed()
        request=self.sql("INSERT INTO supply_requests(company_id,project,material_name,status,selected_suppliers,prorab_confirmed_at,director_approved_at) VALUES(2,'Synthetic','Synthetic','Утверждена',%s,NOW(),NOW()) RETURNING id",([source],))[0][0]
        offer=self.sql('INSERT INTO supplier_offers(company_id,supplier_id,request_id) VALUES(2,%s,%s) RETURNING id',(source,request))[0][0]
        files=[self.sql("INSERT INTO file_ownership(company_id,file_url,context) VALUES(2,%s,'documents') RETURNING id",
                        ('/uploads/company-2-common-documents/'+str(uuid.uuid4())+'.pdf',))[0][0] for _ in range(2)]
        delivery=self.sql("INSERT INTO supply_deliveries(company_id,request_id,offer_id,supplier_id,project,work_package,document_url) VALUES(2,%s,%s,%s,'Synthetic','Test',%s) RETURNING id",
                          (request,offer,source,f'/tenant-files/{files[0]}/content'))[0][0]
        claim=self.sql("INSERT INTO supply_claims(delivery_id,request_id,offer_id,supplier_id,project,work_package,photo_url) VALUES(%s,%s,%s,%s,'Synthetic','Test',%s) RETURNING id",
                       (delivery,request,offer,source,f'/tenant-files/{files[1]}/content'))[0][0]
        plan=self.review(source,target)
        self.assertEqual(plan['newAccess']['files'],files)
        self.assertIn(delivery,plan['newAccess']['deliveries']);self.assertIn(claim,plan['newAccess']['claims'])
        originals=self.sql('SELECT to_jsonb(c) FROM supply_claims c WHERE id=%s',(claim,))
        self.confirm(source,plan)
        for fid in files:self.api('supplier','GET',f'/tenant-files/{fid}')
        self.assertIn(delivery,[r['id'] for r in self.api('supplier','GET','/supply-deliveries')])
        self.assertIn(claim,[r['id'] for r in self.api('supplier','GET','/supply-claims')])
        self.assertEqual(originals,self.sql('SELECT to_jsonb(c) FROM supply_claims c WHERE id=%s',(claim,)))

    def test_unresolved_claim_owner_blocks_history_merge(self):
        source,target,_=self.seed()
        self.sql("INSERT INTO supply_claims(supplier_id,project) VALUES(%s,'Synthetic unknown parent')",(source,))
        self.review(source,target,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_manager_customer_assignment_is_preserved_without_source_archive_grant(self):
        source,target,invoice=self.seed()
        user=self.sql("INSERT INTO users(name,role,active) VALUES('Synthetic manager','поставщик',TRUE) RETURNING id")[0][0]
        self.fixture['users']['history_manager']=dict(id=user,role='поставщик',name='Synthetic manager')
        member=self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role,active) VALUES(%s,%s,'manager',TRUE) RETURNING id",(target,user))[0][0]
        self.sql('INSERT INTO supplier_customer_assignments(supplier_id,company_id,member_id) VALUES(%s,2,%s)',(target,member))
        before=self.sql('SELECT to_jsonb(t) FROM supplier_customer_assignments t WHERE supplier_id=%s',(target,))
        with patch.dict(os.environ,SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED='1'):
            plan=self.review(source,target);self.confirm(source,plan)
            self.assertIn(invoice,[row['id'] for row in self.api('supplier','GET','/supplier-invoices')])
            self.assertNotIn(invoice,[row['id'] for row in self.api('history_manager','GET','/supplier-invoices')])
        self.assertEqual(before,self.sql('SELECT to_jsonb(t) FROM supplier_customer_assignments t WHERE supplier_id=%s',(target,)))

    def test_foreign_selected_supplier_array_cannot_be_activated_by_merge(self):
        source,target,_=self.seed()
        self.sql("INSERT INTO supply_requests(company_id,project,material_name,selected_suppliers) VALUES(3,'Synthetic foreign project','Synthetic',%s)",([source],))
        self.review(source,target,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_new_attachment_after_review_requires_another_plan(self):
        source,target,invoice=self.seed();plan=self.review(source,target)
        fid=self.sql("INSERT INTO file_ownership(company_id,file_url,context) VALUES(2,%s,'documents') RETURNING id",
                     ('/uploads/company-2-common-documents/'+str(uuid.uuid4())+'.pdf',))[0][0]
        self.sql('UPDATE supplier_invoices SET file_url=%s WHERE id=%s',(f'/tenant-files/{fid}/content',invoice))
        self.confirm(source,plan,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.review(source,target)['newAccess']['files'],[fid])

    def test_foreign_recipient_group_does_not_activate_historical_card(self):
        source,target,_=self.seed()
        request=self.sql("INSERT INTO supply_requests(company_id,project,material_name) VALUES(3,'Synthetic foreign','Synthetic') RETURNING id")[0][0]
        self.sql('INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,supplier_group_ids) VALUES(3,%s,%s,%s,%s)',
                 (request,target,target,[source]))
        self.review(source,target,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_new_access_uses_addressed_offer_policy_and_includes_already_owned_target(self):
        source,target,invoice=self.seed()
        request=self.sql("INSERT INTO supply_requests(company_id,project,material_name,status,selected_suppliers,prorab_confirmed_at,director_approved_at) VALUES(2,'Synthetic','Synthetic','Утверждена',%s,NOW(),NOW()) RETURNING id",([source],))[0][0]
        visible=self.sql('INSERT INTO supplier_offers(company_id,supplier_id,request_id) VALUES(2,%s,%s) RETURNING id',(target,request))[0][0]
        hidden_request=self.sql("INSERT INTO supply_requests(company_id,project,material_name,status) VALUES(2,'Synthetic','Synthetic','Новая') RETURNING id")[0][0]
        hidden=self.sql('INSERT INTO supplier_offers(company_id,supplier_id,request_id) VALUES(2,%s,%s) RETURNING id',(source,hidden_request))[0][0]
        plan=self.review(source,target)
        self.assertIn(visible,plan['newAccess']['offers'])
        self.assertNotIn(hidden,plan['newAccess']['offers'])
        self.assertIn(hidden,plan['stillClosed']['offers'])
        self.confirm(source,plan)
        offers=self.api('supplier','GET','/supplier-offers')
        self.assertIn(visible,[row['id'] for row in offers]);self.assertNotIn(hidden,[row['id'] for row in offers])

    def test_audit_failure_rolls_back_pair_and_applied_plan(self):
        source,target,_=self.seed();plan=self.review(source,target)
        self.sql("CREATE FUNCTION synthetic_merge_audit_fail() RETURNS trigger AS $$ BEGIN IF NEW.action='supplier_history_merged' THEN RAISE EXCEPTION 'Synthetic audit failure'; END IF; RETURN NEW; END $$ LANGUAGE plpgsql")
        self.sql('CREATE TRIGGER synthetic_merge_audit_fail BEFORE INSERT ON audit_log FOR EACH ROW EXECUTE FUNCTION synthetic_merge_audit_fail()')
        from psycopg2.errors import RaiseException
        try:
            with self.assertRaises(RaiseException):self.confirm(source,plan)
        finally:self.sql('DROP TRIGGER synthetic_merge_audit_fail ON audit_log; DROP FUNCTION synthetic_merge_audit_fail()')
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.sql('SELECT applied_at FROM supplier_history_merge_plans WHERE id=%s',(plan['id'],)),[(None,)])

    def test_concurrent_confirm_is_atomic_and_retry_returns_same_result(self):
        source,target,_=self.seed();plan=self.review(source,target)
        from fastapi.testclient import TestClient
        token=self.main.create_auth_token(self.fixture['users']['admin'],two_factor_passed=True)
        barrier=Barrier(2)
        def run():
            with TestClient(self.main.app) as client:
                barrier.wait(timeout=10)
                return client.post(self.path(source)+f"/{plan['id']}/confirm",json=dict(confirmed=True,reason='Проверено юрлицо и принадлежность старых документов'),headers={'Authorization':'Bearer '+token})
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending=[pool.submit(run) for _ in range(2)];results=[f.result(timeout=30) for f in pending]
        self.assertIn(200,[r.status_code for r in results])
        self.assertTrue(all(r.status_code in (200,409) for r in results),[r.text for r in results])
        self.assertTrue(self.confirm(source,plan)['ok'])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_history_merged' AND entity_id=%s",(source,)),[(1,)])

    def test_fifty_companies_reuse_one_canonical_cabinet_after_each_merge(self):
        source,target,_=self.seed();inn=self.sql('SELECT inn FROM suppliers WHERE id=%s',(target,))[0][0]
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(199,'Synthetic history accounts','pro','active')")
        for company in range(800,850):
            account=1 if company<825 else 199
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,'Synthetic buyer',%s,TRUE,'pro')",(company,account))
            card=self.sql("INSERT INTO suppliers(name,inn) VALUES('Synthetic legacy receipt',%s) RETURNING id",(inn,))[0][0]
            for sid in (card,target):self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)',(company,account,sid))
            invoice=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(%s,%s,100) RETURNING id',(company,card))[0][0]
            plan=self.review(card,target,company=company)
            self.assertEqual(plan['newAccess']['invoices'],[invoice]);self.confirm(card,plan,company=company)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
