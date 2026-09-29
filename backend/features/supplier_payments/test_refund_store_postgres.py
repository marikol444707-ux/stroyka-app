"""Atomic allocated refunds on disposable PostgreSQL, no mounted endpoint."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import psycopg2
from fastapi import HTTPException
from . import test_allocation_store_postgres as base
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class RefundStoreTests(unittest.TestCase):
    sql = base.AllocationStorePostgresTests.sql
    api = base.AllocationStorePostgresTests.api
    create_offer = base.AllocationStorePostgresTests.create_offer
    check_contract = base.AllocationStorePostgresTests.check_contract
    seed_receipt = base.AllocationStorePostgresTests.seed_receipt
    pay = base.AllocationStorePostgresTests.pay
    replace = base.AllocationStorePostgresTests.replace
    read = base.AllocationStorePostgresTests.read
    snapshot = base.AllocationStorePostgresTests.snapshot
    synthetic_current_group_authorizer = base.AllocationStorePostgresTests.synthetic_current_group_authorizer

    @classmethod
    def setUpClass(cls):
        base.AllocationStorePostgresTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, '0055_supplier_settlements.py')
                migration(cur, '0059_supplier_refund_allocations.py')
                migration(cur, '0059_supplier_refund_allocations.py', method='downgrade')
                migration(cur, '0059_supplier_refund_allocations.py')
        finally:
            conn.close()

    def setUp(self):
        flags = patch.dict(os.environ,SUPPLIER_SETTLEMENTS_ENABLED='1',SUPPLIER_ALLOCATED_REFUNDS_ENABLED='1')
        flags.start(); self.addCleanup(flags.stop)
        base.AllocationStorePostgresTests.setUp(self)
        self.replace(dict(requestId=str(uuid4()),groupId=self.group,expectedVersion=0,reason='Initial map',rows=[
            dict(paymentId=self.payment,receiptId=self.receipts[0]['id'],amount='40'),
            dict(paymentId=self.second_payment,receiptId=self.receipts[1]['id'],amount='20')]))

    def body(self, **changes):
        return dict(dict(requestId=str(uuid4()),groupId=self.group,expectedVersion=1,paymentId=self.payment,
            amount='25',unallocatedAmount='5',paidAt='2026-09-28',reason='Synthetic bank refund',
            releases=[dict(receiptId=self.receipts[0]['id'],amount='20')]), **changes)

    def refund(self, body):
        from .refund_store import refund
        from .policy import validate_new_payment
        return refund(self.main.get_db,self.synthetic_current_group_authorizer,self.payment_resolver,
                      self.actor,2,body,validate_new=validate_new_payment)

    def test_atomic_refund_replay_and_reversal(self):
        body=self.body(); result=self.refund(body)
        self.assertEqual(self.refund(body),result)
        view=self.read()
        self.assertEqual((view['paid'],view['allocated'],view['unallocatedPayments']),('65.00','40.00','25.00'))
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(65,)])
        self.assertEqual(self.sql('SELECT amount FROM project_payments WHERE id=%s',(result['projectPaymentId'],)),[(-25,)])
        self.assertEqual(self.sql('SELECT version FROM supplier_payment_allocation_revisions WHERE group_id=%s ORDER BY version',(self.group,)),[(1,),(2,)])
        self.pay(reverses=result['operationId'])
        self.assertEqual((self.read()['paid'],self.read()['allocated']),('90.00','40.00'))
        self.assertEqual(self.refund(body),result)

    def test_late_failure_rolls_back_cash_map_link_and_balance(self):
        before=self.snapshot(); maps=self.snapshot(allocations=True)
        self.sql("CREATE FUNCTION refund_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'late failure'; END $$")
        self.sql('''CREATE CONSTRAINT TRIGGER refund_test_failure AFTER INSERT ON supplier_payment_refund_links
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refund_test_failure()''')
        body=self.body()
        try:
            with self.assertRaises(psycopg2.Error): self.refund(body)
            self.assertEqual(self.snapshot(),before)
            self.assertEqual(self.snapshot(allocations=True),maps)
            self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_refund_links WHERE group_id=%s',(self.group,)),[(0,)])
        finally:
            self.sql('DROP TRIGGER refund_test_failure ON supplier_payment_refund_links')
            self.sql('DROP FUNCTION refund_test_failure()')
        self.assertEqual(self.refund(body)['version'],2)

    def test_source_reversal_is_blocked_even_with_other_cash_available(self):
        self.refund(self.body())
        self.pay('100')
        before=self.snapshot()
        with self.assertRaises(psycopg2.Error): self.pay(reverses=self.payment)
        self.assertEqual(self.snapshot(),before)

    def test_stale_changed_uuid_and_revoked_membership(self):
        body=self.body(); self.refund(body)
        for attempt in (self.body(), dict(body,amount='26',unallocatedAmount='6')):
            with self.assertRaises(HTTPException) as error: self.refund(attempt)
            self.assertEqual(error.exception.status_code,409)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(self.actor,))
        try:
            with self.assertRaises(HTTPException) as error: self.refund(body)
            self.assertEqual(error.exception.status_code,403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(self.actor,))

    def test_competing_refunds_and_same_uuid(self):
        for same in (True,False):
            # Use the current map version for a new pair of concurrent requests.
            body=self.body(expectedVersion=self.read()['version'],amount='1',unallocatedAmount='1',releases=[])
            gate=Barrier(2)
            def attempt(index):
                gate.wait(timeout=5)
                try: return self.refund(body if same or not index else dict(body,requestId=str(uuid4())))
                except HTTPException as error: return error.status_code
            with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(attempt,range(2)))
            if same: self.assertEqual(results[0],results[1])
            else: self.assertEqual(sum(isinstance(r,dict) for r in results),1); self.assertIn(409,results)

    def test_followup_allocation_respects_net_source_capacity(self):
        self.refund(self.body())
        with self.assertRaises(HTTPException):
            self.replace(dict(requestId=str(uuid4()),groupId=self.group,expectedVersion=2,reason='Too much',
                rows=[dict(paymentId=self.payment,receiptId=self.receipts[0]['id'],amount='36')]))
        result=self.refund(self.body(expectedVersion=2,amount='35',unallocatedAmount='15'))
        self.assertEqual(self.read()['paid'],'30.00')
        self.assertEqual(self.read()['allocated'],'20.00')
        self.assertEqual(result['version'],3)

    def test_direct_sql_cannot_overallocate_net_or_change_evidence(self):
        self.refund(self.body())
        conn=self.main.get_db()
        try:
            with self.assertRaises(psycopg2.Error):
                with conn,conn.cursor() as cur:
                    cur.execute('''INSERT INTO supplier_payment_allocation_revisions
                        (company_id,group_id,version,previous_revision_id,request_id,fingerprint,actor_id,reason,row_count)
                        SELECT 2,%s,3,id,%s,%s,%s,'Forged gross allocation',1
                        FROM supplier_payment_allocation_revisions WHERE group_id=%s AND version=2 RETURNING id''',
                        (self.group,str(uuid4()),'a'*64,self.actor,self.group))
                    revision=cur.fetchone()[0]
                    cur.execute('''INSERT INTO supplier_payment_allocation_rows
                        (revision_id,group_id,company_id,payment_operation_id,receipt_relation_id,amount)
                        VALUES(%s,%s,2,%s,%s,36)''',(revision,self.group,self.payment,self.receipts[0]['id']))
            with self.assertRaises(psycopg2.Error):
                with conn,conn.cursor() as cur:
                    cur.execute('UPDATE supplier_payment_refund_links SET fingerprint=%s WHERE group_id=%s',('b'*64,self.group))
            with self.assertRaises(psycopg2.Error):
                with conn,conn.cursor() as cur:
                    migration(cur,'0059_supplier_refund_allocations.py',method='downgrade')
        finally: conn.close()
        self.assertEqual(self.read()['version'],2)

    def test_flag_blocks_new_but_preserves_authorized_replay(self):
        body=self.body(); result=self.refund(body)
        with patch.dict(os.environ,SUPPLIER_ALLOCATED_REFUNDS_ENABLED='0'):
            self.assertEqual(self.refund(body),result)
            with self.assertRaises(HTTPException) as error:
                self.refund(self.body(expectedVersion=2))
            self.assertEqual(error.exception.status_code,409)

    def test_unlinked_refund_after_empty_map_cannot_bypass_source_evidence(self):
        self.refund(self.body())
        self.replace(dict(requestId=str(uuid4()),groupId=self.group,expectedVersion=2,reason='Clear map',rows=[]))
        from .engine import execute
        from .policy import validate_new_payment
        before=self.snapshot()
        with self.assertRaises(psycopg2.Error):
            execute(self.main.get_db,self.payment_resolver,self.actor,2,
                dict(requestId=str(uuid4()),kind='refund',documentKind='invoice',documentId=self.invoice,
                     amount='1',paidAt='2026-09-28',reason='No source link'),validate_new=validate_new_payment)
        self.assertEqual(self.snapshot(),before)

    def test_database_caps_refund_even_if_planner_is_bypassed(self):
        before=self.snapshot(); maps=self.snapshot(allocations=True)
        # Fault injection verifies the DB independently of the pure planner.
        with patch('backend.features.supplier_payments.refund_store.plan_refund',return_value={'rows':[]}):
            with self.assertRaises(psycopg2.Error):
                self.refund(self.body(amount='65',unallocatedAmount='45'))
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.snapshot(allocations=True),maps)

    def test_real_financial_authority_resolves_all_receipt_scopes(self):
        from .allocation_access import build_allocation_access
        self.synthetic_current_group_authorizer=build_allocation_access(dict(
            resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES,platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access,has_package_access=self.main.has_package_access))
        body=self.body(); result=self.refund(body)
        self.assertEqual(self.refund(body),result)
        self.assertEqual(self.read()['paid'],'65.00')

    def test_disabled_database_guard_fails_closed_before_new_write_or_replay(self):
        body=self.body(); self.refund(body)
        before=self.snapshot(); maps=self.snapshot(allocations=True)
        self.sql('ALTER TABLE supplier_payment_refund_links DISABLE TRIGGER refund_complete')
        try:
            for command in (body,self.body(expectedVersion=2)):
                with self.assertRaises(HTTPException) as error: self.refund(command)
                self.assertEqual(error.exception.status_code,503)
        finally:
            self.sql('ALTER TABLE supplier_payment_refund_links ENABLE TRIGGER refund_complete')
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.snapshot(allocations=True),maps)
