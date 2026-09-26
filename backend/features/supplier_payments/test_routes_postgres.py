"""Opt-in real HTTP, authentication, financial access, resolver and engine.

Only a fresh explicit supply_chain_test_* Unix-socket database. Router is mounted
by this fixture, never by main. No production flag or shared database changes.
"""
import ast
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from . import test_policy_postgres as policy_tests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PaymentHTTPTests(unittest.TestCase):
    sql = policy_tests.PolicyPostgresTests.sql
    create_offer = policy_tests.PolicyPostgresTests.create_offer
    check_contract = policy_tests.PolicyPostgresTests.check_contract
    change_snapshot = policy_tests.PolicyPostgresTests.change_snapshot
    api = policy_tests.PolicyPostgresTests.api
    snapshot = policy_tests.PolicyPostgresTests.snapshot
    body = policy_tests.PolicyPostgresTests.body

    @classmethod
    def setUpClass(cls):
        policy_tests.PolicyPostgresTests.setUpClass.__func__(cls)
        for name in ('0046_supplier_payment_attachments.py', '0047_supplier_payment_packages.py',
                     '0048_supplier_payment_cancellations.py'):
            path = Path(__file__).resolve().parents[3] / 'migrations/versions' / name
            tree = ast.parse(path.read_text())
            conn = cls.main.get_db()
            try:
                conn.autocommit = False
                with conn, conn.cursor() as cur:
                    namespace = {'op': SimpleNamespace(execute=cur.execute), '__file__': str(path)}
                    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))],
                                            type_ignores=[]), str(path), 'exec'), namespace)
                    namespace['upgrade']()
            finally:
                conn.close()
        from .access import build_payment_access
        from .documents import build_document_resolver
        from .routes import register_supplier_payment_routes
        access_deps = dict(resolve_resource_company_actor=cls.main.resolve_resource_company_actor,
            finance_roles=cls.main.FINANCE_ROLES, platform_staff_roles=cls.main.PLATFORM_STAFF_ROLES,
            client_account_roles=cls.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=cls.main.require_project_access, has_package_access=cls.main.has_package_access)
        register_supplier_payment_routes(cls.main.app, dict(get_db=cls.main.get_db,
            get_current_user=cls.main.get_current_user,
            resolve_documents=build_document_resolver(build_payment_access(access_deps)),
            authorize_read=build_payment_access(access_deps, operation='read')))

    def setUp(self):
        policy_tests.PolicyPostgresTests.setUp(self)
        self.flag = patch.dict(os.environ, {'SUPPLIER_PAYMENTS_ENABLED': '1'})
        self.flag.start()
        self.addCleanup(self.flag.stop)
        self.path = '/companies/2/supplier-payments'

    def call(self, method='GET', path=None, body=None, expected=200, actor='accountant', company=2):
        return self.api(actor, method, path or self.path, body, expected=expected,
                        **{'X-Company-Id': str(company), 'X-Company-Mode': 'company'})

    def doc(self, kind='invoice', document_id=None, **kwargs):
        return self.call(path=f'/companies/2/supplier-payment-documents/{kind}/{document_id or self.invoice}', **kwargs)

    def test_default_off_all_routes_leave_database_unchanged(self):
        before = self.snapshot()
        with patch.dict(os.environ, {'SUPPLIER_PAYMENTS_ENABLED': '0'}):
            self.call(expected=404)
            self.call('POST', body=self.body(), expected=404)
            self.call('POST', path=self.path + '/cancel-request', body=self.body(), expected=404)
            self.doc(expected=404)
        self.assertEqual(self.snapshot(), before)

    def test_cancel_exact_attempt_replay_and_late_original_never_write_financial_rows(self):
        body = self.body()
        before = self.snapshot()
        result = self.call('POST', path=self.path + '/cancel-request', body=body)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual({key: result[key] for key in ('companyId', 'requestId', 'documentKind', 'documentId', 'kind')},
                         dict(companyId=2, requestId=body['requestId'], documentKind='invoice', documentId=self.invoice, kind='payment'))
        self.assertIn('cancelledAt', result)
        self.assertNotIn('fingerprint', result)
        self.assertEqual(self.call('POST', path=self.path + '/cancel-request', body=body), result)
        late = self.call('POST', body=body, expected=409)
        self.assertEqual(late['detail']['code'], 'request_cancelled')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_request_cancellations WHERE company_id=2 AND request_id=%s',
                                  (body['requestId'],)), [(1,)])

    def test_cancel_confirmed_payment_and_reversal_return_saved_result_with_identity(self):
        payment = self.body()
        paid = self.call('POST', body=payment)
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=paid['operationId'])
        reversed_result = self.call('POST', body=reversal)
        before = self.snapshot()
        for body, original in ((payment, paid), (reversal, reversed_result)):
            result = self.call('POST', path=self.path + '/cancel-request', body=body)
            self.assertEqual(result['status'], 'confirmed')
            self.assertEqual(result['result'], {key: original[key] for key in ('operationId', 'projectPaymentId', 'kind', 'amount')})
            self.assertEqual({key: result[key] for key in ('companyId', 'requestId', 'documentKind', 'documentId', 'kind')},
                             {key: original[key] for key in ('companyId', 'requestId', 'documentKind', 'documentId', 'kind')})
            self.assertEqual(result['result']['amount'], '10.00')
            self.assertNotIn('fingerprint', result['result'])
            self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_request_cancellations WHERE company_id=2 AND request_id=%s',
                                      (body['requestId'],)), [(0,)])
        self.assertEqual(self.snapshot(), before)

    def test_cancel_current_write_authority_precedes_uuid_conflict(self):
        body = self.body()
        self.call('POST', path=self.path + '/cancel-request', body=body)
        conflicting = {**body, 'amount': '11.00'}
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        try:
            self.call('POST', path=self.path + '/cancel-request', body=conflicting, expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))
        conflict = self.call('POST', path=self.path + '/cancel-request', body=conflicting, expected=409)
        self.assertEqual(conflict['detail']['code'], 'request_id_conflict')

    def test_cancel_requires_0020_while_existing_reads_and_payment_still_work(self):
        self.sql('ALTER TABLE supplier_payment_request_cancellations RENAME TO synthetic_cancellations_unavailable')
        try:
            before = self.snapshot()
            body = self.body()
            self.call('POST', path=self.path + '/cancel-request', body=body, expected=503)
            self.assertEqual(self.snapshot(), before)
            self.doc()
            self.call(path=self.path + '?requestId=' + body['requestId'])
            self.call('POST', body=body)
        finally:
            self.sql('ALTER TABLE synthetic_cancellations_unavailable RENAME TO supplier_payment_request_cancellations')

    def test_cancel_requires_immutable_tombstone_guards_and_auth_before_readiness(self):
        self.sql('ALTER TABLE supplier_payment_request_cancellations DISABLE TRIGGER supplier_payment_cancellation_immutable')
        try:
            body = self.body()
            before = self.snapshot()
            self.call('POST', path=self.path + '/cancel-request', body=body, actor='stranger', expected=403)
            self.call('POST', path=self.path + '/cancel-request', body=body, expected=503)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('ALTER TABLE supplier_payment_request_cancellations ENABLE TRIGGER supplier_payment_cancellation_immutable')

    def test_cancel_late_database_failure_rolls_back_tombstone_with_generic_503(self):
        self.sql('''CREATE FUNCTION synthetic_cancel_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'PRIVATE_CANCELLATION_FAILURE'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_cancel_failure AFTER INSERT ON supplier_payment_request_cancellations
            FOR EACH ROW EXECUTE FUNCTION synthetic_cancel_failure()''')
        body = self.body()
        try:
            before = self.snapshot()
            result = self.call('POST', path=self.path + '/cancel-request', body=body, expected=503)
            self.assertNotIn('PRIVATE_CANCELLATION_FAILURE', str(result))
            self.assertEqual(result['detail']['code'], 'cancellation_unconfirmed')
            self.assertIn('UUID', result['detail']['message'])
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_payment_request_cancellations WHERE company_id=2 AND request_id=%s',
                                      (body['requestId'],)), [(0,)])
        finally:
            self.sql('DROP TRIGGER synthetic_cancel_failure ON supplier_payment_request_cancellations')
            self.sql('DROP FUNCTION synthetic_cancel_failure()')
        self.assertEqual(self.call('POST', path=self.path + '/cancel-request', body=body)['status'], 'cancelled')

    def test_schema_missing_0019_fails_reads_and_writes_without_runtime_ddl(self):
        self.sql('ALTER FUNCTION supplier_payment_warehouse_package(text) RENAME TO synthetic_package_unavailable')
        try:
            before = self.snapshot()
            self.call(expected=503)
            self.doc(expected=503)
            self.call('POST', body=self.body(), expected=503)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('ALTER FUNCTION synthetic_package_unavailable(text) RENAME TO supplier_payment_warehouse_package')

    def test_payment_echo_replay_reversal_and_read_projection(self):
        body = self.body()
        first = self.call('POST', body=body)
        self.assertEqual({key: first[key] for key in ('companyId', 'requestId', 'documentKind', 'documentId')},
                         dict(companyId=2, requestId=body['requestId'], documentKind='invoice', documentId=self.invoice))
        self.assertEqual(self.call('POST', body=body), first)
        second = self.call('POST', body=self.body())
        self.assertNotEqual(first['operationId'], second['operationId'])
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=first['operationId'])
        result = self.call('POST', body=reversal)
        self.assertEqual(result['amount'], '10.00')
        self.assertEqual(self.call('POST', body=reversal), result)
        before = self.snapshot()
        doc = self.doc()
        self.assertEqual((doc['paidAmount'], doc['remainingAmount'], doc['openingPaidAmount']), ('10.00', '190.00', '0.00'))
        history = self.call(path=self.path + f'?documentKind=invoice&documentId={self.invoice}')
        self.assertEqual([r['operationId'] for r in history['items']], [result['operationId'], second['operationId'], first['operationId']])
        self.assertEqual(history['items'][0]['signedAmount'], '-10.00')
        self.assertEqual(history['items'][-1]['reversedById'], result['operationId'])
        self.assertEqual(self.snapshot(), before)

    def test_history_stable_cursor_equal_instalments_and_scope_filters(self):
        older = self.call('POST', body=self.body())
        newer = self.call('POST', body=self.body())
        query = f'?documentKind=invoice&documentId={self.invoice}&limit=1'
        first = self.call(path=self.path + query)
        self.assertTrue(first['hasMore'])
        self.assertEqual(first['nextCursor'], newer['operationId'])
        self.call('POST', body=self.body())
        second = self.call(path=self.path + query + f"&beforeId={first['nextCursor']}")
        self.assertEqual([row['operationId'] for row in second['items']], [older['operationId']])
        self.assertFalse(second['hasMore'])
        self.assertIsNone(second['nextCursor'])
        self.assertEqual(self.call(path=self.path + query + '&supplierId=2147483647')['items'], [])

    def test_uuid_lookup_after_conflict_is_authoritative_and_scoped(self):
        body = self.body()
        result = self.call('POST', body=body)
        self.call('POST', body={**body, 'amount': '11.00'}, expected=409)
        found = self.call(path=self.path + '?requestId=' + body['requestId'])
        self.assertEqual(found['lookup'], dict(requestId=body['requestId'], status='found'))
        self.assertEqual(found['items'][0]['operationId'], result['operationId'])
        absent_id = str(uuid4())
        absent = self.call(path=self.path + '?requestId=' + absent_id)
        self.assertEqual(absent['lookup'], dict(requestId=absent_id, status='not_found'))
        self.assertEqual(absent['items'], [])
        self.call(path=self.path + '?requestId=' + absent_id, actor='stranger', expected=403)

    def test_unregistered_read_does_not_register_or_invent_opening(self):
        self.sql('UPDATE supplier_invoices SET paid_amount=20 WHERE id=%s', (self.invoice,))
        before = self.snapshot()
        result = self.doc()
        self.assertFalse(result['registered'])
        self.assertIsNone(result['openingPaidAmount'])
        self.assertEqual(result['paidAmount'], '20.00')
        self.assertEqual(self.snapshot(), before)

    def test_revoked_membership_blocks_reads_and_replay(self):
        body = self.body()
        self.call('POST', body=body)
        try:
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
            before = self.snapshot()
            self.call('POST', body=body, expected=403)
            self.doc(expected=403)
            self.call(expected=403)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))

    def test_readonly_subscription_can_read_but_not_pay(self):
        original = self.sql('SELECT plan,trial_until,plan_expires_at,payment_status FROM companies WHERE id=2')[0]
        try:
            self.sql("UPDATE companies SET plan='standard',trial_until=NULL,plan_expires_at='2000-01-01',payment_status='expired' WHERE id=2")
            self.doc()
            self.call(path=self.path + f'?documentKind=invoice&documentId={self.invoice}')
            self.call('POST', body=self.body(), expected=403)
        finally:
            self.sql('UPDATE companies SET plan=%s,trial_until=%s,plan_expires_at=%s,payment_status=%s WHERE id=2', original)

    def test_foreign_root_and_matching_header_do_not_grant_access(self):
        self.sql('UPDATE supplier_invoices SET company_id=3 WHERE id=%s', (self.invoice,))
        self.doc(expected=404)
        self.call('POST', body=self.body(), expected=404)
        self.call(path='/companies/3/supplier-payments', company=3, expected=403)

    def test_attached_mirror_uses_invoice_opening_and_one_history(self):
        from .attachments import attach_receipt
        from .access import build_payment_access
        from .documents import build_document_resolver
        self.sql('UPDATE supplier_invoices SET paid_amount=20 WHERE id=%s', (self.invoice,))
        original = self.call('POST', body=self.body())
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status,supplier_invoice_id)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,30,'Принято','Частично оплачена',%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, self.invoice))
        # Fixture-only admission callback: this test exercises the real immutable
        # attachment engine/SQL, not a runtime receipt authorization claim.
        access_deps = dict(resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access, has_package_access=self.main.has_package_access)
        resolver = build_document_resolver(build_payment_access(access_deps))
        def resolve(cur, actor, company, command):
            return resolver(cur, actor, company, dict(documentKind='invoice', documentId=command['documentId']))
        attachment_id = str(uuid4())
        attach_receipt(self.main.get_db, resolve, self.actor, 2,
            dict(requestId=attachment_id, invoiceId=self.invoice, warehouseId=warehouse, reason='Synthetic full receipt'),
            validate_new=lambda *args: None)
        before = self.snapshot()
        result = self.doc('warehouse', warehouse)
        self.assertTrue(result['isMirror'])
        self.assertEqual(result['canonicalTarget'], dict(documentKind='invoice', documentId=self.invoice))
        self.assertEqual((result['paidAmount'], result['openingPaidAmount']), ('30.00', '20.00'))
        page = self.call(path=self.path + f'?documentKind=warehouse&documentId={warehouse}')
        self.assertEqual([row['operationId'] for row in page['items']], [original['operationId']])
        lookup = self.call(path=self.path + '?requestId=' + attachment_id)
        self.assertEqual(lookup['lookup']['status'], 'used_for_attachment')
        self.assertEqual(self.snapshot(), before)

    def test_current_payer_membership_is_required_for_reads_and_replay(self):
        from psycopg2.extras import RealDictCursor
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
            self.cur.execute('SELECT id FROM supplier_contract_versions WHERE offer_id=%s ORDER BY version DESC LIMIT 1', (self.offer_id,))
            self.contract_id = self.cur.fetchone()['id']
            self.cur.execute('UPDATE supplier_deal_parties SET payer_company_id=3 WHERE offer_id=%s AND version=1', (self.offer_id,))
            self.change_snapshot(lambda snapshot: snapshot['payer'].update(companyId=3))
            self.cur.execute("UPDATE supplier_invoices SET status='Утверждён' WHERE id=%s", (self.invoice_id,))
            conn.commit()
        finally:
            conn.close()
        self.invoice = self.invoice_id
        membership = self.sql('''INSERT INTO user_company_roles(user_id,company_id,role,active,
                assigned_projects,assigned_packages) VALUES(%s,3,'бухгалтер',TRUE,'[]','[]') RETURNING id''', (self.actor,))[0][0]
        try:
            body = self.body()
            self.call('POST', body=body)
            self.doc()
            self.call(path=self.path + '?requestId=' + body['requestId'])
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE id=%s', (membership,))
            self.call('POST', body=body, expected=403)
            self.doc(expected=403)
            self.call(path=self.path + '?requestId=' + body['requestId'], expected=403)
        finally:
            self.sql('DELETE FROM user_company_roles WHERE id=%s', (membership,))
            self.sql('UPDATE supplier_deal_parties SET payer_company_id=2 WHERE offer_id=%s AND version=1', (self.offer_id,))

    def test_uuid_lookup_waits_for_company_writer_commit(self):
        body = self.body()
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(1735289201,2)')
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.call, path=self.path + '?requestId=' + body['requestId'])
                try:
                    waiting = []
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker,))
                        if waiting:
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting)
                    # Commit no operation: a miss is authoritative only after
                    # acquiring the writer's lock, not from its old snapshot.
                    conn.commit()
                    self.assertEqual(pending.result(timeout=4)['lookup']['status'], 'not_found')
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def test_denied_recorded_payer_hides_corruption_in_history_uuid_and_lookahead(self):
        from psycopg2.extras import RealDictCursor
        own_invoice = self.invoice
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            self.cur = conn.cursor(cursor_factory=RealDictCursor)
            self.cur.execute('SELECT id FROM supplier_contract_versions WHERE offer_id=%s ORDER BY version DESC LIMIT 1', (self.offer_id,))
            self.contract_id = self.cur.fetchone()['id']
            self.cur.execute('UPDATE supplier_deal_parties SET payer_company_id=3 WHERE offer_id=%s AND version=1', (self.offer_id,))
            self.change_snapshot(lambda snapshot: snapshot['payer'].update(companyId=3))
            self.cur.execute("UPDATE supplier_invoices SET status='Утверждён' WHERE id=%s", (self.invoice_id,))
            conn.commit()
        finally:
            conn.close()
        membership = self.sql('''INSERT INTO user_company_roles(user_id,company_id,role,active,
            assigned_projects,assigned_packages) VALUES(%s,3,'бухгалтер',TRUE,'[]','[]') RETURNING id''', (self.actor,))[0][0]
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status,supplier_invoice_id)
            SELECT company_id,supplier_id,project_name,json_build_array(json_build_object('workPackage',work_package))::text,
                   amount,0,'Принято','К оплате',id FROM supplier_invoices WHERE id=%s RETURNING id''', (self.invoice_id,))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, self.invoice_id))
        original_items = self.sql('SELECT items FROM warehouse_invoices WHERE id=%s', (warehouse,))[0][0]
        try:
            warehouse_body = self.body()
            warehouse_body.update(documentKind='warehouse', documentId=warehouse)
            self.call('POST', body=warehouse_body)
            invoice_body = self.body()
            invoice_body['documentId'] = self.invoice_id
            self.call('POST', body=invoice_body)
            newest = self.call('POST', body=self.body())
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE id=%s', (membership,))
            self.sql("UPDATE warehouse_invoices SET items='not json' WHERE id=%s", (warehouse,))
            # The newer, otherwise authorized row is also corrupt: all recorded
            # scopes (including lookahead) must be checked before any conflicts.
            self.sql('UPDATE supplier_invoices SET company_id=3 WHERE id=%s', (own_invoice,))
            for physical_company in (2, 3):
                self.sql('UPDATE warehouse_invoices SET company_id=%s WHERE id=%s', (physical_company, warehouse))
                before = self.snapshot()
                for query in ('?requestId=' + warehouse_body['requestId'],
                              '?requestId=' + invoice_body['requestId'],
                              f'?documentKind=warehouse&documentId={warehouse}',
                              f'?limit=1&beforeId={newest["operationId"] + 1}'):
                    with self.subTest(physical_company=physical_company, query=query):
                        self.call(path=self.path + query, expected=403)
                self.assertEqual(self.snapshot(), before)
            self.sql('UPDATE warehouse_invoices SET company_id=2 WHERE id=%s', (warehouse,))
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE id=%s', (membership,))
            # Once the recorded payer is authorized the same malformed package
            # is a domain conflict, not a generic database/service error.
            self.call(path=self.path + '?requestId=' + warehouse_body['requestId'], expected=409)
        finally:
            self.sql('UPDATE warehouse_invoices SET company_id=2,items=%s WHERE id=%s', (original_items, warehouse))
            self.sql('UPDATE supplier_invoices SET company_id=2 WHERE id=%s', (own_invoice,))
            self.sql('DELETE FROM user_company_roles WHERE id=%s', (membership,))
            self.sql('UPDATE supplier_deal_parties SET payer_company_id=2 WHERE offer_id=%s AND version=1', (self.offer_id,))

    def test_authorized_malformed_package_is_409_and_savepoint_recovers_transaction(self):
        from fastapi import HTTPException
        from psycopg2.extras import RealDictCursor
        from .reads import history
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,0,'Принято','К оплате') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]
        body = self.body()
        body.update(documentKind='warehouse', documentId=warehouse)
        self.call('POST', body=body)
        self.sql("UPDATE warehouse_invoices SET items='not json' WHERE id=%s", (warehouse,))
        before = self.snapshot()
        self.call(path=self.path + '?requestId=' + body['requestId'], expected=409)
        self.assertEqual(self.snapshot(), before)
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT pg_advisory_xact_lock(1735289201,2)')
                # HTTP case above uses real financial authority. Here isolate
                # the SQL helper's savepoint contract inside the same read txn.
                with self.assertRaises(HTTPException) as error:
                    history(cur, dict(authorize_read=lambda *args, **kwargs: None), self.actor, 2,
                            limit=1, request_id=body['requestId'])
                self.assertEqual(error.exception.status_code, 409)
                cur.execute('SELECT 1 AS usable')
                self.assertEqual(cur.fetchone()['usable'], 1)
        finally:
            conn.rollback()
            conn.close()
            self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s', ('[{"workPackage":""}]', warehouse))

    def test_uuid_lookup_observes_real_payment_after_wait_not_false_absence(self):
        from .policy import validate_new_payment
        entered, release = Event(), Event()
        blocker = []
        body = self.body()

        def pause_policy(cur, context, command, amount):
            validate_new_payment(cur, context, command, amount)
            cur.execute('SELECT pg_backend_pid() AS pid')
            blocker.append(cur.fetchone()['pid'])
            entered.set()
            if not release.wait(4):
                raise AssertionError('Test failed to release payment transaction')

        with patch('backend.features.supplier_payments.routes.validate_new_payment', side_effect=pause_policy), \
                ThreadPoolExecutor(max_workers=2) as pool:
            payment = pool.submit(self.call, 'POST', body=body)
            try:
                self.assertTrue(entered.wait(3))
                lookup = pool.submit(self.call, path=self.path + '?requestId=' + body['requestId'])
                waiting = []
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker[0],))
                    if waiting:
                        break
                    time.sleep(.01)
                self.assertTrue(waiting)
                release.set()
                result = payment.result(timeout=4)
                page = lookup.result(timeout=4)
                self.assertEqual(page['lookup']['status'], 'found')
                self.assertEqual(page['items'][0]['operationId'], result['operationId'])
            finally:
                release.set()

    def test_revocation_during_company_wait_denies_read(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(1735289201,2)')
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.doc, expected=403)
                try:
                    waiting = []
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker,))
                        if waiting:
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting)
                    cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
                    conn.commit()
                    pending.result(timeout=4)
                finally:
                    conn.rollback()
        finally:
            conn.close()
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))

    def test_late_database_failure_rolls_back_and_returns_generic_503(self):
        self.sql('''CREATE FUNCTION synthetic_http_payment_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic private database error'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_http_payment_failure BEFORE UPDATE ON supplier_invoices
                    FOR EACH ROW EXECUTE FUNCTION synthetic_http_payment_failure()''')
        try:
            before = self.snapshot()
            body = self.body()
            error = self.call('POST', body=body, expected=503)
            self.assertNotIn('Synthetic private', str(error))
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.call(path=self.path + '?requestId=' + body['requestId'])['lookup']['status'], 'not_found')
        finally:
            self.sql('DROP TRIGGER synthetic_http_payment_failure ON supplier_invoices')
            self.sql('DROP FUNCTION synthetic_http_payment_failure()')

    def test_nonempty_warehouse_package_is_preserved_in_http_and_history(self):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status)
            VALUES(2,%s,%s,'[{"workPackage":"Основная"}]',200,0,'Принято','К оплате') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]
        body = self.body()
        body.update(documentKind='warehouse', documentId=warehouse)
        result = self.call('POST', body=body)
        self.assertEqual(result['documentKind'], 'warehouse')
        doc = self.doc('warehouse', warehouse)
        self.assertEqual(doc['scope']['workPackage'], 'Основная')
        self.assertEqual(doc['paidAmount'], '10.00')
        page = self.call(path=self.path + f'?documentKind=warehouse&documentId={warehouse}')
        self.assertEqual(page['items'][0]['workPackage'], 'Основная')
