"""Opt-in offer invoice HTTP birth tests; fresh isolated DB per class only."""
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from . import test_contract_context_postgres as base
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class InvoiceLineCreationPostgresTests(unittest.TestCase):
    sql = base.ContractContextTests.sql
    api = base.ContractContextTests.api
    create_offer = base.ContractContextTests.create_offer
    check_contract = base.ContractContextTests.check_contract

    @classmethod
    def setUpClass(cls):
        base.ContractContextTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                for name in ('0045_supplier_payment_ledger.py', '0046_supplier_payment_attachments.py',
                             '0047_supplier_payment_packages.py', '0048_supplier_payment_cancellations.py',
                             '0049_supplier_payment_allocations.py', '0050_supplier_invoice_line_specs.py'):
                    migration(cur, name)
                # Independent per-test offers must not exhaust the two-unit
                # estimate seeded by the shared, unchanged fixture builder.
                cur.execute("""UPDATE estimates SET sections_json=jsonb_set(sections_json::jsonb,
                    '{0,items,0,quantity}','1000'::jsonb)::text WHERE id=%s""", (cls.fixture['estimateId'],))
        finally:
            conn.close()

    def setUp(self):
        self.request_id, self.offer_id = self.create_offer('director', 2, self.fixture['project'])
        self.path = f'/supplier-offers/{self.offer_id}'
        self.api('director', 'PUT', self.path + '/parties', dict(buyerCompanyId=2, payerCompanyId=2,
            expectedVersion=0, reason='Synthetic immutable invoice lines'))
        self.check_contract('director', 'stranger', 2, self.offer_id,
                            self.api('director', 'GET', self.path + '/contract-review-context'))
        self.contract_id = self.api('supplier', 'GET', self.path + '/contracts')['items'][0]['id']
        self.request_items = [dict(materialName=self.fixture['materialName'], quantity='2',
            unit='шт', workPackage=self.fixture['workPackage'])]
        self.kp_items = [{**self.request_items[0], 'pricePerUnit': '100.00', 'totalPrice': '200.00'}]
        self.raw_sources(self.request_items, self.kp_items)
        self.payload = dict(invoiceNumber='LINE-' + uuid4().hex, invoiceDate='2026-09-18',
                            amount='200.00', vatAmount='0.00', contractVersionId=self.contract_id)
        flags = patch.dict(os.environ, SUPPLIER_INVOICE_LINE_SPECS_ENABLED='1')
        flags.start(); self.addCleanup(flags.stop)

    def raw_sources(self, request_items, kp_items):
        self.sql('UPDATE supply_requests SET items_json=%s WHERE id=%s',
                 (json.dumps(request_items, ensure_ascii=False), self.request_id))
        self.sql('UPDATE supplier_offers SET items_kp_json=%s,vat_included=FALSE WHERE id=%s',
                 (json.dumps(kp_items, ensure_ascii=False), self.offer_id))

    def create(self, payload=None, expected=200, actor='supplier'):
        return self.api(actor, 'POST', self.path + '/create-invoice',
                        self.payload if payload is None else payload, expected=expected)

    def finances(self):
        return {table: self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text')
                for table in ('supplier_invoices', 'supplier_offer_events', 'supplier_payment_documents',
                    'supplier_payment_operations', 'supplier_payment_impacts', 'project_payments',
                    'warehouse_invoices', 'supply_deliveries', 'materials')}

    def specifications(self):
        return {table: self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text')
                for table in ('supplier_invoice_line_specs', 'supplier_invoice_lines')}

    def test_new_invoice_persists_exact_spec_and_source_snapshots_atomically(self):
        before = self.finances()
        result = self.create()
        self.assertTrue(result['ok'])
        rows = self.sql('''SELECT s.id,s.company_id,s.row_count,s.amount,s.source_payload,
                          s.source_identity=i.line_spec_insert_identity,
                          s.creation_xid=i.line_spec_insert_xid
                          FROM supplier_invoice_line_specs s JOIN supplier_invoices i ON i.id=s.invoice_id
                          WHERE s.invoice_id=%s''', (result['id'],))
        self.assertEqual(len(rows), 1)
        spec_id, company, count, amount, source, same_identity, same_xid = rows[0]
        self.assertEqual((company, count, amount, same_identity, same_xid), (2, 1, 200, True, True))
        self.assertEqual(json.loads(source['requestItemsJson']), self.request_items)
        self.assertEqual(json.loads(source['offerItemsJson']), self.kp_items)
        self.assertEqual(self.sql('''SELECT line_no,source_request_position,source_offer_position,
            material_name,unit,work_package,quantity,unit_price,amount FROM supplier_invoice_lines WHERE spec_id=%s''',
            (spec_id,)), [(1, 0, 0, self.fixture['materialName'], 'шт', self.fixture['workPackage'], 2, 100, 200)])
        after = self.finances()
        for table in before.keys() - {'supplier_invoices', 'supplier_offer_events'}:
            self.assertEqual(after[table], before[table], table)
        self.assertEqual(len(after['supplier_invoices']), len(before['supplier_invoices']) + 1)
        self.assertEqual(len(after['supplier_offer_events']), len(before['supplier_offer_events']) + 1)

    def test_existing_invoice_replay_does_not_recompute_after_raw_source_change(self):
        saved = self.create(); specs = self.specifications()
        self.raw_sources(self.request_items, [{**self.kp_items[0], 'quantity': '999'}])
        finances = self.finances()
        replay = self.create()
        self.assertEqual(replay, dict(ok=True, id=saved['id'], alreadyExists=True))
        self.assertEqual(self.specifications(), specs)
        self.assertEqual(self.finances(), finances)

    def test_flag_off_preserves_legacy_float_creation_and_later_optin_does_not_backfill(self):
        before = self.specifications()
        with patch.dict(os.environ, SUPPLIER_INVOICE_LINE_SPECS_ENABLED='0'):
            saved = self.create({**self.payload, 'amount': 200.0})
        self.assertEqual(self.specifications(), before)
        self.assertEqual(self.create()['id'], saved['id'])
        self.assertEqual(self.specifications(), before)

    def test_integer_amount_is_supported(self):
        saved = self.create({**self.payload, 'amount': 200, 'vatAmount': 0})
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_invoice_line_specs WHERE invoice_id=%s',
                                 (saved['id'],)), [(1,)])

    def test_unbound_duplicate_is_not_enriched_or_given_spec_under_bound_contract_policy(self):
        duplicate_id = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,supplier_name,project_name,work_package,invoice_number,invoice_date,
             amount,vat_amount,status)
            SELECT company_id,supplier_id,supplier_name,project_name,work_package,%s,%s,200,0,'На утверждении'
            FROM supplier_invoices WHERE id=%s RETURNING id''',
            (self.payload['invoiceNumber'], self.payload['invoiceDate'], type(self).invoice_id))[0][0]
        before, specs = self.finances(), self.specifications()
        self.create(expected=409)
        self.assertEqual(self.sql('SELECT offer_id,request_id,contract_version_id FROM supplier_invoices WHERE id=%s',
                                 (duplicate_id,)), [(None, None, None)])
        self.assertEqual(self.specifications(), specs)
        self.assertEqual(self.finances(), before)

    def test_forced_spec_writer_failure_rolls_back_invoice_spec_and_event(self):
        from .invoice_line_creation import save_invoice_line_spec
        before, specs = self.finances(), self.specifications()
        def fail_after_write(*args):
            save_invoice_line_spec(*args)
            raise HTTPException(503, 'Synthetic spec write failure')
        with patch('backend.features.supplier_offers.routes.save_invoice_line_spec',
                   side_effect=fail_after_write, create=True) as writer:
            self.create(expected=503)
            writer.assert_called_once()
        self.assertEqual(self.finances(), before)
        self.assertEqual(self.specifications(), specs)
        self.assertTrue(self.create()['ok'])

    def test_missing_0022_schema_fails_closed_without_runtime_ddl(self):
        before = self.finances()
        self.sql('ALTER TABLE supplier_invoice_line_specs RENAME TO synthetic_missing_invoice_specs')
        try:
            self.create(expected=503)
            self.assertEqual(self.sql("SELECT to_regclass('public.supplier_invoice_line_specs')"), [(None,)])
            self.assertEqual(self.finances(), before)
        finally:
            self.sql('ALTER TABLE synthetic_missing_invoice_specs RENAME TO supplier_invoice_line_specs')

    def test_optin_float_header_and_nonzero_vat_fail_before_any_writes(self):
        before = self.finances()
        for change in ({'amount': 200.0}, {'vatAmount': '1.00'}):
            with self.subTest(change=change):
                self.create({**self.payload, **change}, expected=409)
                self.assertEqual(self.finances(), before)

    def test_optin_strict_source_mismatch_is_409_without_invoice_or_event(self):
        for change in ({'quantity': '1'}, {'pricePerUnit': '99.00'}, {'workPackage': 'Другое'},
                       {'unit': 'м'}, {'materialName': 'Другой материал'}):
            with self.subTest(change=change):
                self.raw_sources(self.request_items, [{**self.kp_items[0], **change}])
                before = self.finances()
                self.create(expected=409)
                self.assertEqual(self.finances(), before)

    def test_actual_supplier_and_company_authority_denials_create_nothing(self):
        before = self.finances()
        self.create(actor='stranger_supplier', expected=403)
        self.create(actor='stranger', expected=403)
        self.assertEqual(self.finances(), before)

    def test_disabled_line_guard_returns_503_without_invoice_event_or_partial_spec(self):
        before, specs = self.finances(), self.specifications()
        self.sql('ALTER TABLE supplier_invoice_lines DISABLE TRIGGER invoice_line_spec_insert')
        try:
            self.create(expected=503)
            self.assertEqual(self.finances(), before)
            self.assertEqual(self.specifications(), specs)
        finally:
            self.sql('ALTER TABLE supplier_invoice_lines ENABLE TRIGGER invoice_line_spec_insert')
        self.assertTrue(self.create()['ok'])

    def test_concurrent_creation_produces_one_invoice_spec_line_and_event(self):
        before = self.finances()
        start = Barrier(2)
        def create_together():
            start.wait(timeout=5)
            return self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create_together) for _ in range(2)]
            results = [future.result(timeout=25) for future in futures]
        self.assertEqual(results[0]['id'], results[1]['id'])
        self.assertEqual(sum(bool(result.get('alreadyExists')) for result in results), 1)
        self.assertEqual(self.sql('''SELECT count(*) FROM supplier_invoice_line_specs s
            JOIN supplier_invoice_lines l ON l.spec_id=s.id WHERE s.invoice_id=%s''', (results[0]['id'],)), [(1,)])
        after = self.finances()
        self.assertEqual(len(after['supplier_invoices']), len(before['supplier_invoices']) + 1)
        self.assertEqual(len(after['supplier_offer_events']), len(before['supplier_offer_events']) + 1)
        for table in before.keys() - {'supplier_invoices', 'supplier_offer_events'}:
            self.assertEqual(after[table], before[table], table)

    def test_optin_missing_ledger_rejects_before_legacy_ddl_or_preparatory_commit(self):
        before, specs = self.finances(), self.specifications()
        endpoint = next(route.endpoint for route in self.main.app.routes
                        if getattr(route, 'path', '') == '/supplier-offers/{id}/create-invoice')
        cells = dict(zip(endpoint.__code__.co_freevars, endpoint.__closure__))
        cell = cells['get_db']
        original = cell.cell_contents
        statements, commits, opened = [], [], []
        class CursorCollector:
            def __init__(self, cursor):
                self.cursor = cursor

            def __getattr__(self, name):
                return getattr(self.cursor, name)

            def execute(self, statement, params=None):
                statements.append(str(statement))
                return self.cursor.execute(statement, params)

        class ConnectionCollector:
            def __init__(self, connection):
                self.connection = connection

            def __getattr__(self, name):
                return getattr(self.connection, name)

            @property
            def autocommit(self):
                return self.connection.autocommit

            @autocommit.setter
            def autocommit(self, value):
                self.connection.autocommit = value

            def cursor(self, *args, **kwargs):
                return CursorCollector(self.connection.cursor(*args, **kwargs))

            def commit(self):
                commits.append(True)
                return self.connection.commit()

        def tracked_db():
            connection = original()
            opened.append(connection)
            return ConnectionCollector(connection)

        cell.cell_contents = tracked_db
        try:
            with patch('backend.features.supplier_offers.routes.ledger_available', return_value=False):
                self.create(expected=503)
            self.assertEqual(commits, [], 'No preparatory or final commit before prerequisite rejection')
            self.assertFalse(any(sql.lstrip().upper().startswith(('CREATE ', 'ALTER ', 'DROP '))
                                 for sql in statements), statements)
            self.assertTrue(opened and all(conn.closed for conn in opened))
        finally:
            cell.cell_contents = original
            for conn in opened:
                if not conn.closed:
                    conn.rollback()
                    conn.close()
        self.assertEqual(self.finances(), before)
        self.assertEqual(self.specifications(), specs)
