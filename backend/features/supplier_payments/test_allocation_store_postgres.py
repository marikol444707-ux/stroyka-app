"""Allocation service contracts and opt-in isolated PostgreSQL regressions.

No runtime registration or production authorization claim. The transaction
service must call the supplied current-write resolver before replay or CAS.
"""
import importlib
import inspect
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import unittest
from uuid import uuid4

import psycopg2
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from . import test_contract_context_postgres as contract_tests
from .test_cancellations_postgres import migration


class AllocationStoreContractTests(unittest.TestCase):
    def test_wrapper_and_caller_owned_worker_have_explicit_authorization_boundary(self):
        module = importlib.import_module('backend.features.supplier_payments.allocation_store')
        self.assertEqual(list(inspect.signature(module.replace_allocations).parameters),
                         ['get_db', 'authorize_and_lock', 'actor_id', 'company_id', 'body'])
        self.assertEqual(list(inspect.signature(module.replace_allocations_in_transaction).parameters),
                         ['cur', 'authorize_and_lock', 'actor_id', 'company_id', 'body'])
        self.assertEqual(list(inspect.signature(module.read_allocations_in_transaction).parameters),
                         ['cur', 'authorize_and_lock', 'actor_id', 'company_id', 'group_id'])


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AllocationStorePostgresTests(unittest.TestCase):
    sql = contract_tests.ContractContextTests.sql
    api = contract_tests.ContractContextTests.api
    create_offer = contract_tests.ContractContextTests.create_offer
    check_contract = contract_tests.ContractContextTests.check_contract

    @classmethod
    def setUpClass(cls):
        # Requires a NEW explicit supply_chain_test_* DB owned by chain_test;
        # the shared builder rejects a nonempty DB and nonlocal connections.
        contract_tests.ContractContextTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                for name in ('0045_supplier_payment_ledger.py', '0046_supplier_payment_attachments.py',
                             '0047_supplier_payment_packages.py', '0048_supplier_payment_cancellations.py',
                             '0049_supplier_payment_allocations.py'):
                    migration(cur, name)
        finally:
            conn.close()

    def setUp(self):
        from .access import build_payment_access
        from .documents import build_document_resolver
        self.actor = self.fixture['users']['accountant']['id']
        self.invoice = self.sql('''INSERT INTO supplier_invoices
            (company_id,offer_id,request_id,supplier_id,project_name,work_package,amount,
             paid_amount,status,contract_version_id)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,200,
                   0,'Утверждён',contract_version_id FROM supplier_invoices WHERE id=%s RETURNING id''',
            (type(self).invoice_id,))[0][0]
        access = build_payment_access(dict(
            resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access, has_package_access=self.main.has_package_access))
        self.payment_resolver = build_document_resolver(access)
        self.payment = self.pay('60.00')['operationId']
        self.second_payment = self.pay('30.00')['operationId']
        self.group = self.sql('''INSERT INTO supplier_payment_allocation_groups(company_id,invoice_record_id)
            SELECT company_id,id FROM supplier_payment_documents
            WHERE company_id=2 AND document_kind='invoice' AND document_id=%s RETURNING id''', (self.invoice,))[0][0]
        # Deliberately offset physical warehouse IDs from relation IDs.
        self.sql('INSERT INTO warehouse_invoices(company_id) VALUES(2)')
        self.receipts = [self.seed_receipt('60.00'), self.seed_receipt('80.00')]

    def seed_receipt(self, amount):
        delivery = self.sql('''INSERT INTO supply_deliveries
            (company_id,offer_id,request_id,supplier_id,project,work_package,contract_version_id,
             source_supplier_invoice_id,status,quality_status,received_at,received_quantity,
             shipped_quantity,planned_quantity,price_per_unit,material_name,unit)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,contract_version_id,
                   id,'Принято','Принято',NOW(),1,1,1,%s,'Synthetic receipt','шт'
            FROM supplier_invoices WHERE id=%s RETURNING id''', (amount, self.invoice))[0][0]
        warehouse = self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,total_vat,paid_amount,status,
             supply_delivery_id,source_type,source_id,supply_request_id)
            SELECT company_id,supplier_id,project_name,
                   json_build_array(json_build_object('workPackage',work_package,'quantity',1,
                       'price',%s::numeric,'name','Synthetic receipt','unit','шт'))::text,
                   %s,%s,0,0,'Принята',%s,'supply_delivery',%s,request_id
            FROM supplier_invoices WHERE id=%s RETURNING id''',
            (amount, amount, amount, delivery, str(delivery), self.invoice))[0][0]
        relation = self.sql('''INSERT INTO supplier_payment_receipt_relations
            (company_id,group_id,warehouse_invoice_id,amount,provenance)
            VALUES(2,%s,%s,%s,NULL) RETURNING id''', (self.group, warehouse, amount))[0][0]
        return dict(id=relation, warehouse=warehouse, delivery=delivery)

    def synthetic_current_group_authorizer(self, cur, actor_id, company_id, command):
        """TEST ONLY: current membership-backed denial, not runtime scope policy.

        One known fixture group with identical owner/payer/project/package. Every
        relation is checked, including receipts omitted from the proposed map.
        No authorization is inferred from submitted allocation rows.
        """
        if actor_id != self.actor or company_id != 2 or command.get('groupId') != self.group:
            raise HTTPException(403, 'Synthetic allocation scope denied')
        cur.execute('''SELECT u.id FROM users u JOIN user_company_roles m ON m.user_id=u.id
            WHERE u.id=%s AND u.active=TRUE AND m.company_id=%s AND m.active=TRUE
              AND m.role='бухгалтер' FOR SHARE OF u,m''', (actor_id, company_id))
        if not cur.fetchone():
            raise HTTPException(403, 'Synthetic current financial membership denied')
        cur.execute('''SELECT r.id,w.company_id,w.supplier_id,w.project FROM supplier_payment_receipt_relations r
            JOIN warehouse_invoices w ON w.id=r.warehouse_invoice_id
            WHERE r.group_id=%s AND r.company_id=%s ORDER BY r.id FOR SHARE OF w''', (self.group, company_id))
        rows = cur.fetchall()
        if ({row['id'] for row in rows} != {row['id'] for row in self.receipts}
                or any(row['company_id'] != 2 or row['supplier_id'] != self.fixture['supplierId']
                       or row['project'] != self.fixture['project'] for row in rows)):
            raise HTTPException(403, 'Synthetic receipt scope denied')

    def pay(self, amount=None, *, reverses=None, resolver=None, get_db=None):
        from .engine import execute
        from .policy import validate_new_payment
        body = dict(requestId=str(uuid4()), documentKind='invoice', documentId=self.invoice,
                    kind='payment', paidAt='2026-09-18', reason='Synthetic allocation fixture payment')
        if reverses is None:
            body['amount'] = amount
        else:
            body.update(kind='reversal', reversesId=reverses)
        return execute(get_db or self.main.get_db, resolver or self.payment_resolver, self.actor, 2, body,
                       validate_new=validate_new_payment)

    def body(self, *, version=0, rows=None):
        return dict(requestId=str(uuid4()), groupId=self.group, expectedVersion=version,
                    reason='Synthetic complete allocation map', rows=rows if rows is not None else [
                        dict(paymentId=self.payment, receiptId=self.receipts[0]['id'], amount='40.00')])

    def replace(self, body):
        from .allocation_store import replace_allocations
        return replace_allocations(self.main.get_db, self.synthetic_current_group_authorizer,
                                   self.actor, 2, body)

    def read(self):
        from .allocation_store import read_allocations_in_transaction
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                return read_allocations_in_transaction(cur, self.synthetic_current_group_authorizer,
                                                       self.actor, 2, self.group)
        finally:
            conn.rollback()
            conn.close()

    def snapshot(self, *, allocations=False):
        tables = ('supplier_payment_allocation_revisions', 'supplier_payment_allocation_rows') if allocations else (
            'supplier_invoices', 'warehouse_invoices', 'supply_deliveries', 'materials', 'project_payments',
            'supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts',
            'supplier_payment_attachments', 'supplier_payment_request_cancellations',
            'supplier_payment_allocation_groups', 'supplier_payment_receipt_relations')
        return {table: self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text') for table in tables}

    def assert_conflict(self, body):
        with self.assertRaises(HTTPException) as error:
            self.replace(body)
        self.assertEqual(error.exception.status_code, 409)

    def test_save_and_correction_keep_immutable_history_without_financial_writes(self):
        before = self.snapshot()
        original = self.body()
        first = self.replace(original)
        self.assertEqual(first, dict(revisionId=first['revisionId'], groupId=self.group,
                                     version=1, requestId=original['requestId']))
        correction = self.body(version=1, rows=[
            dict(paymentId=self.payment, receiptId=self.receipts[1]['id'], amount='50.00'),
            dict(paymentId=self.second_payment, receiptId=self.receipts[0]['id'], amount='20.00')])
        second = self.replace(correction)
        self.assertEqual((second['version'], second['groupId']), (2, self.group))
        self.assertEqual(self.sql('''SELECT version,previous_revision_id,row_count
            FROM supplier_payment_allocation_revisions WHERE group_id=%s ORDER BY version''', (self.group,)),
            [(1, None, 1), (2, first['revisionId'], 2)])
        self.assertEqual(self.sql('SELECT amount FROM supplier_payment_allocation_rows WHERE revision_id=%s',
                                 (first['revisionId'],)), [(40,)])
        projection = self.read()
        self.assertEqual(projection['allocations'], correction['rows'])
        self.assertEqual(projection['reversedAllocations'], [])
        self.assertEqual((projection['groupId'], projection['version'], projection['allocated'],
                          projection['paid'], projection['unallocatedPayments']), (self.group, 2, '70.00', '90.00', '20.00'))
        self.assertEqual({row['receiptId'] for row in projection['receipts']}, {row['id'] for row in self.receipts})
        self.assertNotEqual({row['id'] for row in self.receipts}, {row['warehouse'] for row in self.receipts})
        self.assertEqual(self.snapshot(), before)

    def test_empty_map_clears_designations_not_money(self):
        self.replace(self.body())
        before = self.snapshot()
        cleared = self.replace(self.body(version=1, rows=[]))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_allocation_rows WHERE revision_id=%s',
                                 (cleared['revisionId'],)), [(0,)])
        projection = self.read()
        self.assertEqual(projection['allocations'], [])
        self.assertEqual(projection['reversedAllocations'], [])
        self.assertEqual((projection['version'], projection['allocated'], projection['paid'],
                          projection['unallocatedPayments']), (2, '0.00', '90.00', '90.00'))
        self.assertEqual(self.snapshot(), before)

    def test_replay_returns_original_receipt_after_later_version_but_new_stale_uuid_conflicts(self):
        original = self.body()
        saved = self.replace(original)
        self.replace(self.body(version=1, rows=[]))
        before = self.snapshot(allocations=True)
        self.assertEqual(self.replace(original), saved)
        self.assert_conflict({**original, 'requestId': str(uuid4())})
        self.assertEqual(self.snapshot(allocations=True), before)

    def test_same_uuid_changed_payload_conflicts_without_changes(self):
        original = self.body()
        self.replace(original)
        before = self.snapshot(allocations=True)
        for change in (dict(reason='Changed reason'), dict(expectedVersion=1), dict(rows=[])):
            with self.subTest(change=change):
                self.assert_conflict({**original, **change})
        self.assertEqual(self.snapshot(allocations=True), before)

    def test_synthetic_current_membership_revocation_denies_replay_read_and_stale_cas(self):
        original = self.body()
        self.replace(original)
        before = self.snapshot(allocations=True)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        try:
            for action in (lambda: self.replace(original), self.read,
                           lambda: self.replace(self.body()),
                           lambda: self.replace({**original, 'reason': 'Changed payload'})):
                with self.assertRaises(HTTPException) as error:
                    action()
                self.assertEqual(error.exception.status_code, 403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))
        self.assertEqual(self.snapshot(allocations=True), before)

    def test_two_cas_writers_exactly_one_wins(self):
        before = self.snapshot()
        gate = Barrier(2)
        def write(body):
            gate.wait(timeout=5)
            try:
                return self.replace(body)
            except HTTPException as error:
                return error.status_code
        commands = [self.body(), self.body(rows=[])]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, commands))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual([result for result in results if isinstance(result, int)], [409])
        self.assertEqual(self.sql('SELECT version FROM supplier_payment_allocation_revisions WHERE group_id=%s',
                                 (self.group,)), [(1,)])
        self.assertEqual(self.snapshot(), before)

    def ordered_allocation_race(self, first_kind, second_kind):
        """Two real writer connections; a read-only observer proves lock waiting.

        Pause only the leader's injected authorization callback, after the real
        service has acquired its company lock. No engine/store implementation is
        patched. All events, lock waits, statements and future waits are bounded.
        """
        from .allocation_store import replace_allocations
        entered, release = Event(), Event()
        leader_pids = []
        body = self.body()

        def get_db():
            conn = self.main.get_db()
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SET lock_timeout='3s'")
                cur.execute("SET statement_timeout='8s'")
            conn.autocommit = False
            return conn

        def run(kind, pause=False):
            resolve = self.synthetic_current_group_authorizer if kind == 'allocation' else self.payment_resolver
            def authorize(cur, actor_id, company_id, command):
                context = resolve(cur, actor_id, company_id, command)
                if pause:
                    cur.execute('SELECT pg_backend_pid() AS pid')
                    leader_pids.append(cur.fetchone()['pid'])
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError('Timed out releasing race leader')
                return context
            if kind == 'allocation':
                return replace_allocations(get_db, authorize, self.actor, 2, body)
            return self.pay(reverses=self.payment, resolver=authorize, get_db=get_db)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, first_kind, True)
            try:
                self.assertTrue(entered.wait(4), 'Leader did not reach company-locked authorization')
                second = pool.submit(run, second_kind)
                waiting = []
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    waiting = self.sql('''SELECT pid FROM pg_stat_activity
                        WHERE datname=current_database() AND wait_event='advisory'
                          AND %s=ANY(pg_blocking_pids(pid))''', (leader_pids[0],))
                    if waiting:
                        break
                    time.sleep(.01)
                self.assertEqual(len(waiting), 1, 'Follower must wait on the leader company advisory lock')
                self.assertNotEqual(waiting[0][0], leader_pids[0])
                self.assertFalse(second.done(), 'Follower completed before leader commit')
            finally:
                release.set()
            first_result = first.result(timeout=5)
            try:
                second_result = second.result(timeout=5)
            except HTTPException as error:
                second_result = error
        return body, first_result, second_result

    def test_allocation_first_then_waiting_reversal_preserves_history_but_zeroes_coverage(self):
        body, saved, reversal = self.ordered_allocation_race('allocation', 'reversal')
        self.assertEqual((saved['version'], reversal['kind']), (1, 'reversal'))
        self.assertEqual(self.sql('''SELECT payment_operation_id,receipt_relation_id,amount
            FROM supplier_payment_allocation_rows WHERE revision_id=%s''', (saved['revisionId'],)),
            [(self.payment, self.receipts[0]['id'], 40)])
        projection = self.read()
        self.assertEqual((projection['version'], projection['paid'], projection['allocated']), (1, '30.00', '0.00'))
        self.assertEqual(projection['allocations'], [])
        self.assertEqual(projection['reversedAllocations'], body['rows'])
        self.assertEqual(self.replace(body), saved)

    def test_reversal_first_then_waiting_new_allocation_rejects_without_revision(self):
        _, reversal, rejected = self.ordered_allocation_race('reversal', 'allocation')
        self.assertEqual(reversal['kind'], 'reversal')
        self.assertIsInstance(rejected, HTTPException)
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_allocation_revisions WHERE group_id=%s',
                                 (self.group,)), [(0,)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_allocation_rows WHERE group_id=%s',
                                 (self.group,)), [(0,)])
        projection = self.read()
        self.assertEqual((projection['version'], projection['paid'], projection['allocated']), (0, '30.00', '0.00'))
        self.assertEqual((projection['allocations'], projection['reversedAllocations']), ([], []))

    def test_waiting_same_uuid_exact_replay_returns_one_version_and_two_equal_results(self):
        before = self.snapshot()
        body, first, replay = self.ordered_allocation_race('allocation', 'allocation')
        self.assertEqual(first, replay)
        self.assertEqual(first['requestId'], body['requestId'])
        self.assertEqual(self.sql('SELECT version,row_count FROM supplier_payment_allocation_revisions WHERE group_id=%s',
                                 (self.group,)), [(1, 1)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_allocation_rows WHERE group_id=%s',
                                 (self.group,)), [(1,)])
        self.assertEqual(self.snapshot(), before)

    def test_deferred_commit_failure_rolls_back_header_rows_and_never_writes_finances(self):
        self.sql('''CREATE FUNCTION synthetic_allocation_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic deferred allocation failure'; END $$''')
        self.sql('''CREATE CONSTRAINT TRIGGER synthetic_allocation_commit_failure
            AFTER INSERT ON supplier_payment_allocation_revisions DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION synthetic_allocation_commit_failure()''')
        before, before_allocations = self.snapshot(), self.snapshot(allocations=True)
        body = self.body()
        try:
            with self.assertRaises(psycopg2.Error):
                self.replace(body)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.snapshot(allocations=True), before_allocations)
        finally:
            self.sql('DROP TRIGGER synthetic_allocation_commit_failure ON supplier_payment_allocation_revisions')
            self.sql('DROP FUNCTION synthetic_allocation_commit_failure()')
        self.assertEqual(self.replace(body)['version'], 1)

    def test_caller_owned_worker_does_not_commit_or_close_and_rollback_removes_complete_revision(self):
        from .allocation_store import replace_allocations_in_transaction
        before = self.snapshot()
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                saved = replace_allocations_in_transaction(cur, self.synthetic_current_group_authorizer,
                                                          self.actor, 2, self.body())
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
                cur.execute('SELECT row_count FROM supplier_payment_allocation_revisions WHERE id=%s', (saved['revisionId'],))
                self.assertEqual(cur.fetchone()['row_count'], 1)
                self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_allocation_revisions WHERE id=%s',
                                         (saved['revisionId'],)), [(0,)])
                conn.rollback()
                cur.execute('SELECT COUNT(*) AS n FROM supplier_payment_allocation_revisions WHERE id=%s', (saved['revisionId'],))
                self.assertEqual(cur.fetchone()['n'], 0)
        finally:
            conn.rollback()
            conn.close()
        self.assertEqual(self.snapshot(), before)

    def test_live_reversal_invalidates_coverage_without_rewriting_history_or_reassigning(self):
        original = self.body(rows=[dict(paymentId=self.payment, receiptId=self.receipts[0]['id'], amount='60.00')])
        saved = self.replace(original)
        history = self.snapshot(allocations=True)
        self.pay(reverses=self.payment)
        before = self.snapshot()
        projection = self.read()
        self.assertEqual(projection['allocations'], [])
        self.assertEqual(projection['reversedAllocations'], original['rows'])
        self.assertEqual((projection['version'], projection['paid'], projection['allocated'],
                          projection['unallocatedPayments']), (1, '30.00', '0.00', '30.00'))
        self.assertTrue(all(row['allocated'] == '0.00' for row in projection['receipts']))
        self.assertEqual(self.snapshot(allocations=True), history)
        self.assertEqual(self.replace(original), saved)
        self.assert_conflict(self.body(version=1, rows=original['rows']))
        self.assertEqual(self.snapshot(allocations=True), history)
        replacement = self.body(version=1, rows=[dict(paymentId=self.second_payment,
            receiptId=self.receipts[1]['id'], amount='30.00')])
        self.assertEqual(self.replace(replacement)['version'], 2)
        corrected = self.read()
        self.assertEqual(corrected['allocated'], '30.00')
        self.assertEqual(corrected['allocations'], replacement['rows'])
        self.assertEqual(corrected['reversedAllocations'], [])
        self.assertEqual(self.snapshot(), before)

    def test_server_loaded_capacities_and_receipt_membership_reject_invalid_maps(self):
        before, history = self.snapshot(), self.snapshot(allocations=True)
        invalid_maps = [
            [dict(paymentId=self.payment, receiptId=self.receipts[1]['id'], amount='60.01')],
            [dict(paymentId=self.payment, receiptId=self.receipts[0]['id'], amount='60.00'),
             dict(paymentId=self.second_payment, receiptId=self.receipts[0]['id'], amount='0.01')],
            [dict(paymentId=self.payment, receiptId=self.receipts[0]['id'] + 10000, amount='1.00')],
        ]
        for rows in invalid_maps:
            with self.subTest(rows=rows):
                self.assert_conflict(self.body(rows=rows))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.snapshot(allocations=True), history)

    def test_workers_require_explicit_read_committed_transaction_before_authorization(self):
        from .allocation_store import replace_allocations_in_transaction, read_allocations_in_transaction
        from unittest.mock import Mock
        conn = self.main.get_db()
        try:
            for worker in (lambda cur, auth: replace_allocations_in_transaction(cur, auth, self.actor, 2, self.body()),
                           lambda cur, auth: read_allocations_in_transaction(cur, auth, self.actor, 2, self.group)):
                conn.autocommit = True
                auth = Mock(side_effect=AssertionError('Invalid transaction must fail before authority'))
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    with self.assertRaises(RuntimeError):
                        worker(cur, auth)
                conn.autocommit = False
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                    with self.assertRaises(HTTPException) as error:
                        worker(cur, auth)
                    self.assertEqual(error.exception.status_code, 409)
                conn.rollback()
                auth.assert_not_called()
        finally:
            conn.rollback()
            conn.close()
