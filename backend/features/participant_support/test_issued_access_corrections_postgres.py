"""Revoke an exact issued chain without editing its financial/stock basis."""
import os
import json
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from .test_quote_corrections_postgres import SupplierQuoteCorrectionsPostgresTests as Fixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierIssuedAccessCorrectionsPostgresTests(unittest.TestCase):
    sql,api,connection,received,rfq,raw,message=Fixture.sql,Fixture.api,Fixture.connection,Fixture.received,Fixture.rfq,Fixture.raw,Fixture.message
    confirm=Fixture.confirm

    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass.__func__(cls)
        patch.dict(os.environ,PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED='1').start()

    def path(self,source,connection,company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{connection}/issued-access-plans'

    def plan(self,source,connection,**kwargs):
        return self.api('admin','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),**kwargs)

    def chain(self,*,ship=False,file=False,stock=False):
        source,target,connection=self.connection();request,recipient,offer=self.rfq(target);url=None
        material=self.fixture['materialName']
        if stock:
            material='Synthetic received material '+str(request)
            line=dict(id='issued-stock-'+str(request),name=material,type='material',itemType='material',
                unit='шт',quantity=2,price=120,priceMaterial=120,lineTotal=240,workPackage=self.fixture['workPackage'])
            self.sql('''UPDATE estimates SET sections_json=jsonb_set(sections_json::jsonb,'{0,items}',
                (sections_json::jsonb #> '{0,items}') || %s::jsonb)::text WHERE id=%s''',
                (json.dumps([line]),self.fixture['estimateId']))
        self.sql('UPDATE supply_requests SET project=%s,work_package=%s,material_name=%s WHERE id=%s',
            (self.fixture['project'],self.fixture['workPackage'],material,request))
        if file:
            upload=self.raw('supplier','POST',f'/supplier-offers/{offer}/files',
                files={'file':('synthetic-issued.pdf',b'%PDF-1.4\nSynthetic issued original\n','application/pdf')})
            self.assertEqual(upload.status_code,200,upload.text);url=upload.json()['contentUrl']
        self.api('supplier','PUT',f'/supplier-offers/{offer}',dict(action='respond',requestId=str(uuid.uuid4()),
            quantity=1,pricePerUnit=120,totalPrice=120,deliveryDays=2,paymentTerms='Предоплата 100%',pdfUrl=url))
        self.api('director','PUT',f'/supplier-offers/{offer}',dict(action='select'),**{'X-Company-Id':'2'})
        invoice=self.api('supplier','POST',f'/supplier-offers/{offer}/create-invoice',dict(invoiceNumber='Synthetic issued '+str(offer),amount=120,vatAmount=0))['id']
        delivery=None
        if ship:
            delivery=self.api('supplier','POST',f'/supplier-offers/{offer}/ship',dict(requestId=str(uuid.uuid4()),shippedQuantity=1))['id']
        return source,target,connection,request,recipient,offer,invoice,delivery,url

    def business_snapshot(self):
        return {table:self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id') for table in
            ('suppliers','users','supply_requests','supplier_offers','supplier_invoices','supply_deliveries',
             'warehouse_invoices','warehouse_history','warehouse_main','project_payments','supplier_shipment_batches','supply_history',
             'file_ownership','supplier_buyer_connection_requests')}

    def test_issued_paid_invoice_original_and_credit_shipment_preserve_business_rows(self):
        source,target,connection,request,recipient,offer,invoice,delivery,url=self.chain(ship=True,file=True,stock=True)
        self.api('accountant','PUT',f'/supplier-invoices/{invoice}',dict(status='Утверждён'))
        self.api('accountant','PUT',f'/supplier-invoices/{invoice}',dict(status='Оплачен',paidAmount=40))
        self.api('accountant','POST','/project-payments',dict(projectName=self.fixture['project'],
            workPackage=self.fixture['workPackage'],amount=40,note='Synthetic payment',date='2026-10-15'))
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,400,100)',(source,))
        foreign=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(3,%s,999,50) RETURNING id',(target,))[0][0]
        before=self.business_snapshot()
        old_events=self.sql('SELECT to_jsonb(e) FROM supplier_offer_events e WHERE offer_id=%s ORDER BY id',(offer,))
        original=self.raw('supplier','GET',url);self.assertEqual(original.status_code,200)
        plan=self.plan(source,connection)
        self.assertEqual(plan['mode'],'revoke_issued_access')
        self.assertEqual(plan['affectedOffers'],[dict(offerId=offer,statusBefore='Утверждено',statusAfter='Утверждено')])
        self.assertIn(dict(kind='invoice',id=invoice),plan['preservedIssuedDocuments'])
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['revokedRequestCount'],1)
        self.assertEqual(result['preservedIssuedCounts'],dict(offers=1,invoices=1,deliveries=1,receipts=0))
        self.assertEqual(self.confirm(source,connection,plan),result)
        self.assertEqual(before,self.business_snapshot())
        self.assertEqual(self.sql('SELECT visible_to_supplier,status FROM supply_request_recipients WHERE id=%s',(recipient,)),[(False,'КП выбрано')])
        self.assertNotIn(invoice,[r['id'] for r in self.api('supplier','GET','/supplier-invoices')])
        self.assertIn(foreign,[r['id'] for r in self.api('supplier','GET','/supplier-invoices')])
        self.assertNotIn(offer,[r['id'] for r in self.api('supplier','GET','/supplier-offers')])
        self.assertNotIn(delivery,[r['id'] for r in self.api('supplier','GET','/supply-deliveries')])
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)
        buyer=self.raw('director','GET',url);self.assertEqual(buyer.status_code,200);self.assertEqual(buyer.content,original.content)
        self.api('supplier','GET',f'/supplier-offers/{offer}/history',expected=403)
        denied_upload=self.raw('supplier','POST',f'/supplier-offers/{offer}/files',
            files={'file':('denied.pdf',b'%PDF-1.4\nDenied stale upload\n','application/pdf')})
        self.assertEqual(denied_upload.status_code,403)
        self.api('supplier','POST',f'/supplier-offers/{offer}/create-invoice',dict(invoiceNumber='Forbidden'),expected=403)
        self.api('supplier','POST',f'/supplier-offers/{offer}/ship',dict(requestId=str(uuid.uuid4()),shippedQuantity=.1),expected=403)
        self.api('supplier','PUT',f'/supplier-offers/{offer}',dict(action='respond',totalPrice=5),expected=403)
        self.assertEqual(before,self.business_snapshot())
        self.assertEqual(old_events,self.sql("SELECT to_jsonb(e) FROM supplier_offer_events e WHERE offer_id=%s AND event_type!='connection_access_revoked' ORDER BY id",(offer,)))

    def test_direct_invoice_or_contract_or_foreign_child_never_uses_generic_disconnect(self):
        for kind in ('direct','foreign'):
            source,target,connection,_,_,offer,_,_,_=self.chain()
            self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,offer_id) VALUES(%s,%s,%s)',
                (2 if kind=='direct' else 3,target,None if kind=='direct' else offer))
            before=self.business_snapshot();self.plan(source,connection,expected=409)
            self.assertEqual(before,self.business_snapshot())

    def test_payment_change_or_inflight_message_after_plan_keeps_access_unchanged(self):
        for kind in ('payment','sending'):
            source,target,connection,request,recipient,offer,invoice,_,_=self.chain()
            message=self.message(request,recipient) if kind=='sending' else None
            plan=self.plan(source,connection)
            if kind=='payment':self.sql('UPDATE supplier_invoices SET paid_amount=70 WHERE id=%s',(invoice,))
            else:self.sql("UPDATE messenger_outbox SET status='sending' WHERE id=%s",(message,))
            self.confirm(source,connection,plan,expected=409)
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_old_modes_flags_and_company_scope_do_not_get_new_authority(self):
        source,_,connection,_,_,_,_,_,_=self.chain()
        for suffix in ('correction-plans','rfq-correction-plans','quote-correction-plans'):
            self.api('admin','POST',self.path(source,connection).replace('issued-access-plans',suffix),dict(operationId=str(uuid.uuid4())),expected=409)
        with patch.dict(os.environ,PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED='0'):self.plan(source,connection,expected=503)
        self.api('admin','POST',self.path(source,connection,3),dict(operationId=str(uuid.uuid4())),expected=404)
        self.api('director','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),expected=403)

    def test_received_stock_and_one_shared_original_inside_closed_chain_are_preserved(self):
        source,target,connection,request,recipient,offer,invoice,delivery,url=self.chain(ship=True,file=True,stock=True)
        receipt=self.api('foreman','PUT',f'/supply-deliveries/{delivery}/receive',
            dict(receivedQuantity=1,qualityStatus='Принято',receivedBy='Synthetic receiver'))['invoiceId']
        self.sql('UPDATE supplier_invoices SET file_url=%s WHERE id=%s',(url,invoice))
        self.sql('UPDATE supply_deliveries SET document_url=%s WHERE id=%s',(url,delivery))
        self.sql('UPDATE warehouse_invoices SET photo_url=%s,photo_urls=%s WHERE id=%s',(url,'["'+url+'"]',receipt))
        before=self.business_snapshot();plan=self.plan(source,connection)
        self.assertEqual(plan['preservedIssuedFileCount'],1)
        self.assertIn(dict(kind='receipt',id=receipt),plan['preservedIssuedDocuments'])
        self.assertEqual(self.confirm(source,connection,plan)['preservedIssuedCounts']['receipts'],1)
        self.assertEqual(before,self.business_snapshot())
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)
        self.assertEqual(self.raw('director','GET',url).status_code,200)
        self.assertNotIn(target,[row['supplierId'] for row in self.api('supplier','GET','/supply-history') if row['companyId']==2])

    def test_other_buyers_and_bidders_keep_access_and_only_queued_messages_are_cancelled(self):
        source,target,connection,request,recipient,offer,invoice,_,_=self.chain()
        foreign=self.received(target,company=3)
        pending,pending_recipient,pending_offer=self.rfq(target)
        message=self.message(pending,pending_recipient)
        self.sql("UPDATE supply_request_recipients SET email_notification_status='В очереди email' WHERE id=%s",(pending_recipient,))
        other=self.sql("INSERT INTO suppliers(name) VALUES('Synthetic independent bidder') RETURNING id")[0][0]
        self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,supplier_group_ids,
            visible_to_supplier) VALUES(2,%s,%s,%s,%s,TRUE)''',(request,other,other,[other]))
        before_foreign=self.sql('SELECT to_jsonb(t) FROM supply_request_recipients t WHERE request_id=%s',(foreign[0],))
        before=self.business_snapshot();plan=self.plan(source,connection)
        self.assertEqual(plan['queuedNotificationCount'],2)
        self.assertEqual(self.confirm(source,connection,plan)['revokedRequestCount'],2)
        self.assertEqual(before,self.business_snapshot())
        self.assertEqual(before_foreign,self.sql('SELECT to_jsonb(t) FROM supply_request_recipients t WHERE request_id=%s',(foreign[0],)))
        self.assertIn(foreign[2],[r['id'] for r in self.api('supplier','GET','/supplier-offers')])
        self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE request_id=%s AND supplier_id=%s',(request,other)),[(True,)])
        self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(message,)),[('cancelled',)])
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',(pending_offer,)),[('Ожидает ответа',)])

    def test_audit_failure_rolls_back_and_concurrent_confirm_has_one_access_event(self):
        source,_,connection,_,recipient,offer,_,_,_=self.chain()
        plan=self.plan(source,connection)
        tables=('company_supplier_links','supplier_connection_correction_plans','supply_request_recipients','supplier_offer_events','audit_log')
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in tables}
        with patch('backend.features.participant_support.corrections.audit',side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):self.confirm(source,connection,plan)
        for t,rows in before.items():self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id'))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.confirm(source,connection,plan),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql("SELECT count(*) FROM supplier_offer_events WHERE offer_id=%s AND event_type='connection_access_revoked'",(offer,)),[(1,)])
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',(offer,)),[('Утверждено',)])

    def test_shared_foreign_deleted_and_drifted_originals_do_not_silently_keep_access(self):
        for kind in ('shared','foreign','deleted','drift'):
            source,target,connection,_,_,_,invoice,_,url=self.chain(file=True)
            fid=int(url.split('/')[2]);plan=self.plan(source,connection) if kind=='drift' else None
            if kind=='shared':self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,file_url) VALUES(2,%s,%s)',(source,url))
            elif kind=='deleted':self.sql("UPDATE file_ownership SET deletion_status='deleted' WHERE id=%s",(fid,))
            else:self.sql('UPDATE file_ownership SET company_id=3 WHERE id=%s',(fid,))
            before=self.business_snapshot()
            if plan:self.confirm(source,connection,plan,expected=409)
            else:self.plan(source,connection,expected=409)
            self.assertEqual(before,self.business_snapshot())

    def test_wrong_mode_and_owner_epoch_cannot_confirm_a_preserving_plan(self):
        source,_,connection,_,_,_,_,_,_=self.chain();plan=self.plan(source,connection)
        for suffix in ('correction-plans','rfq-correction-plans','quote-correction-plans'):
            self.api('admin','POST',self.path(source,connection).replace('issued-access-plans',suffix)+'/'+plan['id']+'/confirm',
                dict(confirmed=True,reason='Synthetic wrong endpoint'),expected=409)
        uid=self.fixture['users']['supplier']['id']
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(uid,));self.sql('UPDATE users SET active=TRUE WHERE id=%s',(uid,))
        self.confirm(source,connection,plan,expected=409)

    def test_unknown_offer_child_and_contract_original_are_explicitly_blocked(self):
        self.sql('CREATE TABLE issued_test_child(id SERIAL PRIMARY KEY,company_id INT,quote_id INT REFERENCES supplier_offers(id))')
        try:
            source,_,connection,_,_,offer,_,_,_=self.chain()
            self.sql('INSERT INTO issued_test_child(company_id,quote_id) VALUES(3,%s)',(offer,))
            self.plan(source,connection,expected=409)
        finally:self.sql('DROP TABLE issued_test_child')
        source,target,connection,_,_,offer,_,_,url=self.chain(file=True)
        self.sql('''INSERT INTO supplier_contract_versions(company_id,version,source_file_id,snapshot_json,snapshot_hash,
            reason,reviewed_by_id,reviewed_by) VALUES(2,1,%s,%s,%s,'Synthetic review',%s,'Synthetic reviewer')''',
            (int(url.split('/')[2]),'{"supplier":{"supplierId":'+str(target)+'}}','0'*64,self.fixture['users']['director']['id']))
        self.plan(source,connection,expected=409)

    def test_group_recipient_and_inconsistent_batch_or_receipt_do_not_receive_an_apply_plan(self):
        for kind in ('group','batch','receipt'):
            source,target,connection,request,recipient,offer,invoice,delivery,_=self.chain(ship=True)
            if kind=='group':self.sql('UPDATE supply_request_recipients SET supplier_group_ids=%s WHERE id=%s',([source,target],recipient))
            elif kind=='batch':self.sql('UPDATE supplier_shipment_batches SET delivery_ids=%s WHERE offer_id=%s',([2147483647],offer))
            else:self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_invoice_id) VALUES(3,%s,%s)',(target,invoice))
            before=self.business_snapshot();self.plan(source,connection,expected=409);self.assertEqual(before,self.business_snapshot())

    def test_reverse_invoice_receipt_reference_preserves_the_whole_archive(self):
        source,target,connection,request,recipient,offer,invoice,_,_=self.chain()
        receipt=self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id) VALUES(2,%s) RETURNING id',(target,))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(receipt,invoice))
        before=self.business_snapshot();plan=self.plan(source,connection)
        self.assertEqual(self.confirm(source,connection,plan)['preservedIssuedCounts']['receipts'],1)
        self.assertEqual(before,self.business_snapshot())

    def test_uncommitted_financial_writer_invalidates_confirmation_after_wait(self):
        import time
        source,_,connection,_,recipient,_,invoice,_,_=self.chain();plan=self.plan(source,connection)
        writer=self.main.get_db();writer.autocommit=False
        try:
            with writer.cursor() as cur:cur.execute('UPDATE supplier_invoices SET paid_amount=90 WHERE id=%s',(invoice,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(self.confirm,source,connection,plan,expected=409)
                time.sleep(.1);self.assertFalse(pending.done());writer.commit();pending.result(timeout=10)
        finally:writer.close()
        self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_missing_financial_schema_and_write_attempt_in_projection_fail_closed(self):
        source,_,connection,_,_,_,_,_,_=self.chain()
        self.sql('ALTER TABLE supplier_invoices RENAME COLUMN warehouse_invoice_id TO issued_test_receipt_id')
        try:self.plan(source,connection,expected=503)
        finally:self.sql('ALTER TABLE supplier_invoices RENAME COLUMN issued_test_receipt_id TO warehouse_invoice_id')
        from .correction_issued import ClosedRecipients
        with self.assertRaises(ValueError):ClosedRecipients(None,[]).execute('UPDATE supply_request_recipients SET visible_to_supplier=TRUE')

    def test_operation_reuse_expiry_and_changed_confirmation_reason_are_rejected(self):
        source,_,connection,_,_,_,_,_,_=self.chain();operation=str(uuid.uuid4())
        plan=self.api('admin','POST',self.path(source,connection),dict(operationId=operation))
        for suffix in ('correction-plans','quote-correction-plans'):
            self.api('admin','POST',self.path(source,connection).replace('issued-access-plans',suffix),dict(operationId=operation),expected=409)
        expired=str(uuid.uuid4())
        self.sql('''INSERT INTO supplier_connection_correction_plans(id,connection_request_id,company_id,platform_account_id,
            source_supplier_id,target_supplier_id,target_link_id,actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,
            operation_id,manifest,created_at,expires_at)
            SELECT %s,connection_request_id,company_id,platform_account_id,source_supplier_id,target_supplier_id,target_link_id,
            actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,%s,manifest,NOW()-INTERVAL '20 minutes',NOW()-INTERVAL '5 minutes'
            FROM supplier_connection_correction_plans WHERE id=%s''',(expired,str(uuid.uuid4()),plan['id']))
        self.confirm(source,connection,{**plan,'id':expired},expected=409)
        self.confirm(source,connection,plan)
        self.confirm(source,connection,plan,reason='Synthetic different reason',expected=409)

    def test_supply_history_follows_recipient_and_keeps_independent_other_buyer_legacy(self):
        source,target,connection,request,recipient,offer,invoice,delivery,_=self.chain(ship=True,stock=True)
        self.api('foreman','PUT',f'/supply-deliveries/{delivery}/receive',
            dict(receivedQuantity=1,qualityStatus='Принято',receivedBy='Synthetic receiver'))
        history=self.sql('SELECT id FROM supply_history WHERE delivery_id=%s',(delivery,))[0][0]
        foreign=self.sql('INSERT INTO supply_history(company_id,supplier_id,material_name) VALUES(3,%s,%s) RETURNING id',
            (target,'Synthetic independent legacy history'))[0][0]
        request_history=self.sql('''INSERT INTO supply_history(company_id,supplier_id,request_id,project)
            VALUES(2,%s,%s,%s) RETURNING id''',(target,request,self.fixture['project']))[0][0]
        self.assertIn(history,[row['id'] for row in self.api('supplier','GET','/supply-history')])
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE id=%s',(recipient,))
        visible={row['id'] for row in self.api('supplier','GET','/supply-history')}
        self.assertNotIn(history,visible)
        self.assertNotIn(request_history,visible)
        self.assertIn(foreign,visible)

    def test_customer_manager_assignments_are_preserved_but_cannot_bypass_closed_documents(self):
        source,target,connection,request,recipient,offer,invoice,_,url=self.chain(file=True)
        foreign=self.received(target,company=3)
        uid=self.sql("INSERT INTO users(name,role,active) VALUES('Synthetic issued manager','поставщик',TRUE) RETURNING id")[0][0]
        self.fixture['users']['issued_manager']=dict(id=uid,role='поставщик',name='Synthetic issued manager')
        member=self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role,active) VALUES(%s,%s,'manager',TRUE) RETURNING id",(target,uid))[0][0]
        self.sql('INSERT INTO supplier_customer_assignments(supplier_id,company_id,member_id) VALUES(%s,2,%s),(%s,3,%s)',(target,member,target,member))
        before=self.sql('SELECT to_jsonb(a) FROM supplier_customer_assignments a WHERE supplier_id=%s ORDER BY company_id',(target,))
        with patch.dict(os.environ,SUPPLIER_TEAM_ENABLED='1',SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED='1'):
            self.assertIn(invoice,[r['id'] for r in self.api('issued_manager','GET','/supplier-invoices')])
            plan=self.plan(source,connection);self.confirm(source,connection,plan)
            self.assertNotIn(invoice,[r['id'] for r in self.api('issued_manager','GET','/supplier-invoices')])
            self.assertIn(foreign[2],[r['id'] for r in self.api('issued_manager','GET','/supplier-offers')])
            self.assertEqual(self.raw('issued_manager','GET',url).status_code,403)
            self.api('issued_manager','POST',f'/supplier-offers/{offer}/create-invoice',dict(invoiceNumber='Forbidden manager'),expected=403)
        self.assertEqual(before,self.sql('SELECT to_jsonb(a) FROM supplier_customer_assignments a WHERE supplier_id=%s ORDER BY company_id',(target,)))

    def test_preserving_mode_is_independent_of_rfq_quote_flags_and_handles_empty_or_received_without_rejection(self):
        with patch.dict(os.environ,PARTICIPANT_RFQ_CORRECTIONS_ENABLED='0',PARTICIPANT_QUOTE_CORRECTIONS_ENABLED='0'):
            for kind in ('empty','pending','received'):
                source,target,connection=self.connection()
                if kind=='pending':self.rfq(target)
                elif kind=='received':self.received(target)
                before=self.business_snapshot();plan=self.plan(source,connection)
                result=self.confirm(source,connection,plan)
                self.assertEqual(result['revokedRequestCount'],0 if kind=='empty' else 1)
                self.assertEqual(result['rejectedQuoteCount'],0)
                self.assertEqual(before,self.business_snapshot())

    def test_offer_manager_assignment_is_retained_without_document_or_file_bypass(self):
        source,target,connection,request,recipient,offer,invoice,_,url=self.chain(file=True)
        uid=self.sql("INSERT INTO users(name,role,active) VALUES('Synthetic per-offer manager','поставщик',TRUE) RETURNING id")[0][0]
        self.fixture['users']['offer_manager']=dict(id=uid,role='поставщик',name='Synthetic per-offer manager')
        member=self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role,active) VALUES(%s,%s,'manager',TRUE) RETURNING id",(target,uid))[0][0]
        self.sql('INSERT INTO supplier_offer_assignments(offer_id,supplier_id,member_id) VALUES(%s,%s,%s)',(offer,target,member))
        before=self.sql('SELECT to_jsonb(a) FROM supplier_offer_assignments a WHERE offer_id=%s',(offer,))
        with patch.dict(os.environ,SUPPLIER_TEAM_ENABLED='1',SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED='0'):
            self.assertIn(invoice,[r['id'] for r in self.api('offer_manager','GET','/supplier-invoices')])
            self.confirm(source,connection,self.plan(source,connection))
            self.assertNotIn(invoice,[r['id'] for r in self.api('offer_manager','GET','/supplier-invoices')])
            self.assertEqual(self.raw('offer_manager','GET',url).status_code,403)
        self.assertEqual(before,self.sql('SELECT to_jsonb(a) FROM supplier_offer_assignments a WHERE offer_id=%s',(offer,)))
