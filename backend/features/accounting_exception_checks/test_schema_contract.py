import inspect
import unittest
from unittest import mock

from backend.features.accounting_exception_checks import schema_contract


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
    def __init__(self, columns, constraints, indexes):
        self._results = [columns, constraints, indexes]
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((" ".join(str(query).split()), tuple(params or ())))

    def fetchall(self):
        return self._results[len(self.calls) - 1]


def _exact_catalog_rows():
    columns = []
    constraints = []
    indexes = []
    for item in schema_contract._TABLES:
        table = item["table"]
        columns.append({
            "table_name": table,
            "column_name": "company_id",
            "data_type": "integer",
            "is_nullable": "YES",
            "column_default": "1" if table == "staff" else None,
        })
        if item["project"] != "none":
            columns.append({
                "table_name": table,
                "column_name": "project_id",
                "data_type": "integer",
                "is_nullable": "YES",
                "column_default": None,
            })
        columns.append({
            "table_name": table,
            "column_name": "company_scope_verified",
            "data_type": "boolean",
            "is_nullable": "NO",
            "column_default": "false",
        })
        owner_fragments = [
            "company_scope_verified IS FALSE",
            "company_id IS NOT NULL",
            "company_id > 0",
        ]
        if item["project"] == "required":
            owner_fragments.extend(("project_id IS NOT NULL", "project_id > 0"))
        elif item["project"] == "nullable":
            owner_fragments.extend(("project_id IS NULL", "project_id > 0"))
        for field in item["money"]:
            owner_fragments.extend((field, "NaN", "Infinity"))
        constraints.append({
            "schema_name": "public",
            "table_name": table,
            "conname": f"ck_a11_{table}_verified_owner",
            "definition": "CHECK (" + " AND ".join(owner_fragments) + ")",
            "contype": "c",
            "convalidated": True,
        })
        index_columns = (
            "company_id, project_id, id"
            if item["project"] == "required"
            else "company_id, id"
        )
        indexes.append({
            "tablename": table,
            "indexname": f"idx_a11_{table}_verified_owner",
            "indexdef": (
                f"CREATE INDEX ON public.{table} ({index_columns}) "
                "WHERE company_scope_verified"
            ),
        })
        for name, column, predicate in item["extraIndexes"]:
            indexes.append({
                "tablename": table,
                "indexname": name,
                "indexdef": (
                    f"CREATE INDEX ON public.{table} ({column}) WHERE {predicate}"
                ),
            })
    return columns, constraints, indexes


class AccountingOwnershipSchemaPlanTests(unittest.TestCase):
    def test_plan_is_deterministic_append_only_and_false_by_default(self):
        first = schema_contract.build_accounting_ownership_schema_plan()
        second = schema_contract.build_accounting_ownership_schema_plan()

        self.assertEqual(first, second)
        self.assertEqual(first["version"], "accounting-ownership-schema-v1")
        self.assertEqual(first["changeCount"], 7)
        self.assertRegex(first["planSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(first["writesAttempted"], 0)
        self.assertTrue(first["dryRun"])
        self.assertEqual(
            [item["table"] for item in first["changes"]],
            [
                "staff",
                "accountable_payments",
                "accountable_expenses",
                "expense_reports",
                "salary_payments",
                "own_expenses",
                "expenses",
            ],
        )

        sql = "\n".join(item["sql"] for item in first["changes"])
        self.assertNotRegex(sql.upper(), r"\b(INSERT|UPDATE|DELETE|TRUNCATE)\b")
        self.assertNotIn("DROP ", sql.upper())
        self.assertEqual(sql.count("company_scope_verified BOOLEAN NOT NULL DEFAULT FALSE"), 7)
        self.assertEqual(sql.count("company_id INTEGER"), 6)
        self.assertEqual(sql.count("project_id INTEGER"), 5)
        self.assertIn("amount NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)", sql)
        self.assertIn("spent_amount NOT IN", sql)
        self.assertIn("balance NOT IN", sql)
        self.assertNotIn("employee_id", sql)

    def test_runtime_module_has_no_application_registration_or_automatic_apply(self):
        source = inspect.getsource(schema_contract)

        self.assertNotIn("backend.main", source)
        self.assertNotIn("get_db", source)
        self.assertNotIn("register_", source)
        self.assertNotIn("if __name__", source)
        self.assertNotIn("argparse", source)


class AccountingOwnershipSchemaRunnerTests(unittest.TestCase):
    def test_catalog_postcheck_is_public_table_bound_and_rejects_id_defaults(self):
        rows = _exact_catalog_rows()
        exact_cursor = _CatalogCursor(*rows)

        self.assertTrue(schema_contract._schema_contract_is_exact(exact_cursor))
        constraint_sql, constraint_params = exact_cursor.calls[1]
        self.assertIn("namespace_row.nspname='public'", constraint_sql)
        self.assertIn("relation_row.relname=ANY(%s)", constraint_sql)
        self.assertEqual(set(constraint_params[0]), {
            item["table"] for item in schema_contract._TABLES
        })

        defaulted_rows = _exact_catalog_rows()
        next(
            row for row in defaulted_rows[0]
            if row["table_name"] == "accountable_payments"
            and row["column_name"] == "company_id"
        )["column_default"] = "1"
        self.assertFalse(schema_contract._schema_contract_is_exact(
            _CatalogCursor(*defaulted_rows)
        ))

        wrong_table_rows = _exact_catalog_rows()
        wrong_table_rows[1][0]["table_name"] = "foreign_staff"
        self.assertFalse(schema_contract._schema_contract_is_exact(
            _CatalogCursor(*wrong_table_rows)
        ))

    def test_dry_run_rolls_back_without_executing_schema_sql(self):
        connection = _Connection()

        report = schema_contract.run_accounting_ownership_schema(connection)

        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertEqual(connection.cursor_value.calls, [])

    def test_apply_requires_exact_count_and_plan_hash_before_lock_or_ddl(self):
        plan = schema_contract.build_accounting_ownership_schema_plan()
        connection = _Connection()

        with self.assertRaisesRegex(ValueError, "accounting_schema_apply_guard_invalid"):
            schema_contract.run_accounting_ownership_schema(
                connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256="0" * 64,
            )

        self.assertEqual(connection.cursor_value.calls, [])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 0)

    def test_guarded_apply_locks_every_table_validates_and_commits_once(self):
        plan = schema_contract.build_accounting_ownership_schema_plan()
        connection = _Connection()

        with mock.patch.object(schema_contract, "_schema_contract_is_exact", return_value=True):
            report = schema_contract.run_accounting_ownership_schema(
                connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )

        self.assertFalse(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 7)
        self.assertTrue(report["schemaReady"])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        sql = " ".join(query for query, _params in connection.cursor_value.calls)
        self.assertEqual(sql.count("LOCK TABLE public."), 7)
        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 8)
        executed_changes = [
            query
            for query, _params in connection.cursor_value.calls
            if not query.startswith("LOCK TABLE public.")
        ]
        self.assertEqual(
            executed_changes,
            [" ".join(item["sql"].split()) for item in plan["changes"]],
        )

    def test_postcheck_failure_rolls_back_every_schema_change(self):
        plan = schema_contract.build_accounting_ownership_schema_plan()
        connection = _Connection()

        with mock.patch.object(schema_contract, "_schema_contract_is_exact", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "accounting_schema_postcheck_failed"):
                schema_contract.run_accounting_ownership_schema(
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
