"""Authenticated shipment/receipt races in an empty disposable PostgreSQL DB."""
from decimal import Decimal
import os
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from backend.features.supplier_offers import test_response_postgres as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class ShipmentPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.SupplierResponsePostgresTests.setUpClass.__func__(cls)
    api = support.SupplierResponsePostgresTests.api
    sql = support.SupplierResponsePostgresTests.sql
    quote = support.SupplierResponsePostgresTests.quote

    def approved(self, multi=False):
        offer, path, body = self.quote(multi)
        self.api('supplier', 'PUT', path, body)
        self.api('director', 'PUT', path, {'action': 'select'})
        return offer, path + '/ship', body['itemsKp']

    def receipt(self, delivery, quantity):
        return self.api('foreman', 'PUT', '/supply-deliveries/%s/receive' % delivery['id'],
                        {'receivedQuantity': quantity, 'qualityStatus': 'Принято', 'receivedBy': 'Local test'})

    def test_partial_receipt_remainder_and_replays_preserve_every_row(self):
        offer, path, _ = self.approved()
        body = dict(requestId=str(uuid4()), shippedQuantity=0.6, waybillNumber='BATCH-1')
        first = self.api('supplier', 'POST', path, body)
        received = self.receipt(first, 0.6)
        self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s', (offer['requestId'],)), [('Частично поставлено',)])
        self.assertEqual(self.api('supplier', 'POST', path, body)['id'], first['id'])
        self.api('supplier', 'POST', path, dict(body, shippedQuantity=0.5), expected=409)
        second = self.api('supplier', 'POST', path, dict(requestId=str(uuid4()), shippedQuantity=0.4))
        self.assertNotEqual(first['id'], second['id'])
        self.receipt(second, 0.4)
        self.assertEqual(self.receipt(first, 0.6)['invoiceId'], received['invoiceId'])
        self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s', (offer['requestId'],)), [('Поставлено',)])
        self.assertEqual(self.sql('SELECT COUNT(*), SUM(shipped_quantity) FROM supply_deliveries WHERE offer_id=%s', (offer['id'],)), [(2, 1)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM warehouse_invoices WHERE supply_delivery_id=ANY(%s)', ([first['id'], second['id']],)), [(2,)])
        self.api('supplier', 'POST', path, dict(requestId=str(uuid4()), shippedQuantity=0.1), expected=409)
        self.api('stranger_supplier', 'POST', path, body, expected=403)
        self.api('stranger', 'POST', path, body, expected=403)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s', (offer['requestId'],))
        self.api('supplier', 'POST', path, body, expected=403)

    def test_concurrent_dispatch_only_one_can_consume_remainder(self):
        offer, path, _ = self.approved()
        token = self.main.create_auth_token(self.fixture['users']['supplier'], two_factor_passed=True)
        def send(_):
            return self.client.post(path, json=dict(requestId=str(uuid4()), shippedQuantity=0.7), headers={'Authorization': 'Bearer '+token})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409], [r.text for r in results])
        self.assertEqual(self.sql('SELECT COUNT(*), SUM(shipped_quantity) FROM supply_deliveries WHERE offer_id=%s', (offer['id'],)), [(1, Decimal('0.7'))])

    def test_multiline_zero_skip_retry_race_and_receive_ship_race(self):
        offer, path, items = self.approved(multi=True)
        body = dict(requestId=str(uuid4()), shippedItems=[dict(items[0], shippedQuantity=1), dict(items[1], shippedQuantity=0)])
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, replay = list(pool.map(lambda _: self.api('supplier', 'POST', path, body), range(2)))
        self.assertEqual(first['id'], replay['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            receiving = pool.submit(self.receipt, first, 1)
            shipping = pool.submit(self.api, 'supplier', 'POST', path, dict(requestId=str(uuid4()), shippedItems=[dict(items[1], shippedQuantity=1)]))
            receiving.result(timeout=20)
            second = shipping.result(timeout=20)
        self.receipt(second, 1)
        self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s', (offer['requestId'],)), [('Поставлено',)])
