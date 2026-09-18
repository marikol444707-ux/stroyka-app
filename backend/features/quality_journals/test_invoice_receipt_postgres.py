import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import HTTPException
from . import test_owner_stock_postgres as support
from .invoice_receipt import create_invoice_quality


class InvoiceQualityPostgresTests(support.OwnerStockPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flag = patch.dict(os.environ, {'OWNED_INVOICE_QUALITY_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def object_payload(self):
        payload = self.receipt_payload()
        payload.update(location=self.f['project'], project=self.f['project'], warehouseTarget='object',
                       inventoryOnly=False, supplierId=self.f['supplierId'], supplierName='Test supplier')
        return payload

    def test_receipt_propagates_one_exact_owner_to_header_history_and_journal(self):
        receipt = self.api('director', 'POST', '/warehouse-invoices', self.object_payload())
        owner = (2, self.f['projectId'])
        for table, condition in [('warehouse_invoices', 'id'), ('warehouse_history', 'source_invoice_id'),
                                 ('material_inspection_journal', 'invoice_id')]:
            self.assertEqual(self.sql(f'SELECT company_id,project_id FROM {table} WHERE {condition}=%s', (receipt['id'],)), [owner])
        self.assertEqual(self.sql('SELECT source_type,source_id,source_item_key FROM material_inspection_journal WHERE invoice_id=%s',
                                 (receipt['id'],)), [('warehouse_invoice', receipt['id'], 'invoice-line:0')])

    def test_new_receipts_do_not_require_historical_director_or_admin_approval(self):
        # The fixture has no review-audit migration. Normal receipts must work
        # with the historical feature both off and on, without its workflow.
        for flag in ('0', '1'):
            with self.subTest(review_flag=flag), patch.dict(os.environ, {'OWNED_QUALITY_REVIEW_ENABLED': flag}):
                receipt = self.api('director', 'POST', '/warehouse-invoices', self.object_payload())
                self.assertEqual(self.sql('SELECT company_id,project_id FROM material_inspection_journal WHERE invoice_id=%s',
                                          (receipt['id'],)), [(2, self.f['projectId'])])

    def call_quality(self, invoice_id, **overrides):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor() as cur:
                args = dict(company_id=2, project_id=self.f['projectId'], invoice_id=invoice_id,
                            line_index=0, name=self.f['materialName'], quantity=2, unit='шт', work_package='Основная')
                return create_invoice_quality(cur, **{**args, **overrides})
        finally:
            conn.close()

    def test_exact_replay_does_not_duplicate_and_changed_line_is_conflict(self):
        receipt = self.api('director', 'POST', '/warehouse-invoices', self.object_payload())
        self.assertEqual(self.call_quality(receipt['id']), {'inspections': 0, 'cables': 0})
        with self.assertRaises(HTTPException) as error:
            self.call_quality(receipt['id'], quantity=3)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.sql('SELECT count(*) FROM material_inspection_journal WHERE invoice_id=%s', (receipt['id'],)), [(1,)])

    def test_foreign_invoice_cannot_generate_our_quality_record(self):
        other_project = self.sql("INSERT INTO projects(name,company_id) VALUES(%s,3) RETURNING id", (self.f['project'],))[0][0]
        invoice = self.sql('INSERT INTO warehouse_invoices(company_id,project_id) VALUES(3,%s) RETURNING id', (other_project,))[0][0]
        # This test intentionally adds a foreign fixture after the base snapshot.
        try:
            with self.assertRaises(HTTPException) as error:
                self.call_quality(invoice)
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(self.sql('SELECT count(*) FROM material_inspection_journal WHERE invoice_id=%s', (invoice,)), [(0,)])
        finally:
            self.sql('DELETE FROM warehouse_invoices WHERE id=%s', (invoice,))

    def test_late_quality_failure_rolls_back_entire_receipt(self):
        tables = ('warehouse_invoices', 'warehouse_history', 'material_inspection_journal', 'materials')
        before = [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables]
        with patch('backend.features.quality_journals.invoice_receipt.create_invoice_quality', side_effect=HTTPException(409, 'Synthetic conflict')):
            self.api('director', 'POST', '/warehouse-invoices', self.object_payload(), expected=409)
        self.assertEqual([self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables], before)

    def test_same_company_duplicate_names_still_fail_without_writes(self):
        self.sql("INSERT INTO projects(name,company_id) VALUES(%s,2)", (self.f['project'],))
        before = self.sql('SELECT * FROM warehouse_invoices ORDER BY id')
        self.api('director', 'POST', '/warehouse-invoices', self.object_payload(), expected=409)
        self.assertEqual(self.sql('SELECT * FROM warehouse_invoices ORDER BY id'), before)

    def test_identical_document_lines_keep_distinct_ordinals(self):
        payload = self.object_payload()
        payload['items'].append(dict(payload['items'][0]))
        receipt = self.api('director', 'POST', '/warehouse-invoices', payload)
        self.assertEqual(self.sql('SELECT source_item_key FROM material_inspection_journal WHERE invoice_id=%s ORDER BY id',
                                 (receipt['id'],)), [('invoice-line:0',), ('invoice-line:1',)])

    def test_concurrent_internal_replay_serializes_on_invoice(self):
        invoice = self.sql('INSERT INTO warehouse_invoices(company_id,project_id) VALUES(2,%s) RETURNING id', (self.f['projectId'],))[0][0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.call_quality, invoice) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(row['inspections'] for row in results), [0, 1])
        self.assertEqual(self.sql('SELECT count(*) FROM material_inspection_journal WHERE invoice_id=%s', (invoice,)), [(1,)])

    def test_cable_and_inspection_share_owner_and_source(self):
        invoice = self.sql('INSERT INTO warehouse_invoices(company_id,project_id) VALUES(2,%s) RETURNING id', (self.f['projectId'],))[0][0]
        cable = self.main._detect_cable_info('ВВГнг 3х2,5')
        result = self.call_quality(invoice, name='ВВГнг 3х2,5', unit='м', cable_info=cable)
        self.assertEqual(result, {'inspections': 1, 'cables': 1})
        self.assertEqual(self.call_quality(invoice, name='ВВГнг 3х2,5', unit='м', cable_info=cable), {'inspections': 0, 'cables': 0})
        for table in ('material_inspection_journal', 'cable_journal'):
            self.assertEqual(self.sql(f'SELECT company_id,project_id,source_type,source_id FROM {table} WHERE invoice_id=%s', (invoice,)),
                             [(2, self.f['projectId'], 'warehouse_invoice', invoice)])

    def test_fractional_cable_replay_and_precision_rejection(self):
        invoice = self.sql('INSERT INTO warehouse_invoices(company_id,project_id) VALUES(2,%s) RETURNING id', (self.f['projectId'],))[0][0]
        args = dict(quantity='1.23', name='Cable', unit='м', cable_info={'isCable': True})
        self.assertEqual(self.call_quality(invoice, **args), {'inspections': 1, 'cables': 1})
        self.assertEqual(self.call_quality(invoice, **args), {'inspections': 0, 'cables': 0})
        with self.assertRaises(HTTPException) as error:
            self.call_quality(invoice, **{**args, 'quantity': '1.234'})
        self.assertEqual(error.exception.status_code, 400)

    def test_repeatable_read_rejected_without_journal_writes(self):
        conn = self.main.get_db()
        try:
            conn.set_session(isolation_level='REPEATABLE READ', autocommit=False)
            with conn, conn.cursor() as cur:
                with self.assertRaises(HTTPException) as error:
                    create_invoice_quality(cur, company_id=2, project_id=self.f['projectId'], invoice_id=1,
                                           line_index=0, name='Material', quantity=1, unit='шт')
                self.assertEqual(error.exception.status_code, 409)
        finally:
            conn.close()

    def test_conflicting_provenance_is_not_accepted_as_replay(self):
        receipt = self.api('director', 'POST', '/warehouse-invoices', self.object_payload())
        self.sql("UPDATE material_inspection_journal SET source_type='supply_delivery' WHERE invoice_id=%s", (receipt['id'],))
        with self.assertRaises(HTTPException) as error:
            self.call_quality(receipt['id'])
        self.assertEqual(error.exception.status_code, 409)
