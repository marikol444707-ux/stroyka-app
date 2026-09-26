"""The same atomic writes remain available before 0017; fresh isolated DB only."""
import os
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException

from ..supplier_access import test_postgres_chain as chain
from . import test_offer_mutation_ledger_postgres as guarded


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class OfferMutationPreledgerTests(unittest.TestCase):
    setUpClass = classmethod(chain.PostgresSupplyChainTests.setUpClass.__func__)
    setUp = guarded.OfferMutationLedgerTests.setUp
    sql = guarded.OfferMutationLedgerTests.sql
    call = guarded.OfferMutationLedgerTests.call
    snapshot = guarded.OfferMutationLedgerTests.snapshot
    test_legacy_behavior = guarded.OfferMutationLedgerTests.test_unmanaged_ship_and_offer_changes_keep_legacy_behavior
    test_edit_rollback = guarded.OfferMutationLedgerTests.test_update_event_failure_rolls_back_offer_and_recipients
    test_ship_rollback = guarded.OfferMutationLedgerTests.test_ship_late_failure_rolls_back_new_deliveries
    test_event_allowlist = guarded.OfferMutationLedgerTests.test_update_event_keeps_allowlist_and_discards_unexpected_private_fields

    def test_concurrent_sibling_updates_complete_without_deadlock(self):
        self.concurrent_mutations('company', 'update')

    def test_ship_schema_preparation_cannot_deadlock_with_running_update(self):
        self.concurrent_mutations('company', 'ship')

    def test_withdraw_and_generic_create_finish_or_retry_without_deadlock(self):
        self.sql('UPDATE supplier_invoices SET offer_id=NULL,request_id=NULL WHERE id=%s', (self.invoice,))
        self.sql("UPDATE supplier_offers SET status='Получено' WHERE id=%s", (self.offer,))
        self.concurrent_mutations('company', 'create')

    def test_busy_core_lock_rolls_back_partial_locks_for_all_three_writers(self):
        before = self.snapshot()
        operations = [lambda: self.call('update'), lambda: self.call('ship'),
                      lambda: self.main.create_supplier_invoice(
                          {'companyId': 2, 'supplierId': self.fixture['supplierId'],
                           'invoiceNumber': self.number + '-BUSY', 'amount': 200},
                          _current_user=self.fixture['users']['director'],
                          x_company_id=None, x_company_mode=None)]
        for operation in operations:
            blocker = self.main.get_db()
            blocker.autocommit = False
            try:
                with blocker.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                    # Emulate an unmodified legacy writer. The new guard will
                    # already have locked both invoice tables before this clash.
                    cur.execute('LOCK TABLE supply_requests IN ACCESS SHARE MODE')
                    pending = pool.submit(operation)
                    try:
                        with self.assertRaises(HTTPException) as error:
                            pending.result(timeout=3)
                        self.assertEqual(error.exception.status_code, 409)
                        self.assertIn('занят', error.exception.detail)
                        cur.execute('''LOCK TABLE supplier_invoices,warehouse_invoices
                            IN ACCESS EXCLUSIVE MODE NOWAIT''')
                    finally:
                        blocker.rollback()
            finally:
                blocker.close()
            self.assertEqual(self.snapshot(), before)

    def concurrent_mutations(self, blocked_table, second_kind):
        sibling = self.sql('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,
            price_per_unit,total_price,status) VALUES(2,%s,%s,100,200,'Утверждено') RETURNING id''',
            (self.request, self.fixture['supplierId']))[0][0]
        def mutate(offer_id, kind):
            if kind == 'create':
                return self.main.create_supplier_invoice(
                    {'companyId': 2, 'supplierId': self.fixture['supplierId'],
                     'invoiceNumber': self.number + '-NEW', 'amount': 200},
                    _current_user=self.fixture['users']['director'], x_company_id=None, x_company_mode=None)
            path = '/supplier-offers/{id}' + ('/ship' if kind == 'ship' else '')
            method = 'POST' if kind == 'ship' else 'PUT'
            endpoint = next(r.endpoint for r in self.main.app.routes
                            if getattr(r, 'path', '') == path and method in r.methods)
            action = 'withdraw' if second_kind == 'create' else 'reject'
            payload = {'shippedQuantity': 2} if kind == 'ship' else {'action': action}
            return endpoint(offer_id, payload, x_company_id=None, x_company_mode=None,
                            _current_user=self.fixture['users']['director'])

        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur, ThreadPoolExecutor(max_workers=2) as pool:
                if blocked_table == 'company':
                    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                else:
                    cur.execute('SELECT id FROM supply_requests WHERE id=%s FOR UPDATE', (self.request,))
                cur.execute('SELECT pg_backend_pid()')
                blocker_pid = cur.fetchone()[0]
                first = pool.submit(mutate, self.offer, 'update')
                second = None
                try:
                    deadline = time.monotonic() + 4
                    first_waiter = None
                    while time.monotonic() < deadline:
                        waiting = self.sql('SELECT pid FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid))',
                                           (blocker_pid,))
                        if waiting:
                            first_waiter = waiting[0][0]
                            break
                        time.sleep(.01)
                    self.assertIsNotNone(first_waiter, 'first update must reach the held row')
                    second = pool.submit(mutate, sibling, second_kind)
                    deadline = time.monotonic() + 4
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql('''SELECT pid FROM pg_stat_activity WHERE pid<>%s
                            AND (%s=ANY(pg_blocking_pids(pid)) OR %s=ANY(pg_blocking_pids(pid)))''',
                            (first_waiter, blocker_pid, first_waiter))
                        if waiting or second.done():
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting or second.done(), 'second writer must reach contention')
                finally:
                    blocker.rollback()
                first.result(timeout=6)
                try:
                    second.result(timeout=6)
                except HTTPException as error:
                    self.assertEqual(error.status_code, 409)
                    self.assertIn('занят', error.detail)
                    # NOWAIT contention is retryable, not a business prohibition.
                    mutate(sibling, second_kind)
        finally:
            blocker.close()
        expected_first = 'Отозвано' if second_kind == 'create' else 'Отклонено'
        expected_sibling = 'Отклонено' if second_kind == 'update' else 'Утверждено'
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id IN (%s,%s) ORDER BY id',
                                  (self.offer, sibling)), [(expected_first,), (expected_sibling,)])
        if second_kind == 'create':
            self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_invoices WHERE invoice_number=%s',
                                      (self.number + '-NEW',)), [(1,)])
