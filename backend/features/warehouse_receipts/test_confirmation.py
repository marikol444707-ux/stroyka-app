"""Focused atomic-confirmation regressions; no database or external services."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from backend.features.warehouse_receipts.confirmation import ReceiptTransaction, confirm_receipt


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 1
        self.closed = False
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.connection.events.append(('sql', sql))
        if sql.lstrip().startswith('UPDATE'):
            self.connection.pending.append(('originals', params))

    def close(self):
        self.closed = True


class Connection:
    def __init__(self):
        self.closed = False
        self.autocommit = True
        self.events = []
        self.pending = []
        self.persisted = []
        self.commits = 0
        self.rollbacks = 0
        self.cur = Cursor(self)

    def cursor(self, *args, **kwargs):
        return self.cur

    def commit(self):
        self.events.append(('commit',))
        self.commits += 1
        self.persisted.extend(self.pending)
        self.pending.clear()

    def rollback(self):
        self.events.append(('rollback',))
        self.rollbacks += 1
        self.pending.clear()

    def close(self):
        self.events.append(('close',))
        self.closed = True


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        schema = patch('backend.features.warehouse_receipts.confirmation.require_receipt_originals_schema')
        self.schema = schema.start()
        self.addCleanup(schema.stop)
        persistence = patch('backend.features.warehouse_receipts.confirmation.persist_receipt_originals')
        self.persist_originals = persistence.start()
        self.addCleanup(persistence.stop)
        retention = patch('backend.features.warehouse_receipts.confirmation.retain_originals')
        self.retain = retention.start()
        self.addCleanup(retention.stop)
        self.conn = Connection()
        self.user = {'id': 1, 'name': 'Warehouse operator'}
        self.headers = {'x_company_id': '2', 'x_company_mode': 'company'}
        self.data = {'physicalReceiptConfirmed': True, 'actualLines': [
            {'deliveryId': i, 'receivedQuantity': '8', 'qualityStatus': 'Недостача'}
            for i in (31, 32)]}
        self.match = {'status': 'match', 'warehouseInvoiceIds': [],
                      'originalUrls': ['/tenant-files/77/content', '/tenant-files/78/content'],
                      'matchedBatch': {'id': 4, 'companyId': 2, 'lines': [
                          {'id': i, 'shippedQuantity': 10, 'receivedAt': None,
                           'status': 'В пути'} for i in (31, 32)]}}
        self.deps = {'prepare_receipt_transaction': Mock(side_effect=lambda cur: self.conn.events.append(('legacy_preflight',))),
                     'get_db': Mock(return_value=self.conn),
                     'lock_stock': Mock(side_effect=lambda cur: self.conn.events.append(('stock_lock',))),
                     'receive_delivery': Mock(side_effect=self.receive)}
        self.resolver_patch = patch('backend.features.warehouse_receipts.confirmation.resolve_receipt',
                                    return_value=self.match)
        self.resolver = self.resolver_patch.start()
        self.addCleanup(self.resolver_patch.stop)

    def test_legacy_preflight_precedes_any_resolver_reads(self):
        def resolve(*args):
            self.assertIn(('stock_lock',),self.conn.events)
            self.assertIn(('legacy_preflight',),self.conn.events)
            return self.match
        self.resolver.side_effect=resolve
        confirm_receipt(self.data,self.user,self.headers,self.deps)
        self.deps['prepare_receipt_transaction'].assert_called_once_with(self.conn.cur)

    def test_busy_legacy_schema_fails_before_resolver_or_writer(self):
        self.deps['prepare_receipt_transaction'].side_effect=HTTPException(409,'busy')
        with self.assertRaises(HTTPException):
            confirm_receipt(self.data,self.user,self.headers,self.deps)
        self.resolver.assert_not_called()
        self.deps['receive_delivery'].assert_not_called()
        self.assertEqual(self.conn.rollbacks,1)

    def test_explicit_source_selection_is_revalidated_before_and_after_lock(self):
        self.data.update(selectedBatchId=4, sourceSupplierInvoiceId=19,
                         explicitSelectionConfirmed=True)
        confirm_receipt(self.data, self.user, self.headers, self.deps)
        self.assertEqual(self.resolver.call_count, 2)
        for call in self.resolver.call_args_list:
            self.assertIs(call.args[1], self.data)
            self.assertEqual(call.args[1]['selectedBatchId'], 4)
            self.assertEqual(call.args[1]['sourceSupplierInvoiceId'], 19)
            self.assertIs(call.args[1]['explicitSelectionConfirmed'], True)

    def test_payment_source_discovery_can_never_authorize_a_posting(self):
        self.resolver.return_value = {'status':'source_selection', 'requiresWaybill':True,
                                      'candidateBatches':[self.match['matchedBatch']]}
        with self.assertRaises(HTTPException) as error:
            confirm_receipt(self.data, self.user, self.headers, self.deps)
        self.assertEqual(error.exception.status_code, 409)
        self.deps['receive_delivery'].assert_not_called()
        self.assertEqual(self.conn.commits, 0)
        self.assertEqual(self.conn.rollbacks, 1)

    def test_existing_stock_evidence_with_stale_delivery_state_cannot_repost(self):
        for evidence in ({'warehouseInvoiceId':88},{'receivedQuantity':3}):
            with self.subTest(evidence=evidence):
                self.match['matchedBatch']['lines'][0].update(evidence)
                with self.assertRaises(HTTPException) as error:
                    confirm_receipt(self.data, self.user, self.headers, self.deps)
                self.assertEqual(error.exception.status_code,409)
                self.deps['receive_delivery'].assert_not_called()
                self.assertEqual(self.conn.commits,0)
                for key in evidence:
                    self.match['matchedBatch']['lines'][0].pop(key)
                self.conn.closed=False

    def test_missing_originals_migration_blocks_before_resolver_or_writer(self):
        self.schema.side_effect=HTTPException(503,'migration required')
        with self.assertRaises(HTTPException) as error:
            confirm_receipt(self.data,self.user,self.headers,self.deps)
        self.assertEqual(error.exception.status_code,503)
        self.resolver.assert_not_called()
        self.deps['receive_delivery'].assert_not_called()
        self.assertEqual(self.conn.commits,0)

    def test_zero_quantity_claim_does_not_require_stock_invoice(self):
        self.data['actualLines'][1]['receivedQuantity'] = '0'
        original = self.receive
        def writer(delivery_id, payload, **kwargs):
            result = original(delivery_id, payload, **kwargs)
            if delivery_id == 32:
                result['invoiceId'] = None
                result['claimId'] = 91
            return result
        self.deps['receive_delivery'].side_effect = writer
        result = confirm_receipt(self.data, self.user, self.headers, self.deps)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['warehouseInvoiceIds']), 1)
        self.assertEqual(self.conn.commits, 1)
        self.assertEqual(sum(1 for sql, _ in self.conn.cur.calls if sql.lstrip().startswith('UPDATE')), 1)
        self.assertEqual(result['receipts'][1]['claimId'], 91)
        self.persist_originals.assert_any_call(self.conn.cur,32,2,self.match['originalUrls'])
        self.assertEqual(self.persist_originals.call_count,2)

    def receive(self, delivery_id, payload, **kwargs):
        transaction = kwargs['connection']
        self.assertIsInstance(transaction, ReceiptTransaction)
        self.assertIs(transaction.connection, self.conn)
        self.assertEqual(self.conn.commits, 0)
        self.assertFalse(self.conn.closed)
        self.conn.events.append(('receive', delivery_id))
        self.conn.pending.append(('receipt', delivery_id))
        transaction.commit()
        transaction.close()
        kwargs['after_commit'].append(lambda: self.conn.events.append(('callback', delivery_id)))
        return {'ok': True, 'invoiceId': delivery_id + 100}

    def confirm(self):
        return confirm_receipt(self.data, self.user, self.headers, self.deps)

    def assert_rejected(self, status):
        with self.assertRaises(HTTPException) as raised:
            self.confirm()
        self.assertEqual(raised.exception.status_code, status)
        self.assertEqual(self.conn.commits, 0)
        self.assertEqual(self.conn.persisted, [])
        return raised.exception

    def test_physical_checkbox_requires_literal_true(self):
        for value in (False, None, 1, 'true'):
            with self.subTest(value=value):
                self.data['physicalReceiptConfirmed'] = value
                self.assert_rejected(400)
        self.deps['get_db'].assert_not_called()

    def test_invalid_quantities_rejected_before_database(self):
        for value in (None, True, {}, [], '', 'NaN', 'Infinity', '-1', '1.00001', '10000000000'):
            with self.subTest(value=value):
                self.data['actualLines'][0]['receivedQuantity'] = value
                self.assert_rejected(400)
        self.deps['get_db'].assert_not_called()

    def test_duplicate_actual_ids_rejected(self):
        self.data['actualLines'][1]['deliveryId'] = 31
        self.assert_rejected(400)
        self.deps['get_db'].assert_not_called()

    def test_cross_batch_actual_id_rejected_without_writes(self):
        self.data['actualLines'][1]['deliveryId'] = 99
        self.assert_rejected(409)
        self.deps['receive_delivery'].assert_not_called()

    def test_all_remaining_lines_required(self):
        self.data['actualLines'].pop()
        self.assert_rejected(400)
        self.deps['receive_delivery'].assert_not_called()

    def test_final_shortage_replay_does_not_write(self):
        for line in self.match['matchedBatch']['lines']:
            line.update(status='Проблема', receivedQuantity=8, receivedAt=None)
        self.match['warehouseInvoiceIds'] = [131, 132]
        result = self.confirm()
        self.assertTrue(result['alreadyReceived'])
        self.assertEqual(result['warehouseInvoiceIds'], [131, 132])
        self.deps['receive_delivery'].assert_not_called()
        self.assertFalse(any(sql.lstrip().startswith('UPDATE') for sql, _ in self.conn.cur.calls))
        self.assertEqual(self.conn.commits, 0)
        self.assertEqual(self.conn.rollbacks, 1)
        self.assertTrue(self.conn.closed)

    def test_received_timestamp_marks_shortage_final(self):
        self.match['matchedBatch']['lines'][0].update(receivedAt='2026-10-18', status='Частично')
        self.data['actualLines'] = self.data['actualLines'][1:]
        self.confirm()
        self.assertEqual([call.args[0] for call in self.deps['receive_delivery'].call_args_list], [32])

    def test_overreceipt_rolls_back_prior_line(self):
        self.data['actualLines'][1]['receivedQuantity'] = '10.0001'
        self.assert_rejected(400)
        self.assertEqual(self.conn.pending, [])
        self.assertEqual(self.conn.rollbacks, 1)
        self.assertFalse(any(event[0] == 'callback' for event in self.conn.events))

    def test_second_writer_failure_rolls_back_entire_batch(self):
        def fail_second(delivery_id, payload, **kwargs):
            result = self.receive(delivery_id, payload, **kwargs)
            if delivery_id == 32:
                raise HTTPException(409, 'ledger failure')
            return result
        self.deps['receive_delivery'].side_effect = fail_second
        self.assert_rejected(409)
        self.assertEqual(self.conn.pending, [])
        self.assertEqual(self.conn.rollbacks, 1)
        self.assertTrue(self.conn.cur.closed)
        self.assertTrue(self.conn.closed)
        self.assertFalse(any(event[0] == 'callback' for event in self.conn.events))

    def test_all_writes_commit_once_before_callbacks(self):
        result = self.confirm()
        self.assertEqual(result['warehouseInvoiceIds'], [131, 132])
        self.assertFalse(result['alreadyReceived'])
        self.assertEqual(self.conn.commits, 1)
        commit_index = self.conn.events.index(('commit',))
        for i in (31, 32):
            self.assertLess(self.conn.events.index(('receive', i)), commit_index)
            self.assertGreater(self.conn.events.index(('callback', i)), commit_index)
        self.assertEqual(len(self.conn.persisted), 4)
        self.assertTrue(self.conn.cur.closed)
        self.assertTrue(self.conn.closed)

    def test_full_canonical_original_urls_persisted_on_each_invoice(self):
        self.data['originalUrls'] = ['/untrusted-client-value']
        self.confirm()
        updates = [params for sql, params in self.conn.cur.calls if sql.lstrip().startswith('UPDATE')]
        self.assertEqual(len(updates), 2)
        for params, delivery_id in zip(updates, (31, 32)):
            self.assertEqual(json.loads(params[0]), self.match['originalUrls'])
            self.assertEqual(params[1:], (2, delivery_id + 100, 2, delivery_id))
        for call in self.deps['receive_delivery'].call_args_list:
            self.assertEqual(call.args[1]['photoUrl'], self.match['originalUrls'][0])
            self.assertEqual(call.kwargs['x_company_id'], '2')

    def test_matched_batch_change_while_locking_rejected(self):
        changed = copy.deepcopy(self.match)
        changed['matchedBatch']['id'] = 5
        self.resolver.side_effect = [self.match, changed]
        self.assert_rejected(409)
        self.deps['receive_delivery'].assert_not_called()

    def test_resolver_runs_after_stock_lock_and_again_after_batch_lock(self):
        def resolve(*args):
            self.conn.events.append(('resolve',))
            return self.match
        self.resolver.side_effect = resolve
        self.confirm()
        events = self.conn.events
        resolves = [i for i, event in enumerate(events) if event[0] == 'resolve']
        advisory = next(i for i, event in enumerate(events) if event[0] == 'sql' and 'pg_advisory_xact_lock' in event[1])
        self.assertLess(events.index(('stock_lock',)), resolves[0])
        self.assertLess(resolves[0], advisory)
        self.assertLess(advisory, resolves[1])
        self.assertLess(resolves[1], events.index(('receive', 31)))

    def test_swallowed_writer_rollback_cannot_commit(self):
        def swallowed(delivery_id, payload, **kwargs):
            self.conn.pending.append(('receipt', delivery_id))
            kwargs['connection'].rollback()
            return {'ok': True, 'invoiceId': 131}
        self.deps['receive_delivery'].side_effect = swallowed
        self.assert_rejected(409)
        self.assertEqual(self.conn.pending, [])
        self.assertEqual(self.deps['receive_delivery'].call_count, 1)

    def test_original_url_update_missing_row_rolls_back(self):
        self.conn.cur.rowcount = 0
        self.assert_rejected(409)
        self.assertEqual(self.conn.pending, [])
        self.assertEqual(self.deps['receive_delivery'].call_count, 1)


class ReceiptTransactionTests(unittest.TestCase):
    def test_commit_close_suppressed_and_cursor_forwarded(self):
        conn = Connection()
        transaction = ReceiptTransaction(conn)
        self.assertIs(transaction.cursor(), conn.cur)
        transaction.commit()
        transaction.close()
        self.assertEqual(conn.commits, 0)
        self.assertFalse(conn.closed)

    def test_rollback_marks_failed_and_forbids_later_commit(self):
        conn = Connection()
        transaction = ReceiptTransaction(conn)
        conn.pending.append(('receipt', 1))
        transaction.rollback()
        self.assertTrue(transaction.failed)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.pending, [])
        with self.assertRaises(RuntimeError):
            transaction.commit()
        self.assertEqual(conn.commits, 0)

    def test_rollback_failure_still_marks_transaction_failed(self):
        conn = Connection()
        conn.rollback = Mock(side_effect=RuntimeError('connection lost'))
        transaction = ReceiptTransaction(conn)
        with self.assertRaises(RuntimeError):
            transaction.rollback()
        self.assertTrue(transaction.failed)
        with self.assertRaises(RuntimeError):
            transaction.commit()
        self.assertEqual(conn.commits, 0)

    def test_autocommit_cannot_be_enabled(self):
        conn = Connection()
        conn.autocommit = False
        transaction = ReceiptTransaction(conn)
        transaction.autocommit = False
        self.assertFalse(transaction.autocommit)
        with self.assertRaises(RuntimeError):
            transaction.autocommit = True
        self.assertFalse(conn.autocommit)


if __name__ == '__main__':
    unittest.main()
