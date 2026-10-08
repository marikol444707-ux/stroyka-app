"""Request -> two supplier cabinets -> comparison -> explicit approval, local DB only."""
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

from . import test_postgres_chain as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ComparisonChainPostgresTests(unittest.TestCase):
    api = support.PostgresSupplyChainTests.api
    sql = support.PostgresSupplyChainTests.sql

    @classmethod
    def setUpClass(cls):
        support.PostgresSupplyChainTests.setUpClass.__func__(cls)
        cls.second_supplier = cls.sql(cls, 'SELECT id FROM suppliers WHERE user_id=%s',
                                     (cls.fixture['users']['stranger_supplier']['id'],))[0][0]
        cls.sql(cls, 'INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(2,%s,1)',
                (cls.second_supplier,))
        sections = json.loads(cls.sql(cls, 'SELECT sections_json FROM estimates WHERE id=%s',
                                      (cls.fixture['estimateId'],))[0][0])
        first = sections[0]['items'][0]
        first['quantity'] = 1000
        sections[0]['items'].append(dict(first, id='comparison-second', name=first['name']+' second'))
        cls.sql(cls, 'UPDATE estimates SET sections_json=%s WHERE id=%s',
                (json.dumps(sections), cls.fixture['estimateId']))

    def chain(self):
        f = self.fixture
        items = [dict(materialName=f['materialName'], quantity=1, unit='шт', workPackage=f['workPackage']),
                 dict(materialName=f['materialName']+' second', quantity=100, unit='шт', workPackage=f['workPackage'])]
        request = self.api('director', 'POST', '/supply-requests', dict(companyId=2,
            project=f['project'], workPackage=f['workPackage'], items=items, notes='Disposable comparison QA'))
        path = '/supply-requests/'+str(request['id'])
        self.api('foreman', 'PUT', path, {'action': 'confirm_prorab'})
        self.api('director', 'PUT', path, {'action': 'approve_director'})
        recipients = {'supplierIds': [f['supplierId'], self.second_supplier]}
        self.api('director', 'POST', path+'/request-kp', recipients)
        self.api('director', 'POST', path+'/request-kp', recipients)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_offers WHERE request_id=%s', (request['id'],)), [(2,)])
        ids = []
        for actor, prices in [('supplier', [1, 100]), ('stranger_supplier', [10, 10])]:
            offer = next(row for row in self.api(actor, 'GET', '/supplier-offers') if row['requestId'] == request['id'])
            ids.append(offer['id'])
            self.api(actor, 'PUT', '/supplier-offers/'+str(offer['id']), dict(action='respond',
                pricePerUnit=prices[0], totalPrice=sum(item['quantity']*price for item, price in zip(items, prices)),
                deliveryDays=2, paymentTerms='Постоплата', vatIncluded=True,
                itemsKp=[dict(item, pricePerUnit=price) for item, price in zip(items, prices)]))
        return path, ids

    def test_complete_chain_and_provider_failure_do_not_approve_or_post_stock(self):
        path, ids = self.chain()
        before = self.sql('SELECT status,total_price FROM supplier_offers WHERE id IN (%s,%s) ORDER BY id', tuple(ids))
        with patch.object(self.main, 'generate_supply_kp_comparison', side_effect=RuntimeError('offline test')):
            result = self.api('director', 'GET', path+'/compare-kp')
        self.assertEqual(result['bestOfferId'], ids[1])
        self.assertEqual(result['ranking'][0]['totalPrice'], 1010)
        self.assertEqual(result['aiStatus'], 'unavailable')
        self.assertFalse(result['automaticApprovalAllowed'])
        self.assertEqual(self.sql('SELECT status,total_price FROM supplier_offers WHERE id IN (%s,%s) ORDER BY id', tuple(ids)), before)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_invoices WHERE offer_id IN (%s,%s)', tuple(ids)), [(0,)])
        self.api('stranger', 'GET', path+'/compare-kp', expected=403)
        self.api('supplier', 'GET', path+'/compare-kp', expected=403)
        self.api('director', 'PUT', '/supplier-offers/'+str(ids[1]), {'action': 'select'})
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s', (ids[1],)), [('Утверждено',)])

    def test_expired_quote_and_model_disagreement_are_excluded(self):
        path, ids = self.chain()
        self.sql('UPDATE supplier_offers SET valid_until=%s WHERE id=%s', (dt.date.today()-dt.timedelta(days=1), ids[1]))
        def explanation(*args):
            winner = json.loads(args[0])['bestOfferId']
            return json.dumps(dict(bestOfferId=winner, explanation='Сравнена полная заявка.'))
        with patch.object(self.main, 'generate_supply_kp_comparison', side_effect=explanation):
            result = self.api('director', 'GET', path+'/compare-kp')
        self.assertEqual(result['bestOfferId'], ids[0])
        self.assertEqual(result['excludedOffers'][0]['offerId'], ids[1])
        self.assertEqual(result['aiStatus'], 'available')
        with patch.object(self.main, 'generate_supply_kp_comparison', return_value=json.dumps(dict(bestOfferId=ids[1], explanation='Другой'))):
            result = self.api('director', 'GET', path+'/compare-kp')
        self.assertIsNone(result['aiText'])
        self.assertEqual(result['bestOfferId'], ids[0])

    def test_incomplete_legacy_quote_does_not_beat_complete_quote(self):
        path, ids = self.chain()
        self.sql("UPDATE supplier_offers SET items_kp_json='[]',total_price=1,price_per_unit=1 WHERE id=%s", (ids[1],))
        with patch.object(self.main, 'generate_supply_kp_comparison', side_effect=RuntimeError('offline test')):
            result = self.api('director', 'GET', path+'/compare-kp')
        self.assertEqual(result['bestOfferId'], ids[0])
        self.assertEqual(len(result['excludedOffers']), 1)
