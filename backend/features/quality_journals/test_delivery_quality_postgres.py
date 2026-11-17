from backend.features.warehouse_receipts.test_http_support import confirm_test_receipt, physical_receipt_payload
import copy
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import HTTPException
from . import test_owner_stock_postgres as support


class DeliveryQualityPostgresTests(support.OwnerStockPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flags = patch.dict(os.environ, {'OWNED_DELIVERY_SOURCES_ENABLED': '1',
                                       'OWNED_DELIVERY_QUALITY_ENABLED': '1'})
        flags.start()
        cls.addClassCleanup(flags.stop)

    def prepare_supplier_delivery(self):
        self.sql("INSERT INTO company_requisites(company_id,full_name,inn) SELECT 2,'Synthetic buyer','7702222222' WHERE NOT EXISTS (SELECT 1 FROM company_requisites WHERE company_id=2)")
        delivery, invoice = super().prepare_supplier_delivery()
        self._receipt_payloads = {delivery: physical_receipt_payload(self, 'director', delivery, 2)}
        return delivery, invoice

    def receive(self, delivery, expected=200, **changes):
        return confirm_test_receipt(self, 'director', delivery,
            {'companyId': 2, 'receivedQuantity': 2, 'qualityStatus': 'Принято', **changes}, expected=expected)

    def test_quality_has_both_sources_and_exact_owner(self):
        delivery, _ = self.prepare_supplier_delivery()
        result = self.receive(delivery, qualityNotes='Проверено на объекте')
        expected = [(2, self.f['projectId'], delivery, result['invoiceId'],
                     'warehouse_invoice', result['invoiceId'], True, 'Проверено на объекте')]
        query = '''SELECT company_id,project_id,delivery_id,invoice_id,source_type,source_id,
                   inspected,remarks FROM material_inspection_journal WHERE delivery_id=%s'''
        self.assertEqual(self.sql(query, (delivery,)), expected)
        self.assertTrue(self.receive(delivery)['alreadyReceived'])
        self.assertEqual(self.sql(query, (delivery,)), expected)

    def test_partial_receipt_and_concurrent_replay_do_not_double_stock(self):
        delivery, _ = self.prepare_supplier_delivery()
        first = self.receive(delivery, receivedQuantity=1, qualityStatus='Частично')
        for table, column, where in (
                ('material_inspection_journal', 'quantity', 'delivery_id'),
                ('warehouse_history', 'quantity', 'source_invoice_id')):
            source = delivery if where == 'delivery_id' else first['invoiceId']
            self.assertEqual(self.sql('SELECT company_id,project_id,'+column+' FROM '+table+' WHERE '+where+'=%s',
                (source,)), [(2,self.f['projectId'],1)])
        tables = ('supply_deliveries','warehouse_invoices','warehouse_history','materials','material_inspection_journal','cable_journal')
        before = [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables]
        payload = copy.deepcopy(self._receipt_payloads[delivery])
        payload['actualLines'][0].update(receivedQuantity=1,qualityStatus='Частично')
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.request('POST','/warehouse-receipts/confirm',payload),range(2)))
        self.assertIn(200,[response.status_code for response in responses])
        results = []
        for response in responses:
            if response.status_code == 409:
                self.assertEqual(response.json()['detail'],'Документы снабжения заняты другой операцией. Повторите запрос.')
                # An explicit retry after the winner finishes uses exactly the same command.
                results.append(self.api('director','POST','/warehouse-receipts/confirm',payload))
            else:
                self.assertEqual(response.status_code,200,response.text)
                results.append(response.json())
        self.assertTrue(all(r['alreadyReceived'] and r['warehouseInvoiceIds']==[first['invoiceId']] for r in results))
        self.assertEqual([self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables], before)

    def test_missing_quality_on_replay_is_not_silently_rebuilt(self):
        delivery, _ = self.prepare_supplier_delivery()
        self.receive(delivery)
        self.sql('DELETE FROM material_inspection_journal WHERE delivery_id=%s', (delivery,))
        self.receive(delivery, expected=409)

    def test_late_quality_failure_rolls_back_all_receipt_records(self):
        delivery, _ = self.prepare_supplier_delivery()
        tables = ('supply_deliveries', 'warehouse_invoices', 'warehouse_history', 'materials',
                  'material_inspection_journal', 'cable_journal', 'supplier_invoices', 'supply_history')
        before = [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables]
        with patch('backend.features.quality_journals.delivery_receipt.create_delivery_quality',
                   side_effect=HTTPException(409, 'Synthetic conflict')):
            self.receive(delivery, expected=409)
        self.assertEqual([self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables], before)

    def test_zero_quantity_has_no_quality_row(self):
        delivery, _ = self.prepare_supplier_delivery()
        self.receive(delivery, receivedQuantity=0)
        self.assertTrue(self.receive(delivery)['alreadyReceived'])
        self.assertEqual(self.sql('SELECT count(*) FROM material_inspection_journal WHERE delivery_id=%s', (delivery,)), [(0,)])

    def test_rejected_material_is_inspected_without_stock(self):
        delivery, _ = self.prepare_supplier_delivery()
        result = self.receive(delivery, qualityStatus='Брак')
        self.assertEqual(self.sql('SELECT visual_inspection_result FROM material_inspection_journal WHERE delivery_id=%s', (delivery,)), [('Брак',)])
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_history WHERE source_invoice_id=%s', (result['invoiceId'],)), [(0,)])
        self.assertTrue(self.receive(delivery)['alreadyReceived'])

    def test_quality_cannot_run_without_owned_sources(self):
        delivery, _ = self.prepare_supplier_delivery()
        with patch.dict(os.environ, {'OWNED_DELIVERY_SOURCES_ENABLED': '0'}):
            self.receive(delivery, expected=503)
        self.assertEqual(self.sql('SELECT received_at FROM supply_deliveries WHERE id=%s', (delivery,)), [(None,)])

    def test_legacy_journal_is_not_adopted_on_replay(self):
        delivery, _ = self.prepare_supplier_delivery()
        with patch.dict(os.environ, {'OWNED_DELIVERY_QUALITY_ENABLED': '0'}):
            self.receive(delivery)
        before = self.sql('SELECT * FROM material_inspection_journal WHERE delivery_id=%s', (delivery,))
        self.receive(delivery, expected=409)
        self.assertEqual(self.sql('SELECT * FROM material_inspection_journal WHERE delivery_id=%s', (delivery,)), before)

    def test_conflicting_reference_fails_replay(self):
        delivery, _ = self.prepare_supplier_delivery()
        self.receive(delivery)
        self.sql("UPDATE material_inspection_journal SET source_type='supply_delivery' WHERE delivery_id=%s", (delivery,))
        self.receive(delivery, expected=409)

    def test_cable_receipt_has_two_owned_journals(self):
        delivery, _ = self.prepare_supplier_delivery()
        cable_name = 'ВВГнг 3х2,5'
        self.sql("UPDATE supply_deliveries SET material_name=%s,unit='метр' WHERE id=%s", (cable_name, delivery))
        self.sql("UPDATE estimates SET sections_json=replace(replace(sections_json,%s,%s),'шт','м') WHERE project_id=%s",
                 (self.f['materialName'], cable_name, self.f['projectId']))
        self._receipt_payloads[delivery] = physical_receipt_payload(self, 'director', delivery, 2)
        result = self.receive(delivery)
        for table in ('material_inspection_journal', 'cable_journal'):
            self.assertEqual(self.sql(f'SELECT company_id,project_id,invoice_id FROM {table} WHERE delivery_id=%s', (delivery,)),
                             [(2, self.f['projectId'], result['invoiceId'])])
        self.assertTrue(self.receive(delivery)['alreadyReceived'])

    def test_excess_precision_rolls_back_instead_of_rounding(self):
        delivery, _ = self.prepare_supplier_delivery()
        self.receive(delivery, expected=400, receivedQuantity=1.23456)
        self.assertEqual(self.sql('SELECT received_at,project_id FROM supply_deliveries WHERE id=%s', (delivery,)), [(None, None)])
