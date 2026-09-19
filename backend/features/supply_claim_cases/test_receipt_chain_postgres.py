"""Real request → offer → shipment → owned receipt → audited claim, local PG only."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.quality_journals import test_owner_stock_postgres as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated socket-only PostgreSQL')
class ReceiptClaimChainPostgresTests(unittest.TestCase):
    sql = support.OwnerStockPostgresTests.sql
    api = support.OwnerStockPostgresTests.api
    request = support.OwnerStockPostgresTests.request
    setUp = support.OwnerStockPostgresTests.setUp
    prepare_supplier_delivery = support.OwnerStockPostgresTests.prepare_supplier_delivery

    @classmethod
    def setUpClass(cls):
        support.OwnerStockPostgresTests.setUpClass.__func__(cls)
        root = Path(__file__).resolve().parents[3]
        connection = cls.main.get_db()
        try:
            with connection, connection.cursor() as cur:
                for name in ('0027_work_material_accounting', '0033_supply_claim_cases'):
                    spec = importlib.util.spec_from_file_location(name, root / 'migrations/versions' / (name+'.py'))
                    migration = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(migration)
                    with patch.object(migration, 'op', SimpleNamespace(execute=cur.execute)):
                        migration.upgrade()
        finally:
            connection.close()
        flags = patch.dict(os.environ, {'OWNED_DELIVERY_SOURCES_ENABLED': '1',
            'OWNED_DELIVERY_QUALITY_ENABLED': '1', 'SUPPLY_CLAIMS_ENABLED': '1'})
        flags.start()
        cls.addClassCleanup(flags.stop)

    def receive(self, delivery, quantity, quality):
        return self.api('director', 'PUT', f'/supply-deliveries/{delivery}/receive',
                        {'companyId': 2, 'receivedQuantity': quantity, 'qualityStatus': quality})

    def business_snapshot(self):
        return [(table, self.sql('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY 1'))
                for table in ('supply_deliveries', 'supply_requests', 'supplier_offers', 'materials',
                    'warehouse_invoices', 'warehouse_history', 'material_inspection_journal',
                    'cable_journal', 'supplier_invoices', 'project_payments')]

    def problem_chain(self, quantity, quality, stock, claim_type):
        delivery, _ = self.prepare_supplier_delivery()
        received = self.receive(delivery, quantity, quality)
        claim_id = received['claimId']
        self.assertIsInstance(claim_id, int)
        path = f'/supply-claims/{claim_id}/case'
        card = self.api('supplier', 'GET', path)
        self.assertEqual((card['claim']['companyId'], card['claim']['deliveryId'], card['claim']['claimType']),
                         (2, delivery, claim_type))
        self.assertTrue(card['canReply'])
        self.assertEqual(self.sql('SELECT COALESCE(sum(quantity),0) FROM materials WHERE company_id=2 AND project=%s AND name=%s',
                                 (self.f['project'], self.f['materialName'])), [(stock,)])
        before = self.business_snapshot()
        for version, (actor, action) in enumerate((('supplier', 'reply'), ('director', 'resolve')), 1):
            body = {'action': action, 'text': 'Synthetic '+action, 'expectedVersion': version,
                    'expectedCompanyId': 2, 'expectedActorId': self.f['users'][actor]['id'], 'requestId': str(uuid4())}
            result = self.api(actor, 'POST', path, body)
            self.assertEqual(self.api(actor, 'POST', path, body), result)
        self.assertEqual(self.business_snapshot(), before)
        replay = self.receive(delivery, quantity, quality)
        self.assertTrue(replay['alreadyReceived'])
        self.assertEqual(replay['claimId'], claim_id)
        self.assertEqual(self.business_snapshot(), before)
        final = self.api('supplier', 'GET', path)
        self.assertEqual(final['claim']['status'], 'Решена')
        self.assertEqual(len(final['history']), 2)
        self.assertFalse(final['canReply'])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claims WHERE delivery_id=%s', (delivery,)), [(1,)])
        self.api('stranger', 'GET', path, expected=404)

    def test_shortage_receipt_to_claim_resolution_preserves_one_actual_stock_unit(self):
        self.problem_chain(1, 'Частично', 1, 'Недостача')

    def test_defective_receipt_to_claim_resolution_never_enters_usable_stock(self):
        self.problem_chain(2, 'Брак', 0, 'Брак')

    def test_zero_receipt_to_claim_resolution_has_no_stock(self):
        self.problem_chain(0, 'Недостача', 0, 'Недостача')

    def test_complete_accepted_receipt_has_no_claim_and_exact_stock(self):
        delivery, _ = self.prepare_supplier_delivery()
        received = self.receive(delivery, 2, 'Принято')
        self.assertIsNone(received['claimId'])
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2 AND project=%s AND name=%s',
                                 (self.f['project'], self.f['materialName'])), [(2,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claims WHERE delivery_id=%s', (delivery,)), [(0,)])
        before = self.business_snapshot()
        self.assertTrue(self.receive(delivery, 2, 'Принято')['alreadyReceived'])
        self.assertEqual(self.business_snapshot(), before)
