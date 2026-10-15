"""Exact standalone-invoice access corrections on a disposable PostgreSQL."""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from .test_issued_access_corrections_postgres import SupplierIssuedAccessCorrectionsPostgresTests as Fixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierInvoiceAccessCorrectionsPostgresTests(unittest.TestCase):
    sql,api,connection,rfq,received,raw,chain,business_snapshot,confirm=(
        Fixture.sql,Fixture.api,Fixture.connection,Fixture.rfq,Fixture.received,Fixture.raw,
        Fixture.chain,Fixture.business_snapshot,Fixture.confirm)

    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass.__func__(cls)
        patch.dict(os.environ,PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED='1').start()

    def path(self,source,connection,company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{connection}/invoice-access-plans'

    def plan(self,source,connection,**kwargs):
        return self.api('admin','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),**kwargs)

    def invoice(self,target,company=2,**values):
        fields=dict(company_id=company,supplier_id=target,amount=400,paid_amount=100,**values)
        return self.sql('INSERT INTO supplier_invoices('+','.join(fields)+') VALUES ('+
            ','.join(['%s']*len(fields))+') RETURNING id',list(fields.values()))[0][0]

    def test_standalone_paid_invoice_receipt_and_foreign_buyer_are_preserved(self):
        source,target,connection=self.connection();invoice=self.invoice(target);foreign=self.invoice(target,3)
        receipt=self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id) VALUES(2,%s,%s) RETURNING id',
            (target,invoice))[0][0]
        self.invoice(source)
        before=self.business_snapshot()
        self.assertIn(invoice,[r['id'] for r in self.api('supplier','GET','/supplier-invoices')])
        plan=self.plan(source,connection)
        self.assertEqual(plan['mode'],'revoke_invoice_access')
        self.assertEqual(plan['affectedRequests'],[])
        self.assertEqual(plan['preservedIssuedDocuments'],[dict(kind='invoice',id=invoice),dict(kind='receipt',id=receipt)])
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['preservedIssuedCounts'],dict(offers=0,invoices=1,deliveries=0,receipts=1))
        self.assertEqual(result['revokedRequestCount'],0)
        self.assertEqual(self.confirm(source,connection,plan),result)
        self.assertEqual(before,self.business_snapshot())
        visible={r['id'] for r in self.api('supplier','GET','/supplier-invoices')}
        self.assertNotIn(invoice,visible);self.assertIn(foreign,visible)
        buyer={r['id'] for r in self.api('accountant','GET','/supplier-invoices',**{'X-Company-Id':'2'})}
        self.assertIn(invoice,buyer)
        # Disabling a command or reactivating the catalog cannot reopen old IDs.
        with patch.dict(os.environ,PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED='0'):
            self.assertNotIn(invoice,{r['id'] for r in self.api('supplier','GET','/supplier-invoices')})
        self.sql("UPDATE company_supplier_links SET status='Активный',version=version+1 WHERE company_id=2 AND supplier_id=%s",(target,))
        fresh=self.invoice(target)
        visible={r['id'] for r in self.api('supplier','GET','/supplier-invoices')}
        self.assertNotIn(invoice,visible);self.assertIn(fresh,visible)

    def test_standalone_invoice_and_receipt_originals_need_no_quote(self):
        source,target,connection=self.connection()
        upload=self.raw('director','POST','/upload-photo',data={'context':'supplier-invoice'},
            files={'file':('standalone.pdf',b'%PDF-1.4\nSynthetic standalone original\n','application/pdf')})
        self.assertEqual(upload.status_code,200,upload.text);url=upload.json()['contentUrl']
        invoice=self.invoice(target,file_url=url)
        self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id,photo_url) VALUES(2,%s,%s,%s)',(target,invoice,url))
        self.assertEqual(self.raw('supplier','GET',url).status_code,200)
        before=self.business_snapshot();plan=self.plan(source,connection)
        self.assertEqual(plan['affectedOffers'],[]);self.assertEqual(plan['preservedIssuedFileCount'],1)
        self.confirm(source,connection,plan)
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)
        self.assertEqual(self.raw('director','GET',url).status_code,200)
        self.assertEqual(before,self.business_snapshot())

    def test_receipt_only_photo_access_closes_through_exact_invoice(self):
        source,target,connection=self.connection()
        upload=self.raw('director','POST','/upload-photo',data={'context':'warehouse-invoice'},
            files={'file':('receipt.pdf',b'%PDF-1.4\nSynthetic receipt original\n','application/pdf')})
        self.assertEqual(upload.status_code,200,upload.text);url=upload.json()['contentUrl']
        invoice=self.invoice(target)
        self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id,photo_urls) VALUES(2,%s,%s,%s)',(target,invoice,'["'+url+'"]'))
        self.assertEqual(self.raw('supplier','GET',url).status_code,200)
        plan=self.plan(source,connection);self.confirm(source,connection,plan)
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)

    def test_linking_closed_invoice_to_new_visible_quote_cannot_restore_file_or_invoice(self):
        source,target,connection=self.connection()
        upload=self.raw('director','POST','/upload-photo',data={'context':'supplier-invoice'},
            files={'file':('closed-invoice.pdf',b'%PDF-1.4\nSynthetic closed invoice\n','application/pdf')})
        self.assertEqual(upload.status_code,200,upload.text);url=upload.json()['contentUrl']
        invoice=self.invoice(target,file_url=url);plan=self.plan(source,connection);self.confirm(source,connection,plan)
        self.api('director','PUT',f'/suppliers/{target}',dict(relationshipVersion=2,status='Активный'),**{'X-Company-Id':'2'})
        request,_,offer=self.rfq(target)
        self.assertIn(offer,{r['id'] for r in self.api('supplier','GET','/supplier-offers')})
        # A later accounting link repair must not silently remove an ID denial.
        self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s WHERE id=%s',(offer,request,invoice))
        self.assertNotIn(invoice,{r['id'] for r in self.api('supplier','GET','/supplier-invoices')})
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)

    def test_mixed_quote_and_standalone_original_close_without_business_changes(self):
        source,target,connection,request,recipient,offer,linked,delivery,url=self.chain(ship=True,file=True,stock=True)
        invoice=self.invoice(target,file_url=url)
        receipt=self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id,photo_url) VALUES(2,%s,%s,%s) RETURNING id',
            (target,invoice,url))[0][0]
        original=self.raw('supplier','GET',url);self.assertEqual(original.status_code,200)
        before=self.business_snapshot();plan=self.plan(source,connection)
        self.assertIn(dict(kind='invoice',id=invoice),plan['preservedIssuedDocuments'])
        self.assertIn(dict(kind='receipt',id=receipt),plan['preservedIssuedDocuments'])
        self.assertEqual(plan['preservedIssuedFileCount'],1)
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['preservedIssuedCounts'],dict(offers=1,invoices=2,deliveries=1,receipts=1))
        self.assertEqual(before,self.business_snapshot())
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)
        self.assertEqual(self.raw('director','GET',url).content,original.content)

    def test_old_issued_mode_never_silently_closes_a_standalone_invoice(self):
        source,target,connection=self.connection();self.invoice(target)
        old=self.path(source,connection).replace('/invoice-access-plans','/issued-access-plans')
        self.api('admin','POST',old,dict(operationId=str(uuid.uuid4())),expected=409)
        with patch.dict(os.environ,PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED='0'):
            self.plan(source,connection,expected=503)
        self.api('director','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),expected=403)
        self.api('admin','POST',self.path(source,connection,3),dict(operationId=str(uuid.uuid4())),expected=404)

    def test_changed_payment_or_new_invoice_after_plan_blocks_atomically(self):
        for kind in ('payment','new'):
            source,target,connection=self.connection();invoice=self.invoice(target);plan=self.plan(source,connection)
            if kind=='payment':self.sql('UPDATE supplier_invoices SET paid_amount=150 WHERE id=%s',(invoice,))
            else:self.invoice(target)
            before=self.business_snapshot();self.confirm(source,connection,plan,expected=409)
            self.assertEqual(before,self.business_snapshot())
            self.assertIn(invoice,{r['id'] for r in self.api('supplier','GET','/supplier-invoices')})

    def test_request_only_or_ambiguous_receipt_and_shared_original_block(self):
        for kind in ('request','receipt','shared'):
            source,target,connection,request,_,_,_,_,url=self.chain(file=True)
            invoice=self.invoice(target,**({'request_id':request} if kind=='request' else {'file_url':url}))
            if kind=='receipt':
                self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id,supply_request_id) VALUES(2,%s,%s,%s)',(target,invoice,request))
            if kind=='shared':self.invoice(target,3,file_url=url)
            before=self.business_snapshot();self.plan(source,connection,expected=409)
            self.assertEqual(before,self.business_snapshot())

    def test_concurrent_confirm_has_one_audit_and_same_result(self):
        source,target,connection=self.connection();self.invoice(target);plan=self.plan(source,connection)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.confirm(source,connection,plan),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_connection_corrected' AND company_id=2 AND entity_id=%s",(target,)),[(1,)])

    def test_catalog_edit_preserves_server_owned_invoice_denials(self):
        from ..supplier_access.company_directory import relationship_values
        source,target,connection=self.connection();invoice=self.invoice(target);plan=self.plan(source,connection)
        self.confirm(source,connection,plan)
        profile=self.sql('SELECT profile FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,))[0][0]
        edited=relationship_values(dict(notes='Updated note',closedStandaloneInvoiceIds=[]),dict(profile=profile))
        self.assertEqual(edited['profile']['closedStandaloneInvoiceIds'],[invoice])
        result=self.api('director','PUT',f'/suppliers/{target}',dict(relationshipVersion=2,status='Активный',notes='Synthetic updated note',
            profile={},closedStandaloneInvoiceIds=[]),**{'X-Company-Id':'2'})
        self.assertEqual(result['relationshipVersion'],3)
        self.assertNotIn('closedStandaloneInvoiceIds',result)
        self.assertEqual(self.sql('SELECT profile FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,))[0][0]['closedStandaloneInvoiceIds'],[invoice])
        self.assertNotIn(invoice,{r['id'] for r in self.api('supplier','GET','/supplier-invoices')})

    def test_team_leader_cannot_bypass_exact_invoice_denial(self):
        source,target,connection=self.connection();invoice=self.invoice(target);foreign=self.invoice(target,3)
        uid=self.sql("INSERT INTO users(name,role,active) VALUES('Synthetic invoice team leader','поставщик',TRUE) RETURNING id")[0][0]
        self.fixture['users']['invoice_leader']=dict(id=uid,role='поставщик',name='Synthetic invoice team leader')
        self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role,active) VALUES(%s,%s,'leader',TRUE)",(target,uid))
        with patch.dict(os.environ,SUPPLIER_TEAM_ENABLED='1',SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED='1',
                PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED='0',PARTICIPANT_QUOTE_CORRECTIONS_ENABLED='0',PARTICIPANT_RFQ_CORRECTIONS_ENABLED='0'):
            self.assertIn(invoice,{r['id'] for r in self.api('invoice_leader','GET','/supplier-invoices')})
            before=self.business_snapshot();plan=self.plan(source,connection);self.confirm(source,connection,plan)
            self.assertEqual(before,self.business_snapshot())
            visible={r['id'] for r in self.api('invoice_leader','GET','/supplier-invoices')}
            self.assertNotIn(invoice,visible);self.assertIn(foreign,visible)

    def test_reverse_invoice_receipt_is_supported_and_foreign_parent_is_blocked(self):
        source,target,connection=self.connection()
        receipt=self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id) VALUES(2,%s) RETURNING id',(target,))[0][0]
        invoice=self.invoice(target,warehouse_invoice_id=receipt)
        plan=self.plan(source,connection);self.assertIn(dict(kind='receipt',id=receipt),plan['preservedIssuedDocuments'])
        self.confirm(source,connection,plan)
        source,target,connection=self.connection()
        receipt=self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id) VALUES(3,%s) RETURNING id',(target,))[0][0]
        self.invoice(target,warehouse_invoice_id=receipt);self.plan(source,connection,expected=409)

    def test_audit_failure_rolls_back_catalog_denial_and_completion(self):
        from . import corrections
        source,target,connection=self.connection();invoice=self.invoice(target);plan=self.plan(source,connection)
        before=self.business_snapshot()
        with patch.object(corrections,'audit',side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaisesRegex(RuntimeError,'Synthetic audit failure'):self.confirm(source,connection,plan)
        self.assertEqual(before,self.business_snapshot())
        self.assertEqual(self.sql('SELECT status,version,profile FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',1,{})])
        self.assertEqual(self.sql('SELECT applied_at FROM supplier_connection_correction_plans WHERE id=%s',(plan['id'],)),[(None,)])
        self.assertIn(invoice,{r['id'] for r in self.api('supplier','GET','/supplier-invoices')})

    def test_expired_changed_owner_wrong_plan_mode_and_replay_denial_drift_block(self):
        source,target,connection=self.connection();self.invoice(target);plan=self.plan(source,connection)
        wrong=self.path(source,connection).replace('invoice-access-plans','issued-access-plans')+'/'+plan['id']+'/confirm'
        self.api('admin','POST',wrong,dict(confirmed=True,reason='Synthetic mistaken connection'),expected=409)
        expired=str(uuid.uuid4())
        self.sql('''INSERT INTO supplier_connection_correction_plans(id,connection_request_id,company_id,platform_account_id,
            source_supplier_id,target_supplier_id,target_link_id,actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,
            operation_id,manifest,created_at,expires_at)
            SELECT %s,connection_request_id,company_id,platform_account_id,source_supplier_id,target_supplier_id,target_link_id,
            actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,%s,manifest,NOW()-INTERVAL '20 minutes',NOW()-INTERVAL '5 minutes'
            FROM supplier_connection_correction_plans WHERE id=%s''',(expired,str(uuid.uuid4()),plan['id']))
        self.confirm(source,connection,{**plan,'id':expired},expected=409)
        source,target,connection=self.connection();self.invoice(target);plan=self.plan(source,connection)
        other_owner=self.sql("INSERT INTO users(name,role,active) VALUES('Synthetic changed invoice owner','поставщик',TRUE) RETURNING id")[0][0]
        self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(other_owner,target))
        self.confirm(source,connection,plan,expected=409)
        source,target,connection=self.connection();self.invoice(target);plan=self.plan(source,connection)
        self.confirm(source,connection,plan)
        self.sql("UPDATE company_supplier_links SET profile='{}'::jsonb WHERE company_id=2 AND supplier_id=%s",(target,))
        self.confirm(source,connection,plan,expected=409)

    def test_projection_cannot_write_or_replace_existing_closed_id_list(self):
        from .correction_invoice_access import ClosedInvoiceAccess
        with self.assertRaises(ValueError):ClosedInvoiceAccess(None,[],2,1,[1]).execute('UPDATE supplier_invoices SET amount=0')
        source,target,connection=self.connection();self.invoice(target)
        self.sql("UPDATE company_supplier_links SET profile=jsonb_build_object('closedStandaloneInvoiceIds',jsonb_build_array(99999)) WHERE company_id=2 AND supplier_id=%s",(target,))
        self.plan(source,connection,expected=409)

    def test_read_only_visibility_diagnostic_is_self_contained(self):
        from ..supplier_access.verify_visibility_postgres import verify
        conn=self.main.get_db()
        try:verify(conn)
        finally:conn.close()
