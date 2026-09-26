"""HTTP boundary tests; no main/config import or database connection."""
import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient


class RouteBoundaryTests(unittest.TestCase):
    def setUp(self):
        from .routes import register_supplier_payment_routes
        self.db = Mock(side_effect=AssertionError('Unexpected database access'))
        app = FastAPI()
        register_supplier_payment_routes(app, {
            'get_db': self.db, 'get_current_user': lambda: {'id': 7},
            'authorize_read': Mock(), 'resolve_documents': Mock(),
        })
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.flag = patch.dict(os.environ, {'SUPPLIER_PAYMENTS_ENABLED': '1'})
        self.flag.start()
        self.addCleanup(self.flag.stop)
        self.path = '/companies/2/supplier-payments'
        self.headers = {'X-Company-Id': '2', 'X-Company-Mode': 'company'}
        self.body = dict(requestId=str(uuid4()), kind='payment', documentKind='invoice',
                         documentId=8, amount='0.01', paidAt='2026-09-18', reason='Recorded payment')

    def test_default_off_hides_all_routes_without_database(self):
        with patch.dict(os.environ, {'SUPPLIER_PAYMENTS_ENABLED': '0'}):
            for method, path in [('GET', self.path), ('POST', self.path),
                                 ('POST', self.path + '/cancel-request'),
                                 ('GET', '/companies/2/supplier-payment-documents/invoice/8')]:
                self.assertEqual(self.client.request(method, path, json=self.body).status_code, 404)
        self.db.assert_not_called()

    def test_selected_headers_required_and_must_match_for_reads_and_writes(self):
        for method in ('GET', 'POST'):
            for headers, status in [({}, 400), ({'X-Company-Id': '3'}, 409),
                                    ({**self.headers, 'X-Company-Mode': 'all_companies'}, 400)]:
                response = self.client.request(method, self.path, json=self.body, headers=headers)
                self.assertEqual(response.status_code, status, response.text)

    def test_command_rejects_extra_authority_and_malformed_identity_before_database(self):
        for body in [{**self.body, 'companyId': 3}, {**self.body, 'paidBy': 'Forged'},
                     {**self.body, 'documentId': True}, {**self.body, 'amount': '0.001'},
                     {**self.body, 'kind': 'reversal', 'reversesId': 1}, []]:
            response = self.client.post(self.path, json=body, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)

    def test_duplicate_company_headers_rejected_before_database_on_every_route(self):
        for key, values in [('X-Company-Id', ('2', '3')), ('X-Company-Id', ('2', '2')),
                            ('X-Company-Mode', ('company', 'all_companies')),
                            ('X-Company-Mode', ('company', 'company'))]:
            headers = [(k, v) for k, v in self.headers.items() if k != key]
            headers.extend((key, value) for value in values)
            for method, path in [('GET', self.path), ('POST', self.path),
                                 ('POST', self.path + '/cancel-request'),
                                 ('GET', '/companies/2/supplier-payment-documents/invoice/8')]:
                with self.subTest(key=key, values=values, method=method, path=path):
                    response = self.client.request(method, path, json=self.body, headers=headers)
                    self.assertEqual(response.status_code, 400, response.text)
        self.db.assert_not_called()

    def test_cancellation_requires_exact_original_command_and_selected_headers(self):
        path = self.path + '/cancel-request'
        for body in [{**self.body, 'companyId': 2}, {**self.body, 'status': 'cancelled'},
                     {**self.body, 'documentId': True}, {**self.body, 'amount': '0.001'},
                     {'requestId': self.body['requestId']}, [],
                     {**self.body, 'kind': 'reversal', 'reversesId': 1}]:
            response = self.client.post(path, json=body, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(set(response.json()['detail']), {'code', 'message'})
        for headers, status in [({}, 400), ({'X-Company-Id': '3'}, 409),
                                ({**self.headers, 'X-Company-Mode': 'all_companies'}, 400)]:
            response = self.client.post(path, json=self.body, headers=headers)
            self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self.client.post(path + '?force=1', json=self.body,
                                         headers=self.headers).status_code, 422)
        self.db.assert_not_called()

    def test_cancellation_database_error_is_generic_and_preserves_retry_uuid(self):
        from psycopg2 import OperationalError
        self.db.side_effect = OperationalError('PRIVATE_DATABASE_DETAIL')
        response = self.client.post(self.path + '/cancel-request', json=self.body, headers=self.headers)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn('PRIVATE_DATABASE_DETAIL', response.text)
        self.assertEqual(response.json()['detail']['code'], 'cancellation_unconfirmed')
        self.assertIn('UUID', response.json()['detail']['message'])

    def test_cancellation_never_falls_back_to_read_authority(self):
        from .routes import register_supplier_payment_routes
        app = FastAPI()
        register_supplier_payment_routes(app, {'get_db': self.db,
            'get_current_user': lambda: {'id': 7}, 'authorize_read': Mock()})
        with TestClient(app) as client:
            response = client.post(self.path + '/cancel-request', json=self.body, headers=self.headers)
            self.assertEqual(response.status_code, 503, response.text)
        self.db.assert_not_called()

    def test_history_rejects_invalid_or_unbounded_filters_before_database(self):
        for query in ('limit=101', 'limit=0', 'beforeId=0', 'documentKind=other',
                      'documentId=8', 'documentKind=invoice', 'requestId=bad',
                      'companyId=3', 'limit=1&limit=2', 'projectName=' + 'x' * 301):
            response = self.client.get(self.path + '?' + query, headers=self.headers)
            self.assertEqual(response.status_code, 422, (query, response.text))

    def test_missing_read_authorizer_fails_closed_without_falling_back_to_writer(self):
        from .routes import register_supplier_payment_routes
        app = FastAPI()
        register_supplier_payment_routes(app, {'get_db': self.db,
            'get_current_user': lambda: {'id': 7}, 'resolve_documents': Mock()})
        with TestClient(app) as client:
            response = client.get(self.path, headers=self.headers)
            self.assertEqual(response.status_code, 503)
        self.db.assert_not_called()
