"""Isolated HTTP boundary: real normalization/transaction wrapper, fake DB only."""
import os
import unittest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from psycopg2 import OperationalError


class AllocationRouteTests(unittest.TestCase):
    def setUp(self):
        from .allocation_routes import register_supplier_allocation_routes
        self.register = register_supplier_allocation_routes
        self.conn = MagicMock()
        self.conn.set_session.side_effect = lambda **kwargs: setattr(self.conn, 'autocommit', kwargs['autocommit'])
        self.cur = self.conn.cursor.return_value.__enter__.return_value
        self.cur.connection = self.conn
        self.cur.fetchone.return_value = {'transaction_isolation': 'read committed'}
        self.events = []
        self.deps = dict(get_db=Mock(return_value=self.conn), get_current_user=lambda: {'id': 7},
            authorize_allocation_write=Mock(side_effect=lambda *args: self.events.append('write')),
            authorize_allocation_read=Mock(side_effect=lambda *args: self.events.append('read')),
            require_allocation_schema=Mock(side_effect=lambda *args: self.events.append('schema')))
        self.app = FastAPI(); self.register(self.app, self.deps)
        self.client = TestClient(self.app); self.addCleanup(self.client.close)
        self.flags = patch.dict(os.environ, SUPPLIER_PAYMENTS_ENABLED='1', SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED='1')
        self.flags.start(); self.addCleanup(self.flags.stop)
        self.post = '/companies/2/supplier-payments/allocations'
        self.get = '/companies/2/supplier-payments/allocation-groups/8'
        self.headers = {'X-Company-Id': '2', 'X-Company-Mode': 'company'}
        self.body = dict(requestId=str(uuid4()), groupId=8, expectedVersion=0, reason='Назначение', rows=[])

    def call(self, method, **kwargs):
        return self.client.request(method, self.post if method == 'POST' else self.get,
                                   headers=self.headers, **({'json': self.body} if method == 'POST' else {}), **kwargs)

    def worker(self, cur, authorize, actor, company, body):
        from .allocation_store import _enter
        command = body if isinstance(body, dict) else {'groupId': body}
        _enter(cur, authorize, actor, company, command)
        self.events.append('worker')
        return dict(groupId=8, version=1, requestId=self.body['requestId'])

    def fake_workers(self):
        for name in ('replace_allocations_in_transaction', 'read_allocations_in_transaction'):
            mocked = patch('backend.features.supplier_payments.allocation_store.' + name, side_effect=self.worker)
            mocked.start(); self.addCleanup(mocked.stop)

    def test_both_flags_exact_one_required_default_off(self):
        for flag in ('SUPPLIER_PAYMENTS_ENABLED', 'SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED'):
            for value in ('0', '', 'true'):
                with patch.dict(os.environ, {flag: value}):
                    for method in ('GET', 'POST'):
                        response = self.call(method)
                        self.assertEqual(response.status_code, 404)
                        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.deps['get_db'].assert_not_called()

    def test_headers_and_query_are_strict_without_database(self):
        for method, path in [('POST', self.post), ('GET', self.get)]:
            for headers, status in [({}, 400), ({'X-Company-Id': '3'}, 409),
                ({**self.headers, 'X-Company-Mode': 'all'}, 400),
                ([('X-Company-Id', '2'), ('X-Company-Id', '2')], 400),
                ([('X-Company-Id', '2'), ('X-Company-Mode', 'company'), ('X-Company-Mode', 'company')], 400)]:
                response = self.client.request(method, path, headers=headers, json=self.body)
                self.assertEqual(response.status_code, status, response.text)
            for query in ('companyId=2', 'groupId=8&groupId=8', 'force=1'):
                response = self.client.request(method, path + '?' + query, headers=self.headers, json=self.body)
                self.assertEqual(response.status_code, 422, response.text)
        self.deps['get_db'].assert_not_called()

    def test_exact_normalizer_and_path_validation_before_db(self):
        for body in [[], {}, {**self.body, 'companyId': 2}, {**self.body, 'groupId': True},
                     {**self.body, 'expectedVersion': -1}, {**self.body, 'rows': [{'paymentId': 1, 'receiptId': 2, 'amount': '0.001'}]}]:
            response = self.client.post(self.post, json=body, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post(self.post, content='{broken', headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get(self.get[:-1] + '0', headers=self.headers).status_code, 422)
        self.deps['get_db'].assert_not_called()

    def test_saved_post_response_auth_schema_worker_commit_order(self):
        self.fake_workers()
        response = self.call('POST')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), dict(companyId=2, groupId=8, version=1, requestId=self.body['requestId']))
        self.assertEqual(self.events, ['write', 'schema', 'worker'])
        self.deps['authorize_allocation_read'].assert_not_called()
        self.conn.commit.assert_called_once(); self.conn.close.assert_called_once()
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_get_read_authority_rc_lock_timeouts_always_rollback(self):
        self.fake_workers(); response = self.call('GET')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.events, ['read', 'schema', 'worker'])
        self.conn.set_session.assert_called_once_with(isolation_level='READ COMMITTED', autocommit=False)
        sql = [args[0][0] for args in self.cur.execute.call_args_list]
        self.assertIn("SET LOCAL lock_timeout='3s'", sql)
        self.assertIn("SET LOCAL statement_timeout='15s'", sql)
        self.cur.execute.assert_any_call('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
        self.conn.rollback.assert_called_once(); self.conn.close.assert_called_once(); self.conn.commit.assert_not_called()
        self.deps['authorize_allocation_write'].assert_not_called()

    def test_missing_callbacks_fail_closed_never_fallback(self):
        for method, dependency in [('POST', 'authorize_allocation_write'), ('GET', 'authorize_allocation_read'),
                                   ('POST', 'require_allocation_schema'), ('GET', 'require_allocation_schema')]:
            with patch.dict(self.deps, {dependency: None}):
                self.assertEqual(self.call(method).status_code, 503)
        self.deps['get_db'].assert_not_called()

    def test_current_authority_denial_precedes_schema_and_replay(self):
        self.fake_workers()
        for method, callback in [('POST', 'authorize_allocation_write'), ('GET', 'authorize_allocation_read')]:
            self.deps[callback].side_effect = HTTPException(403, 'Нет доступа')
            response = self.call(method)
            self.assertEqual(response.status_code, 403, response.text)
        self.deps['require_allocation_schema'].assert_not_called()
        self.conn.commit.assert_not_called()
        self.assertEqual(self.conn.close.call_count, 2)

    def test_real_worker_replay_still_reauthorizes_before_reading_saved_uuid(self):
        from .commands import command_fingerprint
        from .allocation_commands import normalize_allocation_command
        replay = dict(id=19, group_id=8, version=1, request_id=self.body['requestId'],
                      fingerprint=command_fingerprint(2, 7, normalize_allocation_command(self.body)))
        self.cur.fetchone.side_effect = [{'transaction_isolation': 'read committed'}, replay]
        response = self.call('POST')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['revisionId'], 19)
        self.assertEqual(self.events, ['write', 'schema'])
        self.cur.execute.reset_mock()
        self.cur.fetchone.side_effect = [{'transaction_isolation': 'read committed'}]
        self.deps['authorize_allocation_write'].side_effect = HTTPException(403, 'Доступ отозван')
        response = self.call('POST')
        self.assertEqual(response.status_code, 403, response.text)
        self.assertFalse(any('supplier_payment_allocation_revisions' in call.args[0]
                             for call in self.cur.execute.call_args_list))
        self.assertEqual(self.conn.commit.call_count, 1)

    def test_authentication_failure_never_opens_database(self):
        def denied():
            raise HTTPException(401, 'Требуется вход')
        self.app.dependency_overrides[self.deps['get_current_user']] = denied
        for method in ('GET', 'POST'):
            response = self.call(method)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers['cache-control'], 'no-store')
        self.deps['get_db'].assert_not_called()

    def test_schema_exceptions_are_generic_503_after_auth(self):
        self.fake_workers()
        for error in [RuntimeError('PRIVATE_SCHEMA'), HTTPException(409, 'PRIVATE_SCHEMA')]:
            self.deps['require_allocation_schema'].side_effect = error
            for method in ('GET', 'POST'):
                response = self.call(method)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertNotIn('PRIVATE_SCHEMA', response.text)
        self.conn.commit.assert_not_called()

    def test_unknown_database_and_commit_failures_do_not_leak_or_confirm(self):
        self.fake_workers()
        for method in ('GET', 'POST'):
            self.deps['get_db'].side_effect = OperationalError('PRIVATE_DSN')
            response = self.call(method)
            self.assertEqual(response.status_code, 503, response.text)
            self.assertNotIn('PRIVATE_DSN', response.text)
        self.deps['get_db'].side_effect = None
        self.conn.commit.side_effect = OperationalError('PRIVATE_COMMIT')
        response = self.call('POST')
        self.assertEqual(response.status_code, 503)
        self.assertIn('UUID', response.json()['detail']['message'])
        self.assertNotIn('PRIVATE_COMMIT', response.text)
        self.conn.rollback.assert_called_once(); self.conn.close.assert_called_once()

    def test_get_failure_rolls_back_and_closes(self):
        self.fake_workers(); self.deps['authorize_allocation_read'].side_effect = RuntimeError('PRIVATE_RUNTIME')
        response = self.call('GET')
        self.assertEqual(response.status_code, 503); self.assertNotIn('PRIVATE_RUNTIME', response.text)
        self.conn.rollback.assert_called_once(); self.conn.close.assert_called_once()

    def test_only_explicit_registrar_and_no_registration_endpoint(self):
        import inspect
        from . import allocation_routes
        source = inspect.getsource(allocation_routes)
        self.assertNotIn('import main', source)
        self.assertNotIn('from backend import main', source)
        self.assertEqual({route.path for route in self.app.routes if 'supplier-payments' in route.path}, {
            '/companies/{company_id}/supplier-payments/allocations',
            '/companies/{company_id}/supplier-payments/allocation-groups/{group_id}'})


if __name__ == '__main__':
    unittest.main()
