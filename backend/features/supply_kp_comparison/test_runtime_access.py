import ast
import copy
import inspect
import re
import unittest
from unittest import mock

import psycopg2.extras

from backend.features.supply_kp_comparison import runtime_access
from backend.features.supply_kp_comparison.runtime_access import (
    SupplyTechnicalComparisonAccessError,
    run_authorized_supply_technical_comparison,
)
from backend.features.supply_kp_comparison.source_resolver import (
    SupplyTechnicalSourceResolverError,
)


AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
ROLES = ("директор", "зам_директора", "снабженец")
SELECTORS = {
    "company_id": 1,
    "project_id": 7,
    "request_id": 31,
    "source_kind": "supplier_offer",
    "source_id": 81,
    "file_id": 44,
}
ACTOR = {
    "actor_user_id": 41,
    "actor_membership_id": 51,
    "actor_company_id": 1,
    "actor_role": "снабженец",
}


def _result():
    return {
        "ok": True,
        "dryRun": True,
        "contractVersion": 1,
        "companyId": 1,
        "projectId": 7,
        "requestId": 31,
        "sourceKind": "supplier_offer",
        "sourceId": 81,
        "file": {
            "id": 44,
            "contentUrl": "/tenant-files/44/content",
            "context": "supplier-offer",
            "originalName": "offer.pdf",
            "contentType": "application/pdf",
        },
        "requestedLineCount": 1,
        "offeredLineCount": 1,
        "comparisonCount": 1,
        "comparisons": [{"public": "comparison"}],
        "resultSha256": "b" * 64,
        "automaticApprovalAllowed": False,
        "writesAttempted": 0,
        "modelCalls": 0,
    }


class _Cursor:
    def __init__(self, rows=None, *, close_error=None):
        self.rows = [ACTOR] if rows is None else rows
        self.close_error = close_error
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchall(self):
        return copy.deepcopy(self.rows)

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Connection:
    def __init__(self, cursor, *, rollback_error=None, close_error=None):
        self.cursor_value = cursor
        self.rollback_error = rollback_error
        self.close_error = close_error
        self.sessions = []
        self.cursor_kwargs = []
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.sessions.append(dict(kwargs))

    def cursor(self, **kwargs):
        self.cursor_kwargs.append(dict(kwargs))
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def commit(self):
        self.commits += 1
        raise AssertionError("read-only comparison must never commit")

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _fixed_error(test_case, expected, callback):
    with test_case.assertRaises(SupplyTechnicalComparisonAccessError) as raised:
        callback()
    test_case.assertEqual(raised.exception.code, expected)
    test_case.assertEqual(str(raised.exception), expected)
    test_case.assertEqual(raised.exception.args, (expected,))


