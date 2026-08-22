import unittest
from unittest import mock

from backend.features.accounting_exception_checks import runtime_access


AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
FINANCE_ROLES = ("директор", "зам_директора", "бухгалтер")
REPORT = {
    "version": "accounting-exception-projection-v1",
    "companyId": 4,
    "state": "clear",
    "scanComplete": True,
    "sourceCounts": {},
    "findingCount": 0,
    "findings": [],
    "truncated": False,
    "blockers": [],
}


class _Cursor:
    def __init__(self, result_sets, *, execute_error_at=None, close_error=None):
        self.result_sets = list(result_sets)
        self.calls = []
        self.closed = False
        self.execute_error_at = execute_error_at
        self.close_error = close_error

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        if (
            self.execute_error_at is not None
            and len(self.calls) == self.execute_error_at[0]
        ):
            raise self.execute_error_at[1]

    def fetchall(self):
        return self.result_sets.pop(0)

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Connection:
    def __init__(
        self,
        result_sets,
        *,
        execute_error_at=None,
        rollback_error=None,
        cursor_close_error=None,
        close_error=None,
    ):
        self.cursor_value = _Cursor(
            result_sets,
            execute_error_at=execute_error_at,
            close_error=cursor_close_error,
        )
        self.session = None
        self.rollbacks = 0
        self.closed = False
        self.rollback_error = rollback_error
        self.close_error = close_error

    def set_session(self, **kwargs):
        self.session = dict(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class AccountingExceptionRuntimeAccessTests(unittest.TestCase):
    def assert_code(self, code, operation):
        with self.assertRaises(runtime_access.AccountingExceptionAccessError) as ctx:
            operation()
        self.assertEqual(ctx.exception.args, (code,))
        self.assertEqual(ctx.exception.code, code)
        self.assertIsNone(ctx.exception.__cause__)
        self.assertNotIn("PRIVATE", str(ctx.exception))

    def test_finance_membership_is_checked_before_snapshot_in_one_transaction(self):
        connection = _Connection([
            [{"user_id": 31}],
            [{"role": "бухгалтер"}],
        ])

        with mock.patch.object(
            runtime_access,
            "collect_accounting_exception_snapshot",
            return_value=dict(REPORT),
        ) as collect:
            result = runtime_access.run_authorized_accounting_exception_snapshot(
                lambda: connection,
                AUTHENTICATION,
                4,
                FINANCE_ROLES,
            )

        self.assertEqual(result, REPORT)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(len(connection.cursor_value.calls), 3)
        self.assertIn("FROM public.user_sessions", connection.cursor_value.calls[1][0])
        self.assertIn("FROM public.user_company_roles", connection.cursor_value.calls[2][0])
        self.assertEqual(connection.cursor_value.calls[1][1], ("a" * 64,))
        self.assertEqual(connection.cursor_value.calls[2][1], (31, 4))
        collect.assert_called_once_with(connection.cursor_value, 4)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_invalid_session_and_nonfinance_membership_stop_before_snapshot(self):
        cases = (
            ([[], [{"role": "бухгалтер"}]],
             "accounting_exception_review_authentication_required"),
            ([[{"user_id": 31}], [{"role": "прораб"}]],
             "accounting_exception_review_request_forbidden"),
            ([[{"user_id": 31}], [{"role": "бухгалтер"}, {"role": "директор"}]],
             "accounting_exception_review_request_forbidden"),
        )
        for result_sets, code in cases:
            with self.subTest(code=code, result_sets=result_sets):
                connection = _Connection(result_sets)
                with mock.patch.object(
                    runtime_access,
                    "collect_accounting_exception_snapshot",
                ) as collect:
                    self.assert_code(code, lambda: (
                        runtime_access.run_authorized_accounting_exception_snapshot(
                            lambda: connection,
                            AUTHENTICATION,
                            4,
                            FINANCE_ROLES,
                        )
                    ))
                collect.assert_not_called()
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(connection.cursor_value.closed)
                self.assertTrue(connection.closed)

    def test_invalid_inputs_open_no_connection(self):
        invalid = (
            (None, AUTHENTICATION, 4, FINANCE_ROLES),
            (lambda: None, {**AUTHENTICATION, "raw": "PRIVATE"}, 4, FINANCE_ROLES),
            (lambda: None, AUTHENTICATION, True, FINANCE_ROLES),
            (lambda: None, AUTHENTICATION, 4, ("бухгалтер", "бухгалтер")),
            (lambda: None, AUTHENTICATION, 4, ["бухгалтер"]),
        )
        for get_db, authentication, company_id, roles in invalid:
            with self.subTest(company_id=company_id, roles=roles):
                calls = []

                def connect():
                    calls.append(True)
                    return _Connection([])

                factory = connect if callable(get_db) else get_db
                self.assert_code(
                    "accounting_exception_review_input_invalid",
                    lambda: runtime_access.run_authorized_accounting_exception_snapshot(
                        factory, authentication, company_id, roles,
                    ),
                )
                self.assertEqual(calls, [])

    def test_malformed_auth_rows_fail_closed_without_private_text(self):
        malformed_sets = (
            [{"user_id": 31, "private": "PRIVATE"}],
            [{"user_id": True}],
        )
        for session_rows in malformed_sets:
            with self.subTest(session_rows=session_rows):
                connection = _Connection([session_rows, []])
                with mock.patch.object(
                    runtime_access,
                    "collect_accounting_exception_snapshot",
                ) as collect:
                    self.assert_code(
                        "accounting_exception_review_read_failed",
                        lambda: runtime_access.run_authorized_accounting_exception_snapshot(
                            lambda: connection,
                            AUTHENTICATION,
                            4,
                            FINANCE_ROLES,
                        ),
                    )
                collect.assert_not_called()

    def test_rollback_and_cleanup_precedence_are_fixed(self):
        rollback = _Connection(
            [],
            execute_error_at=(1, RuntimeError("PRIVATE_READ")),
            rollback_error=RuntimeError("PRIVATE_ROLLBACK"),
        )
        self.assert_code(
            "accounting_exception_review_rollback_failed",
            lambda: runtime_access.run_authorized_accounting_exception_snapshot(
                lambda: rollback, AUTHENTICATION, 4, FINANCE_ROLES,
            ),
        )
        self.assertTrue(rollback.cursor_value.closed)
        self.assertTrue(rollback.closed)

        cleanup = _Connection(
            [[{"user_id": 31}], [{"role": "бухгалтер"}]],
            cursor_close_error=RuntimeError("PRIVATE_CURSOR"),
        )
        with mock.patch.object(
            runtime_access,
            "collect_accounting_exception_snapshot",
            return_value=dict(REPORT),
        ):
            self.assert_code(
                "accounting_exception_review_cleanup_failed",
                lambda: runtime_access.run_authorized_accounting_exception_snapshot(
                    lambda: cleanup, AUTHENTICATION, 4, FINANCE_ROLES,
                ),
            )
        self.assertTrue(cleanup.closed)

    def test_first_named_control_flow_keeps_identity_after_cleanup(self):
        control = KeyboardInterrupt("PRIVATE_CONTROL")
        connection = _Connection(
            [], execute_error_at=(1, control),
            close_error=SystemExit("LATER_CONTROL"),
        )
        with self.assertRaises(KeyboardInterrupt) as ctx:
            runtime_access.run_authorized_accounting_exception_snapshot(
                lambda: connection, AUTHENTICATION, 4, FINANCE_ROLES,
            )
        self.assertIs(ctx.exception, control)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
