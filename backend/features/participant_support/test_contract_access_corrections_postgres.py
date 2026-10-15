"""Contract versions and originals stay in the buyer archive after access closes."""
import os
import unittest
import uuid
from unittest.mock import patch

from .test_invoice_access_corrections_postgres import SupplierInvoiceAccessCorrectionsPostgresTests as Fixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierContractAccessCorrectionsPostgresTests(unittest.TestCase):
    sql,api,connection,rfq,received,raw,chain,invoice,confirm=(Fixture.sql,Fixture.api,Fixture.connection,
        Fixture.rfq,Fixture.received,Fixture.raw,Fixture.chain,Fixture.invoice,Fixture.confirm)

    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass.__func__(cls)
        from ..supplier_deal_parties.test_contract_postgres import statements
        from ..supplier_deal_parties.test_binding_migration import statements as bindings
        for migration in ('0065_contract_archive.py','0066_contract_publications.py'):
            for statement in statements('upgrade',migration):cls.sql(cls,statement)
        for statement in bindings():cls.sql(cls,statement)
        patch.dict(os.environ,PARTICIPANT_CONTRACT_ACCESS_CORRECTIONS_ENABLED='1').start()
        # Register the real flagged modules on this synthetic authenticated app.
        # The baseline boots first, then earlier correction fixtures apply schema.
        deps=dict(get_db=cls.main.get_db,get_current_user=cls.main.get_current_user,
            resolve_resource_company_actor=cls.main.resolve_resource_company_actor,
            current_supplier_ids=cls.main.current_supplier_access_ids,
            require_project_access=cls.main.require_project_or_warehouse_access,
            has_package_access=cls.main.has_package_access,
            platform_staff_roles=cls.main.PLATFORM_STAFF_ROLES,client_account_roles=cls.main.CLIENT_ACCOUNT_ROLES)
        from ..supplier_deal_parties.supplier_originals import register_supplier_originals
        from ..supplier_deal_parties.contracts import register_supplier_contracts_module
        from ..supplier_deal_parties.document_routes import register_document_contract_routes
        register_supplier_originals(cls.main.app,deps)
        register_supplier_contracts_module(cls.main.app,deps)
        register_document_contract_routes(cls.main.app,deps)
        cls.main.document_access_dependencies['supplier_contract_files_enabled']=True
        for company in (2,3):
            cls.sql(cls,"INSERT INTO company_requisites(company_id,inn,full_name) VALUES(%s,'7701234567','Synthetic buyer') ON CONFLICT(company_id) DO UPDATE SET inn=EXCLUDED.inn,full_name=EXCLUDED.full_name",(company,))

    def path(self,source,connection,company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{connection}/contract-access-plans'

    def plan(self,source,connection,**kwargs):
        return self.api('admin','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),**kwargs)

    def business_snapshot(self):
        result=Fixture.business_snapshot(self)
        result.update({t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY to_jsonb(t)::text') for t in
            ('supplier_contract_versions','supplier_contract_registry','supplier_contract_registry_versions',
             'supplier_contract_registry_events','supplier_contract_publications')})
        return result

    def upload(self,company=2):
        result=self.raw('director' if company==2 else 'stranger','POST','/upload-photo',data={'context':'supplier-contract'},
            files={'file':('synthetic-contract.pdf',b'%PDF-1.4\nSynthetic contract original\n','application/pdf')})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['fileId']

    def original(self,target,*,company=2,previous=None,addendum=False):
        actor='director' if company==2 else 'stranger'
        path=f'/companies/{company}/suppliers/{target}/contracts'
        profile=self.api(actor,'GET',path,**{'X-Company-Id':str(company)})
        fid=previous['sourceFileId'] if previous else self.upload(company)
        data=dict(requestId=str(uuid.uuid4()),sourceFileId=fid,number='Synthetic standalone',date='2026-10-15',
            buyer=profile['buyer'],supplier=profile['supplier'],paymentTerms='After receipt',reviewConfirmed=True,
            applicability=dict(scope='company',term='open_ended',startsOn='2020-01-01'))
        if previous:data['revisesContractId']=previous['id']
        if addendum:data['addendum']=dict(sourceFileId=self.upload(company),number='Synthetic A1',date='2026-10-15')
        return self.api(actor,'POST',path,data,**{'X-Company-Id':str(company)})

    def test_standalone_contract_versions_addendum_and_foreign_buyer_preserve_archive(self):
        source,target,connection=self.connection()
        first=self.original(target);latest=self.original(target,previous=first,addendum=True)
        foreign=self.original(target,company=3)
        original=latest['sourceFileId'];addendum=latest['snapshot']['addenda'][0]['sourceFileId']
        self.assertIn(latest['id'],{r['id'] for r in self.api('supplier','GET','/supplier-documents/contracts')['items']})
        for fid in (original,addendum):self.assertEqual(self.raw('supplier','GET',f'/tenant-files/{fid}/content').status_code,200)
        before=self.business_snapshot();plan=self.plan(source,connection)
        self.assertEqual(plan['mode'],'revoke_contract_access')
        self.assertEqual({r['id'] for r in plan['preservedIssuedDocuments'] if r['kind']=='contract'},{first['id'],latest['id']})
        self.assertEqual(plan['preservedIssuedFileCount'],2)
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['preservedIssuedCounts']['contracts'],2)
        self.assertEqual(self.confirm(source,connection,plan),result)
        self.assertEqual(before,self.business_snapshot())
        visible={r['id'] for r in self.api('supplier','GET','/supplier-documents/contracts')['items']}
        self.assertNotIn(first['id'],visible);self.assertNotIn(latest['id'],visible);self.assertIn(foreign['id'],visible)
        for fid in (original,addendum):
            self.api('supplier','GET',f'/tenant-files/{fid}',expected=403)
            self.assertEqual(self.raw('supplier','GET',f'/tenant-files/{fid}/content').status_code,403)
            self.assertEqual(self.raw('director','GET',f'/tenant-files/{fid}/content').status_code,200)
        buyer=self.api('director','GET',f'/companies/2/suppliers/{target}/contracts')
        self.assertEqual(buyer['items'][0]['id'],latest['id'])

    def test_mixed_contract_and_standalone_paid_invoice_are_preserved(self):
        source,target,connection,_,_,_,_,_,_=self.chain(ship=True,file=True,stock=True)
        contract=self.original(target);invoice=self.invoice(target)
        before=self.business_snapshot();plan=self.plan(source,connection)
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['preservedIssuedCounts'],dict(offers=1,invoices=2,deliveries=1,receipts=0,contracts=1))
        self.assertEqual(before,self.business_snapshot())
        self.assertNotIn(invoice,{r['id'] for r in self.api('supplier','GET','/supplier-invoices')})
        self.assertNotIn(contract['id'],{r['id'] for r in self.api('supplier','GET','/supplier-documents/contracts')['items']})

    def test_old_modes_flags_and_company_do_not_get_contract_authority(self):
        source,target,connection=self.connection();self.original(target)
        old=self.path(source,connection).replace('contract-access-plans','invoice-access-plans')
        self.api('admin','POST',old,dict(operationId=str(uuid.uuid4())),expected=409)
        with patch.dict(os.environ,PARTICIPANT_CONTRACT_ACCESS_CORRECTIONS_ENABLED='0'):self.plan(source,connection,expected=503)
        self.api('director','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),expected=403)
        self.api('admin','POST',self.path(source,connection,3),dict(operationId=str(uuid.uuid4())),expected=404)

    def test_new_version_after_plan_blocks_without_partial_closure(self):
        source,target,connection=self.connection();first=self.original(target);plan=self.plan(source,connection)
        self.original(target,previous=first,addendum=True)
        before=self.business_snapshot();self.confirm(source,connection,plan,expected=409)
        self.assertEqual(before,self.business_snapshot())

    def test_direct_invoice_contract_context_uses_live_invoice_denial(self):
        source,target,connection=self.connection();invoice=self.invoice(target)
        self.api('supplier','GET',f'/supplier-invoices/{invoice}/contract-context')
        old=self.path(source,connection).replace('contract-access-plans','invoice-access-plans')
        plan=self.api('admin','POST',old,dict(operationId=str(uuid.uuid4())))
        self.api('admin','POST',old+'/'+plan['id']+'/confirm',dict(confirmed=True,reason='Synthetic mistaken buyer connection'))
        self.api('supplier','GET',f'/supplier-invoices/{invoice}/contract-context',expected=403)
