"""Real membership boundary tests in an explicitly selected, empty socket DB."""
import os
from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep
from unittest import TestCase, skipUnless
from uuid import uuid4

from fastapi.testclient import TestClient

from .test_postgres_support import Fixture, connection_settings


class ConnectionSettingsTests(TestCase):
    def test_dist_membership_database_prefix(self):
        settings = connection_settings(dict(SUPPLY_CHAIN_RUN_POSTGRES='1',
            SUPPLY_CHAIN_TEST_DB_HOST='/tmp/isolated-socket', SUPPLY_CHAIN_TEST_DB_PORT='55439',
            SUPPLY_CHAIN_TEST_DB_NAME='dist_membership_regression'))
        self.assertEqual(settings, dict(host='/tmp/isolated-socket', port='55439',
            dbname='dist_membership_regression', user='chain_test', password=''))

    def test_unsafe_targets_and_missing_opt_in_are_rejected(self):
        settings = dict(SUPPLY_CHAIN_RUN_POSTGRES='1', SUPPLY_CHAIN_TEST_DB_HOST='/tmp/isolated-socket',
                        SUPPLY_CHAIN_TEST_DB_PORT='55439', SUPPLY_CHAIN_TEST_DB_NAME='dist_membership_regression')
        for change in (dict(SUPPLY_CHAIN_RUN_POSTGRES='0'), dict(SUPPLY_CHAIN_TEST_DB_HOST='localhost'),
                       dict(SUPPLY_CHAIN_TEST_DB_HOST='/tmp/socket,remote'),
                       dict(SUPPLY_CHAIN_TEST_DB_NAME='production'), dict(SUPPLY_CHAIN_TEST_DB_NAME='dist_membership_'),
                       dict(SUPPLY_CHAIN_TEST_DB_PORT='0')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                connection_settings({**settings, **change})


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Explicit isolated PostgreSQL opt-in required')
class MembershipPostgresTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.client = TestClient(self.fixture.app)
        self.addCleanup(self.client.close)

    def issue_body(self):
        return dict(companyId=2, requestId=str(uuid4()), reason='Membership boundary',
                    rows=[dict(lotId=1, projectId=1, quantity='1')])

    def test_real_active_membership_can_issue(self):
        response = self.client.post('/warehouse-distributions', json=self.issue_body())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]
                         ['available_quantity'], 9)

    def operation(self, kind):
        if kind == 'issue':
            return '/warehouse-distributions', self.issue_body()
        issued = self.client.post('/warehouse-distributions', json=self.issue_body())
        self.assertEqual(issued.status_code, 200, issued.text)
        allocation_id = issued.json()['items'][0]['id']
        return f'/warehouse-distributions/{allocation_id}/returns', dict(
            companyId=2, requestId=str(uuid4()), reason='Physical return', quantity='1')

    def stock_state(self):
        tables = ('warehouse_receipt_lots', 'warehouse_main', 'materials',
                  'warehouse_distribution_operations', 'warehouse_distribution_allocations',
                  'warehouse_distribution_returns', 'warehouse_lot_movements',
                  'warehouse_movements', 'warehouse_history')
        return {table: self.fixture.query(f'SELECT * FROM {table} ORDER BY id') for table in tables}

    def post(self, path, body):
        with TestClient(self.fixture.app) as client:
            return client.post(path, json=body)

    def wait_blocked(self, blocker_pid, query_fragment):
        """Observe the actual wait edge; no timing-only assumption about thread order."""
        deadline = monotonic() + 2
        while monotonic() < deadline:
            with self.fixture.control.cursor() as cur:
                cur.execute('''SELECT pid FROM pg_stat_activity
                    WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))
                    AND query LIKE %s''', (blocker_pid, '%' + query_fragment + '%'))
                rows = cur.fetchall()
            if rows:
                self.assertEqual(len(rows), 1)
                return rows[0][0]
            sleep(.01)
        self.fail(f'Did not observe blocked query: {query_fragment}')

    def test_missing_and_inactive_membership_never_use_legacy_director(self):
        path, body = self.operation('return')
        before = self.stock_state()
        for statement in ('UPDATE user_company_roles SET active=FALSE WHERE user_id=1',
                          'DELETE FROM user_company_roles WHERE user_id=1'):
            with self.subTest(statement=statement):
                self.fixture.query(statement)
                for response in (self.client.post('/warehouse-distributions', json=self.issue_body()),
                                 self.client.post(path, json=body),
                                 self.client.get('/warehouse-distributions'),
                                 self.client.get('/warehouse-distributions/sources')):
                    self.assertEqual(response.status_code, 403, response.text)
                self.assertEqual(self.stock_state(), before)

    def test_revoked_membership_cannot_replay_issue_or_return(self):
        issue_body = self.issue_body()
        issued = self.client.post('/warehouse-distributions', json=issue_body)
        self.assertEqual(issued.status_code, 200, issued.text)
        path = '/warehouse-distributions/{}/returns'.format(issued.json()['items'][0]['id'])
        returned = dict(companyId=2, requestId=str(uuid4()), reason='Physical return', quantity='1')
        self.assertEqual(self.client.post(path, json=returned).status_code, 200)
        before = self.stock_state()
        self.fixture.query('UPDATE user_company_roles SET active=FALSE WHERE user_id=1')
        for endpoint, payload in (('/warehouse-distributions', issue_body), (path, returned)):
            response = self.client.post(endpoint, json=payload)
            self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.stock_state(), before)

    def test_selected_membership_role_overrides_legacy_company_and_role(self):
        self.fixture.query("UPDATE users SET company_id=3,role='прораб' WHERE id=1")
        response = self.client.post('/warehouse-distributions', json=self.issue_body(),
                                    headers={'X-Company-Id': '2', 'X-Company-Mode': 'company'})
        self.assertEqual(response.status_code, 200, response.text)
        self.fixture.query("UPDATE users SET role='директор' WHERE id=1")
        self.fixture.query("UPDATE user_company_roles SET role='прораб' WHERE user_id=1")
        before = self.stock_state()
        response = self.client.post('/warehouse-distributions', json=self.issue_body())
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.stock_state(), before)

    def test_foreign_selection_and_conflicting_header_do_not_write(self):
        before = self.stock_state()
        response = self.client.get('/warehouse-distributions/sources', headers={'X-Company-Id': '3'})
        self.assertEqual(response.status_code, 403, response.text)
        response = self.client.post('/warehouse-distributions', json=self.issue_body(), headers={'X-Company-Id': '3'})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.stock_state(), before)

    def test_revocation_committed_during_each_identity_lock_wait_is_seen(self):
        for table, row_id in (('users', 1), ('companies', 2), ('user_company_roles', 1)):
            for kind in ('issue', 'return'):
                with self.subTest(table=table, kind=kind):
                    path, body = self.operation(kind)
                    before = self.stock_state()
                    blocker = self.fixture.get_db()
                    try:
                        with blocker.cursor() as cur:
                            cur.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE', (row_id,))
                        with ThreadPoolExecutor(max_workers=1) as pool:
                            pending = pool.submit(self.post, path, body)
                            try:
                                self.wait_blocked(blocker.get_backend_pid(), f'FROM {table} ')
                                with blocker.cursor() as cur:
                                    cur.execute(f'UPDATE {table} SET active=FALSE WHERE id=%s', (row_id,))
                                blocker.commit()
                            finally:
                                blocker.rollback()
                            response = pending.result(timeout=10)
                        self.assertEqual(response.status_code, 403, response.text)
                        self.assertEqual(self.stock_state(), before)
                    finally:
                        blocker.close()
                        self.fixture.query(f'UPDATE {table} SET active=TRUE WHERE id=%s', (row_id,))

    def test_lock_wait_cannot_switch_to_another_allowed_membership(self):
        for kind in ('issue', 'return'):
            with self.subTest(kind=kind):
                path, body = self.operation(kind)
                self.fixture.query('''INSERT INTO user_company_roles(user_id,company_id,role,is_default)
                    VALUES(1,2,'зам_директора',FALSE)''')
                before = self.stock_state()
                blocker = self.fixture.get_db()
                try:
                    with blocker.cursor() as cur:
                        cur.execute('SELECT id FROM user_company_roles WHERE id=1 FOR UPDATE')
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(self.post, path, body)
                        try:
                            self.wait_blocked(blocker.get_backend_pid(), 'FROM user_company_roles ')
                            with blocker.cursor() as cur:
                                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE id=1')
                            blocker.commit()
                        finally:
                            blocker.rollback()
                        response = pending.result(timeout=10)
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertEqual(self.stock_state(), before)
                    # A fresh operation may lock the alternative membership and succeed.
                    response = self.client.post(path, json=body)
                    self.assertEqual(response.status_code, 200, response.text)
                finally:
                    blocker.close()
                    self.fixture.query('UPDATE user_company_roles SET active=TRUE WHERE id=1')
                    self.fixture.query("DELETE FROM user_company_roles WHERE user_id=1 AND role='зам_директора'")

    def test_identity_locks_hold_through_stock_wait_and_commit(self):
        for table, row_id in (('users', 1), ('companies', 2), ('user_company_roles', 1)):
            for kind in ('issue', 'return'):
                with self.subTest(table=table, kind=kind):
                    path, body = self.operation(kind)
                    stock_blocker = self.fixture.get_db()
                    revoker = self.fixture.get_db()

                    def revoke():
                        with revoker, revoker.cursor() as cur:
                            cur.execute(f'UPDATE {table} SET active=FALSE WHERE id=%s', (row_id,))

                    try:
                        with stock_blocker.cursor() as cur:
                            cur.execute('SELECT id FROM warehouse_invoices WHERE id=1 FOR UPDATE')
                        with ThreadPoolExecutor(max_workers=2) as pool:
                            pending = pool.submit(self.post, path, body)
                            try:
                                operation_pid = self.wait_blocked(stock_blocker.get_backend_pid(), 'FROM warehouse_invoices ')
                                revoked = pool.submit(revoke)
                                self.assertEqual(self.wait_blocked(operation_pid, f'UPDATE {table} '), revoker.get_backend_pid())
                            finally:
                                stock_blocker.rollback()
                            response = pending.result(timeout=10)
                            revoked.result(timeout=10)
                        self.assertEqual(response.status_code, 200, response.text)
                        before = self.stock_state()
                        replay = self.client.post(path, json=body)
                        self.assertEqual(replay.status_code, 403, replay.text)
                        self.assertEqual(self.stock_state(), before)
                    finally:
                        stock_blocker.close()
                        revoker.close()
                        self.fixture.query(f'UPDATE {table} SET active=TRUE WHERE id=%s', (row_id,))

    def test_membership_lock_timeout_rolls_back_and_same_request_can_retry(self):
        for kind in ('issue', 'return'):
            with self.subTest(kind=kind):
                path, body = self.operation(kind)
                before = self.stock_state()
                blocker = self.fixture.get_db()
                try:
                    with blocker.cursor() as cur:
                        cur.execute('SELECT id FROM user_company_roles WHERE id=1 FOR UPDATE')
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(self.post, path, body)
                        self.wait_blocked(blocker.get_backend_pid(), 'FROM user_company_roles ')
                        response = pending.result(timeout=10)
                    self.assertEqual(response.status_code, 409, response.text)
                    self.assertEqual(self.stock_state(), before)
                finally:
                    blocker.rollback()
                    blocker.close()
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 200, response.text)
