"""Real PostgreSQL adapter/resolver regressions, with a synthetic receipt writer.

Run these only through the explicit empty-database gate documented in
test_fixture_postgres.py. No fake cursors or mocked resolver SQL are used here.
The stock, history, proof, claim and resource-limit writer/tables are stand-ins;
passing does not prove the production accounting/claim endpoints or full
migration chain work. Original-evidence SQL and its schema guards are real.
"""
import copy
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import psycopg2
from fastapi import HTTPException
from psycopg2 import sql
from psycopg2.extras import Json

from . import test_fixture_postgres as support


@unittest.skipUnless(support.RUN_POSTGRES, support.SKIP_REASON)
class ConfirmationPostgresTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ReceiptPostgresFixture()
        self.addCleanup(self.fixture.close)
        self.before = self.fixture.snapshot()

    def assert_unchanged(self):
        self.assertEqual(self.fixture.snapshot(), self.before)
        self.assertEqual(self.fixture.callbacks, [])
        self.assertEqual(sum(conn.commits for conn in self.fixture.confirmation_connections), 0)
        self.assertTrue(all(conn.closed for conn in self.fixture.confirmation_connections))

    def assert_rejected(self, status):
        with self.assertRaises(HTTPException) as caught:
            self.fixture.confirm()
        self.assertEqual(caught.exception.status_code, status)
        self.assert_unchanged()

    def wait_for_connection(self, count, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.fixture.confirmation_connections) >= count:
                return self.fixture.confirmation_connections[count - 1]
            time.sleep(.01)
        self.fail('Confirmation did not open the expected PostgreSQL connection')

    def test_batch_commits_once_with_canonical_originals_before_callbacks(self):
        result = self.fixture.confirm()
        state = self.fixture.snapshot()
        conn = self.fixture.confirmation_connections[0]
        self.assertTrue(result['ok'])
        self.assertFalse(result['alreadyReceived'])
        self.assertEqual((conn.commits, conn.rollbacks), (1, 0))
        self.assertTrue(conn.closed)
        self.assertEqual(self.fixture.written_lines, [31, 32])
        self.assertEqual(len(state['warehouse_invoices']), 2)
        self.assertEqual(len(state['warehouse_history_standin']), 2)
        self.assertEqual(len(state['receipt_line_proofs_standin']), 2)
        self.assertEqual(result['warehouseInvoiceIds'], [row['id'] for row in state['warehouse_invoices']])
        for invoice in state['warehouse_invoices']:
            self.assertEqual(invoice['photo_urls'], ['/tenant-files/77/content', '/tenant-files/78/content'])
            self.assertEqual(invoice['pages_count'], 2)
            self.assertEqual(invoice['company_id'], 2)
        for original in state['file_ownership']:
            self.assertEqual(original['retained_at'] is not None, original['id'] in (77, 78))
        self.assertEqual([row['quantity'] for row in state['warehouse_main']],
                         [Decimal(8), Decimal(8), Decimal(100)])
        self.assertEqual([identity for identity, _ in self.fixture.callbacks], [31, 32])
        self.assertTrue(all(observed == state for _, observed in self.fixture.callbacks))
        # Statement ordering is recorded, but every statement was executed by PG.
        stock = next(i for i, query in enumerate(conn.statements) if query.startswith('LOCK TABLE'))
        first_read = next(i for i, query in enumerate(conn.statements) if 'FROM user_company_roles' in query)
        self.assertLess(stock, first_read)

    def test_later_line_exception_rolls_back_stock_invoices_history_and_proofs(self):
        def fail_after_write(identity, transaction):
            if identity == 32:
                raise HTTPException(409, 'Synthetic second-line failure after all SQL mutations')
        self.fixture.after_write = fail_after_write
        self.assert_rejected(409)
        self.assertEqual(self.fixture.written_lines, [31, 32])
        self.assertEqual(self.fixture.confirmation_connections[0].rollbacks, 1)

    def zero_quantities(self):
        for line in self.fixture.data['actualLines']:
            line['receivedQuantity'] = '0'

    def assert_zero_receipt(self, result):
        state = self.fixture.snapshot()
        originals = ['/tenant-files/77/content', '/tenant-files/78/content']
        self.assertTrue(result['ok'])
        self.assertFalse(result['alreadyReceived'])
        self.assertEqual(result['warehouseInvoiceIds'], [])
        for table in ('warehouse_main', 'warehouse_invoices', 'receipt_line_proofs_standin'):
            self.assertEqual(state[table], self.before[table])
        self.assertEqual(len(state['supply_claims']), 2)
        self.assertEqual(len(state['warehouse_history_standin']), 2)
        self.assertTrue(all(row['quantity'] == 0 for row in state['warehouse_history_standin']))
        linked = self.fixture.query('''SELECT c.id,c.delivery_id,d.claim_id,d.company_id,
            d.receipt_original_urls,d.received_quantity,d.received_at,d.status
            FROM supply_claims c JOIN supply_deliveries d ON d.id=c.delivery_id ORDER BY c.delivery_id''')
        self.assertEqual([row['delivery_id'] for row in linked], [31, 32])
        for row in linked:
            self.assertEqual(row['id'], row['claim_id'])
            self.assertEqual(row['company_id'], 2)
            self.assertEqual(row['receipt_original_urls'], originals)
            self.assertEqual(row['received_quantity'], 0)
            self.assertEqual(row['status'], 'Проблема')
            self.assertIsNotNone(row['received_at'])
        self.assertEqual([row['claimId'] for row in result['receipts']], [row['id'] for row in linked])
        self.assertTrue(all(row['invoiceId'] is None for row in result['receipts']))
        return state

    def test_all_zero_receipt_saves_every_original_on_claim_linked_deliveries_without_stock(self):
        self.zero_quantities()
        result = self.fixture.confirm()
        self.assert_zero_receipt(result)
        self.assertEqual(sum(conn.commits for conn in self.fixture.confirmation_connections), 1)

    def test_all_zero_replay_cannot_duplicate_claim_history_or_replace_originals(self):
        self.zero_quantities()
        self.fixture.query('INSERT INTO file_ownership(id,company_id,project_id) VALUES(81,2,11)')
        result = self.fixture.confirm()
        saved = self.assert_zero_receipt(result)
        self.fixture.data['originalUrls'] = ['/tenant-files/81/content']
        replay = self.fixture.confirm()
        self.assertTrue(replay['alreadyReceived'])
        self.assertEqual(replay['warehouseInvoiceIds'], [])
        self.assertEqual(self.fixture.snapshot(), saved)
        self.assertEqual(self.fixture.written_lines, [31, 32])
        self.assertEqual(len(self.fixture.callbacks), 2)
        self.assertEqual(sum(conn.commits for conn in self.fixture.confirmation_connections), 1)
        self.assertEqual(sum(conn.rollbacks for conn in self.fixture.confirmation_connections), 1)

    def test_later_zero_line_failure_rolls_back_originals_claims_history_and_retention(self):
        self.zero_quantities()
        def fail_after_second_claim(identity, transaction):
            if identity == 32:
                raise HTTPException(409, 'Synthetic failure after second zero-quantity claim')
        self.fixture.after_write = fail_after_second_claim
        self.assert_rejected(409)
        self.assertEqual(self.fixture.written_lines, [31, 32])

    def test_committed_zero_receipt_originals_are_database_immutable(self):
        self.zero_quantities()
        saved = self.assert_zero_receipt(self.fixture.confirm())
        for replacement in (None, [], ['/tenant-files/78/content', '/tenant-files/77/content'],
                            ['/tenant-files/81/content']):
            with self.subTest(replacement=replacement), self.assertRaises(psycopg2.errors.CheckViolation):
                self.fixture.query('UPDATE supply_deliveries SET receipt_original_urls=%s WHERE id=31',
                                   (None if replacement is None else Json(replacement),))
            self.assertEqual(self.fixture.snapshot(), saved)
        for field, replacement in (
                ('company_id', 3), ('supplier_id', 8), ('request_id', 19), ('offer_id', 18),
                ('project', 'Private'), ('work_package', 'Private'), ('waybill_number', 'B-13'),
                ('waybill_date', '2026-10-18'), ('source_supplier_invoice_id', 71),
                ('contract_version_id', 21)):
            with self.subTest(lineage_field=field), self.assertRaises(psycopg2.errors.CheckViolation):
                self.fixture.query(sql.SQL('UPDATE supply_deliveries SET {}=%s WHERE id=31').format(
                    sql.Identifier(field)), (replacement,))
            self.assertEqual(self.fixture.snapshot(), saved)

    def test_missing_immutable_schema_guard_prevents_zero_receipt_writes(self):
        self.zero_quantities()
        self.fixture.query('DROP TRIGGER supply_delivery_receipt_originals_immutable ON supply_deliveries')
        self.assert_rejected(503)
        self.assertEqual(self.fixture.written_lines, [])

    def test_later_resource_limit_guard_rolls_back_preceding_line(self):
        self.fixture.query('UPDATE resource_limits_standin SET max_quantity=7 WHERE delivery_id=32')
        self.assert_rejected(409)
        self.assertEqual(self.fixture.written_lines, [31])

    def test_later_overreceipt_rolls_back_preceding_line(self):
        self.fixture.data['actualLines'][1]['receivedQuantity'] = '10.0001'
        self.assert_rejected(400)
        self.assertEqual(self.fixture.written_lines, [31])

    def test_swallowed_writer_rollback_cannot_commit_partial_batch(self):
        self.fixture.after_write = lambda identity, transaction: transaction.rollback()
        self.assert_rejected(409)
        self.assertEqual(self.fixture.written_lines, [31])

    def test_original_update_rechecks_invoice_company_and_delivery(self):
        writer = self.fixture.deps['receive_delivery']
        self.fixture.query("""INSERT INTO warehouse_invoices(id,company_id,supply_delivery_id,photo_urls,pages_count)
            VALUES(900,3,61,'["/tenant-files/79/content"]',1)""")
        self.before = self.fixture.snapshot()
        def wrong_invoice(*args, **kwargs):
            return {**writer(*args, **kwargs), 'invoiceId': 900}
        self.fixture.deps['receive_delivery'] = wrong_invoice
        self.assert_rejected(409)
        self.assertEqual(self.fixture.written_lines, [31])

    def test_real_legacy_prepare_guard_fails_fast_before_resolver_on_conflict(self):
        from backend.features.supplier_payments.guards import lock_legacy_supply_writer
        self.fixture.deps['prepare_receipt_transaction'] = lock_legacy_supply_writer
        blocker = self.fixture.connect()
        with blocker.cursor() as cur:
            cur.execute('SELECT id FROM supplier_invoices')  # Hold ACCESS SHARE.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.fixture.confirm)
            try:
                with self.assertRaises(HTTPException) as caught:
                    future.result(timeout=2)
            finally:
                blocker.rollback()
                blocker.close()
        self.assertEqual(caught.exception.status_code, 409)
        self.assert_unchanged()
        queries = self.fixture.confirmation_connections[0].statements
        self.assertTrue(any('ACCESS EXCLUSIVE MODE NOWAIT' in query for query in queries))
        self.assertFalse(any('FROM user_company_roles' in query for query in queries))
        self.assertEqual(self.fixture.written_lines, [])

    def concurrent_repeat(self, *, stock_lock):
        entered = threading.Event()
        release = threading.Event()
        if not stock_lock:
            # Optional distribution-schema absence must leave real advisory locks
            # sufficient; this dependency intentionally acquires no table lock.
            self.fixture.deps['lock_stock'] = lambda cur: None
        def hold_first(identity, transaction):
            if identity == 31:
                entered.set()
                if not release.wait(10):
                    raise AssertionError('First receipt was not released')
        self.fixture.before_write = hold_first
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.fixture.confirm)
            try:
                self.assertTrue(entered.wait(5))
                second = pool.submit(self.fixture.confirm)
                conn1, conn2 = self.wait_for_connection(1), self.wait_for_connection(2)
                requested = conn2.stock_lock_requested if stock_lock else conn2.document_lock_requested
                self.assertTrue(requested.wait(5))
                self.fixture.wait_for_blocked(conn2, conn1.backend_pid)
            finally:
                release.set()
            results = [first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual(sorted(result['alreadyReceived'] for result in results), [False, True])
        self.assertEqual(results[0]['warehouseInvoiceIds'], results[1]['warehouseInvoiceIds'])
        self.assertEqual(self.fixture.written_lines, [31, 32])
        self.assertEqual(sum(conn.commits for conn in self.fixture.confirmation_connections), 1)
        state = self.fixture.snapshot()
        self.assertEqual(len(state['warehouse_invoices']), 2)
        self.assertEqual(len(state['receipt_line_proofs_standin']), 2)
        self.assertEqual(len(state['warehouse_history_standin']), 2)
        self.assertEqual(sum(row['quantity'] for row in state['warehouse_main'] if row['company_id'] == 2), 16)
        self.assertEqual(len(self.fixture.callbacks), 2)

    def test_concurrent_repeat_posts_once_under_stock_lock(self):
        self.concurrent_repeat(stock_lock=True)

    def test_concurrent_repeat_posts_once_without_optional_stock_lock(self):
        self.concurrent_repeat(stock_lock=False)

    def test_concurrent_other_batch_of_same_document_cannot_post_again(self):
        self.fixture.add_duplicate_batch()
        self.fixture.deps['lock_stock'] = lambda cur: None
        first_data = {**copy.deepcopy(self.fixture.data), 'selectedBatchId': 4,
                      'explicitSelectionConfirmed': True}
        second_data = {**copy.deepcopy(self.fixture.data), 'selectedBatchId': 5,
                       'explicitSelectionConfirmed': True}
        for line in second_data['actualLines']:
            line['deliveryId'] += 10
        # Equivalent formatting must contend on the same legal-document lock.
        second_data['document'].update(waybillNumber=' Ａ-12 ', waybillDate='17.10.2026')
        entered, release = threading.Event(), threading.Event()
        def hold_first(identity, transaction):
            if identity == 31:
                entered.set()
                if not release.wait(10):
                    raise AssertionError('First selected batch was not released')
        self.fixture.before_write = hold_first
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.fixture.confirm, first_data)
            try:
                self.assertTrue(entered.wait(5))
                second = pool.submit(self.fixture.confirm, second_data)
                conn1, conn2 = self.wait_for_connection(1), self.wait_for_connection(2)
                self.assertTrue(conn2.document_lock_requested.wait(5))
                self.fixture.wait_for_blocked(conn2, conn1.backend_pid)
            finally:
                release.set()
            result = first.result(timeout=10)
            with self.assertRaises(HTTPException) as caught:
                second.result(timeout=10)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertTrue(result['ok'])
        self.assertEqual(self.fixture.written_lines, [31, 32])
        self.assertEqual(sum(conn.commits for conn in self.fixture.confirmation_connections), 1)
        state = self.fixture.snapshot()
        self.assertEqual(len(state['warehouse_invoices']), 2)
        self.assertEqual(len(state['receipt_line_proofs_standin']), 2)
        self.assertEqual(len(state['warehouse_history_standin']), 2)
        self.assertEqual(sum(row['quantity'] for row in state['warehouse_main'] if row['company_id'] == 2), 16)
        self.assertTrue(all(row['received_quantity'] == 0 and row['received_at'] is None
                            for row in state['supply_deliveries'] if row['id'] in (41, 42)))

    def change_while_waiting_for_batch(self, statement, params=None, *, status, writes=()):
        blocker = self.fixture.connect()
        with blocker.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('physical-receipt-batch:2:4',))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.fixture.confirm)
            try:
                conn = self.wait_for_connection(1)
                self.assertTrue(conn.batch_lock_requested.wait(5))
                self.fixture.wait_for_blocked(conn, blocker.get_backend_pid())
                # Separate committed transaction changes data after first resolve,
                # before the adapter obtains the advisory lock and resolves again.
                self.fixture.query(statement, params)
                self.before = self.fixture.snapshot()
            finally:
                blocker.rollback()
                blocker.close()
            with self.assertRaises(HTTPException) as caught:
                future.result(timeout=10)
        self.assertEqual(caught.exception.status_code, status)
        self.assertEqual(self.fixture.written_lines, list(writes))
        self.assert_unchanged()

    def test_revoked_same_company_membership_revalidated_after_lock_wait(self):
        self.change_while_waiting_for_batch(
            'UPDATE user_company_roles SET active=FALSE WHERE user_id=1 AND company_id=2', status=403)

    def test_original_reassigned_company_revalidated_after_lock_wait(self):
        self.change_while_waiting_for_batch(
            'UPDATE file_ownership SET company_id=3 WHERE id=77', status=409)

    def test_original_marked_deleting_before_retention_blocks_all_posting(self):
        self.change_while_waiting_for_batch(
            "UPDATE file_ownership SET deletion_status='deleting' WHERE id=78", status=409)

    def test_same_company_package_access_revalidated_after_lock_wait(self):
        self.change_while_waiting_for_batch(
            "UPDATE user_company_roles SET assigned_packages='[\"Private\"]' WHERE user_id=1 AND company_id=2",
            status=409)

    def test_delivery_company_link_revalidated_after_lock_wait(self):
        self.change_while_waiting_for_batch(
            'UPDATE supply_deliveries SET company_id=3 WHERE id=32', status=409)

    def test_resource_limit_rechecked_by_writer_after_lock_wait(self):
        self.change_while_waiting_for_batch(
            'UPDATE resource_limits_standin SET max_quantity=7 WHERE delivery_id=32',
            status=409, writes=(31,))


