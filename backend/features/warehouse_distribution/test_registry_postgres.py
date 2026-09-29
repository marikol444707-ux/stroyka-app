"""Real list queries against the isolated, synthetic receipt/distribution schema."""
from datetime import datetime, timezone
import os
from unittest import TestCase, skipUnless
from uuid import uuid4

from fastapi.testclient import TestClient
from .test_postgres_support import Fixture


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Isolated PostgreSQL opt-in required')
class RegistryTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.client = TestClient(self.fixture.app)
        self.addCleanup(self.client.close)

    def issue(self, count=1, project=1):
        response = self.client.post('/warehouse-distributions', json=dict(
            companyId=2, requestId=str(uuid4()), reason='Registry fixture',
            rows=[dict(lotId=1, projectId=project, quantity='0.01')] * count))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['items']

    def test_history_reaches_records_beyond_old_cap_and_return(self):
        oldest = self.issue(50)[0]['id']
        self.issue(50)
        self.issue(5, project=2)
        first = self.client.get('/warehouse-distributions').json()
        self.assertEqual(len(first['items']), 100)
        self.assertTrue(first['truncated'])
        second = self.client.get('/warehouse-distributions', params={'beforeId': first['nextCursor']}).json()
        self.assertEqual(len(second['items']), 5)
        self.assertIsNone(second['nextCursor'])
        self.assertFalse(second['truncated'])
        ids = [r['id'] for r in first['items'] + second['items']]
        self.assertEqual(len(set(ids)), 105)
        self.assertIn(oldest, ids)
        returned = self.client.post(f'/warehouse-distributions/{oldest}/returns', json=dict(
            companyId=2, requestId=str(uuid4()), reason='Old allocation return', quantity='0.01'))
        self.assertEqual(returned.status_code, 200, returned.text)

    def test_history_filters_literal_search_and_utc_period(self):
        row = self.issue()[0]
        self.issue(project=2)
        today = datetime.now(timezone.utc).date().isoformat()
        for q in ('alpha', 'R1', 'cement', str(row['id'])):
            response = self.client.get('/warehouse-distributions', params=dict(
                q=q, projectId=1, dateFrom=today, dateTo=today, limit=1))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual([r['id'] for r in response.json()['items']], [row['id']])
        for params in (dict(q='%'), dict(q='_'), dict(q="' OR 1=1 --"), dict(q='\\'),
                       dict(projectId=3), dict(dateTo='2000-01-01'), dict(dateFrom='2999-01-01')):
            self.assertEqual(self.client.get('/warehouse-distributions', params=params).json()['items'], [])
        other = self.client.get('/warehouse-distributions', params={'q': 'R1'}, headers={'X-Test-Company': '3'})
        self.assertEqual(other.json()['items'], [])

    def test_sources_cursor_and_search_reach_old_lots(self):
        self.fixture.query('''INSERT INTO warehouse_invoices(id,company_id,number,items)
            SELECT n,2,'Receipt-' || n,'[{"name":"Cement","quantity":10,"unit":"кг"}]'
            FROM generate_series(100,304) n''')
        self.fixture.query('''INSERT INTO warehouse_receipt_lots(company_id,warehouse_location,warehouse_target,
            warehouse_invoice_id,invoice_line_index,material_name,document_quantity,document_unit,
            received_quantity,unit,available_quantity)
            SELECT 2,'Основной склад','main',n,0,'Cement',10,'кг',10,'кг',10
            FROM generate_series(100,304) n''')
        first = self.client.get('/warehouse-distributions/sources').json()
        self.assertEqual(len(first['items']), 200)
        second = self.client.get('/warehouse-distributions/sources', params={'beforeId': first['nextCursor']}).json()
        self.assertEqual(len(second['items']), 6)
        self.assertIsNone(second['nextCursor'])
        matched = self.client.get('/warehouse-distributions/sources', params={'q': 'Receipt-100'}).json()
        self.assertEqual([r['warehouseInvoiceId'] for r in matched['items']], [100])
        for q in ('%', '_', "' OR 1=1 --"):
            self.assertEqual(self.client.get('/warehouse-distributions/sources', params={'q': q}).json()['items'], [])

    def test_invalid_filters_and_cursors_rejected(self):
        for suffix in ('', '/sources'):
            for params in (dict(beforeId=0), dict(beforeId=-1), dict(beforeId='nan'),
                           dict(beforeId='9223372036854775808'), dict(limit=0), dict(limit=201),
                           dict(q='x' * 201), dict(q='\x00')):
                response = self.client.get('/warehouse-distributions' + suffix, params=params)
                self.assertIn(response.status_code, (400, 422), response.text)
        for params in (dict(dateFrom='bad'), dict(dateFrom='2026-09-17', dateTo='2026-09-16'), dict(projectId=0)):
            response = self.client.get('/warehouse-distributions', params=params)
            self.assertIn(response.status_code, (400, 422), response.text)

    def test_operational_roles_real_context_and_financial_values_unchanged(self):
        before = self.fixture.query('SELECT id,payment_status FROM warehouse_invoices ORDER BY id')
        for role in ('storekeeper', 'supply'):
            headers = {'X-Test-Role': role}
            for path in ('/warehouse-distributions', '/warehouse-distributions/sources'):
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
            issued = self.client.post('/warehouse-distributions', headers=headers, json=dict(
                companyId=2, requestId=str(uuid4()), reason='Operational issue',
                rows=[dict(lotId=1, projectId=1, quantity='1')]))
            self.assertEqual(issued.status_code, 200, issued.text)
            allocation_id = issued.json()['items'][0]['id']
            returned = self.client.post(f'/warehouse-distributions/{allocation_id}/returns', headers=headers, json=dict(
                companyId=2, requestId=str(uuid4()), reason='Operational return', quantity='1'))
            self.assertEqual(returned.status_code, 200, returned.text)
        self.assertEqual(self.fixture.query('SELECT id,payment_status FROM warehouse_invoices ORDER BY id'), before)
