"""Allocated RFQ lines, independent awards and fulfilment on disposable PostgreSQL."""
from importlib import import_module
import json
import os
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from backend.features.supplier_access import test_postgres_chain as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class ItemScopesPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.PostgresSupplyChainTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(import_module('migrations.versions.0051_supplier_offer_item_scopes').SCHEMA_SQL)
                cur.execute('SELECT id FROM suppliers WHERE user_id=%s',
                            (cls.fixture['users']['stranger_supplier']['id'],))
                cls.second_supplier = cur.fetchone()[0]
                cur.execute('''INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id)
                               SELECT id,%s,platform_account_id FROM companies WHERE id=%s''',
                            (cls.second_supplier, cls.fixture['companyId']))
                cur.execute('SELECT sections_json FROM estimates WHERE id=%s', (cls.fixture['estimateId'],))
                sections = json.loads(cur.fetchone()[0])
                base = sections[0]['items'][0]
                sections[0]['items'] = [dict(base, id='scoped-%s' % pos,
                    name=base['name'] + ' scope-%s' % pos, quantity=1000) for pos in range(3)]
                cur.execute('UPDATE estimates SET sections_json=%s WHERE id=%s',
                            (json.dumps(sections), cls.fixture['estimateId']))
            conn.commit()
        finally:
            conn.close()

    api = support.PostgresSupplyChainTests.api
    sql = support.PostgresSupplyChainTests.sql

    def request(self):
        f = self.fixture
        items = [dict(materialName=f['materialName'] + ' scope-%s' % pos,
                      quantity=2, unit=f['unit'], workPackage=f['workPackage']) for pos in range(3)]
        request = self.api('director', 'POST', '/supply-requests', dict(
            project=f['project'], companyId=f['companyId'], workPackage=f['workPackage'], items=items))
        path = '/supply-requests/%s' % request['id']
        self.api('foreman', 'PUT', path, {'action': 'confirm_prorab'})
        self.api('director', 'PUT', path, {'action': 'approve_director'})
        return request, path, items

    def allocated(self):
        request, path, items = self.request()
        self.api('director', 'POST', path + '/request-kp', {
            'supplierIds': [self.fixture['supplierId'], self.second_supplier],
            'supplierItems': {str(self.fixture['supplierId']): [0, 1], str(self.second_supplier): [1, 2]}})
        offers = {}
        for actor in ('supplier', 'stranger_supplier'):
            offers[actor] = next(row for row in self.api(actor, 'GET', '/supplier-offers')
                                 if row['requestId'] == request['id'])
        return request, items, offers

    def respond(self, actor, offer, items, positions, expected=200):
        lines = [dict(items[pos], requestPosition=pos, pricePerUnit=100 + pos * 10) for pos in positions]
        return self.api(actor, 'PUT', '/supplier-offers/%s' % offer['id'], dict(
            action='respond', requestId=str(uuid4()), expectedRespondedAt=None,
            pricePerUnit=100, totalPrice=sum(line['quantity'] * line['pricePerUnit'] for line in lines),
            deliveryDays=1, paymentTerms='Постоплата', itemsKp=lines), expected=expected)

    def test_supplier_sees_only_assigned_lines_and_cannot_respond_with_unassigned_material(self):
        request, items, offers = self.allocated()
        for actor, positions in (('supplier', [0, 1]), ('stranger_supplier', [1, 2])):
            scope = json.loads(offers[actor]['requestedItemsJson'])
            self.assertEqual([line['requestPosition'] for line in scope], positions)
            visible = next(row for row in self.api(actor, 'GET', '/supply-requests') if row['id'] == request['id'])
            self.assertEqual([line['materialName'] for line in json.loads(visible['itemsJson'])],
                             [items[pos]['materialName'] for pos in positions])
        self.respond('supplier', offers['supplier'], items, [0, 2], expected=422)
        self.api('stranger_supplier', 'PUT', '/supplier-offers/%s' % offers['supplier']['id'],
                 {'action': 'respond', 'totalPrice': 1}, expected=403)
        self.respond('supplier', offers['supplier'], items, [0, 1])

    def test_supplier_requested_scope_excludes_internal_estimate_prices_and_controls(self):
        request, path, items = self.request()
        private_items = [dict(line, estimateControl={'status': 'internal-only', 'estimatePrice': 98765},
            priceMaterial=98765, estimatePrice=98765, estimatedPrice=98765, lineTotal=197530,
            price=98765, companyBudget=98765) for line in items]
        self.sql('UPDATE supply_requests SET items_json=%s WHERE id=%s',
                 (json.dumps(private_items), request['id']))
        self.api('director', 'POST', path + '/request-kp', {
            'supplierIds': [self.fixture['supplierId']],
            'supplierItems': {str(self.fixture['supplierId']): [1]}})
        offer = next(row for row in self.api('supplier', 'GET', '/supplier-offers')
                     if row['requestId'] == request['id'])
        scope = json.loads(offer['requestedItemsJson'])
        self.assertEqual(scope[0]['requestPosition'], 1)
        self.assertEqual(scope[0]['materialName'], items[1]['materialName'])
        for private_field in ('estimateControl', 'priceMaterial', 'estimatePrice', 'estimatedPrice',
                              'lineTotal', 'price', 'companyBudget'):
            self.assertNotIn(private_field, scope[0])
        self.assertNotIn('98765', offer['requestedItemsJson'])

    def test_independent_awards_keep_other_quotes_available_and_fulfil_only_selected_lines(self):
        request, items, offers = self.allocated()
        self.respond('supplier', offers['supplier'], items, [0, 1])
        self.respond('stranger_supplier', offers['stranger_supplier'], items, [1, 2])
        first_path = '/supplier-offers/%s' % offers['supplier']['id']
        second_path = '/supplier-offers/%s' % offers['stranger_supplier']['id']
        self.api('director', 'PUT', first_path, {'action': 'select', 'itemPositions': [0]})
        second = next(row for row in self.api('director', 'GET', '/supplier-offers')
                      if row['id'] == offers['stranger_supplier']['id'])
        self.assertEqual(second['status'], 'Получено')
        self.api('director', 'PUT', second_path, {'action': 'select', 'itemPositions': [1, 2]})
        first = next(row for row in self.api('director', 'GET', '/supplier-offers')
                     if row['id'] == offers['supplier']['id'])
        self.assertEqual(first['totalPrice'], 200)
        self.assertEqual([line['requestPosition'] for line in json.loads(first['awardedItemsJson'])], [0])
        self.assertEqual([line['requestPosition'] for line in json.loads(first['itemsKpJson'])], [0])
        events = self.sql("SELECT payload_json FROM supplier_offer_events WHERE offer_id=%s AND event_type='responded'",
                          (first['id'],))
        self.assertTrue(any(items[1]['materialName'] in str(row[0]) for row in events), 'Full original quote retained in history')
        invoice = self.api('supplier', 'POST', first_path + '/create-invoice',
                           dict(invoiceNumber='SCOPE-' + str(request['id']), amount=200, vatAmount=0))
        self.assertEqual(self.sql('SELECT amount FROM supplier_invoices WHERE id=%s', (invoice['id'],)), [(200,)])
        self.api('supplier', 'POST', first_path + '/ship', dict(requestId=str(uuid4()),
                 shippedItems=[dict(items[1], requestPosition=1, shippedQuantity=2)]), expected=400)
        shipment = self.api('supplier', 'POST', first_path + '/ship', dict(requestId=str(uuid4()),
                 shippedItems=[dict(items[0], requestPosition=0, shippedQuantity=2)]))
        self.assertEqual(shipment['materialName'], items[0]['materialName'])
        self.api('foreman', 'PUT', '/supply-deliveries/%s/receive' % shipment['id'],
                 dict(receivedQuantity=2, qualityStatus='Принято', receivedBy='Synthetic scoped test'))
        self.assertEqual(self.sql('SELECT delivery_status FROM supplier_offers WHERE id=%s', (first['id'],)), [('Поставлено',)])
        self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s', (request['id'],)), [('Частично поставлено',)])
        for pos in (1, 2):
            delivery = self.api('stranger_supplier', 'POST', second_path + '/ship', dict(requestId=str(uuid4()),
                shippedItems=[dict(items[pos], requestPosition=pos, shippedQuantity=2)]))
            self.api('foreman', 'PUT', '/supply-deliveries/%s/receive' % delivery['id'],
                     dict(receivedQuantity=2, qualityStatus='Принято', receivedBy='Synthetic scoped test'))
            expected_status = 'Частично поставлено' if pos == 1 else 'Поставлено'
            self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s', (request['id'],)), [(expected_status,)])
            self.assertEqual(self.sql('SELECT delivery_status FROM supplier_offers WHERE id=%s',
                                      (offers['stranger_supplier']['id'],)), [(expected_status,)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supply_deliveries WHERE offer_id=%s', (first['id'],)), [(1,)])

    def test_overlapping_award_is_rejected_without_changing_second_quote(self):
        _, items, offers = self.allocated()
        self.respond('supplier', offers['supplier'], items, [0, 1])
        self.respond('stranger_supplier', offers['stranger_supplier'], items, [1, 2])
        self.api('director', 'PUT', '/supplier-offers/%s' % offers['supplier']['id'],
                 {'action': 'select', 'itemPositions': [1]})
        self.api('director', 'PUT', '/supplier-offers/%s' % offers['stranger_supplier']['id'],
                 {'action': 'select', 'itemPositions': [1]}, expected=409)
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s',
                                  (offers['stranger_supplier']['id'],)), [('Получено',)])

    def test_concurrent_overlapping_awards_have_exactly_one_winner(self):
        _, items, offers = self.allocated()
        self.respond('supplier', offers['supplier'], items, [0, 1])
        self.respond('stranger_supplier', offers['stranger_supplier'], items, [1, 2])
        token = self.main.create_auth_token(self.fixture['users']['director'], two_factor_passed=True)
        def select(offer):
            return self.client.put('/supplier-offers/%s' % offer['id'],
                json={'action': 'select', 'itemPositions': [1]}, headers={'Authorization': 'Bearer ' + token})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(select, offers.values()))
        self.assertEqual(sorted(row.status_code for row in results), [200, 409], [row.text for row in results])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supplier_offers WHERE id=ANY(%s) AND status='Утверждено'",
                                  ([offer['id'] for offer in offers.values()],)), [(1,)])

    def test_invalid_allocation_does_not_create_partial_offers(self):
        request, path, _ = self.request()
        self.api('director', 'POST', path + '/request-kp', {
            'supplierIds': [self.fixture['supplierId'], self.second_supplier],
            'supplierItems': {str(self.fixture['supplierId']): [0], str(self.second_supplier): [9]}}, expected=422)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_offers WHERE request_id=%s', (request['id'],)), [(0,)])
