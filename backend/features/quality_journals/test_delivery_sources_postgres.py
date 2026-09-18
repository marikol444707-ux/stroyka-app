"""Exact automatic-receipt source owners, on an explicit isolated database."""
import os
from unittest.mock import patch
from fastapi import HTTPException

from . import test_owner_stock_postgres as support


class DeliverySourcesPostgresTests(support.OwnerStockPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flag = patch.dict(os.environ, {'OWNED_DELIVERY_SOURCES_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def receive(self, delivery, expected=200, **overrides):
        return self.api('director', 'PUT', f'/supply-deliveries/{delivery}/receive',
            {**dict(companyId=2, receivedQuantity=2, qualityStatus='Принято'), **overrides}, expected=expected)

    def test_receipt_sources_share_exact_owner_and_replay_is_stable(self):
        delivery, _ = self.prepare_supplier_delivery()
        accepted = self.receive(delivery)
        for table, column, value in [('supply_deliveries', 'id', delivery),
                                    ('warehouse_invoices', 'id', accepted['invoiceId']),
                                    ('warehouse_history', 'source_invoice_id', accepted['invoiceId'])]:
            self.assertEqual(self.sql(f'SELECT company_id,project_id FROM {table} WHERE {column}=%s', (value,)),
                             [(2, self.f['projectId'])])
        self.assertTrue(self.receive(delivery)['alreadyReceived'])

    def test_duplicate_project_name_fails_before_acceptance(self):
        delivery, _ = self.prepare_supplier_delivery()
        self.sql('INSERT INTO projects(name,company_id) VALUES(%s,2)', (self.f['project'],))
        self.receive(delivery, expected=409)
        self.assertEqual(self.sql('SELECT received_at,project_id FROM supply_deliveries WHERE id=%s', (delivery,)), [(None, None)])

    def test_preexisting_receipt_is_not_silently_bound(self):
        delivery, _ = self.prepare_supplier_delivery()
        with patch.dict(os.environ, {'OWNED_DELIVERY_SOURCES_ENABLED': '0'}):
            self.receive(delivery)
        before = self.sql('SELECT * FROM warehouse_invoices WHERE supply_delivery_id=%s', (delivery,))
        self.receive(delivery, expected=409)
        self.assertEqual(self.sql('SELECT * FROM warehouse_invoices WHERE supply_delivery_id=%s', (delivery,)), before)

    def test_late_source_failure_rolls_back_acceptance_and_stock(self):
        delivery, _ = self.prepare_supplier_delivery()
        tables = ('supply_deliveries', 'warehouse_invoices', 'warehouse_history', 'materials',
                  'material_inspection_journal', 'supplier_invoices', 'supply_history')
        before = [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables]
        with patch('backend.features.quality_journals.delivery_sources.bind_new_delivery_sources',
                   side_effect=HTTPException(409, 'Synthetic ownership conflict')):
            self.receive(delivery, expected=409)
        self.assertEqual([self.sql('SELECT * FROM '+table+' ORDER BY id') for table in tables], before)

    def test_foreign_same_name_project_does_not_change_owner(self):
        delivery, _ = self.prepare_supplier_delivery()
        self.sql('INSERT INTO projects(name,company_id) VALUES(%s,3)', (self.f['project'],))
        accepted = self.receive(delivery)
        self.assertEqual(self.sql('SELECT company_id,project_id FROM warehouse_invoices WHERE id=%s',
                                 (accepted['invoiceId'],)), [(2, self.f['projectId'])])

    def test_missing_movement_on_replay_is_conflict_not_repair(self):
        delivery, _ = self.prepare_supplier_delivery()
        accepted = self.receive(delivery)
        self.sql('DELETE FROM warehouse_history WHERE source_invoice_id=%s', (accepted['invoiceId'],))
        self.receive(delivery, expected=409)
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_history WHERE source_invoice_id=%s',
                                 (accepted['invoiceId'],)), [(0,)])

    def test_zero_receipt_keeps_owner_without_invoice_or_movement(self):
        delivery, _ = self.prepare_supplier_delivery()
        accepted = self.receive(delivery, receivedQuantity=0)
        self.assertIsNone(accepted['invoiceId'])
        self.assertTrue(self.receive(delivery, receivedQuantity=0)['alreadyReceived'])
        self.assertEqual(self.sql('SELECT project_id FROM supply_deliveries WHERE id=%s', (delivery,)), [(self.f['projectId'],)])

    def test_rejected_quality_keeps_invoice_but_no_stock_movement(self):
        delivery, _ = self.prepare_supplier_delivery()
        accepted = self.receive(delivery, qualityStatus='Брак')
        self.assertEqual(self.sql('SELECT project_id FROM warehouse_invoices WHERE id=%s',
                                 (accepted['invoiceId'],)), [(self.f['projectId'],)])
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_history WHERE source_invoice_id=%s',
                                 (accepted['invoiceId'],)), [(0,)])
        self.assertTrue(self.receive(delivery)['alreadyReceived'])
