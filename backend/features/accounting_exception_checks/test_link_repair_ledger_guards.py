"""Focused ledger boundary/ordering regressions; no application or DB import."""
import unittest
from unittest.mock import patch

from . import link_repair_runtime as runtime
from .test_link_repair_runtime import (
    AUTHENTICATION, FINANCE_ROLES, FakeConnection, FakeCursor,
)


class LedgerCursor(FakeCursor):
    def execute(self, sql, params=None):
        super().execute(sql, params)
        normalized = ' '.join(sql.split())
        if 'to_regclass' in normalized:
            self.rows = [{'present': self.connection.ledger}]
        elif 'pg_try_advisory_xact_lock' in normalized:
            self.rows = [{'locked': True}]
        elif normalized.startswith('SELECT company_id FROM supplier_invoices'):
            self.rows = [{'company_id': 4}]
        elif normalized.startswith('SELECT company_id FROM warehouse_invoices'):
            self.rows = [{'company_id': 4}]
        elif normalized.startswith('WITH invoices AS'):
            self.rows = [{'managed': self.connection.managed, 'foreign_owner': False}]
        elif 'FROM public.user_company_roles' in normalized and self.connection.forbidden:
            self.rows = []


class LedgerConnection(FakeConnection):
    def __init__(self, *, ledger=True, managed=False, forbidden=False):
        super().__init__()
        self.ledger, self.managed, self.forbidden = ledger, managed, forbidden
        self.cursor_value = LedgerCursor(self)


class LinkRepairLedgerGuardsTests(unittest.TestCase):
    def preview(self):
        return runtime.preview_accounting_link_repairs(
            lambda: FakeConnection(), AUTHENTICATION, 4, FINANCE_ROLES,
        )

    def apply(self, connection):
        preview = self.preview()
        return runtime.apply_accounting_link_repairs(
            lambda: connection, AUTHENTICATION, 4, FINANCE_ROLES,
            expected_repair_count=preview['repairCount'],
            expected_plan_sha256=preview['planSha256'],
        )

    def test_registered_baseline_blocks_all_business_and_audit_writes(self):
        conn = LedgerConnection(managed=True)
        with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
            self.apply(conn)
        self.assertEqual(error.exception.code, 'accounting_link_repair_plan_blocked')
        self.assertFalse(conn.committed)
        self.assertFalse(any(sql.startswith(('UPDATE ', 'INSERT ')) for sql, _ in conn.executed))

    def test_guard_checks_both_roots_and_proposed_links_before_writes(self):
        from backend.features.supplier_payments import guards
        conn = LedgerConnection()
        with patch.object(guards, 'require_unmanaged_document', wraps=guards.require_unmanaged_document) as guard:
            self.apply(conn)
        self.assertEqual([(call.args[1:], call.kwargs) for call in guard.call_args_list], [
            (('invoice', 91), {'proposed_link': 44}),
            (('warehouse', 44), {'proposed_link': 91}),
        ])

    def test_nonblocking_stock_table_company_row_order_and_fresh_snapshot(self):
        conn = LedgerConnection()
        self.apply(conn)
        self.assertEqual(conn.session['isolation_level'], 'READ COMMITTED')
        statements = [sql for sql, _ in conn.executed]
        advisory = next(i for i, sql in enumerate(statements) if 'pg_try_advisory_xact_lock' in sql)
        self.assertEqual(conn.executed[advisory][1], (1735289201, 4))
        auth = [i for i, sql in enumerate(statements) if 'FROM public.user_company_roles' in sql]
        self.assertLess(auth[0], advisory)
        self.assertGreater(auth[-1], advisory)
        self.assertTrue(any(sql.startswith('LOCK TABLE') for sql in statements))
        self.assertTrue(all(i > advisory for i, sql in enumerate(statements) if 'FOR UPDATE' in sql))
        self.assertTrue(all(i < advisory and 'NOWAIT' in sql for i, sql in enumerate(statements)
                            if sql.startswith('LOCK TABLE')))

    def test_authorization_failure_precedes_locks_and_ledger_conflict(self):
        conn = LedgerConnection(managed=True, forbidden=True)
        with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
            self.apply(conn)
        self.assertEqual(error.exception.code, 'accounting_link_repair_request_forbidden')
        self.assertFalse(any('pg_advisory' in sql or 'FOR UPDATE' in sql or sql.startswith('LOCK TABLE')
                             for sql, _ in conn.executed))

    def test_no_0017_keeps_original_serializable_apply(self):
        conn = LedgerConnection(ledger=False)
        self.assertTrue(self.apply(conn)['ok'])
        self.assertEqual(conn.session['isolation_level'], 'SERIALIZABLE')

    def test_revocation_at_locked_reauthorization_prevents_all_writes(self):
        conn = LedgerConnection()
        authorize = runtime._authorize
        calls = []

        def revoke(cur, *args, **kwargs):
            calls.append(True)
            if len(calls) == 2:
                conn.forbidden = True
            return authorize(cur, *args, **kwargs)

        # Build preview outside the mocked authorization count.
        preview = self.preview()
        with patch.object(runtime, '_authorize', side_effect=revoke):
            with self.assertRaises(runtime.AccountingLinkRepairRuntimeError) as error:
                runtime.apply_accounting_link_repairs(
                    lambda: conn, AUTHENTICATION, 4, FINANCE_ROLES,
                    expected_repair_count=preview['repairCount'],
                    expected_plan_sha256=preview['planSha256'],
                )
        self.assertEqual(error.exception.code, 'accounting_link_repair_request_forbidden')
        self.assertFalse(any(sql.startswith(('UPDATE ', 'INSERT ')) for sql, _ in conn.executed))

    def test_preview_remains_read_only_without_ledger_probe_or_locks(self):
        conn = LedgerConnection(managed=True)
        runtime.preview_accounting_link_repairs(lambda: conn, AUTHENTICATION, 4, FINANCE_ROLES)
        self.assertEqual(conn.session['isolation_level'], 'REPEATABLE READ')
        self.assertTrue(conn.session['readonly'])
        self.assertFalse(any('to_regclass' in sql or 'pg_advisory' in sql or 'FOR UPDATE' in sql or 'FOR SHARE' in sql
                             for sql, _ in conn.executed))


if __name__ == '__main__':
    unittest.main()