@unittest.skipUnless(support.RUN_POSTGRES, support.SKIP_REASON)
class ResolverPostgresTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ReceiptPostgresFixture()
        self.addCleanup(self.fixture.close)

    def test_complete_authorized_batch_uses_real_frozen_projection_without_writes(self):
        before = self.fixture.snapshot()
        result = self.fixture.resolve()
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['matchedBatch']['companyId'], 2)
        self.assertEqual([row['id'] for row in result['matchedBatch']['lines']], [31, 32])
        self.assertEqual(result['matchedBatch']['documentParties']['buyer']['inn'], '9876543210')
        self.assertFalse(result['postingAllowed'])
        self.assertEqual(result['originalUrls'], ['/tenant-files/77/content', '/tenant-files/78/content'])
        self.assertEqual(self.fixture.snapshot(), before)

    def test_duplicate_batch_requires_explicit_choice_before_any_posting(self):
        self.fixture.add_duplicate_batch()
        before = self.fixture.snapshot()
        ambiguous = self.fixture.resolve()
        self.assertEqual(ambiguous['status'], 'ambiguous')
        self.assertNotIn('matchedBatch', ambiguous)
        data = {**copy.deepcopy(self.fixture.data), 'selectedBatchId': 4,
                'explicitSelectionConfirmed': True}
        selected = self.fixture.resolve(data)
        self.assertEqual(selected['status'], 'match')
        self.assertEqual(selected['matchedBatch']['id'], 4)
        self.assertFalse(selected['postingAllowed'])
        self.assertEqual(self.fixture.snapshot(), before)

    def test_hidden_finalized_canonical_waybill_peer_blocks_without_disclosure(self):
        self.fixture.add_duplicate_batch()
        self.fixture.hide_duplicate_batch()
        self.fixture.query("""UPDATE supply_deliveries SET received_quantity=8,
            received_at=NOW(),status='Проблема' WHERE id IN (41,42)""")
        for visible_number, hidden_number in (('A12', 'Ａ-12'), ('Е1', 'Ё-1')):
            with self.subTest(visible=visible_number, hidden=hidden_number):
                self.fixture.query('UPDATE supply_deliveries SET waybill_number=%s WHERE id IN (31,32)',
                                   (visible_number,))
                self.fixture.query('UPDATE supply_deliveries SET waybill_number=%s WHERE id IN (41,42)',
                                   (hidden_number,))
                self.fixture.data['document']['waybillNumber'] = visible_number
                before = self.fixture.snapshot()
                result = self.fixture.resolve()
                self.assertEqual(result['status'], 'review')
                for field in ('matchedBatch', 'lineIds', 'warehouseInvoiceIds', 'candidateBatches'):
                    self.assertNotIn(field, result)
                self.assertNotIn('Private', str(result))
                with self.assertRaises(HTTPException) as caught:
                    self.fixture.confirm()
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(self.fixture.snapshot(), before)
                self.assertEqual(self.fixture.written_lines, [])

    def test_other_company_original_is_denied_by_sql_ownership(self):
        self.fixture.data['originalUrls'] = ['/tenant-files/79/content']
        with self.assertRaises(HTTPException) as caught:
            self.fixture.resolve()
        self.assertEqual(caught.exception.status_code, 403)

    def test_same_company_other_project_original_is_denied_by_sql_ownership(self):
        self.fixture.data['originalUrls'] = ['/tenant-files/80/content']
        with self.assertRaises(HTTPException) as caught:
            self.fixture.resolve()
        self.assertEqual(caught.exception.status_code, 403)

    def test_hidden_package_prevents_partial_batch_and_id_disclosure(self):
        self.fixture.query("UPDATE supply_deliveries SET work_package='Private' WHERE id=32")
        result = self.fixture.resolve()
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('matchedBatch', result)
        self.assertNotIn('lineIds', result)
        self.assertNotIn('warehouseInvoiceIds', result)

    def test_cross_company_offer_chain_cannot_authorize_same_company_delivery(self):
        self.fixture.query('UPDATE supplier_offers SET company_id=3 WHERE id=8')
        result = self.fixture.resolve()
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('matchedBatch', result)
        self.assertNotIn('warehouseInvoiceIds', result)

    def test_invalid_source_invoice_is_rejected_by_actual_sql_chain(self):
        self.fixture.query("""INSERT INTO supplier_invoices(id,company_id,supplier_id,offer_id,request_id,status)
            VALUES(71,3,7,8,9,'Утверждён')""")
        self.fixture.query('UPDATE supply_deliveries SET source_supplier_invoice_id=71')
        result = self.fixture.resolve()
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('matchedBatch', result)

    def test_selected_source_invoice_never_falls_back_to_other_offer_deliveries(self):
        self.fixture.data['sourceSupplierInvoiceId'] = 999
        result = self.fixture.resolve()
        self.assertEqual(result['status'], 'no_match')
        self.assertNotIn('matchedBatch', result)

    def test_account_role_does_not_override_revoked_company_receiving_role(self):
        self.fixture.query("UPDATE user_company_roles SET role='главный_инженер' WHERE user_id=1")
        with self.assertRaises(HTTPException) as caught:
            self.fixture.resolve()
        self.assertEqual(caught.exception.status_code, 403)


if __name__ == '__main__':
    unittest.main()
