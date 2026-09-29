"""Quote submission retries against authenticated HTTP and disposable PostgreSQL."""
import json
import os
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from backend.features.supplier_access import test_postgres_chain as chain_support
from .test_retry_support import api_after_busy


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class SupplierResponsePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chain_support.PostgresSupplyChainTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT sections_json FROM estimates WHERE id=%s', (cls.fixture['estimateId'],))
                sections = json.loads(cur.fetchone()[0])
                item = sections[0]['items'][0]
                item['quantity'] = 100
                sections[0]['items'].append(dict(item, id='chain-material-2', name=item['name'] + ' second'))
                cur.execute('UPDATE estimates SET sections_json=%s WHERE id=%s', (json.dumps(sections), cls.fixture['estimateId']))
            conn.commit()
        finally:
            conn.close()
    api = chain_support.PostgresSupplyChainTests.api
    sql = chain_support.PostgresSupplyChainTests.sql

    def quote(self, multi=False):
        f = self.fixture
        item = {key: f[key] for key in ('materialName', 'quantity', 'unit', 'workPackage')}
        item['quantity'] = 1
        items = [item, dict(item, materialName=item['materialName'] + ' second')] if multi else [item]
        request = self.api('director', 'POST', '/supply-requests', {
            'project': f['project'], 'companyId': f['companyId'], 'workPackage': f['workPackage'], 'items': items})
        path = '/supply-requests/' + str(request['id'])
        self.api('foreman', 'PUT', path, {'action': 'confirm_prorab'})
        self.api('director', 'PUT', path, {'action': 'approve_director'})
        self.api('director', 'POST', path + '/request-kp', {'supplierIds': [f['supplierId']]})
        offer = next(o for o in self.api('supplier', 'GET', '/supplier-offers') if o['requestId'] == request['id'])
        body = dict(action='respond', requestId=str(uuid4()), expectedRespondedAt=None,
                    pricePerUnit=100, totalPrice=250 if multi else 100, deliveryDays=1, paymentTerms='Постоплата',
                    itemsKp=[dict(line, pricePerUnit=100 + 50 * index) for index, line in enumerate(items)])
        return offer, '/supplier-offers/' + str(offer['id']), body

    def test_concurrent_retry_one_event_buyer_visibility_and_selected_offer_immutable(self):
        offer, path, body = self.quote()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: api_after_busy(self, 'supplier', 'PUT', path, body), range(2)))
        self.assertEqual([r['id'] for r in results], [offer['id']] * 2)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supplier_offer_events WHERE offer_id=%s AND event_type='responded'", (offer['id'],)), [(1,)])
        buyer = next(o for o in self.api('director', 'GET', '/supplier-offers') if o['id'] == offer['id'])
        self.assertEqual(buyer['status'], 'Получено')
        self.assertEqual(buyer['totalPrice'], 100)
        self.assertEqual(json.loads(buyer['itemsKpJson'])[0]['pricePerUnit'], 100)
        self.api('supplier', 'PUT', path, dict(body, supplierMessage='changed same token'), expected=409)
        self.api('director', 'PUT', path, {'action': 'select'})
        replay = self.api('supplier', 'PUT', path, body)
        self.assertEqual(replay['status'], 'Утверждено')
        self.assertTrue(replay['submissionAccepted'])
        self.api('supplier', 'PUT', path, dict(body, requestId=str(uuid4())), expected=409)
        self.assertEqual(self.sql('SELECT status,total_price FROM supplier_offers WHERE id=%s', (offer['id'],)), [('Утверждено', 100)])

    def test_retry_requires_live_access_and_stale_edit_is_rejected(self):
        offer, path, body = self.quote()
        saved = self.api('supplier', 'PUT', path, body)
        self.api('supplier', 'PUT', path, dict(body, requestId=str(uuid4()), supplierMessage='stale'), expected=409)
        revised = dict(body, requestId=str(uuid4()), expectedRespondedAt=saved['respondedAt'], supplierMessage='revision')
        self.api('supplier', 'PUT', path, revised)
        self.api('stranger_supplier', 'PUT', path, body, expected=403)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s', (offer['requestId'],))
        self.api('supplier', 'PUT', path, body, expected=403)

    def test_multiple_lines_reach_buyer_and_can_be_selected(self):
        offer, path, body = self.quote(multi=True)
        self.api('supplier', 'PUT', path, body)
        buyer = next(o for o in self.api('director', 'GET', '/supplier-offers') if o['id'] == offer['id'])
        lines = json.loads(buyer['itemsKpJson'])
        self.assertEqual([line['pricePerUnit'] for line in lines], [100, 150])
        self.assertEqual(buyer['totalPrice'], 250)
        self.api('director', 'PUT', path, {'action': 'select'})
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s', (offer['id'],)), [('Утверждено',)])
