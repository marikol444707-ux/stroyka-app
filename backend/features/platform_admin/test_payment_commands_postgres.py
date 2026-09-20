"""Real payment admission, replay and subscription state on disposable PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import psycopg2
import importlib
import os
import unittest
import uuid
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from ..customer_cabinet import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1','isolated PostgreSQL required')
class PlatformPaymentTests(unittest.TestCase):
    api=support.CustomerExtraWorksTests.api
    sql=support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)
        conn=cls.main.get_db();conn.autocommit=False
        try:
            with conn.cursor() as cur:
                migration=importlib.import_module('migrations.versions.0005_platform_client_contracts')
                with patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):migration.upgrade()
                cur.execute(importlib.import_module('migrations.versions.0041_platform_payment_commands').SCHEMA_SQL)
                cur.execute("INSERT INTO users(name,email,password,role) VALUES('Billing test','billing-command@local.test','unused','system_owner') RETURNING id")
                cls.operator={'id':cur.fetchone()[0],'role':'system_owner','name':'Billing test','email':'billing-command@local.test'}
            conn.commit()
        finally:conn.close()

    def body(self,**changes):
        return dict({'companyId':2,'amount':'150.12','paymentDate':'2026-09-20','method':'transfer','requestId':str(uuid.uuid4())},**changes)

    def test_same_request_is_one_payment_and_changed_request_conflicts(self):
        body=self.body()
        first=self.api(self.operator,'POST','/system/payments',body)
        second=self.api(self.operator,'POST','/system/payments',body)
        self.assertEqual(first['id'],second['id'])
        self.api(self.operator,'POST','/system/payments',dict(body,amount='151.12'),expected=409)
        self.assertEqual(self.sql('SELECT amount,created_by FROM company_payments WHERE id=%s',(first['id'],)),[(Decimal('150.12'),'Billing test')])

    def test_invalid_money_status_and_missing_request_do_not_create_payments(self):
        before=self.sql('SELECT COUNT(*) FROM company_payments')[0][0]
        for changes in ({'amount':'NaN'},{'amount':'Infinity'},{'amount':'0.001'},{'amount':'-1'},{'status':'pending'},{'requestId':''}):
            self.api(self.operator,'POST','/system/payments',self.body(**changes),expected=422)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM company_payments')[0][0],before)

    def test_paid_period_never_shortens_or_reactivates_admin_block(self):
        self.sql("UPDATE companies SET plan_expires_at='2030-12-31',active=FALSE,suspended_at=NOW(),suspended_reason='Administrative block' WHERE id=2")
        try:
            self.api(self.operator,'POST','/system/payments',self.body(periodEnd='2030-06-01'))
            row=self.sql('SELECT plan_expires_at::text,active,suspended_reason FROM companies WHERE id=2')[0]
            self.assertEqual(row,('2030-12-31',False,'Administrative block'))
        finally:self.sql('UPDATE companies SET active=TRUE,suspended_at=NULL,suspended_reason=NULL,plan_expires_at=NULL WHERE id=2')

    def test_concurrent_retries_create_exactly_one_receipt(self):
        body=self.body()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _: self.api(self.operator,'POST','/system/payments',body),range(2)))
        self.assertEqual(results[0]['id'],results[1]['id'])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM company_payments WHERE command_id=%s',(body['requestId'],)),[(1,)])

    def test_schema_rejects_partial_command_identity(self):
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql("INSERT INTO company_payments(company_id,amount,command_id) VALUES(2,1,%s)",(str(uuid.uuid4()),))

    def test_customer_and_director_cannot_credit_platform(self):
        for actor in (self.customer,self.fixture['users']['director']):
            self.api(actor,'POST','/system/payments',self.body(),expected=403)

    def seed_event(self, **changes):
        account=self.sql('SELECT platform_account_id FROM companies WHERE id=2')[0][0]
        document=self.sql("""INSERT INTO platform_billing_documents(company_id,platform_account_id,number,
            status,amount,currency,payment_provider) VALUES(2,%s,%s,'issued',150.12,'RUB','yukassa') RETURNING id""",
            (account,'TEST-'+str(uuid.uuid4())))[0][0]
        event=self.sql("""INSERT INTO platform_payment_events(company_id,platform_account_id,billing_document_id,
            provider,event_id,provider_status,amount,currency,trusted)
            VALUES(%s,%s,%s,'yukassa',%s,'succeeded',150.12,'RUB',TRUE) RETURNING id""",
            (changes.get('company_id',2),account,document,str(uuid.uuid4())))[0][0]
        return document,event

    def test_provider_cannot_credit_another_company_from_event(self):
        document,event=self.seed_event(company_id=3)
        self.api(self.operator,'POST',f'/system/payment-events/{event}/confirm',{},expected=400)
        self.assertEqual(self.sql('SELECT status FROM platform_billing_documents WHERE id=%s',(document,)),[('issued',)])

    def test_provider_preserves_longer_period_and_administrative_block(self):
        document,event=self.seed_event()
        self.sql("UPDATE companies SET plan_expires_at='2030-12-31',active=FALSE,suspended_reason='Block' WHERE id=2")
        try:
            self.api(self.operator,'POST',f'/system/payment-events/{event}/confirm',{'periodEnd':'2030-06-01'})
            self.assertEqual(self.sql('SELECT plan_expires_at::text,active,suspended_reason FROM companies WHERE id=2'),[('2030-12-31',False,'Block')])
        finally:self.sql('UPDATE companies SET active=TRUE,suspended_reason=NULL,plan_expires_at=NULL WHERE id=2')

    def test_two_provider_events_cannot_settle_one_invoice_twice(self):
        document,event=self.seed_event()
        second=self.sql("""INSERT INTO platform_payment_events(company_id,platform_account_id,billing_document_id,
            provider,event_id,provider_status,amount,currency,trusted)
            SELECT company_id,platform_account_id,billing_document_id,provider,%s,provider_status,amount,currency,trusted
            FROM platform_payment_events WHERE id=%s RETURNING id""",(str(uuid.uuid4()),event))[0][0]
        lock=self.main.get_db();lock.autocommit=False
        token=self.main.create_auth_token(self.operator,two_factor_passed=True)
        def confirm(event_id):
            return self.client.post(f'/system/payment-events/{event_id}/confirm',json={},headers={'Authorization':'Bearer '+token})
        try:
            with lock.cursor() as cur:cur.execute('SELECT id FROM platform_billing_documents WHERE id=%s FOR UPDATE',(document,))
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(confirm,event_id) for event_id in (event,second)]
                try:
                    deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        waiting=self.sql("""SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database()
                            AND wait_event_type='Lock' AND query LIKE '%%platform_billing_documents%%'""")[0][0]
                        if waiting>=2:break
                        time.sleep(.02)
                    self.assertGreaterEqual(waiting,2,'Both confirmations must overlap while invoice is locked')
                finally:lock.commit()
                responses=[f.result(timeout=10) for f in futures]
            self.assertEqual(sorted(r.status_code for r in responses),[200,400])
            self.assertEqual(self.sql("SELECT COUNT(*) FROM platform_payment_events WHERE billing_document_id=%s AND payment_id IS NOT NULL",(document,)),[(1,)])
        finally:lock.close()

    def test_audit_failure_rolls_back_payment_and_period(self):
        from . import routes
        body=self.body(periodEnd='2031-01-01')
        before=self.sql('SELECT plan_expires_at,payment_status FROM companies WHERE id=2')
        with patch.object(routes,'_system_write_audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaisesRegex(RuntimeError,'audit unavailable'):
                self.api(self.operator,'POST','/system/payments',body)
        self.assertEqual(self.sql('SELECT id FROM company_payments WHERE command_id=%s',(body['requestId'],)),[])
        self.assertEqual(self.sql('SELECT plan_expires_at,payment_status FROM companies WHERE id=2'),before)

    def test_provider_requires_exact_kopecks_and_rubles(self):
        for amount,currency in (('150.11','RUB'),('150.12','EUR')):
            document,event=self.seed_event()
            self.sql('UPDATE platform_payment_events SET amount=%s,currency=%s WHERE id=%s',(amount,currency,event))
            self.sql('UPDATE platform_billing_documents SET currency=%s WHERE id=%s',(currency,document))
            self.api(self.operator,'POST',f'/system/payment-events/{event}/confirm',{},expected=400)
            self.assertEqual(self.sql('SELECT status FROM platform_billing_documents WHERE id=%s',(document,)),[('issued',)])
