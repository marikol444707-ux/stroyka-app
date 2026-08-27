import inspect
import unittest
from unittest import mock

from backend.features.accounting_exception_checks import link_integrity_schema


class AccountingLinkIntegritySchemaPlanTests(unittest.TestCase):
    def test_plan_is_deterministic_additive_and_clears_deleted_targets(self):
        first = link_integrity_schema.build_accounting_link_integrity_schema_plan()
        second = link_integrity_schema.build_accounting_link_integrity_schema_plan()

        self.assertEqual(first, second)
        self.assertEqual(first["version"], "accounting-link-integrity-schema-v1")
        self.assertTrue(first["dryRun"])
        self.assertFalse(first["schemaReady"])
        self.assertEqual(first["changeCount"], 2)
        self.assertEqual(first["writesAttempted"], 0)
        self.assertRegex(first["planSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            [change["table"] for change in first["changes"]],
            ["supplier_invoices", "warehouse_invoices"],
        )

        sql = "\n".join(change["sql"] for change in first["changes"])
        self.assertIn(
            "FOREIGN KEY (warehouse_invoice_id) "
            "REFERENCES public.warehouse_invoices(id)",
            sql,
        )
        self.assertIn(
            "FOREIGN KEY (supplier_invoice_id) "
            "REFERENCES public.supplier_invoices(id)",
            sql,
        )
        self.assertEqual(sql.count("ON DELETE SET NULL"), 2)
        self.assertEqual(sql.count("DEFERRABLE INITIALLY IMMEDIATE"), 2)
        self.assertNotRegex(sql.upper(), r"\b(INSERT|UPDATE|DELETE FROM|TRUNCATE)\b")
        self.assertNotIn("DROP ", sql.upper())

    def test_contract_has_no_database_factory_or_application_registration(self):
        source = inspect.getsource(link_integrity_schema)

        self.assertNotIn("backend.main", source)
        self.assertNotIn("get_db", source)
        self.assertNotIn("register_", source)
        self.assertNotIn("if __name__", source)


class _Cursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, query, params=()):
        self.calls.append((" ".join(str(query).split()), tuple(params or ())))

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_value = _Cursor()
        self.session_calls = []
        self.commits = 0
        self.rollbacks = 0

    def set_session(self, **kwargs):
        self.session_calls.append(dict(kwargs))

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _CatalogCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((" ".join(str(query).split()), tuple(params or ())))

    def fetchall(self):
        return self.rows


def _exact_constraint_rows():
    rows = []
    for contract in link_integrity_schema._CONTRACTS:
        rows.append({
            "source_schema": "public",
            "source_table": contract["table"],
            "target_schema": "public",
            "target_table": contract["target"],
            "conname": contract["constraint"],
            "contype": "f",
            "convalidated": True,
            "condeferrable": True,
            "condeferred": False,
            "definition": (
                f"FOREIGN KEY ({contract['column']}) "
                f"REFERENCES {contract['target']}(id) "
                "ON DELETE SET NULL DEFERRABLE"
            ),
        })
    return rows


