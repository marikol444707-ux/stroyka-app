from copy import deepcopy
from decimal import Decimal
import unittest
from unittest import mock

from backend.features.accounting_exception_checks.link_repair_runtime import (
    AccountingLinkRepairRuntimeError,
    apply_accounting_link_repairs,
    preview_accounting_link_repairs,
)


AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
FINANCE_ROLES = ("директор", "зам_директора", "бухгалтер")
PROJECTS = [{"id": 17, "company_id": 4, "name": "ЖК Северный"}]
SUPPLIERS = [{
    "id": 91,
    "company_id": 4,
    "supplier_id": 12,
    "supplier_name": "ООО Поставка",
    "project_name": "ЖК Северный",
    "amount": Decimal("1000.00"),
    "offer_id": 51,
    "request_id": 31,
    "warehouse_invoice_id": 999,
    "invoice_number": "Счёт № 14555",
    "invoice_date": "2026-08-10",
    "status": "На утверждении",
}]
WAREHOUSES = [{
    "id": 44,
    "company_id": 4,
    "supplier_id": 12,
    "supplier_name": "ООО Поставка",
    "project": "ЖК Северный",
    "total_with_vat": Decimal("1000.00"),
    "total_base": Decimal("1000.00"),
    "supply_delivery_id": 71,
    "supply_request_id": 31,
    "supplier_invoice_id": None,
    "number": "14555",
    "date": "2026-08-10",
    "status": "Принята",
}]
DELIVERIES = [{
    "id": 71,
    "company_id": 4,
    "offer_id": 51,
    "request_id": 31,
    "supplier_id": 12,
    "supplier_name": "ООО Поставка",
    "project": "ЖК Северный",
    "status": "Принято",
}]


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.connection.executed.append((normalized, params))
        self.rowcount = -1
        if self.connection.fail_on and self.connection.fail_on in normalized:
            raise RuntimeError("PRIVATE DATABASE FAILURE")
        if "FROM public.user_sessions" in normalized:
            self.rows = [{"user_id": 8}]
        elif "FROM public.user_company_roles" in normalized:
            self.rows = [{"membership_id": 81, "role": "бухгалтер"}]
        elif "FROM public.projects" in normalized:
            self.rows = deepcopy(PROJECTS)
        elif "FROM public.supplier_invoices" in normalized:
            self.rows = (
                [{"id": 91}]
                if "= ANY" in normalized
                else deepcopy(SUPPLIERS)
            )
        elif "FROM public.warehouse_invoices" in normalized:
            self.rows = (
                [{"id": 44}]
                if "= ANY" in normalized
                else deepcopy(WAREHOUSES)
            )
        elif "FROM public.supply_deliveries" in normalized:
            self.rows = deepcopy(DELIVERIES)
        elif normalized.startswith("UPDATE public.supplier_invoices"):
            self.rows = []
            self.rowcount = 1
        elif normalized.startswith("UPDATE public.warehouse_invoices"):
            self.rows = []
            self.rowcount = 1
        elif normalized.startswith("INSERT INTO public.audit_log"):
            self.rows = [{"id": 501}]
        else:
            self.rows = []

    def fetchall(self):
        return deepcopy(self.rows)

    def fetchone(self):
        return deepcopy(self.rows[0]) if self.rows else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, *, fail_on=None, fail_commit=False):
        self.fail_on = fail_on
        self.fail_commit = fail_commit
        self.executed = []
        self.session = None
        self.committed = False
        self.rollback_count = 0
        self.closed = False
        self.cursor_value = FakeCursor(self)

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("PRIVATE COMMIT FAILURE")
        self.committed = True

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


