"""Exact user/staff selections through real contract and assignment HTTP APIs."""
import importlib
import json
import os
import unittest
from uuid import uuid4

from ..work_acceptance import test_integration_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class TypedContractorSelectionPostgresTests(unittest.TestCase):
    sql = support.WorkAcceptanceIntegrationPostgresTests.sql
    api = support.WorkAcceptanceIntegrationPostgresTests.api
    request = support.WorkAcceptanceIntegrationPostgresTests.request

    @classmethod
    def setUpClass(cls):
        support.WorkAcceptanceIntegrationPostgresTests.setUpClass.__func__(cls)
        from .manual_schema import SCHEMA_SQL
        before = cls.sql(cls,'SELECT to_jsonb(c) FROM brigade_contracts c ORDER BY id')
        cls.sql(cls, SCHEMA_SQL)
        if cls.sql(cls,'SELECT to_jsonb(c) FROM brigade_contracts c ORDER BY id') != before:
            raise AssertionError('Manual origin migration modified historical contracts')
        if cls.sql(cls,'SELECT COUNT(*) FROM manual_brigade_contract_origins') != [(0,)]:
            raise AssertionError('Manual origin migration backfilled historical identities')
        migration=importlib.import_module('migrations.versions.0006_user_company_staff_links')
        cls.sql(cls,'ALTER TABLE staff ADD COLUMN IF NOT EXISTS company_scope_verified BOOLEAN NOT NULL DEFAULT FALSE')
        for statement in (migration._ADD_STAFF_LINK,migration._ADD_INDEXES,migration._ADD_FOREIGN_KEY):
            cls.sql(cls,statement)

    def setUp(self):
        self.f=self.fixture
        self.tag=uuid4().hex[:12]
        # One actual user has the exact same numeric ID/name/email as a staff
        # record whose persisted account link points to another actual user.
        self.collision=self.sql("""INSERT INTO users(name,email,role,active,company_id)
            VALUES(%s,%s,'мастер',TRUE,2) RETURNING id""",('Typed '+self.tag,self.tag+'@local.invalid'))[0][0]
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,role,active,assigned_projects,assigned_packages)
            VALUES(%s,2,'мастер',TRUE,'[]','[]')""",(self.collision,))
        self.target=self.sql("""INSERT INTO users(name,email,role,active,company_id)
            VALUES(%s,%s,'мастер',TRUE,2) RETURNING id""",('Typed '+self.tag,'target-'+self.tag+'@local.invalid'))[0][0]
        self.sql("""INSERT INTO staff(id,company_id,name,email_work,status,company_scope_verified)
            VALUES(%s,2,%s,%s,'Активен',TRUE)""",(self.collision,'Typed '+self.tag,self.tag+'@local.invalid'))
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,staff_id,role,active,assigned_projects,assigned_packages)
            VALUES(%s,2,%s,'мастер',TRUE,'[]','[]')""",(self.target,self.collision))
        for actor,uid in (('typed_collision',self.collision),('typed_target',self.target)):
            self.f['users'][actor]={'id':uid,'name':'Typed '+self.tag,'role':'мастер','companyId':2,'company_id':2}
        self.name='Typed '+self.tag
        self.contract={'projectId':self.f['projectId'],'projectName':self.f['project'],
            'brigadeName':self.name,'workPackage':self.f['workPackage'],'contractorType':'Мастер'}

    def state(self):
        return [(table,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id')) for table in
            ('brigade_contracts','brigade_contract_items','users','user_company_roles','estimates','estimate_versions')]

    def test_same_number_selects_different_exact_user_and_staff_accounts(self):
        for kind,owner in (('staff',self.target),('user',self.collision)):
            selected=self.api('director','POST','/brigade-contracts',{**self.contract,
                'contractorId':self.collision,'contractorRef':{'type':kind,'id':self.collision}})
            self.assertEqual(selected['contractorId'],owner)
            self.assertEqual(self.sql('SELECT contractor_id FROM brigade_contracts WHERE id=%s',(selected['id'],)),[(owner,)])
            self.api('director','POST','/brigade-contract-items',{'contractId':selected['id'],
                'name':'Typed contract work','unit':'м','quantity':5,'priceBrigade':60,'priceSmeta':100})
            visible=self.api('typed_target' if kind=='staff' else 'typed_collision','GET','/brigade-contracts')
            self.assertIn(selected['id'],[row['id'] for row in visible])
            foreign=self.api('typed_collision' if kind=='staff' else 'typed_target','GET','/brigade-contracts')
            self.assertNotIn(selected['id'],[row['id'] for row in foreign])

    def test_revoked_user_membership_does_not_fall_back_to_users_company_id(self):
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(self.collision,))
        before=self.state()
        self.api('director','POST','/brigade-contracts',{**self.contract,
            'contractorRef':{'type':'user','id':self.collision}},expected=409)
        self.assertEqual(before,self.state())

    def test_fired_staff_and_foreign_staff_cannot_use_name_email_or_numeric_collision(self):
        for change,restore,args in (
            ("UPDATE staff SET status='Уволен' WHERE id=%s","UPDATE staff SET status='Активен' WHERE id=%s",(self.collision,)),
            ('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s',
             'UPDATE user_company_roles SET active=TRUE WHERE user_id=%s',(self.target,)),
        ):
            with self.subTest(change=change):
                self.sql(change,args)
                before=self.state()
                try:
                    self.api('director','POST','/brigade-contracts',{**self.contract,
                        'contractorRef':{'type':'staff','id':self.collision}},expected=409)
                    self.assertEqual(before,self.state())
                finally:self.sql(restore,args)
        foreign=self.sql("INSERT INTO staff(company_id,name,status,company_scope_verified) VALUES(3,%s,'Активен',TRUE) RETURNING id",(self.name,))[0][0]
        self.api('director','POST','/brigade-contracts',{**self.contract,
            'contractorRef':{'type':'staff','id':foreign}},expected=409)

    def test_invalid_explicit_reference_does_not_downgrade_to_legacy_matching(self):
        before=self.state()
        for reference in (None,{'type':'unknown','id':self.collision},{'type':'user','id':True}):
            with self.subTest(reference=reference):
                self.api('director','POST','/brigade-contracts',{**self.contract,
                    'contractorId':self.collision,'contractorRef':reference},expected=400)
        self.api('director','POST','/brigade-contracts',{**self.contract,'contractorId':self.target,
            'contractorRef':{'type':'staff','id':self.collision}},expected=400)
        self.assertEqual(before,self.state())

    def test_estimate_assignment_uses_the_same_typed_staff_link_and_preserves_failed_attempts(self):
        estimate=self.f['estimateId']
        key='typed-work-'+self.tag
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s',(json.dumps([{'name':'Typed section','items':[
            {'name':'Typed work','type':'work','unit':'м','quantity':5,'priceWork':100,'estimateItemKey':key}]}]),estimate))
        payload={'assignee':{'contractorId':self.collision,'contractorRef':{'type':'staff','id':self.collision},
            'brigadeName':self.name},'priceMode':'coefficient','coefficient':0.6,
            'items':[{'sectionIndex':0,'itemIndex':0,'estimateItemKey':key}]}
        initial=self.state()
        self.api('director','POST',f'/estimates/{estimate}/work-assignment',
            {**payload,'contractorRef':{'type':'user','id':self.collision}},expected=400)
        self.api('director','POST',f'/estimates/{estimate}/work-assignment',
            {**payload,'assignee':{**payload['assignee'],'contractorId':0}},expected=400)
        self.assertEqual(initial,self.state())
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s',(self.target,))
        before=self.state()
        self.api('director','POST',f'/estimates/{estimate}/work-assignment',payload,expected=409)
        self.assertEqual(before,self.state())
        self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s',(self.target,))
        assigned=self.api('director','POST',f'/estimates/{estimate}/work-assignment',payload)
        self.assertEqual(assigned['contractorId'],self.target)
        self.assertEqual(self.api('typed_collision','GET',f"/brigade-contract-items/{assigned['contractId']}"),[])
        items=self.api('typed_target','GET',f"/brigade-contract-items/{assigned['contractId']}")
        self.assertEqual([row['name'] for row in items],['Typed work'])

    def test_selected_staff_membership_is_pinned_until_the_command_transaction_ends(self):
        from concurrent.futures import ThreadPoolExecutor
        import psycopg2
        from .selection import resolve_selected_user
        conn=self.main.get_db()
        conn.autocommit=False
        try:
            with conn.cursor() as cur:
                self.assertEqual(resolve_selected_user(cur,2,{'type':'staff','id':self.collision}),self.target)
            def revoke():
                other=self.main.get_db()
                other.autocommit=False
                try:
                    with other.cursor() as cur:
                        cur.execute("SET LOCAL lock_timeout='100ms'")
                        cur.execute('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s',(self.target,))
                    other.commit()
                finally:other.close()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(revoke)
                with self.assertRaises(psycopg2.errors.LockNotAvailable):future.result(timeout=3)
        finally:
            conn.rollback();conn.close()
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s',(self.target,))
        self.api('director','POST','/brigade-contracts',{**self.contract,
            'contractorRef':{'type':'staff','id':self.collision}},expected=409)
