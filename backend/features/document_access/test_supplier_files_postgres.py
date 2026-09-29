"""Real authentication and PostgreSQL file/offer/customer boundaries."""
from types import SimpleNamespace
import importlib
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from backend.features.supplier_team import test_customer_team_postgres as support

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Requires isolated PostgreSQL')
class SupplierFilesPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.CustomerTeamPostgresTests.setUpClass.__func__(cls)
        cls.sql=support.CustomerTeamPostgresTests.sql
        conn=cls.main.get_db()
        try:
            with conn.cursor() as cur:
                for name in ('0027_work_material_accounting','0033_supply_claim_cases'):
                    module=importlib.import_module('migrations.versions.'+name)
                    with patch.object(module, 'op', SimpleNamespace(execute=cur.execute)):
                        module.upgrade()
        finally:conn.close()
        flag=patch.dict(os.environ,{'SUPPLY_CLAIMS_ENABLED':'1'})
        flag.start();cls.addClassCleanup(flag.stop)
    sql=support.CustomerTeamPostgresTests.sql
    api=support.CustomerTeamPostgresTests.api
    quote=support.CustomerTeamPostgresTests.quote
    command=support.CustomerTeamPostgresTests.command
    setUp=support.CustomerTeamPostgresTests.setUp

    def raw(self,actor,method,path,**kw):
        headers=kw.pop('headers',{})
        if actor:
            headers['Authorization']='Bearer '+self.main.create_auth_token(self.fixture['users'][actor],two_factor_passed=True)
        return self.client.request(method,path,headers=headers,**kw)

    def upload(self,offer,actor='supplier',expected=200):
        response=self.raw(actor,'POST',f"/supplier-offers/{offer['id']}/files",data={'supplierOfferId':offer['id'], 'projectId':9999,'context':'forged'},
                          files={'file':('quote.pdf',b'%PDF-1.4\nTest supplier document\n','application/pdf')})
        self.assertEqual(response.status_code,expected,response.text)
        return response.json()

    def assigned(self):
        offer,path,body=self.quote()
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=self.member_id,version=0)
        return offer,path,body

    def test_upload_download_buyer_and_manager_revocation(self):
        offer,path,body=self.assigned()
        file=self.upload(offer,'manager')
        self.assertEqual(file['companyId'],self.fixture['companyId'])
        self.assertEqual(self.sql('SELECT company_id,name FROM projects WHERE id=%s',(file['projectId'],)),[(self.fixture['companyId'],self.fixture['project'])])
        url=file['contentUrl']
        for actor in ('supplier','manager','director'):
            response=self.raw(actor,'GET',url)
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.content.startswith(b'%PDF'))
            self.assertIn('no-store',response.headers['cache-control'])
        for actor in (None,'stranger_supplier'):
            self.assertIn(self.raw(actor,'GET',url).status_code,(401,403))
        self.assertEqual(self.raw('supplier','DELETE',file['metadataUrl']).status_code,403)
        self.api('manager','PUT',path,{**body,'pdfUrl':url})
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=None,version=1)
        self.assertEqual(self.raw('manager','GET',url).status_code,403)
        self.upload(offer,'manager',403)
        self.assertEqual(self.raw('supplier','GET',url).status_code,200)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s',(offer['requestId'],))
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)

    def test_cross_offer_and_unrelated_file_injection_denied(self):
        offer,path,body=self.assigned()
        other,_,_=self.quote()
        file=self.upload(other)
        self.api('supplier','PUT',path,{**body,'pdfUrl':file['contentUrl']},expected=403)
        self.api('supplier','PUT',path,body)
        self.api('director','PUT',path,{'action':'select'})
        for field in ('documentUrl','photoUrl'):
            self.api('supplier','POST',path+'/ship',{'requestId':str(uuid4()),'shippedQuantity':1,field:file['contentUrl']},expected=403)
        self.api('supplier','POST',path+'/create-invoice',{'invoiceNumber':'Forbidden','amount':100,'fileUrl':file['contentUrl']},expected=403)
        self.sql("UPDATE file_ownership SET company_id=3 WHERE id=%s",(file['fileId'],))
        self.api('supplier','POST',path+'/ship',{'requestId':str(uuid4()),'shippedQuantity':1,'documentUrl':file['contentUrl']},expected=403)

    def test_pdf_invoice_shipment_claim_and_manager_reply_chain(self):
        offer,path,body=self.assigned()
        file=self.upload(offer,'manager');url=file['contentUrl']
        self.api('manager','PUT',path,{**body,'pdfUrl':url})
        self.api('director','PUT',path,{'action':'select'})
        self.api('manager','POST',path+'/create-invoice',{'invoiceNumber':'File chain','amount':100,'fileUrl':url})
        delivery=self.api('manager','POST',path+'/ship',{'requestId':str(uuid4()),'shippedQuantity':1,'documentUrl':url})
        # Claim attachment is supplied by buyer, and read through coherent chain.
        claim=self.sql('''INSERT INTO supply_claims(delivery_id,request_id,offer_id,supplier_id,project,material_name,
            work_package,claim_type,description,expected_quantity,received_quantity,shortage_quantity,status,photo_url)
            SELECT id,request_id,offer_id,supplier_id,project,material_name,work_package,'Брак','Test',1,0,1,'Открыта',%s
            FROM supply_deliveries WHERE id=%s RETURNING id''',(url,delivery['id']))[0][0]
        claimpath=f'/supply-claims/{claim}/case'
        card=self.api('manager','GET',claimpath)
        self.assertTrue(card['canReply'])
        message={'action':'reply','text':'Replace item','expectedVersion':1,'expectedCompanyId':self.fixture['companyId'],
                 'expectedActorId':self.manager['id'],'requestId':str(uuid4())}
        saved=self.api('manager','POST',claimpath,message)
        self.assertEqual(self.api('manager','POST',claimpath,message),saved)
        self.command('assign_customer',companyId=self.fixture['companyId'],memberId=None,version=1)
        self.api('manager','GET',claimpath,expected=404)
        self.api('manager','POST',claimpath,message,expected=403)
        self.assertEqual(self.raw('manager','GET',url).status_code,403)

    def buyer_upload(self):
        response=self.raw('director','POST','/upload-photo',data={'context':'documents'},
                          files={'file':('receipt.pdf',b'%PDF-1.4\nBuyer file\n','application/pdf')})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_buyer_files_need_actual_invoice_delivery_claim_or_warehouse_reference(self):
        offer,path,body=self.assigned()
        self.api('manager','PUT',path,body)
        self.api('director','PUT',path,{'action':'select'})
        inv=self.api('manager','POST',path+'/create-invoice',{'invoiceNumber':'Buyer attachments','amount':100})
        delivery=self.api('manager','POST',path+'/ship',{'requestId':str(uuid4()),'shippedQuantity':1})
        for table,column,identity in [('supplier_invoices','file_url',inv['id']),('supplier_invoices','photo_url',inv['id']),
                                      ('supply_deliveries','document_url',delivery['id']),('supply_deliveries','photo_url',delivery['id'])]:
            file=self.buyer_upload();url=file['contentUrl']
            self.assertEqual(self.raw('manager','GET',url).status_code,403)
            self.sql('UPDATE '+table+' SET '+column+'=%s WHERE id=%s',(url,identity))
            self.assertEqual(self.raw('manager','GET',url).status_code,200)
            self.sql('UPDATE '+table+' SET '+column+'=NULL WHERE id=%s',(identity,))
            self.assertEqual(self.raw('manager','GET',url).status_code,403)
        file=self.buyer_upload();url=file['contentUrl']
        self.sql('''INSERT INTO supply_claims(delivery_id,request_id,offer_id,supplier_id,project,material_name,
            work_package,claim_type,description,status,photo_url)
            SELECT id,request_id,offer_id,supplier_id,project,material_name,work_package,'Брак','Test','Открыта',%s
            FROM supply_deliveries WHERE id=%s''',(url,delivery['id']))
        self.assertEqual(self.raw('manager','GET',url).status_code,200)
        file=self.buyer_upload();url=file['contentUrl']
        wi=self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,photo_urls)
            VALUES(%s,%s,%s) RETURNING id''',(self.fixture['companyId'],self.fixture['supplierId'],'["'+url+'"]'))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(wi,inv['id']))
        self.assertEqual(self.raw('manager','GET',url).status_code,200)
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=NULL WHERE id=%s',(inv['id'],))
        self.assertEqual(self.raw('manager','GET',url).status_code,403)
        for field,value in [('supplier_invoice_id',inv['id']),('supply_delivery_id',delivery['id']),('supply_request_id',offer['requestId'])]:
            self.sql('UPDATE warehouse_invoices SET '+field+'=%s WHERE id=%s',(value,wi))
            self.assertEqual(self.raw('manager','GET',url).status_code,200)
            self.sql('UPDATE warehouse_invoices SET '+field+'=NULL WHERE id=%s',(wi,))
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(wi,inv['id']))
        self.sql('UPDATE warehouse_invoices SET company_id=3 WHERE id=%s',(wi,))
        self.assertEqual(self.raw('manager','GET',url).status_code,403)

    def test_direct_invoice_leader_only_legacy_reuse_and_delete_pending(self):
        offer,path,body=self.assigned()
        file=self.buyer_upload();url=file['contentUrl']
        self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,invoice_number,file_url)
                    VALUES(%s,%s,'Direct legacy',%s)''',(self.fixture['companyId'],self.fixture['supplierId'],url))
        self.assertEqual(self.raw('supplier','GET',url).status_code,200)
        self.assertEqual(self.raw('manager','GET',url).status_code,403)
        legacy=self.sql('SELECT file_url FROM file_ownership WHERE id=%s',(file['fileId'],))[0][0]
        self.sql('UPDATE supplier_offers SET pdf_url=%s WHERE id=%s',(legacy,offer['id']))
        self.api('manager','PUT',path,{**body,'pdfUrl':legacy})
        self.assertEqual(self.raw('manager','GET',url).status_code,200)
        self.sql("UPDATE file_ownership SET deletion_status='pending' WHERE id=%s",(file['fileId'],))
        self.assertEqual(self.raw('manager','GET',url).status_code,410)
        self.api('manager','POST','/supplier-invoices',{'offerId':offer['id'],'fileUrl':url},expected=409)

    def test_expired_buyer_subscription_blocks_supplier_upload_without_creating_file(self):
        offer,_,_=self.assigned()
        company=self.fixture['companyId']
        before=self.sql('SELECT plan,trial_until,plan_expires_at,payment_status FROM companies WHERE id=%s',(company,))[0]
        count=self.sql('SELECT count(*) FROM file_ownership')
        try:
            self.sql("UPDATE companies SET trial_until='2000-01-01',plan_expires_at='2000-01-01',payment_status='expired' WHERE id=%s",(company,))
            self.upload(offer,'supplier',403)
            self.assertEqual(self.sql('SELECT count(*) FROM file_ownership'),count)
        finally:
            self.sql('UPDATE companies SET plan=%s,trial_until=%s,plan_expires_at=%s,payment_status=%s WHERE id=%s',(*before,company))