class AccountingLinkRepairRuntimeTests(unittest.TestCase):
    def assert_fixed(self, code, callback):
        with self.assertRaises(AccountingLinkRepairRuntimeError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(str(raised.exception), code)

    def test_preview_is_read_only_bounded_and_always_rolled_back(self):
        connection = FakeConnection()

        result = preview_accounting_link_repairs(
            lambda: connection,
            AUTHENTICATION,
            4,
            FINANCE_ROLES,
        )

        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["repairCount"], 1)
        self.assertEqual(result["unresolvedCount"], 0)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertFalse(connection.committed)
        self.assertEqual(connection.rollback_count, 1)
        self.assertTrue(connection.closed)
        source_queries = [
            sql for sql, _params in connection.executed
            if "ORDER BY id LIMIT" in sql
        ]
        self.assertTrue(any(
            "invoice_number" in sql and "invoice_date" in sql
            for sql in source_queries
        ))
        self.assertTrue(any(
            "COALESCE(number,'') AS number" in sql
            and "COALESCE(date::text,'') AS date" in sql
            for sql in source_queries
        ))

    def test_apply_locks_rebuilds_updates_both_sides_audits_and_commits_once(self):
        preview_connection = FakeConnection()
        preview = preview_accounting_link_repairs(
            lambda: preview_connection,
            AUTHENTICATION,
            4,
            FINANCE_ROLES,
        )
        connection = FakeConnection()

        result = apply_accounting_link_repairs(
            lambda: connection,
            AUTHENTICATION,
            4,
            FINANCE_ROLES,
            expected_repair_count=preview["repairCount"],
            expected_plan_sha256=preview["planSha256"],
        )

        self.assertEqual(result, {
            "ok": True,
            "appliedCount": 1,
            "unresolvedCount": 0,
            "planSha256": preview["planSha256"],
        })
        statements = [sql for sql, _params in connection.executed]
        self.assertTrue(any(
            "FROM public.supplier_invoices" in sql
            and "FOR UPDATE" in sql for sql in statements
        ))
        self.assertTrue(any(
            "FROM public.warehouse_invoices" in sql
            and "FOR UPDATE" in sql for sql in statements
        ))
        self.assertEqual(sum(
            sql.startswith("UPDATE public.supplier_invoices")
            for sql in statements
        ), 1)
        self.assertEqual(sum(
            sql.startswith("UPDATE public.warehouse_invoices")
            for sql in statements
        ), 1)
        self.assertEqual(sum(
            sql.startswith("INSERT INTO public.audit_log")
            for sql in statements
        ), 1)
        mutation_sql = " ".join(
            sql for sql in statements
            if sql.startswith(("UPDATE ", "INSERT INTO public.audit_log"))
        ).lower()
        for forbidden in (
            " set amount", " set status", "paid_amount", "total_with_vat",
            "total_base", "photo", "file", "items", "stock",
        ):
            self.assertNotIn(forbidden, mutation_sql)
        self.assertTrue(connection.committed)
        self.assertEqual(connection.rollback_count, 0)

    def test_apply_clears_only_the_stale_supplier_link_and_audits_it(self):
        with mock.patch(f"{__name__}.PROJECTS", []), mock.patch(
            f"{__name__}.WAREHOUSES", [],
        ), mock.patch(
            f"{__name__}.DELIVERIES", [],
        ):
            preview = preview_accounting_link_repairs(
                lambda: FakeConnection(), AUTHENTICATION, 4, FINANCE_ROLES,
            )
            connection = FakeConnection()
            result = apply_accounting_link_repairs(
                lambda: connection,
                AUTHENTICATION,
                4,
                FINANCE_ROLES,
                expected_repair_count=preview["repairCount"],
                expected_plan_sha256=preview["planSha256"],
            )

        self.assertEqual(preview["proofCounts"]["dangling"], 1)
        self.assertEqual(result["appliedCount"], 1)
        statements = [sql for sql, _params in connection.executed]
        self.assertEqual(sum(
            sql.startswith("UPDATE public.supplier_invoices")
            and "SET warehouse_invoice_id=NULL" in sql
            for sql in statements
        ), 1)
        self.assertFalse(any(
            sql.startswith("UPDATE public.warehouse_invoices")
            for sql in statements
        ))
        audit_params = next(
            params for sql, params in connection.executed
            if sql.startswith("INSERT INTO public.audit_log")
        )
        self.assertIn(
            "accounting_supplier_dangling_warehouse_link_cleared",
            audit_params,
        )
        self.assertIsNone(audit_params[-1])
        self.assertTrue(connection.committed)

    def test_stale_plan_rolls_back_without_any_business_or_audit_write(self):
        connection = FakeConnection()

        self.assert_fixed(
            "accounting_link_repair_plan_stale",
            lambda: apply_accounting_link_repairs(
                lambda: connection,
                AUTHENTICATION,
                4,
                FINANCE_ROLES,
                expected_repair_count=1,
                expected_plan_sha256="0" * 64,
            ),
        )

        self.assertFalse(connection.committed)
        self.assertEqual(connection.rollback_count, 1)
        self.assertFalse(any(
            sql.startswith(("UPDATE ", "INSERT "))
            for sql, _params in connection.executed
        ))

    def test_audit_failure_rolls_back_both_document_updates(self):
        preview = preview_accounting_link_repairs(
            lambda: FakeConnection(), AUTHENTICATION, 4, FINANCE_ROLES,
        )
        connection = FakeConnection(fail_on="INSERT INTO public.audit_log")

        self.assert_fixed(
            "accounting_link_repair_write_failed",
            lambda: apply_accounting_link_repairs(
                lambda: connection,
                AUTHENTICATION,
                4,
                FINANCE_ROLES,
                expected_repair_count=1,
                expected_plan_sha256=preview["planSha256"],
            ),
        )

        self.assertFalse(connection.committed)
        self.assertEqual(connection.rollback_count, 1)

    def test_commit_uncertainty_has_a_fixed_error_and_closes_the_connection(self):
        preview = preview_accounting_link_repairs(
            lambda: FakeConnection(), AUTHENTICATION, 4, FINANCE_ROLES,
        )
        connection = FakeConnection(fail_commit=True)

        self.assert_fixed(
            "accounting_link_repair_commit_uncertain",
            lambda: apply_accounting_link_repairs(
                lambda: connection,
                AUTHENTICATION,
                4,
                FINANCE_ROLES,
                expected_repair_count=1,
                expected_plan_sha256=preview["planSha256"],
            ),
        )
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
