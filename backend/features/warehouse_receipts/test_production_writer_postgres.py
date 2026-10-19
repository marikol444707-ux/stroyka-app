"""Unified confirmation with the actual main.py receipt and stock/invoice writers.

Uses the existing supply-chain fixture's AST loader, explicit empty disposable
Unix-socket database, isolated config and outbound-network prohibition. Source
rows are synthetic, but confirmation, authorization, resolver, claims, history,
stock and invoice SQL are production code. Only optional post-commit AI work is
replaced. This covers legacy receipt accounting, not enabled payment-ledger,
line-proof or owned-quality-journal feature combinations.
"""
import copy
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from backend.features.supplier_access.offer_party_snapshot import build_offer_party_snapshot
from backend.features.supplier_access.rfq_requester_snapshot import build_rfq_requester_snapshot
from .confirmation import confirm_receipt
from .receipt_originals_schema import SCHEMA_SQL


class ObservedConnection:
    """Observe the real transaction owner without changing PostgreSQL behavior."""
    def __init__(self, connection):
        self.connection = connection
        self.commits = 0
        self.rollbacks = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    @property
    def autocommit(self):
        return self.connection.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self.connection.autocommit = value

    def commit(self):
        self.connection.commit()
        self.commits += 1

    def rollback(self):
        self.connection.rollback()
        self.rollbacks += 1


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ProductionWriterPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        conn = cls.main.get_db()
        try:
            with conn.cursor() as cur:
                # Exact receipt-original migration DDL, only inside guarded test DB.
                cur.execute(SCHEMA_SQL)
        finally:
            conn.close()

    def query(self, statement, values=()):
        conn = self.main.get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(statement, values)
                return [dict(row) for row in cur.fetchall()] if cur.description else []
        finally:
            conn.close()

    def setUp(self):
        self.key = uuid4().hex[:12]
        self.project = 'Receipt production writer ' + self.key
        self.names = ['Кирпич красный ' + self.key, 'Цемент портландский ' + self.key]
        self.originals = []
        self.connections = []
        self.callback_snapshots = []
        self.user = self.fixture['users']['director']
        self.headers = {'x_company_id': '2', 'x_company_mode': 'company'}
        self.project_id = self.query('''INSERT INTO projects(company_id,name,status,archived)
            VALUES(2,%s,'В работе',FALSE) RETURNING id''', (self.project,))[0]['id']
        items = [dict(materialName=name, name=name, type='material', itemType='material',
                      quantity=2, unit='шт', workPackage='Основная', price=100,
                      priceMaterial=100, lineTotal=200) for name in self.names]
        self.query('''INSERT INTO estimates(company_id,project_id,project_name,name,version,
            sections_json,status,is_template,smeta_type,work_package)
            VALUES(2,%s,%s,'Receipt estimate','1',%s,'Активная',FALSE,'Заказчик','Основная')''',
            (self.project_id, self.project, json.dumps([dict(name='Основная', items=items)])))
        self.request_id = self.query('''INSERT INTO supply_requests(company_id,project,work_package,
            material_name,quantity,unit,items_json,status) VALUES(2,%s,'Основная',%s,4,'шт',%s,'Заказано')
            RETURNING id''', (self.project, self.names[0], json.dumps(items)))[0]['id']
        requester = build_rfq_requester_snapshot(request_id=self.request_id, company_id=2,
            project_id=self.project_id, project_name=self.project, delivery_address='Synthetic address',
            company={'name': 'Synthetic buyer'}, actor=self.user, frozen_at='2026-10-17T10:00:00Z')
        self.query('UPDATE supply_requests SET requester_snapshot_json=%s WHERE id=%s',
                   (Json(requester), self.request_id))
        self.offer_id = self.query('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,status,
            price_per_unit,total_price) VALUES(2,%s,%s,'Выбран',100,400) RETURNING id''',
            (self.request_id, self.fixture['supplierId']))[0]['id']
        parties = build_offer_party_snapshot(offer_id=self.offer_id, request_id=self.request_id,
            company_id=2, supplier_id=self.fixture['supplierId'], buyer={'fullName': 'Synthetic buyer',
            'inn': '7702222222'}, supplier={'fullName': 'Synthetic supplier', 'inn': '7701234567'},
            actor=self.fixture['users']['supplier'], frozen_at='2026-10-17T10:00:00Z')
        self.query('UPDATE supplier_offers SET party_snapshot_json=%s WHERE id=%s',
                   (Json(parties), self.offer_id))
        self.deliveries = []
        for name in self.names:
            self.deliveries.append(self.query('''INSERT INTO supply_deliveries(company_id,request_id,
                offer_id,supplier_id,project,work_package,material_name,unit,planned_quantity,
                shipped_quantity,price_per_unit,total_price,waybill_number,waybill_date,status)
                VALUES(2,%s,%s,%s,%s,'Основная',%s,'шт',2,2,100,200,%s,'2026-10-17','В пути') RETURNING id''',
                (self.request_id, self.offer_id, self.fixture['supplierId'], self.project, name, self.key))[0]['id'])
        self.query('''INSERT INTO supplier_shipment_batches(company_id,offer_id,request_key,payload_hash,delivery_ids)
            VALUES(2,%s,%s,%s,%s)''', (self.offer_id, self.key, 'a' * 64, self.deliveries))
        for index in range(2):
            identity = self.query('''INSERT INTO file_ownership(company_id,project_id,file_url)
                VALUES(2,%s,%s) RETURNING id''', (self.project_id, '/synthetic/' + self.key + str(index)))[0]['id']
            self.originals.append(f'/tenant-files/{identity}/content')
        self.data = dict(companyId=2, project=self.project, projectId=self.project_id,
            document=dict(documentType='waybill', waybillNumber=self.key, waybillDate='2026-10-17',
                supplierInn='7701234567', buyerInn='7702222222',
                lines=[dict(materialName=name, quantity='2', unit='шт') for name in self.names]),
            originalUrls=self.originals + self.originals[:1], physicalReceiptConfirmed=True,
            actualLines=[dict(deliveryId=identity, receivedQuantity='1.5', qualityStatus='Недостача')
                         for identity in self.deliveries])
        self.deps = dict(self.main._receipt_workflow_deps, get_db=self.observed_connection)
        self.assertIs(self.deps['receive_delivery'], self.main._receive_supply_delivery_record)
        callback = patch.object(self.main, '_run_project_ai_control_safely',
                                side_effect=lambda *_: self.callback_snapshots.append(self.snapshot()))
        callback.start()
        self.addCleanup(callback.stop)
        self.before = self.snapshot()

    def observed_connection(self):
        connection = ObservedConnection(self.main.get_db())
        self.connections.append(connection)
        return connection

    def snapshot(self):
        return {table: self.query(sql.SQL('SELECT to_jsonb(t) AS row FROM {} t ORDER BY to_jsonb(t)::text').format(
                    sql.Identifier(table)))
                for table in ('supply_requests', 'supplier_offers', 'supply_deliveries', 'materials',
                    'warehouse_invoices', 'warehouse_history', 'supply_history', 'supply_claims',
                    'file_ownership', 'material_inspection_journal', 'cable_journal')}

    def confirm(self):
        return confirm_receipt(copy.deepcopy(self.data), self.user, self.headers, self.deps)

    def assert_rolled_back(self):
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(self.callback_snapshots, [])
        self.assertEqual(sum(conn.commits for conn in self.connections), 0)
        self.assertTrue(all(conn.closed for conn in self.connections))
        self.assertGreater(sum(conn.rollbacks for conn in self.connections), 0)

    def test_multiline_shortage_commits_real_stock_invoices_claims_and_evidence_once(self):
        result = self.confirm()
        self.assertTrue(result['ok'])
        self.assertFalse(result['alreadyReceived'])
        self.assertEqual((self.connections[0].commits, self.connections[0].rollbacks), (1, 0))
        self.assertTrue(self.connections[0].closed)
        self.assertEqual(len(result['warehouseInvoiceIds']), 2)
        self.assertEqual(self.query('SELECT quantity FROM materials WHERE project=%s ORDER BY name',
                                   (self.project,)), [{'quantity': 1.5}, {'quantity': 1.5}])
        invoices = self.query('''SELECT supply_delivery_id,company_id,photo_urls,pages_count,total_with_vat
            FROM warehouse_invoices WHERE supply_delivery_id=ANY(%s) ORDER BY supply_delivery_id''', (self.deliveries,))
        self.assertEqual([row['supply_delivery_id'] for row in invoices], self.deliveries)
        for invoice in invoices:
            self.assertEqual(invoice['company_id'], 2)
            self.assertEqual(json.loads(invoice['photo_urls']), self.originals)
            self.assertEqual(invoice['pages_count'], 2)
            self.assertEqual(invoice['total_with_vat'], 150)
        claims = self.query('''SELECT d.id,d.claim_id,d.receipt_original_urls,c.received_quantity,
            c.shortage_quantity FROM supply_deliveries d JOIN supply_claims c ON c.id=d.claim_id
            WHERE d.id=ANY(%s) ORDER BY d.id''', (self.deliveries,))
        self.assertEqual(len(claims), 2)
        for claim in claims:
            self.assertEqual(claim['receipt_original_urls'], self.originals)
            self.assertEqual((claim['received_quantity'], claim['shortage_quantity']), (1.5, .5))
        self.assertEqual(self.query('SELECT count(*) AS n FROM warehouse_history WHERE source_id=ANY(%s)',
                                   (self.deliveries,)), [{'n': 2}])
        self.assertEqual(self.query('SELECT count(*) AS n FROM supply_history WHERE delivery_id=ANY(%s)',
                                   (self.deliveries,)), [{'n': 2}])
        self.assertEqual(len(self.callback_snapshots), 2)
        self.assertTrue(all(value == self.snapshot() for value in self.callback_snapshots))

    def test_replay_does_not_repeat_real_writer_effects(self):
        first = self.confirm()
        saved = self.snapshot()
        self.data['originalUrls'] = list(reversed(self.originals))
        second = self.confirm()
        self.assertTrue(second['alreadyReceived'])
        self.assertEqual(second['warehouseInvoiceIds'], first['warehouseInvoiceIds'])
        self.assertEqual(self.snapshot(), saved)
        self.assertEqual(sum(conn.commits for conn in self.connections), 1)
        self.assertEqual(len(self.callback_snapshots), 2)

    def test_later_real_stock_constraint_failure_rolls_back_every_line(self):
        # Inject a database failure after the second real invoice and claim write.
        constraint = 'receipt_stock_failure_' + self.key
        self.query(sql.SQL('ALTER TABLE materials ADD CONSTRAINT {} CHECK(name <> {})').format(
            sql.Identifier(constraint), sql.Literal(self.names[1])))
        self.addCleanup(self.query, sql.SQL('ALTER TABLE materials DROP CONSTRAINT {}').format(sql.Identifier(constraint)))
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.confirm()
        self.assert_rolled_back()

    def test_later_real_estimate_guard_rolls_back_earlier_production_receipt(self):
        from fastapi import HTTPException
        # The second line must fail real resource admission after the first write.
        self.query("""UPDATE estimates SET sections_json=jsonb_set(sections_json::jsonb,
            '{0,items}', jsonb_build_array(sections_json::jsonb->0->'items'->0))::text
            WHERE project_id=%s""", (self.project_id,))
        with self.assertRaises(HTTPException) as caught:
            self.confirm()
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn('смет', caught.exception.detail)
        self.assert_rolled_back()

    def test_later_excess_quantity_rolls_back_earlier_production_receipt(self):
        from fastapi import HTTPException
        self.data['actualLines'][1]['receivedQuantity'] = '2.0001'
        with self.assertRaises(HTTPException) as caught:
            self.confirm()
        self.assertEqual(caught.exception.status_code, 400)
        self.assert_rolled_back()

    def test_zero_quantity_saves_real_claims_and_originals_without_stock_or_invoices(self):
        for line in self.data['actualLines']:
            line['receivedQuantity'] = '0'
        result = self.confirm()
        self.assertEqual(result['warehouseInvoiceIds'], [])
        state = self.snapshot()
        for table in ('materials', 'warehouse_invoices', 'warehouse_history'):
            self.assertEqual(state[table], self.before[table])
        rows = self.query('''SELECT d.id,d.received_quantity,d.receipt_original_urls,d.claim_id,
            c.shortage_quantity FROM supply_deliveries d JOIN supply_claims c ON c.id=d.claim_id
            WHERE d.id=ANY(%s) ORDER BY d.id''', (self.deliveries,))
        self.assertEqual([row['id'] for row in rows], self.deliveries)
        for row in rows:
            self.assertEqual(row['received_quantity'], 0)
            self.assertEqual(row['shortage_quantity'], 2)
            self.assertEqual(row['receipt_original_urls'], self.originals)
        saved = self.snapshot()
        self.assertTrue(self.confirm()['alreadyReceived'])
        self.assertEqual(self.snapshot(), saved)
        self.assertEqual(sum(conn.commits for conn in self.connections), 1)
        self.assertEqual(len(self.callback_snapshots), 2)
