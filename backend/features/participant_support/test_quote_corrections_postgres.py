"""Reject received, unawarded quotes without changing their commercial data."""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from .test_rfq_corrections_postgres import SupplierRfqCorrectionsPostgresTests as Fixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierQuoteCorrectionsPostgresTests(unittest.TestCase):
    sql,api,connection,rfq,message,confirm=Fixture.sql,Fixture.api,Fixture.connection,Fixture.rfq,Fixture.message,Fixture.confirm

    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass.__func__(cls)
        patch.dict(os.environ,PARTICIPANT_QUOTE_CORRECTIONS_ENABLED='1').start()

    def path(self,source,request,company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{request}/quote-correction-plans'

    def plan(self,source,request,**kwargs):
        return self.api('admin','POST',self.path(source,request),dict(operationId=str(uuid.uuid4())),**kwargs)

    def raw(self,actor,method,path,**kwargs):
        headers={'Authorization':'Bearer '+self.main.create_auth_token(self.fixture['users'][actor],two_factor_passed=True)}
        return self.client.request(method,path,headers=headers,**kwargs)

    def received(self,target,*,file=False,company=2):
        request,recipient,offer=self.rfq(target,company)
        url=None
        if file:
            response=self.raw('supplier','POST',f'/supplier-offers/{offer}/files',
                files={'file':('synthetic-quote.pdf',b'%PDF-1.4\nSynthetic quote original\n','application/pdf')})
            self.assertEqual(response.status_code,200,response.text);url=response.json()['contentUrl']
        self.api('supplier','PUT',f'/supplier-offers/{offer}',dict(action='respond',requestId=str(uuid.uuid4()),
            quantity=1,pricePerUnit=120,totalPrice=120,deliveryDays=2,supplierMessage='Synthetic delivery included',pdfUrl=url))
        return request,recipient,offer,url

    def test_exact_received_quote_rejection_preserves_prices_snapshot_file_and_buyer_archive(self):
        source,target,connection=self.connection();request,recipient,offer,url=self.received(target,file=True)
        self.assertIsNotNone(self.sql('SELECT party_snapshot_json FROM supplier_offers WHERE id=%s',(offer,))[0][0])
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,400,100)',(source,))
        before=self.sql("SELECT to_jsonb(o)-'status' FROM supplier_offers o WHERE id=%s",(offer,))
        originals=self.sql('SELECT to_jsonb(f) FROM file_ownership f ORDER BY id')
        old_events=self.sql('SELECT id,payload_json FROM supplier_offer_events WHERE offer_id=%s ORDER BY id',(offer,))
        original_file=self.raw('supplier','GET',url)
        self.assertEqual(original_file.status_code,200)
        self.assertTrue(original_file.content.startswith(b'%PDF'))
        plan=self.plan(source,connection)
        self.assertEqual(plan['mode'],'reject_received_quotes')
        self.assertEqual(plan['affectedOffers'],[dict(offerId=offer,statusBefore='Получено',statusAfter='Отклонено')])
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['rejectedQuoteCount'],1)
        self.assertEqual(self.confirm(source,connection,plan),result)
        self.assertEqual(before,self.sql("SELECT to_jsonb(o)-'status' FROM supplier_offers o WHERE id=%s",(offer,)))
        self.assertEqual(originals,self.sql('SELECT to_jsonb(f) FROM file_ownership f ORDER BY id'))
        self.assertEqual(old_events,self.sql("SELECT id,payload_json FROM supplier_offer_events WHERE offer_id=%s AND event_type!='connection_corrected' ORDER BY id",(offer,)))
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',(offer,)),[('Отклонено',)])
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)
        buyer_file=self.raw('director','GET',url)
        self.assertEqual(buyer_file.status_code,200)
        self.assertEqual(buyer_file.content,original_file.content)
        self.assertNotIn(offer,[r['id'] for r in self.api('supplier','GET','/supplier-offers')])
        self.api('supplier','PUT',f'/supplier-offers/{offer}',dict(action='respond',totalPrice=130),expected=403)
        self.api('supplier','POST',f'/supplier-offers/{offer}/create-invoice',dict(invoiceNumber='Forbidden',amount=120),expected=403)
        self.api('director','PUT',f'/supplier-offers/{offer}',dict(action='select'),expected=400,**{'X-Company-Id':'2'})
        buyer=self.api('director','GET','/supplier-offers',**{'X-Company-Id':'2'})
        self.assertEqual(next(r for r in buyer if r['id']==offer)['totalPrice'],120)

    def test_invoice_award_or_foreign_original_blocks_without_changing_quote(self):
        for kind in ('invoice','awarded','foreign_file'):
            source,target,connection=self.connection();request,recipient,offer,url=self.received(target,file=kind=='foreign_file')
            if kind=='invoice':self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,offer_id) VALUES(3,%s,%s)',(target,offer))
            elif kind=='awarded':self.sql("UPDATE supplier_offers SET status='Утверждено' WHERE id=%s",(offer,))
            else:self.sql("UPDATE file_ownership SET company_id=3 WHERE id=%s",(int(url.split('/')[2]),))
            before=self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s',(offer,))
            self.plan(source,connection,expected=409)
            self.assertEqual(before,self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s',(offer,)))
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_old_paths_do_not_reject_received_quotes_and_new_flag_is_required(self):
        source,target,connection=self.connection();self.received(target)
        for old in ('correction-plans','rfq-correction-plans'):
            self.api('admin','POST',self.path(source,connection).replace('quote-correction-plans',old),dict(operationId=str(uuid.uuid4())),expected=409)
        with patch.dict(os.environ,PARTICIPANT_QUOTE_CORRECTIONS_ENABLED='0'):self.plan(source,connection,expected=503)
        self.api('admin','POST',self.path(source,connection,3),dict(operationId=str(uuid.uuid4())),expected=404)
        self.api('director','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),expected=403)

    def test_mixed_pending_received_other_bidders_and_foreign_buyers_are_preserved(self):
        source,target,connection=self.connection();request,recipient,offer,_=self.received(target)
        pending,pending_recipient,pending_offer=self.rfq(target)
        foreign=self.received(target,company=3)
        other=self.sql("INSERT INTO suppliers(name) VALUES('Synthetic independent bidder') RETURNING id")[0][0]
        self.sql('INSERT INTO supplier_offers(company_id,supplier_id,request_id,status) VALUES(2,%s,%s,\'Получено\')',(other,request))
        other_recipient=self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,
            supplier_group_ids,visible_to_supplier) VALUES(2,%s,%s,%s,%s,TRUE) RETURNING id''',(request,other,other,[other]))[0][0]
        foreign_before=self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s',(foreign[2],))
        bidder_before=self.sql('SELECT to_jsonb(r) FROM supply_request_recipients r WHERE id=%s',(other_recipient,))
        message=self.message(pending,pending_recipient)
        self.sql("UPDATE supply_request_recipients SET email_notification_status='В очереди email' WHERE id=%s",(pending_recipient,))
        plan=self.plan(source,connection)
        self.assertEqual(plan['queuedNotificationCount'],2)
        result=self.confirm(source,connection,plan)
        self.assertEqual((result['rejectedQuoteCount'],result['withdrawnRequestCount']),(1,2))
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',(pending_offer,)),[('Отозвано',)])
        self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(message,)),[('cancelled',)])
        self.assertEqual(foreign_before,self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s',(foreign[2],)))
        self.assertEqual(bidder_before,self.sql('SELECT to_jsonb(r) FROM supply_request_recipients r WHERE id=%s',(other_recipient,)))

    def test_price_change_selection_and_inflight_notification_invalidate_plan(self):
        for change in ('price','selection','sending'):
            source,target,connection=self.connection();request,recipient,offer,_=self.received(target)
            message=self.message(request,recipient) if change=='sending' else None
            plan=self.plan(source,connection)
            if change=='price':self.sql('UPDATE supplier_offers SET total_price=121 WHERE id=%s',(offer,))
            elif change=='selection':self.sql("UPDATE supplier_offers SET status='Утверждено' WHERE id=%s",(offer,))
            else:self.sql("UPDATE messenger_outbox SET status='sending' WHERE id=%s",(message,))
            before=self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s',(offer,))
            self.confirm(source,connection,plan,expected=409)
            self.assertEqual(before,self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s',(offer,)))
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_original_deleted_missing_shared_or_changed_after_plan_blocks(self):
        for kind in ('missing','deleted','shared','drift'):
            source,target,connection=self.connection();request,recipient,offer,url=self.received(target,file=True)
            plan=self.plan(source,connection) if kind=='drift' else None
            fid=int(url.split('/')[2])
            if kind=='missing':self.sql('UPDATE supplier_offers SET pdf_url=%s WHERE id=%s',('/tenant-files/2147483647/content',offer))
            elif kind=='deleted':self.sql("UPDATE file_ownership SET deletion_status='deleted' WHERE id=%s",(fid,))
            elif kind=='shared':
                other=self.sql("INSERT INTO suppliers(name) VALUES('Synthetic unrelated file reference') RETURNING id")[0][0]
                self.sql('INSERT INTO supplier_offers(company_id,supplier_id,pdf_url) VALUES(3,%s,%s)',(other,url))
            else:self.sql('UPDATE file_ownership SET company_id=3 WHERE id=%s',(fid,))
            if plan:self.confirm(source,connection,plan,expected=409)
            else:self.plan(source,connection,expected=409)
            self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',(offer,)),[('Получено',)])

    def test_audit_rollback_and_concurrent_confirm_do_not_duplicate_events(self):
        source,target,connection=self.connection();request,recipient,offer,_=self.received(target)
        plan=self.plan(source,connection)
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in
            ('supplier_offers','supply_request_recipients','supplier_offer_events','supplier_connection_correction_plans','company_supplier_links')}
        with patch('backend.features.participant_support.corrections.audit',side_effect=RuntimeError('Synthetic failed audit')):
            with self.assertRaises(RuntimeError):self.confirm(source,connection,plan)
        for table,values in before.items():self.assertEqual(values,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.confirm(source,connection,plan),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql("SELECT count(*) FROM supplier_offer_events WHERE offer_id=%s AND event_type='connection_corrected'",(offer,)),[(1,)])

    def test_cross_endpoint_plan_replay_and_owner_epoch_are_rejected(self):
        source,target,connection=self.connection();self.received(target)
        plan=self.plan(source,connection)
        for old in ('correction-plans','rfq-correction-plans'):
            path=self.path(source,connection).replace('quote-correction-plans',old)+'/'+plan['id']+'/confirm'
            self.api('admin','POST',path,dict(confirmed=True,reason='Synthetic mistaken connection'),expected=409)
        owner=self.fixture['users']['supplier']['id']
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(owner,));self.sql('UPDATE users SET active=TRUE WHERE id=%s',(owner,))
        self.confirm(source,connection,plan,expected=409)

    def test_new_financial_fk_and_uncommitted_selection_cannot_be_lost(self):
        import time
        source,target,connection=self.connection();request,recipient,offer,_=self.received(target)
        plan=self.plan(source,connection);writer=self.main.get_db();writer.autocommit=False
        try:
            with writer.cursor() as cur:cur.execute("UPDATE supplier_offers SET status='Утверждено' WHERE id=%s",(offer,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(self.confirm,source,connection,plan,expected=409)
                time.sleep(.1);self.assertFalse(pending.done());writer.commit();pending.result(timeout=10)
        finally:writer.close()
        self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])
        self.sql('CREATE TABLE correction_test_quote_child(id SERIAL PRIMARY KEY,company_id INT,quote_id INT REFERENCES supplier_offers(id))')
        try:
            source,target,connection=self.connection();request,recipient,offer,_=self.received(target)
            plan=self.plan(source,connection)
            self.sql('INSERT INTO correction_test_quote_child(company_id,quote_id) VALUES(3,%s)',(offer,))
            self.confirm(source,connection,plan,expected=409)
        finally:self.sql('DROP TABLE correction_test_quote_child')

    def test_recipient_history_and_schema_mismatches_block(self):
        for kind in ('recipient','event','missing_registry'):
            source,target,connection=self.connection();request,recipient,offer,_=self.received(target)
            if kind=='recipient':self.sql("UPDATE supply_request_recipients SET status='Ожидает ответа' WHERE id=%s",(recipient,))
            elif kind=='event':self.sql("INSERT INTO supplier_offer_events(offer_id,event_type) VALUES(%s,'selected')",(offer,))
            else:self.sql('ALTER TABLE file_ownership RENAME TO correction_test_originals')
            try:self.plan(source,connection,expected=503 if kind=='missing_registry' else 409)
            finally:
                if kind=='missing_registry':self.sql('ALTER TABLE correction_test_originals RENAME TO file_ownership')

    def test_quote_mode_accepts_only_pending_and_empty_connections_without_rfq_flag(self):
        with patch.dict(os.environ,PARTICIPANT_RFQ_CORRECTIONS_ENABLED='0'):
            for addressed in (False,True):
                source,target,connection=self.connection()
                if addressed:self.rfq(target)
                plan=self.plan(source,connection)
                self.assertEqual(self.confirm(source,connection,plan)['rejectedQuoteCount'],0)
        source,target,connection=self.connection();_,_,offer=self.rfq(target)
        self.sql('ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS awarded_items_json TEXT')
        self.sql('UPDATE supplier_offers SET awarded_items_json=%s WHERE id=%s',('[{"requestPosition":0}]',offer))
        self.plan(source,connection,expected=409)
        self.api('admin','POST',self.path(source,connection).replace('quote-correction-plans','rfq-correction-plans'),dict(operationId=str(uuid.uuid4())),expected=409)

    def test_operation_type_reuse_and_expired_immutable_copy_cannot_apply(self):
        source,target,connection=self.connection();self.received(target)
        operation=str(uuid.uuid4())
        plan=self.api('admin','POST',self.path(source,connection),dict(operationId=operation))
        for suffix in ('correction-plans','rfq-correction-plans'):
            self.api('admin','POST',self.path(source,connection).replace('quote-correction-plans',suffix),dict(operationId=operation),expected=409)
        expired=str(uuid.uuid4())
        self.sql('''INSERT INTO supplier_connection_correction_plans(id,connection_request_id,company_id,platform_account_id,
            source_supplier_id,target_supplier_id,target_link_id,actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,
            operation_id,manifest,created_at,expires_at)
            SELECT %s,connection_request_id,company_id,platform_account_id,source_supplier_id,target_supplier_id,target_link_id,
            actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,%s,manifest,NOW()-INTERVAL '20 minutes',NOW()-INTERVAL '5 minutes'
            FROM supplier_connection_correction_plans WHERE id=%s''',(expired,str(uuid.uuid4()),plan['id']))
        self.confirm(source,connection,{**plan,'id':expired},expected=409)

    def test_received_quote_recipient_group_and_other_owned_card_are_not_silently_revoked(self):
        for kind in ('group','owned_card'):
            source,target,connection=self.connection();request,recipient,_,_=self.received(target)
            if kind=='group':self.sql('UPDATE supply_request_recipients SET supplier_group_ids=%s WHERE id=%s',([source,target],recipient))
            else:
                owner=self.fixture['users']['supplier']['id']
                other=self.sql("INSERT INTO suppliers(name,user_id) VALUES('Synthetic second cabinet card',%s) RETURNING id",(owner,))[0][0]
                self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,
                    supplier_user_id,supplier_group_ids,visible_to_supplier) VALUES(2,%s,%s,%s,%s,%s,TRUE)''',(request,other,other,owner,[other]))
            self.plan(source,connection,expected=409)

    def test_one_registered_original_shared_only_by_target_quotes_is_preserved_once(self):
        source,target,connection=self.connection();_,_,first,url=self.received(target,file=True)
        _,_,second,_=self.received(target)
        self.sql('UPDATE supplier_offers SET pdf_url=%s WHERE id=%s',(url,second))
        plan=self.plan(source,connection)
        self.assertEqual(plan['preservedQuoteFileCount'],1)
        self.assertEqual(self.confirm(source,connection,plan)['rejectedQuoteCount'],2)
        self.assertEqual(self.raw('supplier','GET',url).status_code,403)
        self.assertEqual(self.raw('director','GET',url).status_code,200)
