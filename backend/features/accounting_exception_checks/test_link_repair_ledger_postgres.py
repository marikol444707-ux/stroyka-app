"""Opt-in synthetic ledger/link-repair regression on an isolated Unix PostgreSQL."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch

from . import link_repair_runtime as runtime
from ..supplier_payments import test_engine_postgres as ledger


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LinkRepairLedgerPostgresTests(unittest.TestCase):
    setUpClass = classmethod(ledger.LedgerTests.setUpClass.__func__)
    sql = ledger.LedgerTests.sql
    seed_warehouse = ledger.LedgerTests.seed_warehouse

    def setUp(self):
        # Previous cases remain synthetic but must not join this case's plan.
        self.sql("UPDATE supplier_invoices SET status='Аннулирован'")
        self.sql("UPDATE warehouse_invoices SET status='Аннулирована'")
        ledger.LedgerTests.setUp(self)
        self.warehouse = self.seed_warehouse()
        self.sql('UPDATE supplier_invoices SET paid_amount=0 WHERE id=%s', (self.invoice,))
        self.sql('UPDATE warehouse_invoices SET paid_amount=0 WHERE id=%s', (self.warehouse,))
        session_hash = uuid4().hex + uuid4().hex
        self.sql('''INSERT INTO user_sessions(user_id,session_hash,two_factor_passed,expires_at)
                    VALUES(%s,%s,TRUE,NOW()+INTERVAL '1 hour')''', (self.actor, session_hash))
        self.authentication = {'authenticationKind': 'cookie_session', 'sessionHash': session_hash}
        self.preview = runtime.preview_accounting_link_repairs(
            self.main.get_db, self.authentication, 2, ('бухгалтер',),
        )
        self.assertEqual(self.preview['repairCount'], 1)

    def apply(self, get_db=None):
        return runtime.apply_accounting_link_repairs(
            get_db or self.main.get_db, self.authentication, 2, ('бухгалтер',),
            expected_repair_count=self.preview['repairCount'],
            expected_plan_sha256=self.preview['planSha256'],
        )

    def register(self, kind, document_id, cur=None):
        sql = '''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,
             project_name,work_package,amount,opening_paid)
            VALUES(2,%s,%s,2,%s,%s,'',200,0)'''
        params = (kind, document_id, self.fixture['supplierId'], self.fixture['project'])
        (cur.execute if cur else self.sql)(sql, params)

    def snapshot(self):
        return {table: self.sql(f'SELECT * FROM {table} ORDER BY id') for table in (
            'supplier_invoices', 'warehouse_invoices', 'supplier_payment_documents',
            'supplier_payment_operations', 'project_payments', 'audit_log',
        )}

    def assert_blocked(self):
        before = self.snapshot()
        with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
            self.apply()
        self.assertEqual(error.exception.code, 'accounting_link_repair_plan_blocked')
        self.assertEqual(self.snapshot(), before)

    def test_direct_zero_paid_baseline_blocks(self):
        self.register('invoice', self.invoice)
        self.assert_blocked()

    def test_proposed_registered_warehouse_blocks(self):
        self.register('warehouse', self.warehouse)
        self.assert_blocked()

    def test_reverse_link_to_registered_annulled_invoice_blocks(self):
        other = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,project_name,amount,paid_amount,status,warehouse_invoice_id)
            VALUES(2,%s,%s,200,0,'Аннулирован',%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], self.warehouse))[0][0]
        self.register('invoice', other)
        self.assert_blocked()

    def test_current_annulled_warehouse_baseline_blocks_dangling_clear(self):
        other = self.seed_warehouse()
        self.sql("UPDATE warehouse_invoices SET status='Аннулирована',supplier_invoice_id=NULL,paid_amount=0 WHERE id=%s", (other,))
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (other, self.invoice))
        # Clearing a dangling/inactive link is also a document mutation.
        self.preview = runtime.preview_accounting_link_repairs(self.main.get_db, self.authentication, 2, ('бухгалтер',))
        self.register('warehouse', other)
        self.assert_blocked()

    def test_reverse_registered_warehouse_blocks_invoice_root(self):
        other = self.seed_warehouse()
        self.sql("UPDATE warehouse_invoices SET status='Аннулирована',paid_amount=0 WHERE id=%s", (other,))
        self.register('warehouse', other)
        self.assert_blocked()

    def test_one_registered_repair_blocks_the_whole_plan_without_partial_writes(self):
        ledger.LedgerTests.setUp(self)
        self.warehouse = self.seed_warehouse()
        self.sql('UPDATE supplier_invoices SET paid_amount=0 WHERE id=%s', (self.invoice,))
        self.sql('UPDATE warehouse_invoices SET paid_amount=0 WHERE id=%s', (self.warehouse,))
        self.preview = runtime.preview_accounting_link_repairs(self.main.get_db, self.authentication, 2, ('бухгалтер',))
        self.assertEqual(self.preview['repairCount'], 2)
        self.register('invoice', self.invoice)
        self.assert_blocked()

    def test_late_audit_failure_rolls_back_both_links(self):
        before = self.snapshot()
        self.sql('''CREATE FUNCTION synthetic_repair_audit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic repair audit failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_repair_audit_failure BEFORE INSERT ON audit_log
                    FOR EACH ROW EXECUTE FUNCTION synthetic_repair_audit_failure()''')
        try:
            with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
                self.apply()
            self.assertEqual(error.exception.code, 'accounting_link_repair_write_failed')
        finally:
            self.sql('DROP TRIGGER synthetic_repair_audit_failure ON audit_log')
            self.sql('DROP FUNCTION synthetic_repair_audit_failure()')
        self.assertEqual(self.snapshot(), before)

    def test_unregistered_pair_repairs_both_sides(self):
        self.assertTrue(self.apply()['ok'])
        self.assertEqual(self.sql('SELECT warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                  (self.invoice,)), [(self.warehouse,)])
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s',
                                  (self.warehouse,)), [(self.invoice,)])

    def revocations(self):
        return [
            ('UPDATE user_sessions SET revoked_at=NOW() WHERE session_hash=%s', (self.authentication['sessionHash'],)),
            ('UPDATE users SET active=FALSE WHERE id=%s', (self.actor,)),
            ('UPDATE companies SET active=FALSE WHERE id=%s', (2,)),
            ('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,)),
        ]

    def test_authority_is_locked_between_final_check_and_write_until_commit(self):
        import psycopg2
        apply_plan = runtime._apply_plan
        blocked = []

        def at_write_boundary(*args):
            # Separate real PG transaction attempts revocation at an exact
            # barrier after authorization and before the first repair write.
            for sql, params in self.revocations():
                other = self.main.get_db()
                other.autocommit = False
                try:
                    with other.cursor() as cur:
                        cur.execute("SET LOCAL lock_timeout='50ms'")
                        try:
                            cur.execute(sql, params)
                            blocked.append(False)
                        except psycopg2.errors.LockNotAvailable:
                            blocked.append(True)
                finally:
                    other.rollback()
                    other.close()
            return apply_plan(*args)

        with patch.object(runtime, '_apply_plan', side_effect=at_write_boundary):
            self.assertTrue(self.apply()['ok'])
        self.assertEqual(blocked, [True] * 4)
        # Once committed, none of the authority locks leak into later requests.
        for sql, params in self.revocations():
            other = self.main.get_db()
            other.autocommit = False
            try:
                with other.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='50ms'")
                    cur.execute(sql, params)
            finally:
                other.rollback()
                other.close()

    def test_inflight_revocation_returns_busy_without_repair_writes(self):
        before = self.snapshot()
        for sql, params in self.revocations():
            with self.subTest(sql=sql):
                other = self.main.get_db()
                other.autocommit = False
                try:
                    with other.cursor() as cur:
                        cur.execute(sql, params)
                        with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
                            self.apply()
                        self.assertEqual(error.exception.code, 'accounting_link_repair_busy')
                finally:
                    other.rollback()
                    other.close()
                self.assertEqual(self.snapshot(), before)

    def test_inflight_registration_is_busy_then_committed_baseline_blocks(self):
        first = self.main.get_db()
        first.autocommit = False
        try:
            with first.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                self.register('invoice', self.invoice, cur)
                with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
                    self.apply()
                self.assertEqual(error.exception.code, 'accounting_link_repair_busy')
                first.commit()
                self.assert_blocked()
        finally:
            first.rollback()
            first.close()

    def test_stock_writer_can_finish_after_repair_declines_conflicting_tables(self):
        first = self.main.get_db()
        first.autocommit = False
        try:
            with first.cursor() as cur:
                cur.execute('LOCK TABLE materials,warehouse_main,projects IN SHARE ROW EXCLUSIVE MODE')
                with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
                    self.apply()
                self.assertEqual(error.exception.code, 'accounting_link_repair_busy')
                cur.execute('SELECT pg_try_advisory_xact_lock(%s,%s)', (1735289201, 2))
                self.assertTrue(cur.fetchone()[0])
                cur.execute('SELECT id FROM warehouse_invoices WHERE id=%s FOR UPDATE NOWAIT', (self.warehouse,))
        finally:
            first.rollback()
            first.close()
        self.assertTrue(self.apply()['ok'])


if __name__ == '__main__':
    unittest.main()