class AccountingLinkIntegritySchemaRunnerTests(unittest.TestCase):
    def test_catalog_check_requires_the_exact_referenced_id_column(self):
        exact = _CatalogCursor(_exact_constraint_rows())
        self.assertTrue(link_integrity_schema._schema_contract_is_exact(exact))

        wrong_rows = _exact_constraint_rows()
        wrong_rows[0]["definition"] = wrong_rows[0]["definition"].replace(
            "warehouse_invoices(id)", "warehouse_invoices(external_id)",
        )
        self.assertFalse(link_integrity_schema._schema_contract_is_exact(
            _CatalogCursor(wrong_rows),
        ))

    def test_dry_run_reports_readiness_and_rolls_back_without_ddl(self):
        connection = _Connection()
        readiness = {
            "supplierInvoiceDanglingCount": 0,
            "warehouseInvoiceDanglingCount": 0,
        }

        with mock.patch.object(
            link_integrity_schema, "_readiness", return_value=readiness,
        ), mock.patch.object(
            link_integrity_schema, "_schema_contract_is_exact", return_value=False,
        ):
            report = link_integrity_schema.run_accounting_link_integrity_schema(
                connection,
            )

        self.assertTrue(report["dryRun"])
        self.assertTrue(report["readyForApply"])
        self.assertFalse(report["schemaReady"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["rolledBack"])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)

    def test_dry_run_blocks_when_either_direction_is_dangling(self):
        connection = _Connection()
        readiness = {
            "supplierInvoiceDanglingCount": 2,
            "warehouseInvoiceDanglingCount": 1,
        }

        with mock.patch.object(
            link_integrity_schema, "_readiness", return_value=readiness,
        ), mock.patch.object(
            link_integrity_schema, "_schema_contract_is_exact", return_value=False,
        ):
            report = link_integrity_schema.run_accounting_link_integrity_schema(
                connection,
            )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(
            report["blockers"],
            ["supplier_invoice_links_dangling", "warehouse_invoice_links_dangling"],
        )

    def test_apply_requires_exact_plan_before_opening_a_cursor(self):
        plan = link_integrity_schema.build_accounting_link_integrity_schema_plan()
        connection = _Connection()

        with self.assertRaisesRegex(
            ValueError, "accounting_link_integrity_apply_guard_invalid",
        ):
            link_integrity_schema.run_accounting_link_integrity_schema(
                connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256="0" * 64,
            )

        self.assertEqual(connection.cursor_value.calls, [])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 0)

    def test_guarded_apply_rechecks_under_locks_and_commits_exact_plan(self):
        plan = link_integrity_schema.build_accounting_link_integrity_schema_plan()
        connection = _Connection()
        readiness = {
            "supplierInvoiceDanglingCount": 0,
            "warehouseInvoiceDanglingCount": 0,
        }

        with mock.patch.object(
            link_integrity_schema, "_readiness", return_value=readiness,
        ), mock.patch.object(
            link_integrity_schema, "_schema_contract_is_exact", return_value=True,
        ):
            report = link_integrity_schema.run_accounting_link_integrity_schema(
                connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )

        self.assertFalse(report["dryRun"])
        self.assertTrue(report["schemaReady"])
        self.assertEqual(report["writesAttempted"], 2)
        self.assertFalse(report["rolledBack"])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        sql = [query for query, _params in connection.cursor_value.calls]
        self.assertEqual(sum(query.startswith("LOCK TABLE public.") for query in sql), 2)
        self.assertEqual(sum("ADD CONSTRAINT" in query for query in sql), 2)

    def test_apply_rolls_back_before_ddl_when_dangling_link_reappears(self):
        plan = link_integrity_schema.build_accounting_link_integrity_schema_plan()
        connection = _Connection()
        readiness = {
            "supplierInvoiceDanglingCount": 1,
            "warehouseInvoiceDanglingCount": 0,
        }

        with mock.patch.object(
            link_integrity_schema, "_readiness", return_value=readiness,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "accounting_link_integrity_not_ready",
            ):
                link_integrity_schema.run_accounting_link_integrity_schema(
                    connection,
                    apply=True,
                    expected_change_count=plan["changeCount"],
                    expected_plan_sha256=plan["planSha256"],
                )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        sql = [query for query, _params in connection.cursor_value.calls]
        self.assertEqual(sum("ADD CONSTRAINT" in query for query in sql), 0)

    def test_apply_rolls_back_when_catalog_postcheck_is_not_exact(self):
        plan = link_integrity_schema.build_accounting_link_integrity_schema_plan()
        connection = _Connection()
        readiness = {
            "supplierInvoiceDanglingCount": 0,
            "warehouseInvoiceDanglingCount": 0,
        }

        with mock.patch.object(
            link_integrity_schema, "_readiness", return_value=readiness,
        ), mock.patch.object(
            link_integrity_schema, "_schema_contract_is_exact", return_value=False,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "accounting_link_integrity_postcheck_failed",
            ):
                link_integrity_schema.run_accounting_link_integrity_schema(
                    connection,
                    apply=True,
                    expected_change_count=plan["changeCount"],
                    expected_plan_sha256=plan["planSha256"],
                )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)


if __name__ == "__main__":
    unittest.main()