class SupplyTechnicalComparisonAccessTests(unittest.TestCase):
    def _run(self, connection, *, load=None, resolve=None, **updates):
        values = dict(SELECTORS)
        values.update(updates)
        get_db = mock.Mock(return_value=connection)
        loaded = {"request": {}, "source": {}, "file": {}}
        with mock.patch.object(
            runtime_access.source_resolver,
            "load_supply_technical_source_rows",
            side_effect=load or (lambda _cur, **_values: copy.deepcopy(loaded)),
        ) as load_mock, mock.patch.object(
            runtime_access.source_resolver,
            "resolve_supply_technical_source_rows",
            side_effect=resolve or (lambda _rows, **_values: _result()),
        ) as resolve_mock:
            result = run_authorized_supply_technical_comparison(
                get_db,
                AUTHENTICATION,
                ROLES,
                **values,
            )
        return result, get_db, load_mock, resolve_mock

    def test_public_runtime_surface_is_read_only_and_has_no_model_or_writer_imports(self):
        signature = inspect.signature(run_authorized_supply_technical_comparison)
        self.assertEqual(list(signature.parameters), [
            "get_db", "authentication", "allowed_roles", "company_id",
            "project_id", "request_id", "source_kind", "source_id",
            "file_id",
        ])
        self.assertEqual(runtime_access.__all__, [
            "SupplyTechnicalComparisonAccessError",
            "run_authorized_supply_technical_comparison",
        ])
        source = inspect.getsource(runtime_access)
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name.lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append((node.module or "").lower())
                imported.extend(alias.name.lower() for alias in node.names)
        joined = " ".join(imported)
        for forbidden in (
            "backend.main", "writer", "yandex", "openai", "gemini",
            "requests", "httpx", "smtp", "messenger", "outbox",
        ):
            self.assertNotIn(forbidden, joined)
        sql = " ".join(
            node.value.upper() for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
        self.assertIsNone(re.search(
            r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b", sql,
        ))
        self.assertNotIn("FOR UPDATE", sql)
        self.assertFalse(any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            for node in ast.walk(tree)
        ))

    def test_one_snapshot_authorizes_company_role_then_resolves_and_always_rolls_back(self):
        cursor = _Cursor()
        connection = _Connection(cursor)
        events = []

        def load(cur, **values):
            self.assertIs(cur, cursor)
            self.assertEqual(values, SELECTORS)
            events.append("load")
            return {"request": {}, "source": {}, "file": {}}

        def resolve(rows, **values):
            self.assertEqual(rows, {"request": {}, "source": {}, "file": {}})
            self.assertEqual(values, SELECTORS)
            events.append("resolve")
            return _result()

        result, get_db, load_mock, resolve_mock = self._run(
            connection, load=load, resolve=resolve,
        )

        get_db.assert_called_once_with()
        load_mock.assert_called_once()
        resolve_mock.assert_called_once()
        self.assertEqual(connection.sessions, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.cursor_kwargs, [{
            "cursor_factory": psycopg2.extras.RealDictCursor,
        }])
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        self.assertEqual(events, ["load", "resolve"])
        auth_sql, auth_params = cursor.calls[-1]
        compact = auth_sql.lower()
        for required in (
            "from public.user_sessions", "join public.user_company_roles",
            "session.revoked_at is null", "session.two_factor_passed is true",
            "membership.company_id=%s", "membership.active is true",
            "company.active is true", "platform_account.status='active'",
        ):
            self.assertIn(required, compact)
        self.assertEqual(auth_params, ("a" * 64, 1, 2))
        self.assertEqual(result, {
            **_result(),
            "readOnlyTransaction": True,
            "rolledBack": True,
        })

    def test_invalid_inputs_fail_before_opening_database(self):
        invalid = (
            (None, AUTHENTICATION, ROLES, SELECTORS),
            (lambda: None, {**AUTHENTICATION, "private": "x"}, ROLES, SELECTORS),
            (lambda: None, AUTHENTICATION, ("снабженец", "снабженец"), SELECTORS),
            (lambda: None, AUTHENTICATION, ROLES, {**SELECTORS, "company_id": True}),
            (lambda: None, AUTHENTICATION, ROLES, {**SELECTORS, "source_kind": "PRIVATE"}),
        )
        for get_db, authentication, roles, selectors in invalid:
            with self.subTest(selectors=selectors):
                _fixed_error(
                    self,
                    "supply_technical_comparison_access_input_invalid",
                    lambda: run_authorized_supply_technical_comparison(
                        get_db, authentication, roles, **selectors,
                    ),
                )

    def test_inactive_foreign_or_wrong_role_actor_is_nonleaking_not_found(self):
        for rows in ([], [ACTOR, ACTOR], [{**ACTOR, "actor_role": "бухгалтер"}]):
            with self.subTest(rows=rows):
                connection = _Connection(_Cursor(rows=rows))
                _fixed_error(
                    self,
                    "supply_technical_comparison_access_not_found",
                    lambda: self._run(connection),
                )
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(connection.closed)

    def test_source_failure_is_nonleaking_not_found_and_unknown_failure_is_unavailable(self):
        connection = _Connection(_Cursor())
        error = SupplyTechnicalSourceResolverError()
        error.private = "PRIVATE_DB"
        _fixed_error(
            self,
            "supply_technical_comparison_access_not_found",
            lambda: self._run(
                connection,
                resolve=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
            ),
        )
        self.assertNotIn("PRIVATE", repr(error))

        connection = _Connection(_Cursor())
        _fixed_error(
            self,
            "supply_technical_comparison_access_read_failed",
            lambda: self._run(
                connection,
                resolve=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("PRIVATE_STACK")
                ),
            ),
        )

    def test_rollback_failure_has_priority_and_cleanup_failure_is_fixed(self):
        connection = _Connection(_Cursor(), rollback_error=RuntimeError("PRIVATE"))
        _fixed_error(
            self,
            "supply_technical_comparison_access_rollback_failed",
            lambda: self._run(connection),
        )
        connection = _Connection(_Cursor(close_error=RuntimeError("PRIVATE")))
        _fixed_error(
            self,
            "supply_technical_comparison_access_cleanup_failed",
            lambda: self._run(connection),
        )


if __name__ == "__main__":
    unittest.main()
