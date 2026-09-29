"""Real authenticated stock-writer interleavings on a fresh explicit UTF8 DB.

Uses the guarded Unix-only fixture and whole migration 0012. No auth, stock or
estimate mocks. SQL triggers below only pause a transaction at a known boundary;
the production handlers perform every business mutation. Each run needs a NEW DB.
The shared fixture enforces statement_timeout=15s and lock_timeout=5s.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.material_traceability import test_transfer_workflow_postgres as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Requires fresh explicit isolated PostgreSQL database')
class StockChainPostgresTests(unittest.TestCase):
    sql = support.TransferWorkflowPostgresTests.sql
    api = support.TransferWorkflowPostgresTests.api
    payload = support.TransferWorkflowPostgresTests.payload
    balance = support.TransferWorkflowPostgresTests.balance

    @classmethod
    def setUpClass(cls):
        support.TransferWorkflowPostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {'WAREHOUSE_DISTRIBUTION_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def setUp(self):
        from psycopg2.extras import Json, RealDictCursor
        self.f = dict(self.fixture)
        self.f['users'] = dict(self.fixture['users'])
        suffix = uuid4().hex[:10]
        self.f['project'] = 'STOCK CHAIN ' + suffix
        self.f['materialName'] = 'CHAIN resource ' + suffix
        self.f['projectId'] = self.sql("""INSERT INTO projects(name,company_id,status,archived)
            VALUES(%s,2,'В работе',FALSE) RETURNING id""", (self.f['project'],))[0][0]
        foreman_id = self.f['users']['foreman']['id']
        self.sql('UPDATE users SET assigned_projects=%s WHERE id=%s',
                 (Json([self.f['project']]), foreman_id))
        self.sql('UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=2',
                 (Json([self.f['project']]), foreman_id))
        sections = [{'name': 'Основная', 'items': [{'id': suffix, 'name': self.f['materialName'],
            'type': 'material', 'itemType': 'material', 'unit': 'шт', 'quantity': 20,
            'price': 100, 'priceMaterial': 100, 'lineTotal': 2000, 'workPackage': 'Основная'}]}]
        self.sql("""INSERT INTO estimates(company_id,project_id,project_name,name,version,
            sections_json,status,is_template,smeta_type,work_package)
            VALUES(2,%s,%s,'CHAIN estimate','1',%s,'Активная',FALSE,'Заказчик','Основная')""",
            (self.f['projectId'], self.f['project'], json.dumps(sections, ensure_ascii=False)))
        # Actual membership and project/package assignment, not dependency overrides.
        uid = self.sql("""INSERT INTO users(name,email,password,role,active,company_id,
            assigned_projects,assigned_packages) VALUES(%s,%s,%s,'мастер',TRUE,2,%s,%s) RETURNING id""",
            ('CHAIN worker '+suffix, suffix+'@supply-chain.invalid',
             self.f['users']['foreman']['password'], Json([self.f['project']]), Json(['Основная'])))[0][0]
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
            role,assigned_projects,assigned_packages,active,is_default)
            VALUES(%s,2,1,'мастер',%s,%s,TRUE,TRUE)""",
            (uid, Json([self.f['project']]), Json(['Основная'])))
        conn = self.main.get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT * FROM users WHERE id=%s', (uid,))
                self.f['users']['worker'] = dict(cur.fetchone())
        finally:
            conn.close()
        self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
            VALUES(3,%s,'шт',7,%s,'Основная')""", (self.f['materialName'], self.f['project']))
        self.sql("INSERT INTO warehouse_main(company_id,name,unit,quantity) VALUES(3,%s,'шт',11)",
                 (self.f['materialName'],))
        foreign = self.foreign_snapshot()
        self.addCleanup(lambda: self.assertEqual(self.foreign_snapshot(), foreign))

    def foreign_snapshot(self):
        return [self.sql('SELECT * FROM '+table+' WHERE company_id=3 ORDER BY id')
                for table in ('materials', 'warehouse_main', 'warehouse_invoices', 'supplier_invoices')]

    def finances(self, allow_receipt_link=False):
        invoices = self.sql("SELECT to_jsonb(i)-'warehouse_invoice_id' FROM supplier_invoices i ORDER BY id"
                            if allow_receipt_link else 'SELECT * FROM supplier_invoices ORDER BY id')
        return [invoices, self.sql('SELECT * FROM project_payments ORDER BY id')]

    def receipt_payload(self, quantity=2):
        return dict(companyId=2, location='Основной склад', warehouseTarget='main',
            inventoryOnly=True, number='CHAIN-'+uuid4().hex, date='2026-09-16',
            items=[dict(name=self.f['materialName'], materialName=self.f['materialName'],
                        unit='шт', quantity=quantity, price=100, workPackage='Основная')])

    def prepare_lot(self):
        self.api('director', 'POST', '/warehouse-invoices', self.receipt_payload())
        sources = self.api('director', 'GET', '/warehouse-distributions/sources?companyId=2')['items']
        return next(row['lotId'] for row in sources if row['materialName'] == self.f['materialName'])

    def distribution(self, lot):
        return dict(companyId=2, requestId=str(uuid4()), reason='Synthetic concurrency check',
                    rows=[dict(lotId=lot, projectId=self.f['projectId'], quantity='2')])

    def request(self, method, path, data, actor='director'):
        from fastapi.testclient import TestClient
        token = self.main.create_auth_token(self.f['users'][actor], two_factor_passed=True)
        with TestClient(self.main.app, raise_server_exceptions=False) as client:
            return client.request(method, path, json=data, headers={'Authorization': 'Bearer '+token})

    def wait_blocked(self, query_fragment, count=1):
        deadline = time.monotonic() + 3
        rows = []
        while time.monotonic() < deadline:
            rows = self.sql("""SELECT pid,query FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()
                AND wait_event_type='Lock' AND query LIKE %s""", ('%'+query_fragment+'%',))
            if len(rows) >= count:
                return rows
            time.sleep(.02)
        self.fail('Expected blocked SQL '+query_fragment+'; observed '+repr(rows))

    def stocks(self):
        return tuple(self.sql('SELECT coalesce(sum(quantity),0) FROM '+table+
                             ' WHERE company_id=2 AND name=%s', (self.f['materialName'],))[0][0]
                     for table in ('warehouse_main', 'materials'))

    def test_transfer_vs_distribution_return_cannot_spend_same_stock_twice(self):
        lot = self.prepare_lot()
        allocation = self.api('director', 'POST', '/warehouse-distributions', self.distribution(lot))['items'][0]
        finances = self.finances()
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('LOCK TABLE materials IN SHARE ROW EXCLUSIVE MODE')
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.request, 'POST', '/material-transfers', self.payload()),
                    pool.submit(self.request, 'POST', '/warehouse-distributions/'+str(allocation['id'])+'/returns',
                                dict(companyId=2, requestId=str(uuid4()), quantity='2', reason='Return unused stock'))]
                try:
                    self.wait_blocked('LOCK TABLE materials, warehouse_main, projects', 2)
                finally:
                    blocker.rollback()
                responses = [f.result(timeout=20) for f in futures]
        finally:
            blocker.close()
        self.assertEqual(sum(r.status_code == 200 for r in responses), 1,
                         [(r.status_code,r.text) for r in responses])
        self.assertIn(next(r.status_code for r in responses if r.status_code != 200), (400,409))
        issued = self.sql('SELECT coalesce(sum(quantity),0) FROM material_transfers WHERE project_id=%s',
                          (self.f['projectId'],))[0][0]
        main, obj = self.stocks()
        self.assertEqual(main + obj + issued, 2)
        self.assertEqual(obj, 0)
        returned = self.sql('SELECT returned_quantity FROM warehouse_distribution_allocations WHERE id=%s',
                            (allocation['id'],))[0][0]
        self.assertEqual(returned, main)
        self.assertEqual(self.sql('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=%s', (lot,)),
                         [(returned,)])
        self.assertEqual(self.finances(), finances)

    def restore_personal_stock_vs_distribution_return(self, signed):
        lot = self.prepare_lot()
        allocation = self.api('director', 'POST', '/warehouse-distributions', self.distribution(lot))['items'][0]
        transfer_id = self.api('director', 'POST', '/material-transfers', self.payload(1))['id']
        if signed:
            self.api('worker', 'PUT', '/material-transfers/'+str(transfer_id)+'/sign')
        self.assertEqual(self.stocks(), (0,1))
        finances = self.finances()
        return_path = '/warehouse-distributions/'+str(allocation['id'])+'/returns'
        return_payload = dict(companyId=2, requestId=str(uuid4()), quantity='1', reason='Unused object stock')
        personal_request = (('POST', '/material-transfers/return', self.payload(1), 'worker') if signed else
                            ('DELETE', '/material-transfers/'+str(transfer_id), None, 'director'))
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('LOCK TABLE materials IN SHARE ROW EXCLUSIVE MODE')
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.request, *personal_request),
                           pool.submit(self.request, 'POST', return_path, return_payload)]
                try:
                    self.wait_blocked('LOCK TABLE materials, warehouse_main, projects', 2)
                finally:
                    blocker.rollback()
                responses = [f.result(timeout=20) for f in futures]
        finally:
            blocker.close()
        self.assertEqual([r.status_code for r in responses], [200,200],
                         [(r.status_code,r.text) for r in responses])
        self.assertEqual(self.stocks(), (1,1))
        self.assertEqual(self.balance(), dict(issued=1 if signed else 0, used=0,
                                              returned=1 if signed else 0, available=0))
        self.assertEqual(self.sql("""SELECT quantity,signed,coalesce(status,'Активна')
            FROM material_transfers WHERE id=%s""", (transfer_id,)),
            [(1,signed,'Активна' if signed else 'Аннулирована')])
        self.assertEqual(self.sql('SELECT received_quantity,available_quantity FROM warehouse_receipt_lots WHERE id=%s',
                                  (lot,)), [(2,1)])
        self.assertEqual(self.sql('SELECT quantity,returned_quantity FROM warehouse_distribution_allocations WHERE id=%s',
                                  (allocation['id'],)), [(2,1)])
        returned = self.sql('SELECT quantity,movement_id FROM warehouse_distribution_returns WHERE allocation_id=%s',
                            (allocation['id'],))
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0][0], 1)
        movement_id = returned[0][1]
        self.assertEqual(self.sql('''SELECT company_id,quantity,source_invoice_id,source_invoice_line_index
            FROM warehouse_movements WHERE id=%s''', (movement_id,)),
            [(2,1,allocation['warehouseInvoiceId'],allocation['invoiceLineIndex'])])
        self.assertEqual(self.sql('''SELECT company_id,quantity,source_invoice_id,source_invoice_line_index
            FROM warehouse_history WHERE source_type='warehouse_movement' AND source_id=%s ORDER BY id''',
            (movement_id,)), [(2,1,allocation['warehouseInvoiceId'],allocation['invoiceLineIndex'])]*2)
        event = 'возврат от мастера' if signed else 'отмена передачи'
        actor_name = self.f['users']['worker' if signed else 'director']['name']
        self.assertEqual(self.sql('''SELECT company_id,quantity,issued_by FROM warehouse_history
            WHERE project=%s AND material=%s AND type=%s''',
            (self.f['project'], self.f['materialName'], event)), [(2,1,actor_name)])
        self.assertEqual(self.finances(), finances)
        # Replaying the distribution cannot repeat its stock or lot journal.
        after = self.chain_snapshot()
        self.assertEqual(self.api('director', 'POST', return_path, return_payload), responses[1].json())
        if signed:
            self.api('worker', 'POST', '/material-transfers/return', self.payload(1), expected=400)
        else:
            self.api('director', 'DELETE', '/material-transfers/'+str(transfer_id))
        self.assertEqual(self.chain_snapshot(), after)

    def test_unsigned_transfer_cancel_vs_distribution_return(self):
        self.restore_personal_stock_vs_distribution_return(signed=False)

    def test_signed_worker_return_vs_distribution_return(self):
        self.restore_personal_stock_vs_distribution_return(signed=True)

    def overlap_distribution(self, command, method, path, payload):
        # Stop the real distribution after its stock locks, before receipt locks.
        # Baseline manual receipt then holds receipt DDL locks and waits for stock:
        # releasing this gate completes the cycle and PostgreSQL detects deadlock.
        self.sql("""CREATE FUNCTION stock_chain_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(914225,1); RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER stock_chain_pause BEFORE INSERT ON warehouse_distribution_operations
            FOR EACH ROW EXECUTE FUNCTION stock_chain_pause()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(914225,1)')
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, 'POST', '/warehouse-distributions', command)
                try:
                    self.wait_blocked('INSERT INTO warehouse_distribution_operations')
                    second = pool.submit(self.request, method, path, payload)
                    # Stock query on baseline, early common lock after the fix.
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        waits = self.sql("""SELECT query FROM pg_stat_activity WHERE datname=current_database()
                            AND pid<>pg_backend_pid() AND wait_event_type='Lock'
                            AND query NOT LIKE '%%INSERT INTO warehouse_distribution_operations%%'""")
                        if waits:
                            break
                        time.sleep(.02)
                    self.assertTrue(waits, 'Manual receipt must overlap the paused distribution')
                finally:
                    blocker.rollback()
                responses = [first.result(timeout=20), second.result(timeout=20)]
        finally:
            blocker.close()
            self.sql('DROP TRIGGER stock_chain_pause ON warehouse_distribution_operations')
            self.sql('DROP FUNCTION stock_chain_pause()')
        return responses

    def test_manual_receipt_vs_distribution_has_consistent_lock_order(self):
        lot = self.prepare_lot()
        finances = self.finances()
        command = self.distribution(lot)
        responses = self.overlap_distribution(command, 'POST', '/warehouse-invoices', self.receipt_payload(3))
        self.assertEqual([r.status_code for r in responses], [200,200],
                         [(r.status_code,r.text) for r in responses])
        self.assertEqual(self.stocks(), (3,2))
        self.assertEqual(self.finances(), finances)
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_distribution_operations WHERE request_id=%s',
                                  (command['requestId'],)), [(1,)])
        replay = self.api('director', 'POST', '/warehouse-distributions', command)
        self.assertEqual(replay, responses[0].json())
        self.assertEqual(self.stocks(), (3,2))
        self.assertEqual(self.finances(), finances)

    def prepare_supplier_delivery(self):
        """Create the actual addressed request, offer, invoice and shipment via HTTP."""
        item = dict(materialName=self.f['materialName'], quantity=2, unit='шт', workPackage='Основная')
        rid = self.api('director', 'POST', '/supply-requests', dict(companyId=2,
            project=self.f['project'], workPackage='Основная', items=[item]))['id']
        path = '/supply-requests/'+str(rid)
        self.api('foreman', 'PUT', path, {'action': 'confirm_prorab'})
        self.api('director', 'PUT', path, {'action': 'approve_director'})
        self.api('director', 'POST', path+'/request-kp', {'supplierIds': [self.f['supplierId']]})
        offer = next(r for r in self.api('supplier', 'GET', '/supplier-offers') if r['requestId'] == rid)
        path = '/supplier-offers/'+str(offer['id'])
        self.api('supplier', 'PUT', path, dict(action='respond', pricePerUnit=100, totalPrice=200,
            deliveryDays=1, paymentTerms='Предоплата 100%', vatIncluded=False,
            itemsKp=[dict(item, pricePerUnit=100, totalPrice=200, deliveryDays=1)]))
        self.api('director', 'PUT', path, {'action': 'select'})
        invoice = self.api('supplier', 'POST', path+'/create-invoice',
            dict(invoiceNumber='CHAIN-'+str(rid), invoiceDate='2026-09-16', amount=200, vatAmount=0))['id']
        self.api('accountant', 'PUT', '/supplier-invoices/'+str(invoice), {'status': 'Утверждён'})
        self.api('accountant', 'PUT', '/supplier-invoices/'+str(invoice),
                 dict(status='Оплачен', paidAmount=200, paidAt='2026-09-16'))
        delivery = self.api('supplier', 'POST', path+'/ship',
            dict(shippedQuantity=2, waybillNumber='SHIP-'+str(rid), waybillDate='2026-09-16'))['id']
        return delivery, invoice

    def test_supplier_acceptance_vs_distribution_and_replay_do_not_duplicate_debt(self):
        lot = self.prepare_lot()
        delivery_id, supplier_invoice_id = self.prepare_supplier_delivery()
        finances = self.finances(allow_receipt_link=True)
        links = dict(self.sql('SELECT id,warehouse_invoice_id FROM supplier_invoices ORDER BY id'))
        self.assertIsNone(links[supplier_invoice_id])
        command = self.distribution(lot)
        path = '/supply-deliveries/'+str(delivery_id)+'/receive'
        payload = dict(companyId=2, receivedQuantity=2, qualityStatus='Принято', receivedBy='Synthetic director')
        responses = self.overlap_distribution(command, 'PUT', path, payload)
        self.assertEqual([r.status_code for r in responses], [200,200],
                         [(r.status_code,r.text) for r in responses])
        self.assertEqual(self.stocks(), (0,4))
        self.assertEqual(self.finances(allow_receipt_link=True), finances)
        invoice_id = responses[1].json()['invoiceId']
        self.assertTrue(invoice_id)
        links[supplier_invoice_id] = invoice_id
        self.assertEqual(dict(self.sql('SELECT id,warehouse_invoice_id FROM supplier_invoices ORDER BY id')), links)
        self.assertEqual(self.sql('SELECT id,supplier_invoice_id FROM warehouse_invoices WHERE supply_delivery_id=%s',
                                  (delivery_id,)), [(invoice_id,supplier_invoice_id)])
        before = [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in
                  ('materials', 'warehouse_main', 'warehouse_history', 'warehouse_invoices', 'supply_deliveries')]
        replay = self.api('director', 'PUT', path, payload)
        self.assertTrue(replay['alreadyReceived'])
        self.assertEqual(replay['invoiceId'], invoice_id)
        self.assertEqual([self.sql('SELECT * FROM '+table+' ORDER BY id') for table in
                  ('materials', 'warehouse_main', 'warehouse_history', 'warehouse_invoices', 'supply_deliveries')], before)
        self.assertEqual(self.finances(allow_receipt_link=True), finances)
        self.assertEqual(dict(self.sql('SELECT id,warehouse_invoice_id FROM supplier_invoices ORDER BY id')), links)

    def test_foreman_receipt_projection_retains_original_indices_and_overrides_spoof(self):
        from psycopg2.extras import Json
        items = [dict(name='Hidden', unit='шт', quantity=5, price=999, workPackage='Other', invoiceLineIndex=2),
                 dict(name='Visible first', unit='шт', quantity=1, price=3, workPackage='Основная', invoiceLineIndex=0),
                 dict(name='Visible second', unit='шт', quantity=2, price=4, workPackage='Основная', invoiceLineIndex=999)]
        rid = self.sql("""INSERT INTO warehouse_invoices(company_id,number,project,location,items,
            total_base,total_with_vat,status) VALUES(2,'CHAIN-VISIBILITY',%s,%s,%s,5006,5006,'Принята') RETURNING id""",
            (self.f['project'], self.f['project'], Json(items)))[0][0]
        before = self.sql('SELECT * FROM warehouse_invoices WHERE id=%s', (rid,))
        visible = next(r for r in self.api('foreman', 'GET', '/warehouse-invoices') if r['id'] == rid)
        self.assertEqual([r['invoiceLineIndex'] for r in visible['items']], [1,2])
        self.assertEqual([r['name'] for r in visible['items']], ['Visible first', 'Visible second'])
        self.assertEqual(visible['totalWithVat'], 11)
        self.assertEqual(self.sql('SELECT * FROM warehouse_invoices WHERE id=%s', (rid,)), before)
        self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
            VALUES(2,'Visible second','шт',2,%s,'Основная')""", (self.f['project'],))
        finances = self.finances()
        snapshot = [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in
                    ('materials', 'warehouse_main', 'warehouse_movements', 'warehouse_history')]
        # A visible position of zero is NOT the stored source index. This rejects
        # a wrong material reference, not foreman package access (legacy policy
        # deliberately grants foremen all packages in has_package_access).
        movement = dict(materialName='Visible second', unit='шт', quantity=1, workPackage='Основная',
                        fromLocation=self.f['project'], toLocation='Основной склад', invoiceId=rid,
                        invoiceLineIndex=0, date='2026-09-16', createdBy='Synthetic foreman')
        rejection = self.api('foreman', 'POST', '/warehouse-movements', movement, expected=400)
        self.assertIn('не совпадает', rejection['detail'])
        self.assertEqual([self.sql('SELECT * FROM '+table+' ORDER BY id') for table in
                    ('materials', 'warehouse_main', 'warehouse_movements', 'warehouse_history')], snapshot)
        movement.update(materialName='Visible second', workPackage='Основная', invoiceLineIndex=2)
        result = self.api('foreman', 'POST', '/warehouse-movements', movement)
        self.assertEqual((result['sourceInvoiceId'], result['sourceInvoiceLineIndex']), (rid,2))
        self.assertEqual(self.sql('SELECT source_invoice_id,source_invoice_line_index FROM warehouse_movements WHERE id=%s',
                                  (result['id'],)), [(rid,2)])
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE company_id=2 AND project=%s AND name='Visible second'",
                                  (self.f['project'],)), [(1,)])
        self.assertEqual(self.sql('SELECT * FROM warehouse_invoices WHERE id=%s', (rid,)), before)
        self.assertEqual(self.finances(), finances)

    def chain_snapshot(self):
        return [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in
                ('materials', 'warehouse_main', 'warehouse_invoices', 'warehouse_history',
                 'material_transfers', 'warehouse_movements', 'warehouse_distribution_operations',
                 'warehouse_distribution_allocations', 'warehouse_distribution_returns',
                 'warehouse_receipt_lots', 'warehouse_lot_movements', 'supply_deliveries',
                 'supply_requests', 'supplier_offers', 'supply_history', 'supplier_invoices',
                 'project_payments', 'material_inspection_journal', 'cable_journal')]

    def inject_failure(self, table, method, path, payload):
        # Table names are test-owned constants, never API input. AFTER INSERT
        # proves a business write occurred before the statement aborts its tx.
        self.assertIn(table, ('warehouse_receipt_lots', 'materials'))
        before = self.chain_snapshot()
        self.sql("""CREATE FUNCTION stock_chain_fail() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'injected stock chain persistence failure'; END $$""")
        self.sql('CREATE TRIGGER stock_chain_fail AFTER INSERT ON '+table+
                 ' FOR EACH ROW EXECUTE FUNCTION stock_chain_fail()')
        try:
            response = self.request(method, path, payload)
        finally:
            self.sql('DROP TRIGGER stock_chain_fail ON '+table)
            self.sql('DROP FUNCTION stock_chain_fail()')
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(self.chain_snapshot(), before,
                         'Receipt, lot, stock, journals, delivery and financial rows must all roll back')

    def test_manual_receipt_late_lot_failure_rolls_back_and_retry_is_single(self):
        payload = self.receipt_payload()
        finances = self.finances()
        self.inject_failure('warehouse_receipt_lots', 'POST', '/warehouse-invoices', payload)
        self.assertEqual(self.stocks(), (0,0))
        self.api('director', 'POST', '/warehouse-invoices', payload)
        self.assertEqual(self.stocks(), (2,0))
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_invoices WHERE company_id=2 AND number=%s',
                                  (payload['number'],)), [(1,)])
        self.assertEqual(self.sql('SELECT received_quantity,available_quantity FROM warehouse_receipt_lots WHERE material_name=%s',
                                  (self.f['materialName'],)), [(2,2)])
        after = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-invoices', payload, expected=409)
        self.assertEqual(self.chain_snapshot(), after)
        self.assertEqual(self.finances(), finances)

    def test_supplier_acceptance_late_stock_failure_rolls_back_and_retry_is_single(self):
        delivery_id, supplier_invoice_id = self.prepare_supplier_delivery()
        path = '/supply-deliveries/'+str(delivery_id)+'/receive'
        payload = dict(companyId=2, receivedQuantity=2, qualityStatus='Принято', receivedBy='Synthetic director')
        finances = self.finances(allow_receipt_link=True)
        self.inject_failure('materials', 'PUT', path, payload)
        self.assertEqual(self.stocks(), (0,0))
        self.assertEqual(self.sql('SELECT received_at FROM supply_deliveries WHERE id=%s', (delivery_id,)), [(None,)])
        accepted = self.api('director', 'PUT', path, payload)
        self.assertEqual(self.stocks(), (0,2))
        self.assertEqual(self.sql('SELECT id,supplier_invoice_id FROM warehouse_invoices WHERE supply_delivery_id=%s',
                                  (delivery_id,)), [(accepted['invoiceId'],supplier_invoice_id)])
        after = self.chain_snapshot()
        replay = self.api('director', 'PUT', path, payload)
        self.assertTrue(replay['alreadyReceived'])
        self.assertEqual(replay['invoiceId'], accepted['invoiceId'])
        self.assertEqual(self.chain_snapshot(), after)
        self.assertEqual(self.finances(allow_receipt_link=True), finances)
        self.assertEqual(self.sql('SELECT warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                  (supplier_invoice_id,)), [(accepted['invoiceId'],)])


if __name__ == '__main__':
    unittest.main()
