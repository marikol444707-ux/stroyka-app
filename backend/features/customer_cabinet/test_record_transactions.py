"""Selected-company authorization and transaction completion are separate gates."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from fastapi import HTTPException

from .record_scope import RecordScope


class RecordTransactionTests(unittest.TestCase):
    def build(self, actors):
        connection = MagicMock()
        connection.autocommit = True
        context = {'mode': 'company', 'companyId': 2}
        resolve = Mock(return_value=context)
        effective = Mock(return_value=actors)
        scope = RecordScope(lambda: connection, resolve, effective, lambda actor: None)
        return scope, connection, resolve, effective, context

    def test_default_read_combines_authorized_companies_without_enabling_writes(self):
        allowed = [{'id': 10, 'companyId': 2, 'role': 'заказчик'},
                   {'id': 10, 'companyId': 3, 'role': 'директор'}]
        scope, connection, resolve, effective, context = self.build(
            allowed + [{'id': 10, 'companyId': 4, 'role': 'поставщик'}])
        context.update(mode='all_companies', companyIds=[2, 3, 4])
        context.pop('companyId')
        user = {'id': 10, 'role': 'директор', 'company_id': 9}
        request = SimpleNamespace(headers={'x-company-mode': 'all_companies'})
        with scope.transaction(user, request, ('заказчик', 'директор')) as (_cur, actors):
            self.assertEqual(actors, allowed)
            self.assertFalse(connection.autocommit)
        self.assertEqual(resolve.call_args.args[1:], (user, None, 'read'))
        self.assertEqual(resolve.call_args.kwargs, {'x_company_id': None, 'x_company_mode': 'all_companies'})
        effective.assert_called_once_with(user, context)
        connection.commit.assert_not_called()
        connection.close.assert_called_once()

    def test_explicit_write_commits_for_the_single_selected_company(self):
        scope, connection, resolve, _effective, _context = self.build(
            [{'id': 10, 'company_id': 2, 'role': 'директор'}])
        request = SimpleNamespace(headers={'x-company-id': '2', 'x-company-mode': 'company'})
        with scope.transaction({'id': 10}, request, ('директор',), write=True) as (_cur, actors):
            self.assertEqual([(actor['companyId'], actor['role']) for actor in actors], [(2, 'директор')])
            self.assertFalse(connection.autocommit)
        self.assertEqual(resolve.call_args.args[-1], 'write')
        self.assertEqual(resolve.call_args.kwargs, {'x_company_id': '2', 'x_company_mode': 'company'})
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    def test_write_requires_one_company_and_its_own_role(self):
        director = {'id': 10, 'companyId': 2, 'role': 'директор'}
        cases = [([], 409), ([director, dict(director, companyId=3)], 409),
                 ([dict(director, role='заказчик')], 403)]
        for actors, status in cases:
            with self.subTest(actors=actors):
                scope, connection, _resolve, _effective, _context = self.build(actors)
                with self.assertRaises(HTTPException) as error:
                    with scope.transaction(director, None, ('директор',), write=True):
                        self.fail('Unauthorized write body must not run')
                self.assertEqual(error.exception.status_code, status)
                connection.commit.assert_not_called()
                connection.rollback.assert_called_once()
                connection.close.assert_called_once()

    def test_authorization_body_and_commit_failures_abort_and_close_transaction(self):
        for failure_stage in ('authorization', 'body', 'commit'):
            with self.subTest(failure_stage=failure_stage):
                scope, connection, resolve, _effective, _context = self.build(
                    [{'id': 10, 'companyId': 2, 'role': 'директор'}])
                failure = RuntimeError('Synthetic transaction failure')
                if failure_stage == 'authorization':
                    resolve.side_effect = failure
                elif failure_stage == 'commit':
                    connection.commit.side_effect = failure
                with self.assertRaises(RuntimeError) as error:
                    with scope.transaction({'id': 10}, None, ('директор',), write=True):
                        if failure_stage == 'body':
                            raise failure
                self.assertIs(error.exception, failure)
                if failure_stage != 'commit':
                    connection.commit.assert_not_called()
                connection.rollback.assert_called_once()
                connection.close.assert_called_once()
