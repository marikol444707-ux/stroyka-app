"""Run: explicit SUPPLY_CHAIN_* socket settings + python -m unittest this module."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from threading import Barrier
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from fastapi import HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor

from .test_postgres_support import Fixture, MovementModel, migration


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Explicit isolated PostgreSQL opt-in required')
class PostgresTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.client = self.enterContext(TestClient(self.fixture.app)) if hasattr(self, 'enterContext') else TestClient(self.fixture.app)
        self.addCleanup(self.client.close)

    def issue(self, quantity='4', **updates):
        data = dict(companyId=2, requestId=str(uuid4()), reason='Synthetic issue',
                    rows=[dict(lotId=1, projectId=1, quantity=quantity)])
        data.update(updates)
        return data

    def return_body(self, quantity='1'):
        return dict(companyId=2, requestId=str(uuid4()), reason='Operator attests physical return', quantity=quantity)

    def stock(self):
        return self.fixture.query('''SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1''')[0]['available_quantity']

    def assert_clean(self):
        self.assertEqual(self.stock(), Decimal(10))
        for table in ('warehouse_distribution_operations', 'warehouse_distribution_allocations',
                      'warehouse_distribution_returns', 'warehouse_lot_movements', 'warehouse_movements', 'warehouse_history', 'materials'):
            self.assertEqual(self.fixture.query(f'SELECT count(*) AS n FROM {table}')[0]['n'], 0, table)

    def test_sixteen_competing_commands_conserve_stock_and_replays(self):
        commands = [self.issue('0.25') for _ in range(16)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda body: self.client.post('/warehouse-distributions', json=body), commands))
        for body, response in zip(commands, responses):
            self.assertIn(response.status_code, (200, 409), response.text)
            # Retry the original identity, including commands whose reply arrived.
            retry = self.client.post('/warehouse-distributions', json=body)
            self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(self.stock(), Decimal(6))
        self.assertEqual(self.fixture.query('SELECT quantity FROM warehouse_main WHERE company_id=2')[0]['quantity'], 6)
        self.assertEqual(self.fixture.query('SELECT quantity FROM materials WHERE company_id=2')[0]['quantity'], 4)
        self.assertEqual(self.fixture.query('SELECT count(*) AS n FROM warehouse_distribution_operations')[0]['n'], 16)

    def test_stale_snapshot_cannot_downgrade_committed_distribution(self):
        conn = self.fixture.get_db()
        conn.set_session(isolation_level='REPEATABLE READ')
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM warehouse_distribution_operations')
                self.assertEqual(cur.fetchone()[0], 0)
                response = self.client.post('/warehouse-distributions', json=self.issue())
                self.assertEqual(response.status_code, 200, response.text)
                with self.assertRaisesRegex(psycopg2.Error, 'READ COMMITTED'):
                    migration(cur, 'downgrade')
        finally:
            conn.rollback()
            conn.close()
        self.assertEqual(self.stock(), Decimal(6))

    def test_issue_return_replay_and_reissue(self):
        data = self.issue()
        first = self.client.post('/warehouse-distributions', json=data)
        self.assertEqual(first.status_code, 200, first.text)
        result = first.json()
        allocation_id = result['items'][0]['id']
        self.assertEqual(result['items'][0]['workPackage'], 'Synthetic package')
        self.assertEqual(self.stock(), Decimal(6))
        self.assertEqual(self.client.post('/warehouse-distributions', json=data).json(), result)
        self.assertEqual(self.stock(), Decimal(6))
        self.assertEqual(self.client.post('/warehouse-distributions', json={**data, 'reason': 'different'}).status_code, 409)
        returned = self.return_body('4')
        path = f'/warehouse-distributions/{allocation_id}/returns'
        response = self.client.post(path, json=returned)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['item']['netQuantity'], '0')
        self.assertEqual(self.client.post(path, json=returned).json(), response.json())
        self.assertEqual(self.stock(), Decimal(10))
        self.assertEqual(self.client.post(path, json=self.return_body()).status_code, 409)
        reissued = self.client.post('/warehouse-distributions', json=self.issue('10'))
        self.assertEqual(reissued.status_code, 200, reissued.text)
        self.assertEqual(self.stock(), Decimal(0))
        movements = self.fixture.query('SELECT source_invoice_id,source_invoice_line_index FROM warehouse_movements')
        self.assertTrue(all(r['source_invoice_id'] == 1 and r['source_invoice_line_index'] == 0 for r in movements))
        self.assertEqual(len(self.fixture.query('SELECT * FROM warehouse_history WHERE source_invoice_id=1')), 6)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_returns')[0]['n'], 1)
        self.assertEqual(self.fixture.query('SELECT items,payment_status FROM warehouse_invoices WHERE id=1')[0],
                         dict(items=[dict(name='Cement', quantity=10, unit='кг')], payment_status='Не оплачено'))

    def test_batch_failure_rolls_back_helper_and_journals(self):
        self.fixture.fail_on_call = 2
        data = self.issue(rows=[dict(lotId=1, projectId=1, quantity='2'), dict(lotId=1, projectId=2, quantity='3')])
        self.assertEqual(self.client.post('/warehouse-distributions', json=data).status_code, 409)
        self.assert_clean()

    def test_authorization_before_replay(self):
        data = self.issue()
        self.assertEqual(self.client.post('/warehouse-distributions', json=data).status_code, 200)
        for role in ('accountant', 'foreman', 'supplier'):
            self.assertEqual(self.client.post('/warehouse-distributions', json=data, headers={'X-Test-Role': role}).status_code, 403)
        self.assertEqual(self.client.get('/warehouse-distributions', headers={'X-Test-Role': 'foreman'}).status_code, 403)
        self.assertEqual(self.client.get('/warehouse-distributions', headers={'X-Test-Role': 'accountant'}).status_code, 200)
        self.assertEqual(self.client.get('/warehouse-distributions', headers={'X-Company-Mode': 'all_companies'}).status_code, 400)

    def test_tenant_missing_lot_duplicate_project_and_source_evidence(self):
        for row in (dict(lotId=2, projectId=1, quantity='1'), dict(lotId=999, projectId=1, quantity='1'),
                    dict(lotId=1, projectId=3, quantity='1')):
            self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue(rows=[row])).status_code, 404)
        self.fixture.query("INSERT INTO projects(id,company_id,name) VALUES(4,2,'Alpha')")
        self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue()).status_code, 409)
        self.fixture.query('DELETE FROM projects WHERE id=4')
        self.fixture.query("UPDATE warehouse_invoices SET items='[]' WHERE id=1")
        self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue()).status_code, 409)
        self.assert_clean()

    def test_duplicate_aggregate_rejected_and_lot_overdraw_rejected(self):
        self.fixture.query("INSERT INTO warehouse_main(company_id,name,unit,quantity) VALUES(2,'CEMENT','кг.',3)")
        self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue()).status_code, 409)
        self.fixture.query('DELETE FROM warehouse_main WHERE id>2')
        data = self.issue(rows=[dict(lotId=1, projectId=1, quantity='6'), dict(lotId=1, projectId=2, quantity='6')])
        self.assertEqual(self.client.post('/warehouse-distributions', json=data).status_code, 409)
        self.assert_clean()

    def test_return_checks_current_stock_and_is_atomic(self):
        result = self.client.post('/warehouse-distributions', json=self.issue()).json()
        allocation_id = result['items'][0]['id']
        self.fixture.query('UPDATE materials SET quantity=0 WHERE company_id=2')
        response = self.client.post(f'/warehouse-distributions/{allocation_id}/returns', json=self.return_body())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.stock(), Decimal(6))
        self.assertEqual(self.fixture.query('SELECT returned_quantity FROM warehouse_distribution_allocations')[0]['returned_quantity'], 0)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_operations')[0]['n'], 1)

    def test_concurrent_same_request_and_competing_issue(self):
        data = self.issue('7')
        def post(body):
            with TestClient(self.fixture.app) as client:
                return client.post('/warehouse-distributions', json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(post, [data, data]))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(self.stock(), Decimal(3))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(post, [self.issue('2'), self.issue('2')]))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        self.assertEqual(self.stock(), Decimal(1))

    def test_guards_remain_when_feature_disabled_and_downgrade_refuses_data(self):
        result = self.client.post('/warehouse-distributions', json=self.issue()).json()
        os.environ['WAREHOUSE_DISTRIBUTION_ENABLED'] = '0'
        for statement in ("UPDATE projects SET name='renamed' WHERE id=1",
                          "UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=1",
                          "UPDATE warehouse_invoices SET supplier_name='Other' WHERE id=1",
                          "UPDATE materials SET name='Other' WHERE company_id=2",
                          "UPDATE warehouse_main SET unit='шт' WHERE company_id=2",
                          'DELETE FROM warehouse_distribution_allocations'):
            with self.subTest(statement=statement), self.assertRaises(psycopg2.Error):
                self.fixture.query(statement)
        self.fixture.query("UPDATE warehouse_invoices SET payment_status='Оплачено' WHERE id=1")
        conn = self.fixture.get_db()
        try:
            with self.assertRaises(psycopg2.Error), conn, conn.cursor() as cur:
                migration(cur, 'downgrade')
        finally:
            conn.close()
        self.assertEqual(self.client.get('/warehouse-distributions').status_code, 404)
        self.assertEqual(result['items'][0]['netQuantity'], '4')

    def test_sources_and_report_are_scoped_and_report_is_not_on_hand(self):
        self.assertEqual(len(self.client.get('/warehouse-distributions/sources').json()['items']), 1)
        self.client.post('/warehouse-distributions', json=self.issue())
        self.fixture.query('UPDATE materials SET quantity=0 WHERE company_id=2')
        report = self.client.get('/warehouse-distributions').json()
        self.assertEqual(report['items'][0]['netQuantity'], '4')
        self.assertEqual(report['items'][0]['returns'], [])
        other = self.client.get('/warehouse-distributions', headers={'X-Test-Company': '3'}).json()
        self.assertEqual(other['items'], [])

    def test_incoming_stock_identity_collision_is_guarded(self):
        self.client.post('/warehouse-distributions', json=self.issue())
        self.fixture.query("INSERT INTO warehouse_main(company_id,name,unit,quantity) VALUES(2,'Other','кг',1)")
        with self.assertRaises(psycopg2.Error):
            self.fixture.query("UPDATE warehouse_main SET name='Cement' WHERE name='Other'")

    def test_new_duplicate_project_name_is_guarded(self):
        self.client.post('/warehouse-distributions', json=self.issue())
        with self.assertRaises(psycopg2.Error):
            self.fixture.query("INSERT INTO projects(id,company_id,name) VALUES(4,2,'Alpha')")

    def test_normalized_duplicate_keys_and_source_limit(self):
        self.fixture.query("UPDATE warehouse_receipt_lots SET unit='м²',document_unit='м²' WHERE id=1")
        self.fixture.query("UPDATE warehouse_invoices SET items='[{\"name\":\"Cement\",\"quantity\":10,\"unit\":\"м²\"}]' WHERE id=1")
        self.fixture.query("UPDATE warehouse_main SET unit='м²' WHERE company_id=2")
        self.fixture.query("INSERT INTO warehouse_main(company_id,name,unit,quantity) VALUES(2,'Cement','м2',1)")
        self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue()).status_code, 409)
        self.assertEqual(self.fixture.calls, 0)  # Rejected before the real movement helper.
        self.fixture.query('''INSERT INTO warehouse_receipt_lots(company_id,warehouse_location,warehouse_target,
            warehouse_invoice_id,invoice_line_index,material_name,document_quantity,document_unit,
            received_quantity,unit,available_quantity)
            SELECT 2,'Основной склад','main',1,n,'Cement',1,'кг',1,'кг',1 FROM generate_series(1,201) n''')
        sources = self.client.get('/warehouse-distributions/sources').json()
        self.assertEqual(len(sources['items']), 200)
        self.assertEqual(sources['max'], 200)
        self.assertTrue(sources['truncated'])

    def test_deadlock_rolls_back_and_same_uuid_can_retry(self):
        original = self.fixture.helper
        def fail(cur, model, company_id, actor):
            original(cur, model, company_id, actor)
            cur.execute("DO $$ BEGIN RAISE EXCEPTION 'Synthetic deadlock' USING ERRCODE='40P01'; END $$")
        self.fixture.helper = fail
        data = self.issue()
        response = self.client.post('/warehouse-distributions', json=data)
        self.assertEqual(response.status_code, 409)
        self.assertIn('requestId', response.json()['detail'])
        self.assert_clean()
        self.fixture.helper = original
        self.assertEqual(self.client.post('/warehouse-distributions', json=data).status_code, 200)

    def test_concurrent_returns_capped_and_history_immutable(self):
        allocation_id = self.client.post('/warehouse-distributions', json=self.issue()).json()['items'][0]['id']
        path = f'/warehouse-distributions/{allocation_id}/returns'
        def post(body):
            with TestClient(self.fixture.app) as client:
                return client.post(path, json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(post, [self.return_body('3'), self.return_body('3')]))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        self.assertEqual(self.stock(), Decimal(9))
        for statement in ('DELETE FROM warehouse_distribution_returns',
                          "UPDATE warehouse_distribution_returns SET reason='rewrite'",
                          'UPDATE warehouse_distribution_allocations SET quantity=9'):
            with self.assertRaises(psycopg2.Error):
                self.fixture.query(statement)

    def test_empty_downgrade_preserves_source_tables(self):
        conn = self.fixture.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, 'downgrade')
        finally:
            conn.close()
        self.assertEqual(self.stock(), Decimal(10))

    def test_real_cancellation_guard_outstanding_and_after_full_return(self):
        from backend.features.material_traceability.guards import close_receipt_lots_for_cancellation
        allocation_id = self.client.post('/warehouse-distributions', json=self.issue()).json()['items'][0]['id']
        def close_lots():
            conn = self.fixture.get_db()
            try:
                with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SELECT id FROM warehouse_invoices WHERE id=1 AND company_id=2 FOR UPDATE')
                    with patch('backend.features.material_traceability.guards._has_lots', return_value=True):
                        close_receipt_lots_for_cancellation(cur, 2, 1)
            finally:
                conn.close()
        with self.assertRaises(HTTPException) as error:
            close_lots()
        self.assertEqual(error.exception.status_code, 409)
        response = self.client.post(f'/warehouse-distributions/{allocation_id}/returns', json=self.return_body('4'))
        self.assertEqual(response.status_code, 200, response.text)
        close_lots()
        self.assertEqual(self.fixture.query('SELECT status FROM warehouse_receipt_lots WHERE id=1')[0]['status'], 'cancelled')
        self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue()).status_code, 409)

    def test_real_legacy_source_helper_can_reissue_after_return(self):
        allocation_id = self.client.post('/warehouse-distributions', json=self.issue('10')).json()['items'][0]['id']
        response = self.client.post(f'/warehouse-distributions/{allocation_id}/returns', json=self.return_body('10'))
        self.assertEqual(response.status_code, 200, response.text)
        model = MovementModel(materialName='Cement', fromLocation='Основной склад', toLocation='Alpha',
                              quantity=10, unit='кг', workPackage='Synthetic package', date='2026-09-16',
                              createdBy='Synthetic legacy actor', notes='Legacy reissue', invoiceId=1, invoiceLineIndex=0)
        conn = self.fixture.get_db()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                result = self.fixture.helper(cur, model, 2, dict(name='Synthetic legacy actor'))
                self.assertEqual(result['sourceInvoiceId'], 1)
        finally:
            conn.close()
        self.assertEqual(self.stock(), Decimal(0))

    def test_fractional_issue_and_return_exact_projection(self):
        self.fixture.query('UPDATE warehouse_main SET quantity=0.3 WHERE company_id=2')
        first = self.client.post('/warehouse-distributions', json=self.issue('0.1'))
        second = self.client.post('/warehouse-distributions', json=self.issue('0.2'))
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        for response, quantity in ((first, '0.1'), (second, '0.2')):
            allocation_id = response.json()['items'][0]['id']
            returned = self.client.post(f'/warehouse-distributions/{allocation_id}/returns', json=self.return_body(quantity))
            self.assertEqual(returned.status_code, 200, returned.text)
        self.assertEqual(self.fixture.query('SELECT quantity FROM warehouse_main WHERE company_id=2')[0]['quantity'], 0.3)
        self.assertEqual(self.fixture.query('SELECT quantity FROM materials WHERE company_id=2')[0]['quantity'], 0.0)

    def test_legacy_excess_precision_is_not_silently_rounded(self):
        self.fixture.query('UPDATE warehouse_main SET quantity=0.19999999999999998 WHERE company_id=2')
        self.assertEqual(self.client.post('/warehouse-distributions', json=self.issue('0.1')).status_code, 409)
        self.assertEqual(self.stock(), Decimal(10))

    def test_legacy_and_distribution_writers_share_lock_order(self):
        from backend.features.material_traceability.guards import lock_distribution_compatible_stock
        barrier = Barrier(2)
        class SchemaProbeCursor:
            # Fixture schema is non-public; only override the presence probe.
            def __init__(self, cur):
                self.cur = cur
            def execute(self, statement, args=()):
                if "to_regclass('public.warehouse_distribution_operations')" in statement:
                    return self.cur.execute('SELECT TRUE AS present')
                return self.cur.execute(statement, args)
            def fetchone(self):
                return self.cur.fetchone()
        def legacy():
            conn = self.fixture.get_db()
            try:
                barrier.wait(timeout=10)
                with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    lock_distribution_compatible_stock(SchemaProbeCursor(cur))
                    model = MovementModel(materialName='Cement', fromLocation='Основной склад', toLocation='Alpha',
                        quantity=6, unit='кг', workPackage='Synthetic package', date='2026-09-16',
                        createdBy='Synthetic legacy actor', notes='Concurrent legacy', invoiceId=1, invoiceLineIndex=0)
                    self.fixture.helper(cur, model, 2, dict(name='Synthetic legacy actor'))
                return 200
            except HTTPException as error:
                return error.status_code
            finally:
                conn.close()
        def distribution():
            barrier.wait(timeout=10)
            with TestClient(self.fixture.app) as client:
                return client.post('/warehouse-distributions', json=self.issue('6')).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(legacy), pool.submit(distribution)
            statuses = sorted((a.result(timeout=20), b.result(timeout=20)))
        self.assertIn(statuses, ([200, 400], [200, 409]))
        self.assertEqual(self.stock(), Decimal(4))
        self.assertEqual(self.fixture.query('SELECT sum(quantity) AS n FROM warehouse_movements')[0]['n'], 6)

    def test_projection_verifies_database_round_trip(self):
        self.fixture.query('''CREATE FUNCTION synthetic_round_stock() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN NEW.quantity=round(NEW.quantity::numeric,1)::double precision; RETURN NEW; END $$''')
        self.fixture.query('''CREATE TRIGGER synthetic_round_stock BEFORE UPDATE ON warehouse_main
            FOR EACH ROW EXECUTE FUNCTION synthetic_round_stock()''')
        response = self.client.post('/warehouse-distributions', json=self.issue('0.15'))
        self.assertEqual(response.status_code, 409)
        self.assert_clean()

    def test_concurrent_cancellation_preauth_rollback_before_ddl_protocol(self):
        """Real two-session lock protocol, not the full authenticated cancel route."""
        from backend.features.material_traceability.guards import lock_distribution_compatible_stock
        barrier = Barrier(2)
        class SchemaProbeCursor:
            def __init__(self, cur):
                self.cur = cur
            def execute(self, statement, args=()):
                if "to_regclass('public.warehouse_distribution_operations')" in statement:
                    return self.cur.execute('SELECT TRUE AS present')
                return self.cur.execute(statement, args)
            def fetchone(self):
                return self.cur.fetchone()
        def cancellation_protocol():
            conn = self.fixture.get_db()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SELECT id FROM warehouse_invoices WHERE company_id=2 AND id=1')
                    self.assertEqual(cur.fetchone()['id'], 1)
                    # Release preliminary ACCESS SHARE before the coarse lock and
                    # lazy legacy ALTER; otherwise a second cancel can form a cycle.
                    conn.rollback()
                    barrier.wait(timeout=10)
                    lock_distribution_compatible_stock(SchemaProbeCursor(cur))
                    cur.execute('''ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS
                        distribution_cancel_protocol_test integer''')
                    cur.execute('SELECT id FROM warehouse_invoices WHERE company_id=2 AND id=1 FOR UPDATE')
                    result = cur.fetchone()['id']
                    conn.commit()
                    return result
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(cancellation_protocol), pool.submit(cancellation_protocol)
            self.assertEqual([first.result(timeout=20), second.result(timeout=20)], [1, 1])
        self.assert_clean()
