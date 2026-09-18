"""Synthetic, dedicated empty PostgreSQL only; transit never calls supplier writers."""
import ast
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import psycopg2
from fastapi import HTTPException
from fastapi.testclient import TestClient
from .test_postgres_support import Fixture
from . import transfers


def migrate_transfers(cur, action='upgrade'):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/0026_distribution_transfers.py'
    tree = ast.parse(path.read_text())
    namespace = {'op': SimpleNamespace(execute=cur.execute)}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)],
                            type_ignores=[]), str(path), 'exec'), namespace)
    namespace[action]()


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Dedicated PostgreSQL opt-in required')
class TransitPostgresTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        conn = self.fixture.get_db()
        with conn, conn.cursor() as cur:
            migrate_transfers(cur)
        conn.close()
        os.environ['WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED'] = '1'
        self.client = TestClient(self.fixture.app)
        self.addCleanup(self.client.close)

    def body(self, **values):
        return dict(companyId=2, requestId=str(uuid4()), reason='Operator attestation', **values)

    def post(self, path, body, status=200, headers=None):
        response = self.client.post('/warehouse-distributions'+path, json=body, headers=headers or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def issue(self, qty='6'):
        return self.post('', self.body(rows=[dict(lotId=1, projectId=1, quantity=qty)]))['items'][0]

    def dispatch(self, allocation, qty='4'):
        return self.post('/transfers', self.body(allocationId=allocation['id'], toProjectId=2, quantity=qty))['item']

    def receive(self, transfer, qty='2', expected='2', status=200):
        return self.post('/transfers/'+str(transfer['id'])+'/receipts',
                         self.body(quantity=qty, expectedQuantity=expected), status)

    def balances(self):
        return self.fixture.query('SELECT project,quantity FROM materials WHERE company_id=2 ORDER BY project')

    def test_stale_snapshot_cannot_downgrade_committed_transfer(self):
        allocation = self.issue()
        conn = self.fixture.get_db()
        conn.set_session(isolation_level='REPEATABLE READ')
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM warehouse_distribution_transfers')
                self.assertEqual(cur.fetchone()[0], 0)
                self.dispatch(allocation)
                with self.assertRaisesRegex(psycopg2.Error, 'READ COMMITTED'):
                    migrate_transfers(cur, 'downgrade')
        finally:
            conn.rollback()
            conn.close()
        self.assertEqual(len(self.fixture.query('SELECT id FROM warehouse_distribution_transfers')), 1)

    def test_dispatch_partial_discrepancy_receipt_return_and_redispatch(self):
        documents = self.fixture.query('SELECT * FROM warehouse_invoices ORDER BY id')
        a = self.issue()
        transfer = self.dispatch(a)
        self.assertEqual((transfer['status'], transfer['inTransitQuantity']), ('in_transit','4'))
        self.assertEqual(self.balances(), [dict(project='Alpha', quantity=2)])
        self.post('/'+str(a['id'])+'/returns', self.body(quantity='3'), 409)
        accepted = self.receive(transfer, '2', '3')['item']
        self.assertEqual((accepted['status'], accepted['inTransitQuantity']), ('discrepancy','2'))
        child = accepted['receipts'][0]['allocationId']
        self.assertEqual(accepted['receipts'][0]['discrepancyQuantity'], '1')
        self.post('/'+str(child)+'/returns', self.body(quantity='1'))
        self.post('/transfers', self.body(allocationId=child, toProjectId=1, quantity='1'))
        self.post('/'+str(child)+'/returns', self.body(quantity='0.01'), 409)
        completed = self.receive(transfer)['item']
        self.assertEqual((completed['status'], completed['inTransitQuantity']), ('received','0'))
        self.receive(transfer, '0', '1', 409)
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]['available_quantity'], 5)
        self.assertEqual(self.fixture.query('SELECT * FROM warehouse_invoices ORDER BY id'),documents)

    def test_empty_migration_downgrade_reupgrade_and_missing_schema_fail_closed(self):
        conn = self.fixture.get_db()
        with conn,conn.cursor() as cur:
            migrate_transfers(cur,'downgrade')
        conn.close()
        self.assertEqual(self.client.get('/warehouse-distributions/transfers').status_code,409)
        # Existing 0012-only flows continue to work; no request-time DDL.
        a = self.issue()
        self.post('/'+str(a['id'])+'/returns',self.body(quantity='1'))
        conn = self.fixture.get_db()
        with conn,conn.cursor() as cur:
            migrate_transfers(cur)
        conn.close()
        self.dispatch(a,'1')

    def test_zero_discrepancy_has_no_stock_child_or_journal(self):
        transfer = self.dispatch(self.issue())
        before = self.balances()
        result = self.receive(transfer, '0', '4')['item']
        self.assertEqual((result['receivedQuantity'], result['inTransitQuantity']), ('0','4'))
        self.assertIsNone(result['receipts'][0]['allocationId'])
        self.assertEqual(self.balances(), before)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_allocations')[0]['n'], 1)

    def test_replay_tenant_scope_roles_and_flags(self):
        a = self.issue()
        body = self.body(allocationId=a['id'], toProjectId=2, quantity='2')
        first = self.post('/transfers', body, headers={'X-Test-Role':'storekeeper'})
        self.assertEqual(self.post('/transfers', body), first)
        self.post('/transfers', dict(body, quantity='1'), 409)
        self.post('/transfers', self.body(allocationId=a['id'], toProjectId=3, quantity='1'), 404)
        self.post('/transfers', self.body(allocationId=a['id'], toProjectId=1, quantity='1'), 409)
        path = '/transfers/'+str(first['item']['id'])+'/receipts'
        receipt = self.body(quantity='1', expectedQuantity='1')
        accepted = self.post(path, receipt, headers={'X-Test-Role':'supply'})
        self.assertEqual(self.post(path, receipt), accepted)
        self.post(path, self.body(quantity='1', expectedQuantity='1'), 403, {'X-Test-Role':'accountant'})
        self.post(path, dict(self.body(quantity='1', expectedQuantity='1'),companyId=3), 404, {'X-Test-Company':'3'})
        for q in ('%', "' OR 1=1 --", '_'):
            self.assertEqual(self.client.get('/warehouse-distributions/transfers',params={'q':q}).json()['items'], [])
        self.assertEqual(self.client.get('/warehouse-distributions/transfers',headers={'X-Test-Company':'3'}).json()['items'], [])
        os.environ['WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED'] = '0'
        self.assertEqual(self.client.get('/warehouse-distributions/transfers').status_code,404)
        self.post('/'+str(a['id'])+'/returns', self.body(quantity='5'), 409)

    def test_dispatch_vs_source_return_and_competing_receipts(self):
        a = self.issue('4')
        dispatch = self.body(allocationId=a['id'],toProjectId=2,quantity='4')
        def request(args):
            path, body = args
            with TestClient(self.fixture.app) as client:
                return client.post('/warehouse-distributions'+path,json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(request,[('/transfers',dispatch),('/'+str(a['id'])+'/returns',self.body(quantity='4'))]))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        if results[0].status_code==200:
            t = results[0].json()['item']
        else:
            t = self.dispatch(self.issue('4'),'4')
        path = '/transfers/'+str(t['id'])+'/receipts'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(request,[(path,self.body(quantity='3',expectedQuantity='3')),
                                             (path,self.body(quantity='3',expectedQuantity='3'))]))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertEqual(self.fixture.query('SELECT sum(quantity) q FROM warehouse_distribution_transfer_receipts')[0]['q'],3)

    def test_concurrent_replay_does_not_duplicate(self):
        a = self.issue()
        body = self.body(allocationId=a['id'],toProjectId=2,quantity='4')
        def request(_):
            with TestClient(self.fixture.app) as client:
                return client.post('/warehouse-distributions/transfers',json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(request,range(2)))
        self.assertEqual([r.status_code for r in results],[200,200])
        self.assertEqual(results[0].json(),results[1].json())
        self.assertEqual(self.fixture.query('SELECT transferred_quantity q FROM warehouse_distribution_allocations WHERE id=%s',(a['id'],))[0]['q'],4)

    def test_failed_receipt_rolls_back_stock_event_and_operation(self):
        t = self.dispatch(self.issue())
        before = self.balances()
        count = self.fixture.query('SELECT count(*) n FROM warehouse_distribution_operations')[0]['n']
        with patch.object(transfers.quality,'create_distribution_quality',side_effect=HTTPException(409,'Injected failure')):
            self.receive(t,status=409)
        self.assertEqual(self.balances(),before)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_operations')[0]['n'],count)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_transfer_receipts')[0]['n'],0)

    def test_stock_shortfall_and_dispatch_rollback(self):
        a = self.issue()
        self.fixture.query("UPDATE materials SET quantity=1 WHERE project='Alpha'")
        self.post('/transfers',self.body(allocationId=a['id'],toProjectId=2,quantity='2'),409)
        before = self.balances()
        with patch.object(transfers,'movement_leg',side_effect=HTTPException(409,'Injected after stock delta')):
            self.post('/transfers',self.body(allocationId=a['id'],toProjectId=2,quantity='1'),409)
        self.assertEqual(self.balances(),before)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_transfers')[0]['n'],0)

    def test_immutable_transit_destination_and_receipt_even_flag_off(self):
        t = self.dispatch(self.issue())
        self.receive(t,'0','4')
        os.environ['WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED']='0'
        for sql in ("UPDATE projects SET name='Renamed' WHERE id=2",
                    "UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=1",
                    'DELETE FROM warehouse_distribution_transfers',
                    'UPDATE warehouse_distribution_transfer_receipts SET quantity=1'):
            with self.subTest(sql=sql),self.assertRaises(psycopg2.Error):
                self.fixture.query(sql)
        conn = self.fixture.get_db()
        try:
            with self.assertRaises(psycopg2.Error),conn,conn.cursor() as cur:
                migrate_transfers(cur,'downgrade')
        finally:
            conn.close()

    def test_list_keyset_literal_search_and_accountant_read(self):
        a = self.issue()
        ts = [self.dispatch(a,'1') for _ in range(3)]
        first = self.client.get('/warehouse-distributions/transfers',params=dict(q='Alpha',limit=2),headers={'X-Test-Role':'accountant'}).json()
        second = self.client.get('/warehouse-distributions/transfers',params=dict(q='Alpha',limit=2,beforeId=first['nextCursor'])).json()
        self.assertEqual([t['id'] for t in first['items']+second['items']],[t['id'] for t in reversed(ts)])
        self.assertIsNone(second['nextCursor'])
        self.assertFalse(second['truncated'])
        for params in (dict(limit=201),dict(beforeId=0),dict(q='\x00')):
            self.assertEqual(self.client.get('/warehouse-distributions/transfers',params=params).status_code,422)

    def test_dispatch_snapshots_price_category_and_receipt_preserves_them(self):
        a = self.issue()
        self.fixture.query("UPDATE materials SET price=123.45,category='Captured category' WHERE project='Alpha'")
        t = self.dispatch(a)
        self.fixture.query("UPDATE materials SET price=999,category='Later category' WHERE project='Alpha'")
        self.receive(t,'1','1')
        expected = self.fixture.query("SELECT price,category FROM materials WHERE project='Beta'")[0]
        self.assertEqual(str(expected['price']),'123.45')
        self.assertEqual(expected['category'],'Captured category')
        self.fixture.query("UPDATE materials SET price=321,category='Other' WHERE project='Beta'")
        self.receive(t,'1','1')
        self.assertEqual(self.fixture.query("SELECT price,category FROM materials WHERE project='Beta'")[0],expected)

    def test_reserved_transit_name_rejected_and_protected(self):
        a = self.issue()
        self.fixture.query("UPDATE projects SET name='В пути' WHERE id=2")
        self.post('/transfers',self.body(allocationId=a['id'],toProjectId=2,quantity='1'),409)
        self.fixture.query("UPDATE projects SET name='Beta' WHERE id=2")
        self.dispatch(a)
        with self.assertRaises(psycopg2.Error):
            self.fixture.query("INSERT INTO projects(id,company_id,name) VALUES(9,2,'В пути')")

    def test_unowned_corrupt_chain_blocks_child_return_and_redispatch(self):
        # Deliberately disable quality even in the owned-fixture subclass.
        os.environ['OWNED_DISTRIBUTION_QUALITY_ENABLED']='0'
        t = self.dispatch(self.issue())
        child = self.receive(t)['item']['receipts'][0]['allocationId']
        for column, value in [('quantity',Decimal('3')), ('source_invoice_id',2)]:
            h = self.fixture.query('SELECT history_id FROM warehouse_distribution_transfers WHERE id=%s',(t['id'],))[0]['history_id']
            original = self.fixture.query('SELECT '+column+' FROM warehouse_history WHERE id=%s',(h,))[0][column]
            self.fixture.query('UPDATE warehouse_history SET '+column+'=%s WHERE id=%s',(value,h))
            before = self.balances()
            self.post('/'+str(child)+'/returns',self.body(quantity='1'),409)
            self.post('/transfers',self.body(allocationId=child,toProjectId=1,quantity='1'),409)
            self.assertEqual(self.balances(),before)
            self.fixture.query('UPDATE warehouse_history SET '+column+'=%s WHERE id=%s',(original,h))
        # Parent root movement evidence, not only the immediate transit history.
        root = self.fixture.query('SELECT movement_id FROM warehouse_distribution_allocations WHERE id=%s',
                                  (t['sourceAllocationId'],))[0]['movement_id']
        self.fixture.query('UPDATE warehouse_movements SET source_invoice_id=2 WHERE id=%s',(root,))
        before = self.balances()
        self.post('/'+str(child)+'/returns',self.body(quantity='1'),409)
        self.post('/transfers',self.body(allocationId=child,toProjectId=1,quantity='1'),409)
        self.assertEqual(self.balances(),before)

    def test_unowned_child_root_keys_are_checked_before_return_or_redispatch(self):
        os.environ['OWNED_DISTRIBUTION_QUALITY_ENABLED']='0'
        t = self.dispatch(self.issue())
        child = self.receive(t)['item']['receipts'][0]['allocationId']
        # Simulate historical corruption; restore guard in the same transaction.
        conn = self.fixture.get_db()
        with conn,conn.cursor() as cur:
            cur.execute('ALTER TABLE warehouse_distribution_allocations DISABLE TRIGGER warehouse_distribution_allocations_immutable')
            cur.execute("UPDATE warehouse_distribution_allocations SET receipt_number='Wrong root' WHERE id=%s",(child,))
            cur.execute('ALTER TABLE warehouse_distribution_allocations ENABLE TRIGGER warehouse_distribution_allocations_immutable')
        conn.close()
        before = self.balances()
        self.post('/'+str(child)+'/returns',self.body(quantity='1'),409)
        self.post('/transfers',self.body(allocationId=child,toProjectId=1,quantity='1'),409)
        self.assertEqual(self.balances(),before)

    def test_unowned_return_replay_rechecks_custody(self):
        os.environ['OWNED_DISTRIBUTION_QUALITY_ENABLED']='0'
        t = self.dispatch(self.issue())
        child = self.receive(t)['item']['receipts'][0]['allocationId']
        body = self.body(quantity='1')
        path = '/'+str(child)+'/returns'
        original = self.post(path,body)
        self.assertEqual(self.post(path,body),original)
        self.fixture.query("UPDATE warehouse_history SET quantity=3 WHERE issued_to='В пути' AND project='Alpha'")
        before = self.balances()
        self.post(path,body,409)
        self.assertEqual(self.balances(),before)

    def test_receipt_trigger_rejects_unrelated_root_allocation(self):
        t = self.dispatch(self.issue('4'))
        self.fixture.query('''INSERT INTO warehouse_invoices(id,company_id,number,items)
            VALUES(3,2,'Different root','[{"name":"Cement","quantity":10,"unit":"кг"}]');
            INSERT INTO warehouse_receipt_lots(id,company_id,warehouse_location,warehouse_target,warehouse_invoice_id,
                invoice_line_index,material_name,document_quantity,document_unit,received_quantity,unit,available_quantity)
            VALUES(3,2,'Основной склад','main',3,0,'Cement',10,'кг',10,'кг',10)''')
        candidate = self.post('',self.body(rows=[dict(lotId=3,projectId=2,quantity='1')]))['items'][0]
        operation = self.fixture.query('SELECT operation_id FROM warehouse_distribution_allocations WHERE id=%s',
                                       (candidate['id'],))[0]['operation_id']
        with self.assertRaisesRegex(psycopg2.Error,'Invalid receipt allocation'):
            self.fixture.query('''INSERT INTO warehouse_distribution_transfer_receipts(company_id,transfer_id,
                operation_id,quantity,expected_quantity,allocation_id,reason,created_by)
                VALUES(2,%s,%s,1,1,%s,'Bad child association','Synthetic')''',(t['id'],operation,candidate['id']))

    def test_receipt_trigger_rejects_each_corrupted_child_root_key(self):
        t = self.dispatch(self.issue())
        # Receipt trigger, not quality verification, must reject before finalization.
        for field, value in [('invoice_line_index','99'),('material_name',"'Wrong'"),
                             ('unit',"'Wrong'"),('work_package',"'Wrong'"),('receipt_number',"'Wrong'")]:
            with self.subTest(field=field):
                self.fixture.query(f'''CREATE OR REPLACE FUNCTION test_bad_child() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.movement_snapshot ? 'transferId' THEN NEW.{field}={value}; END IF;
                    RETURN NEW; END $$''')
                self.fixture.query('''CREATE TRIGGER test_bad_child BEFORE INSERT ON warehouse_distribution_allocations
                    FOR EACH ROW EXECUTE FUNCTION test_bad_child()''')
                before = self.balances()
                self.receive(t,'1','1',409)
                self.assertEqual(self.balances(),before)
                self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_transfer_receipts')[0]['n'],0)
                self.fixture.query('DROP TRIGGER test_bad_child ON warehouse_distribution_allocations')

    def test_empty_downgrade_restores_exact_0012_identity_guard(self):
        from .test_postgres_support import migration
        # Compare pg source against the actual 0012 function, without duplicating it in the test.
        conn = self.fixture.get_db()
        with conn,conn.cursor() as cur:
            migrate_transfers(cur,'downgrade')
            cur.execute("SELECT prosrc FROM pg_proc WHERE oid='guard_warehouse_distribution_identity()'::regprocedure")
            restored = cur.fetchone()[0]
            migration(cur,'downgrade')
            migration(cur,'upgrade')
            cur.execute("SELECT prosrc FROM pg_proc WHERE oid='guard_warehouse_distribution_identity()'::regprocedure")
            original = cur.fetchone()[0]
        conn.close()
        self.assertEqual(restored,original)

    def test_receipt_guard_tracks_entitlement_and_transit_until_last_actual_return(self):
        a = self.issue('4')
        t = self.dispatch(a,'4')
        def protected():
            with self.assertRaisesRegex(psycopg2.Error,'Outstanding distribution receipt'):
                self.fixture.query("UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=1")
        protected()  # all in transit, source entitlement zero
        first = self.receive(t,'2','3')['item']['receipts'][0]['allocationId']
        self.post('/'+str(first)+'/returns',self.body(quantity='2'))
        protected()  # first child returned, remaining transfer is still outstanding
        second = self.receive(t,'2','2')['item']['receipts'][-1]['allocationId']
        second_transfer = self.post('/transfers',self.body(allocationId=second,toProjectId=1,quantity='2'))['item']
        protected()  # all ancestors fully forwarded; descendant transfer still in transit
        leaf = self.receive(second_transfer,'2','2')['item']['receipts'][0]['allocationId']
        self.post('/'+str(leaf)+'/returns',self.body(quantity='1'))
        protected()  # no transit, but leaf entitlement remains
        self.post('/'+str(leaf)+'/returns',self.body(quantity='1'))
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]['available_quantity'],10)
        self.fixture.query("UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=1")

    def test_dispatch_and_receipt_replay_after_full_return_and_cancellation(self):
        a = self.issue('2')
        dispatch_body = self.body(allocationId=a['id'],toProjectId=2,quantity='2')
        dispatched = self.post('/transfers',dispatch_body)
        path = '/transfers/'+str(dispatched['item']['id'])+'/receipts'
        receipt_body = self.body(quantity='2',expectedQuantity='2')
        accepted = self.post(path,receipt_body)
        child = accepted['item']['receipts'][0]['allocationId']
        self.post('/'+str(child)+'/returns',self.body(quantity='2'))
        self.fixture.query("UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=1")
        self.fixture.query("UPDATE warehouse_receipt_lots SET status='cancelled',available_quantity=0 WHERE id=1")
        before = {table:self.fixture.query('SELECT * FROM '+table+' ORDER BY id') for table in (
            'materials','warehouse_main','warehouse_history','warehouse_movements','warehouse_receipt_lots',
            'warehouse_lot_movements','warehouse_distribution_operations','warehouse_distribution_transfer_receipts')}
        self.assertEqual(self.post('/transfers',dispatch_body),dispatched)
        self.assertEqual(self.post(path,receipt_body),accepted)
        self.post('/transfers',self.body(allocationId=child,toProjectId=1,quantity='1'),409)
        self.post(path,self.body(quantity='1',expectedQuantity='1'),409)
        after = {table:self.fixture.query('SELECT * FROM '+table+' ORDER BY id') for table in before}
        self.assertEqual(after,before)


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Dedicated PostgreSQL opt-in required')
class TransitQualityPostgresTests(TransitPostgresTests):
    def setUp(self):
        super().setUp()
        self.fixture.query('''CREATE UNIQUE INDEX projects_owner ON projects(id,company_id);
            CREATE TABLE supply_deliveries(id serial PRIMARY KEY,company_id integer);
            CREATE TABLE material_inspection_journal(id serial PRIMARY KEY,project_name text,
                warehouse_history_id integer,source_type text,source_id integer,source_item_key text,
                material_name text,quantity NUMERIC(14,4),unit text,work_package text,supplier text,received_at text,
                invoice_id integer,delivery_id integer);
            CREATE TABLE cable_journal(id serial PRIMARY KEY,project_name text,
                warehouse_history_id integer,source_type text,source_id integer,source_item_key text,
                cable_brand text,length_received NUMERIC(10,2),work_package text,supplier text,received_at text,
                cable_type text,cross_section text,cores_count integer,invoice_id integer,delivery_id integer)''')
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0023_quality_journal_owners.py'
        tree = ast.parse(path.read_text())
        namespace = {'op':SimpleNamespace(execute=self.fixture.query)}
        exec(compile(ast.Module(body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))],
                               type_ignores=[]),str(path),'exec'),namespace)
        namespace['upgrade']()
        self.fixture.deps['detect_cable_info'] = lambda name: dict(isCable=name.startswith('Cable'),cableType='test',section='2.5',cores=3)
        self.fixture.deps['normalize_unit'] = lambda unit: unit
        os.environ['OWNED_DISTRIBUTION_QUALITY_ENABLED']='1'

    def test_quality_only_accepted_qty_and_flag_off_child_return(self):
        a = self.issue()
        t = self.dispatch(a)
        self.receive(t,'0','4')
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM material_inspection_journal')[0]['n'],1)
        received = self.receive(t,'2','3')['item']
        child = received['receipts'][-1]['allocationId']
        self.assertEqual(self.fixture.query('SELECT project_id,quantity FROM material_inspection_journal ORDER BY id'),
                         [dict(project_id=1,quantity=6),dict(project_id=2,quantity=2)])
        os.environ['OWNED_DISTRIBUTION_QUALITY_ENABLED']='0'
        self.post('/'+str(child)+'/returns',self.body(quantity='1'))
        # Proof follows existing provenance despite flag-off, including new receipts.
        self.receive(t,'1','1')
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM material_inspection_journal')[0]['n'],3)

    def test_broken_dispatch_evidence_blocks_child_return_and_replay(self):
        t = self.dispatch(self.issue())
        receipt = self.body(quantity='2',expectedQuantity='2')
        path = '/transfers/'+str(t['id'])+'/receipts'
        child = self.post(path,receipt)['item']['receipts'][0]['allocationId']
        self.fixture.query("UPDATE warehouse_history SET quantity=3 WHERE type='перемещение: списание' AND issued_to='В пути'")
        self.post('/'+str(child)+'/returns',self.body(quantity='1'),409)
        self.post(path,receipt,409)

    def test_unsupported_quality_precision_rolls_back_receipt(self):
        t = self.dispatch(self.issue())
        before = self.balances()
        self.receive(t,'0.00001','1',409)
        self.assertEqual(self.balances(),before)

    def test_cable_acceptance_only_and_precision(self):
        self.fixture.query('''UPDATE warehouse_invoices SET items='[{"name":"Cable 3x2.5","quantity":10,"unit":"м"}]' WHERE id=1;
            UPDATE warehouse_receipt_lots SET material_name='Cable 3x2.5',unit='м',document_unit='м' WHERE id=1;
            UPDATE warehouse_main SET name='Cable 3x2.5',unit='м' WHERE company_id=2''')
        t = self.dispatch(self.issue())
        self.receive(t,'0','1')
        self.receive(t,'1.234','2',409)
        self.receive(t,'1.23','2')
        self.assertEqual(self.fixture.query('SELECT project_id,length_received FROM cable_journal ORDER BY id'),
                         [dict(project_id=1,length_received=6),dict(project_id=2,length_received=Decimal('1.23'))])

    def test_source_proof_corruption_blocks_dispatch_and_receipt(self):
        a = self.issue()
        t = self.dispatch(a)
        self.fixture.query('DELETE FROM material_inspection_journal WHERE project_id=1')
        before = self.balances()
        self.post('/transfers',self.body(allocationId=a['id'],toProjectId=2,quantity='1'),409)
        self.receive(t,status=409)
        self.assertEqual(self.balances(),before)

    def test_dispatch_quality_precision_rejects_before_stock_or_transit(self):
        a = self.issue()
        before = self.balances()
        for flag in ('1','0'):
            os.environ['OWNED_DISTRIBUTION_QUALITY_ENABLED']=flag
            self.post('/transfers',self.body(allocationId=a['id'],toProjectId=2,quantity='0.000001'),409)
            self.assertEqual(self.balances(),before)
            self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_transfers')[0]['n'],0)

    def test_cable_dispatch_unreceivable_precision_rejected(self):
        self.fixture.query('''UPDATE warehouse_invoices SET items='[{"name":"Cable 3x2.5","quantity":10,"unit":"м"}]' WHERE id=1;
            UPDATE warehouse_receipt_lots SET material_name='Cable 3x2.5',unit='м',document_unit='м' WHERE id=1;
            UPDATE warehouse_main SET name='Cable 3x2.5',unit='м' WHERE company_id=2''')
        a = self.issue('1')
        before = self.balances()
        self.post('/transfers',self.body(allocationId=a['id'],toProjectId=2,quantity='0.001'),409)
        self.assertEqual(self.balances(),before)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_transfers')[0]['n'],0)
