"""HTTP boundary regressions using mocked connections only; never import main."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ..company_context.service import effective_company_actors
from . import routes


def membership(**changes):
    return dict(dict(mode='company', source='membership', companyId=2,
                     membershipId=23, active=True, companyActive=True,
                     role='директор', readOnly=False), **changes)


@contextmanager
def boundary(initial=None, refreshed=None, missing_lock=None, user_role='рабочий'):
    cur, conn = MagicMock(), MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchall.return_value = []

    def fetchone():
        sql = cur.execute.call_args.args[0]
        if 'FOR SHARE' in sql:
            return None if missing_lock and f'FROM {missing_lock} ' in sql else {'id': 1}
        if 'AS more' in sql:
            return {'more': False}
        raise AssertionError(f'Unexpected fetch: {sql}')

    cur.fetchone.side_effect = fetchone
    initial = membership() if initial is None else initial
    resolver = Mock(side_effect=[initial, initial if refreshed is None else refreshed])
    user = dict(id=7, companyId=99, role=user_role)
    deps = dict(get_db=Mock(return_value=conn), get_current_user=lambda: user,
                resolve_work_company_context=resolver,
                effective_company_actors=effective_company_actors,
                finance_roles={'директор', 'зам_директора', 'инженер'})
    with patch('psycopg2.connect', side_effect=AssertionError('No database allowed')), \
            patch.dict('os.environ', {'WAREHOUSE_DISTRIBUTION_ENABLED': '1'}), \
            patch.object(routes, 'issue', return_value={'ok': True}) as issue, \
            patch.object(routes, 'physical_return', return_value={'ok': True}) as physical_return:
        app = FastAPI()
        routes.register_warehouse_distribution_module(app, deps)
        with TestClient(app) as client:
            def post(kind):
                payload = dict(companyId=2, requestId=str(uuid4()), reason='boundary test')
                if kind == 'issue':
                    payload['rows'] = [dict(lotId=1, projectId=3, quantity='1')]
                    path = ''
                else:
                    payload['quantity'] = '1'
                    path = '/1/returns'
                return client.post('/warehouse-distributions' + path, json=payload,
                                   headers={'X-Company-Id': '2', 'X-Company-Mode': 'company'})

            yield SimpleNamespace(client=client, post=post, cur=cur, conn=conn,
                                  resolver=resolver, issue=issue, physical_return=physical_return)


class MembershipBoundaryTests(TestCase):
    def test_operational_memberships_can_issue_return_and_read(self):
        for role in ('кладовщик', 'снабженец'):
            for kind in ('issue', 'return', 'sources', 'allocations'):
                with self.subTest(role=role, kind=kind), boundary(membership(role=role)) as case:
                    response = (case.post(kind) if kind in ('issue', 'return') else
                                case.client.get('/warehouse-distributions' + ('/sources' if kind == 'sources' else '')))
                    self.assertEqual(response.status_code, 200, response.text)

    def test_operational_membership_revocation_and_readonly_deny_writes(self):
        for role in ('кладовщик', 'снабженец'):
            for change in (dict(active=False), dict(readOnly=True), dict(role='бухгалтер')):
                for kind in ('issue', 'return'):
                    with self.subTest(role=role, change=change, kind=kind), boundary(
                            membership(role=role), refreshed=membership(**dict(dict(role=role), **change))) as case:
                        self.assert_denied(case, case.post(kind))

    def assert_denied(self, case, response, status=403):
        self.assertEqual(response.status_code, status, response.text)
        case.issue.assert_not_called()
        case.physical_return.assert_not_called()
        case.conn.commit.assert_not_called()
        case.conn.rollback.assert_called_once()
        case.conn.close.assert_called_once()

    def test_all_routes_require_active_membership_not_legacy_or_account(self):
        invalid = [dict(source='legacy'), dict(source='account'), dict(source='platform'),
                   dict(source=None), dict(active=False), dict(companyActive=False),
                   dict(membershipId=None)]
        for change in invalid:
            for endpoint in ('issue', 'return', 'sources', 'allocations'):
                with self.subTest(change=change, endpoint=endpoint), boundary(membership(**change)) as case:
                    if endpoint in ('issue', 'return'):
                        response = case.post(endpoint)
                    else:
                        suffix = '/sources' if endpoint == 'sources' else ''
                        response = case.client.get('/warehouse-distributions' + suffix + '?companyId=2')
                    self.assert_denied(case, response)

    def test_write_locks_then_refreshes_same_membership_before_command(self):
        for kind in ('issue', 'return'):
            with self.subTest(kind=kind), boundary() as case:
                def command(*args):
                    case.conn.commit.assert_not_called()
                    case.conn.close.assert_not_called()
                    case.conn.set_session.assert_called_once_with(
                        isolation_level='READ COMMITTED', autocommit=False)
                    self.assertEqual(case.resolver.call_count, 2)
                    locks = [(c.args[0], c.args[1]) for c in case.cur.execute.call_args_list
                             if 'FOR SHARE' in c.args[0]]
                    self.assertEqual(locks, [
                        ('SELECT id FROM users WHERE id=%s AND active=TRUE FOR SHARE', (7,)),
                        ('SELECT id FROM companies WHERE id=%s FOR SHARE', (2,)),
                        ('SELECT id FROM user_company_roles WHERE id=%s AND user_id=%s AND company_id=%s FOR SHARE',
                         (23, 7, 2)),
                    ])
                    case.cur.execute.assert_any_call("SET LOCAL lock_timeout='3s'")
                    case.cur.execute.assert_any_call("SET LOCAL statement_timeout='15s'")
                    actor = args[-1]
                    self.assertEqual((actor['companyId'], actor['membershipId'], actor['role']),
                                     (2, 23, 'директор'))
                    return {'ok': True}

                case.issue.side_effect = case.physical_return.side_effect = command
                self.assertEqual(case.post(kind).status_code, 200)
                case.conn.commit.assert_called_once()
                case.conn.rollback.assert_not_called()
                case.conn.close.assert_called_once()
                for call in case.resolver.call_args_list:
                    self.assertEqual(call.args[2:], (2, 'write'))

    def test_lock_wait_refresh_cannot_switch_to_another_membership(self):
        changes = [dict(source='legacy'), dict(active=False), dict(companyActive=False),
                   dict(membershipId=24), dict(membershipId=None), dict(companyId=3),
                   dict(mode='all_companies'), dict(readOnly=True), dict(role='рабочий')]
        for change in changes:
            for kind in ('issue', 'return'):
                with self.subTest(change=change, kind=kind), boundary(refreshed=membership(**change)) as case:
                    self.assert_denied(case, case.post(kind))

    def test_refresh_occurs_after_membership_lock_not_before(self):
        for kind in ('issue', 'return'):
            with self.subTest(kind=kind), boundary() as case:
                current = membership()

                def execute(sql, params=None):
                    if 'FROM user_company_roles ' in sql and 'FOR SHARE' in sql:
                        # Simulate revocation committed while this SELECT waited.
                        current.update(source='legacy', membershipId=None)

                case.cur.execute.side_effect = execute
                case.resolver.side_effect = lambda *args, **kwargs: dict(current)
                self.assert_denied(case, case.post(kind))
                self.assertEqual(case.resolver.call_count, 2)

    def test_missing_locked_user_company_or_membership_prevents_commands(self):
        for table in ('users', 'companies', 'user_company_roles'):
            for kind in ('issue', 'return'):
                with self.subTest(table=table, kind=kind), boundary(missing_lock=table) as case:
                    self.assert_denied(case, case.post(kind))

    def test_selected_role_never_falls_back_to_primary_director(self):
        for role in ('рабочий', '', None):
            for kind in ('issue', 'return'):
                with self.subTest(role=role, kind=kind), boundary(
                        membership(role=role), user_role='директор') as case:
                    self.assert_denied(case, case.post(kind))

    def test_command_receives_refreshed_selected_role(self):
        for kind in ('issue', 'return'):
            with self.subTest(kind=kind), boundary(refreshed=membership(role='зам_директора')) as case:
                self.assertEqual(case.post(kind).status_code, 200)
                command = case.issue if kind == 'issue' else case.physical_return
                self.assertEqual(command.call_args.args[-1]['role'], 'зам_директора')

    def test_reads_preserve_snapshot_and_do_not_attempt_row_locks(self):
        for suffix in ('', '/sources'):
            with self.subTest(suffix=suffix), boundary(membership(role='инженер')) as case:
                response = case.client.get('/warehouse-distributions' + suffix + '?companyId=2')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(case.resolver.call_count, 1)
                self.assertFalse(any('FOR SHARE' in c.args[0] for c in case.cur.execute.call_args_list))
                if not suffix:
                    case.cur.execute.assert_any_call('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')

    def test_command_failure_rolls_back_and_closes(self):
        for kind in ('issue', 'return'):
            with self.subTest(kind=kind), boundary() as case:
                command = case.issue if kind == 'issue' else case.physical_return
                command.side_effect = HTTPException(409, 'Stock changed')
                self.assertEqual(case.post(kind).status_code, 409)
                case.conn.commit.assert_not_called()
                case.conn.rollback.assert_called_once()
                case.conn.close.assert_called_once()

    def test_explicit_company_mismatch_still_rejected(self):
        with boundary(membership(companyId=3)) as case:
            self.assert_denied(case, case.post('issue'), status=409)
