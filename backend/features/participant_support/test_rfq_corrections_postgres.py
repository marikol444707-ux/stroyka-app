"""Withdraw unanswered RFQs only, on a disposable Unix-only PostgreSQL."""
import importlib
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from .test_corrections_postgres import SupplierCorrectionsPostgresTests as Fixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierRfqCorrectionsPostgresTests(unittest.TestCase):
    sql,api,connection,confirm=Fixture.sql,Fixture.api,Fixture.connection,Fixture.confirm

    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass.__func__(cls)
        if not cls.sql(cls,"SELECT to_regclass('public.supplier_email_attempts')")[0][0]:
            cls.sql(cls,importlib.import_module('migrations.versions.0039_supplier_email_history').SCHEMA_SQL)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                cls.main._ensure_supply_notification_messenger_tables(cur)
                cls.main._ensure_supply_runtime_columns(cur)
        finally:conn.close()
        patch.dict(os.environ,PARTICIPANT_RFQ_CORRECTIONS_ENABLED='1').start()

    def path(self,source,request,company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{request}/rfq-correction-plans'

    def plan(self,source,request,**kwargs):
        return self.api('admin','POST',self.path(source,request),dict(operationId=str(uuid.uuid4())),**kwargs)

    def rfq(self,target,company=2):
        owner=self.fixture['users']['supplier']['id']
        request=self.sql("""INSERT INTO supply_requests(company_id,material_name,quantity,unit,status,
            selected_suppliers,prorab_confirmed_at,director_approved_at)
            VALUES(%s,'Synthetic RFQ',1,'шт','КП запрошены',%s,NOW(),NOW()) RETURNING id""",(company,[target]))[0][0]
        recipient=self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,
            target_supplier_id,supplier_user_id,supplier_group_ids,visible_to_supplier,status)
            VALUES(%s,%s,%s,%s,%s,%s,TRUE,'Ожидает ответа') RETURNING id''',(company,request,target,target,owner,[target]))[0][0]
        offer=self.sql("INSERT INTO supplier_offers(company_id,request_id,supplier_id,status) VALUES(%s,%s,%s,'Ожидает ответа') RETURNING id",(company,request,target))[0][0]
        return request,recipient,offer

    def test_withdraw_exact_unanswered_rfq_keep_originals_foreign_buyers_and_replay(self):
        source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
        foreign=self.rfq(target,3)
        original=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,400,100) RETURNING id',(source,))[0][0]
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in ('suppliers','users','supplier_invoices','supply_requests','supplier_buyer_connection_requests')}
        self.assertIn(request,[r['id'] for r in self.api('supplier','GET','/supply-requests')])
        self.assertIn(offer,[r['id'] for r in self.api('supplier','GET','/supplier-offers')])
        plan=self.plan(source,connection)
        self.assertEqual(plan['affectedRequests'],[dict(requestId=request,recipientId=recipient,offerIds=[offer])])
        self.assertEqual(plan['mode'],'withdraw_unanswered_rfq')
        result=self.confirm(source,connection,plan)
        self.assertEqual(result['withdrawnRequestCount'],1)
        self.assertEqual(self.confirm(source,connection,plan),result)
        self.assertEqual(self.sql('SELECT visible_to_supplier,status FROM supply_request_recipients WHERE id=%s',(recipient,)),[(False,'Отозвано')])
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',(offer,)),[('Отозвано',)])
        self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(foreign[1],)),[(True,)])
        for table,rows in before.items():self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(original,)),[(100,)])
        self.assertNotIn(request,[r['id'] for r in self.api('supplier','GET','/supply-requests')])
        self.assertNotIn(offer,[r['id'] for r in self.api('supplier','GET','/supplier-offers')])
        self.api('supplier','PUT',f'/supplier-offers/{offer}',dict(action='respond',totalPrice=10,pricePerUnit=10),expected=403)
        # The original legacy array stays, but hidden recipients prevent fallback.
        self.assertEqual(self.sql('SELECT selected_suppliers FROM supply_requests WHERE id=%s',(request,)),[([target],)])

    def test_response_or_invoice_blocks_without_partial_changes(self):
        for change in ('response','draft_price','invoice'):
            source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
            if change=='response':self.sql("UPDATE supplier_offers SET status='Получено',responded_at=NOW() WHERE id=%s",(offer,))
            elif change=='draft_price':self.sql('UPDATE supplier_offers SET total_price=1 WHERE id=%s',(offer,))
            else:self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,offer_id,request_id) VALUES(2,%s,%s,%s)',(target,offer,request))
            self.plan(source,connection,expected=409)
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])
            self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',)])

    def test_old_unused_endpoint_does_not_silently_withdraw_rfq_and_flags_are_required(self):
        source,target,connection=self.connection();self.rfq(target)
        unused=self.path(source,connection).replace('/rfq-correction-plans','/correction-plans')
        self.api('admin','POST',unused,dict(operationId=str(uuid.uuid4())),expected=409)
        with patch.dict(os.environ,PARTICIPANT_RFQ_CORRECTIONS_ENABLED='0'):self.plan(source,connection,expected=503)
        self.api('director','POST',self.path(source,connection),dict(operationId=str(uuid.uuid4())),expected=403)
        self.api('admin','POST',self.path(source,connection,3),dict(operationId=str(uuid.uuid4())),expected=404)

    def test_rfq_mode_keeps_empty_connection_correction_working(self):
        source,_,connection=self.connection()
        plan=self.plan(source,connection)
        self.assertEqual(plan['affectedRequests'],[])
        self.assertEqual(plan['queuedNotificationCount'],0)
        self.assertEqual(self.confirm(source,connection,plan)['withdrawnRequestCount'],0)

    def message(self,request,recipient,status='queued'):
        owner=self.fixture['users']['supplier']['id']
        message=self.sql('''INSERT INTO messenger_outbox(owner_scope,company_id,provider,user_id,event_type,entity_type,entity_id,status)
            VALUES('company',2,'max',%s,'supplier_kp_requested','supply_request',%s,%s) RETURNING id''',(owner,request,status))[0][0]
        self.sql("UPDATE supply_request_recipients SET max_outbox_id=%s,max_notification_status='В очереди MAX' WHERE id=%s",(message,recipient))
        return message

    def test_cancel_only_queued_notifications_and_keep_sent_history(self):
        from ..supplier_access.email_attempts import EMAIL_QUEUED
        source,target,connection=self.connection();request,recipient,_=self.rfq(target)
        message=self.message(request,recipient)
        self.sql('UPDATE supply_request_recipients SET email_notification_status=%s WHERE id=%s',(EMAIL_QUEUED,recipient))
        plan=self.plan(source,connection);self.assertEqual(plan['queuedNotificationCount'],2)
        self.confirm(source,connection,plan)
        self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(message,)),[('cancelled',)])
        self.assertEqual(self.sql('SELECT email_notification_status,max_notification_status FROM supply_request_recipients WHERE id=%s',(recipient,)),[('Отменено','Отменено')])
        source,target,connection=self.connection();request,recipient,_=self.rfq(target)
        message=self.message(request,recipient,'sent')
        self.sql("UPDATE supply_request_recipients SET email_notification_status='Отправлено',email_sent_at=NOW(),max_notification_status='Отправлено MAX' WHERE id=%s",(recipient,))
        self.sql("INSERT INTO supplier_email_attempts(company_id,request_id,recipient_id,outcome,finished_at) VALUES(2,%s,%s,'accepted',NOW())",(request,recipient))
        history=self.sql('SELECT email_sent_at FROM supply_request_recipients WHERE id=%s',(recipient,))
        plan=self.plan(source,connection);self.assertEqual(plan['queuedNotificationCount'],0)
        self.confirm(source,connection,plan)
        self.assertEqual(history,self.sql('SELECT email_sent_at FROM supply_request_recipients WHERE id=%s',(recipient,)))
        self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(message,)),[('sent',)])

    def test_inflight_or_unknown_delivery_blocks(self):
        for kind in ('email_status','email_attempt','max_sending','missing_message'):
            source,target,connection=self.connection();request,recipient,_=self.rfq(target)
            if kind=='email_status':
                from ..supplier_access.email_attempts import EMAIL_UNCONFIRMED
                self.sql('UPDATE supply_request_recipients SET email_notification_status=%s WHERE id=%s',(EMAIL_UNCONFIRMED,recipient))
            elif kind=='email_attempt':self.sql('INSERT INTO supplier_email_attempts(company_id,request_id,recipient_id) VALUES(2,%s,%s)',(request,recipient))
            else:
                message=self.message(request,recipient,'sending')
                if kind=='missing_message':self.sql('DELETE FROM messenger_outbox WHERE id=%s',(message,))
            self.plan(source,connection,expected=409)
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_new_response_or_notification_claim_invalidates_plan(self):
        for kind in ('response','max_claim','attempt'):
            source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
            message=self.message(request,recipient) if kind=='max_claim' else None
            plan=self.plan(source,connection)
            if kind=='response':self.sql("UPDATE supplier_offers SET status='Получено',responded_at=NOW() WHERE id=%s",(offer,))
            elif kind=='max_claim':self.sql("UPDATE messenger_outbox SET status='sending' WHERE id=%s",(message,))
            else:self.sql('INSERT INTO supplier_email_attempts(company_id,request_id,recipient_id) VALUES(2,%s,%s)',(request,recipient))
            self.confirm(source,connection,plan,expected=409)
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_shared_groups_legacy_and_cross_company_recipient_cannot_be_revoked(self):
        for kind in ('group','legacy','mixed_company','other_owned_card'):
            source,target,connection=self.connection();request,recipient,_=self.rfq(target)
            if kind=='group':self.sql('UPDATE supply_request_recipients SET supplier_group_ids=%s WHERE id=%s',([source,target],recipient))
            elif kind=='legacy':self.sql('DELETE FROM supply_request_recipients WHERE id=%s',(recipient,))
            else:
                owner=self.fixture['users']['supplier']['id']
                other=self.sql("INSERT INTO suppliers(name,user_id) VALUES('Synthetic independent card',%s) RETURNING id",(owner,))[0][0]
                self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,
                    supplier_user_id,supplier_group_ids,visible_to_supplier) VALUES(%s,%s,%s,%s,%s,%s,TRUE)''',
                    (3 if kind=='mixed_company' else 2,request,other,other,owner,[other]))
            self.plan(source,connection,expected=409)

    def test_another_supplier_on_same_request_is_preserved(self):
        source,target,connection=self.connection();request,recipient,_=self.rfq(target)
        other=self.sql("INSERT INTO suppliers(name) VALUES('Synthetic other bidder') RETURNING id")[0][0]
        other_recipient=self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,
            supplier_group_ids,visible_to_supplier) VALUES(2,%s,%s,%s,%s,TRUE) RETURNING id''',(request,other,other,[other]))[0][0]
        before=self.sql('SELECT to_jsonb(r) FROM supply_request_recipients r WHERE id=%s',(other_recipient,))
        self.confirm(source,connection,self.plan(source,connection))
        self.assertEqual(before,self.sql('SELECT to_jsonb(r) FROM supply_request_recipients r WHERE id=%s',(other_recipient,)))

    def test_audit_failure_rolls_back_all_rfq_changes(self):
        source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
        message=self.message(request,recipient);plan=self.plan(source,connection)
        tables=('supply_request_recipients','supplier_offers','supplier_offer_events','messenger_outbox','company_supplier_links','supplier_connection_correction_plans')
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in tables}
        with patch('backend.features.participant_support.corrections.audit',side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):self.confirm(source,connection,plan)
        for table,values in before.items():self.assertEqual(values,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))

    def test_concurrent_confirm_and_cross_endpoint_replay(self):
        source,target,connection=self.connection();self.rfq(target)
        plan=self.plan(source,connection)
        unused=self.path(source,connection).replace('/rfq-correction-plans','/correction-plans')
        self.api('admin','POST',unused+'/'+plan['id']+'/confirm',dict(confirmed=True,reason='Synthetic correction reason'),expected=409)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.confirm(source,connection,plan),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE entity_id=%s AND action='supplier_connection_corrected'",(target,)),[(1,)])
        self.assertEqual(self.sql("SELECT count(*) FROM supplier_offer_events WHERE event_type='connection_corrected' AND offer_id IN (SELECT id FROM supplier_offers WHERE supplier_id=%s)",(target,)),[(1,)])

    def test_stale_supplier_response_transaction_cannot_be_lost(self):
        import time
        source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
        plan=self.plan(source,connection);writer=self.main.get_db();writer.autocommit=False
        try:
            with writer.cursor() as cur:cur.execute("UPDATE supplier_offers SET status='Получено',responded_at=NOW() WHERE id=%s",(offer,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(self.confirm,source,connection,plan,expected=409)
                time.sleep(.1);self.assertFalse(pending.done());writer.commit();pending.result(timeout=10)
        finally:writer.close()
        self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])

    def test_response_history_unknown_schema_and_large_batch_block(self):
        source,target,connection=self.connection();request,_,offer=self.rfq(target)
        self.sql("INSERT INTO supplier_offer_events(offer_id,event_type) VALUES(%s,'responded')",(offer,))
        self.plan(source,connection,expected=409)
        source,target,connection=self.connection();self.rfq(target)
        self.sql('ALTER TABLE supplier_email_attempts RENAME TO correction_test_attempts')
        try:self.plan(source,connection,expected=503)
        finally:self.sql('ALTER TABLE correction_test_attempts RENAME TO supplier_email_attempts')
        source,target,connection=self.connection()
        for _ in range(51):self.rfq(target)
        self.plan(source,connection,expected=409)

    def test_cross_company_financial_descendant_and_new_offer_reference_block(self):
        source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,offer_id) VALUES(3,%s,%s)',(source,offer))
        self.plan(source,connection,expected=409)
        self.sql('CREATE TABLE correction_test_offer_child(id SERIAL PRIMARY KEY,company_id INT,quote_id INT REFERENCES supplier_offers(id))')
        try:
            source,target,connection=self.connection();request,recipient,offer=self.rfq(target)
            plan=self.plan(source,connection)
            self.sql('INSERT INTO correction_test_offer_child(company_id,quote_id) VALUES(3,%s)',(offer,))
            self.confirm(source,connection,plan,expected=409)
            self.assertEqual(self.sql('SELECT visible_to_supplier FROM supply_request_recipients WHERE id=%s',(recipient,)),[(True,)])
        finally:self.sql('DROP TABLE correction_test_offer_child')
