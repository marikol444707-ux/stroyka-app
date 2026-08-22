"""Private guarded schema contract for A11 accounting ownership.

The module has no CLI, application registration or database factory.  Dry-run
is the default; callers must explicitly provide the exact deterministic plan
count and hash before any schema statement can run.
"""

import copy
import hashlib
import json
import re

import psycopg2.extras


_VERSION = "accounting-ownership-schema-v1"
_PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MONEY_SPECIALS = "('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)"

_TABLES = (
    {
        "table": "staff",
        "project": "none",
        "money": (),
        "extraIndexes": (),
    },
    {
        "table": "accountable_payments",
        "project": "required",
        "money": ("amount", "spent_amount"),
        "extraIndexes": (),
    },
    {
        "table": "accountable_expenses",
        "project": "required",
        "money": ("amount",),
        "extraIndexes": (),
    },
    {
        "table": "expense_reports",
        "project": "required",
        "money": ("total_amount", "issued_amount", "spent_amount", "balance"),
        "extraIndexes": (),
    },
    {
        "table": "salary_payments",
        "project": "none",
        "money": ("amount",),
        "extraIndexes": (),
    },
    {
        "table": "own_expenses",
        "project": "nullable",
        "money": ("amount",),
        "extraIndexes": (
            (
                "idx_a11_own_expenses_expense_id",
                "expense_id",
                "expense_id IS NOT NULL",
            ),
        ),
    },
    {
        "table": "expenses",
        "project": "nullable",
        "money": ("amount",),
        "extraIndexes": (),
    },
)


def _owner_expression(table_contract):
    parts = ["company_id IS NOT NULL", "company_id > 0"]
    if table_contract["project"] == "required":
        parts.extend(("project_id IS NOT NULL", "project_id > 0"))
    elif table_contract["project"] == "nullable":
        parts.append("(project_id IS NULL OR project_id > 0)")
    for field in table_contract["money"]:
        parts.extend((
            f"{field} IS NOT NULL",
            f"{field} NOT IN {_MONEY_SPECIALS}",
        ))
    return " AND ".join(parts)


def _change_for(table_contract):
    table = table_contract["table"]
    columns = []
    if table != "staff":
        columns.append("ADD COLUMN IF NOT EXISTS company_id INTEGER")
    if table_contract["project"] != "none":
        columns.append("ADD COLUMN IF NOT EXISTS project_id INTEGER")
    columns.append(
        "ADD COLUMN IF NOT EXISTS company_scope_verified "
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )
    constraint = f"ck_a11_{table}_verified_owner"
    owner_expression = _owner_expression(table_contract)
    if table_contract["project"] == "required":
        index_columns = "company_id, project_id, id"
    else:
        index_columns = "company_id, id"
    owner_index = f"idx_a11_{table}_verified_owner"
    statements = [
        f"ALTER TABLE public.{table} " + ", ".join(columns),
        (
            f"DO $a11_{table}$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint "
            f"WHERE conname='{constraint}' "
            f"AND conrelid='public.{table}'::regclass) THEN "
            f"ALTER TABLE public.{table} ADD CONSTRAINT {constraint} "
            f"CHECK (company_scope_verified IS FALSE OR ({owner_expression})); "
            f"END IF; END $a11_{table}$"
        ),
        (
            f"CREATE INDEX IF NOT EXISTS {owner_index} "
            f"ON public.{table} ({index_columns}) "
            "WHERE company_scope_verified"
        ),
    ]
    for index_name, column, predicate in table_contract["extraIndexes"]:
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON public.{table} ({column}) WHERE {predicate}"
        )
    return {
        "table": table,
        "sql": ";\n".join(statements),
    }


def _changes():
    return [_change_for(table_contract) for table_contract in _TABLES]


def _plan_sha256(changes):
    payload = json.dumps(changes, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_accounting_ownership_schema_plan():
    changes = _changes()
    return {
        "version": _VERSION,
        "dryRun": True,
        "schemaReady": False,
        "changeCount": len(changes),
        "planSha256": _plan_sha256(changes),
        "writesAttempted": 0,
        "changes": copy.deepcopy(changes),
    }


def _false_default(value):
    normalized = "".join(str(value or "").lower().split())
    return normalized in {"false", "false::boolean", "'false'::boolean"}


def _schema_contract_is_exact(cursor):
    table_names = [item["table"] for item in _TABLES]
    expected_columns = {}
    for item in _TABLES:
        table = item["table"]
        expected_columns[(table, "company_id")] = ("integer", "YES", None)
        if item["project"] != "none":
            expected_columns[(table, "project_id")] = ("integer", "YES", None)
        expected_columns[(table, "company_scope_verified")] = (
            "boolean",
            "NO",
            "false",
        )

    cursor.execute(
        """SELECT table_name,column_name,data_type,is_nullable,column_default
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
              AND column_name=ANY(%s)
            ORDER BY table_name,column_name""",
        (table_names, ["company_id", "project_id", "company_scope_verified"]),
    )
    actual_columns = {}
    for raw in cursor.fetchall() or []:
        row = dict(raw or {})
        actual_columns[(row.get("table_name"), row.get("column_name"))] = (
            row.get("data_type"),
            row.get("is_nullable"),
            row.get("column_default"),
        )
    if set(actual_columns) != set(expected_columns):
        return False
    for key, expected in expected_columns.items():
        actual = actual_columns[key]
        if actual[:2] != expected[:2]:
            return False
        if key[1] == "company_scope_verified":
            if not _false_default(actual[2]):
                return False
        elif key != ("staff", "company_id") and actual[2] is not None:
            return False

    constraint_names = {
        f"ck_a11_{item['table']}_verified_owner"
        for item in _TABLES
    }
    cursor.execute(
        """SELECT namespace_row.nspname AS schema_name,
                  relation_row.relname AS table_name,
                  constraint_row.conname,
                  pg_catalog.pg_get_constraintdef(constraint_row.oid,TRUE) AS definition,
                  constraint_row.contype,
                  constraint_row.convalidated
             FROM pg_catalog.pg_constraint constraint_row
             JOIN pg_catalog.pg_class relation_row
               ON relation_row.oid=constraint_row.conrelid
             JOIN pg_catalog.pg_namespace namespace_row
               ON namespace_row.oid=relation_row.relnamespace
            WHERE namespace_row.nspname='public'
              AND relation_row.relname=ANY(%s)
              AND constraint_row.conname=ANY(%s)
            ORDER BY relation_row.relname,constraint_row.conname""",
        (table_names, sorted(constraint_names)),
    )
    constraints = {
        (row.get("table_name"), row.get("conname")): dict(row or {})
        for row in (cursor.fetchall() or [])
    }
    expected_constraint_keys = {
        (item["table"], f"ck_a11_{item['table']}_verified_owner")
        for item in _TABLES
    }
    if set(constraints) != expected_constraint_keys:
        return False
    for item in _TABLES:
        table = item["table"]
        constraint = constraints[(table, f"ck_a11_{table}_verified_owner")]
        definition = " ".join(str(constraint.get("definition") or "").split())
        required_fragments = [
            "company_scope_verified IS FALSE",
            "company_id IS NOT NULL",
            "company_id > 0",
        ]
        if item["project"] == "required":
            required_fragments.extend(("project_id IS NOT NULL", "project_id > 0"))
        elif item["project"] == "nullable":
            required_fragments.extend(("project_id IS NULL", "project_id > 0"))
        for field in item["money"]:
            required_fragments.extend((field, "NaN", "Infinity"))
        if (
            constraint.get("schema_name") != "public"
            or constraint.get("contype") != "c"
            or constraint.get("convalidated") is not True
            or any(
            fragment not in definition for fragment in required_fragments
            )
        ):
            return False

    index_contract = {}
    for item in _TABLES:
        table = item["table"]
        columns = (
            "company_id, project_id, id"
            if item["project"] == "required"
            else "company_id, id"
        )
        index_contract[f"idx_a11_{table}_verified_owner"] = (
            table,
            columns,
            "company_scope_verified",
        )
        for name, column, predicate in item["extraIndexes"]:
            index_contract[name] = (table, column, predicate)
    cursor.execute(
        """SELECT tablename,indexname,indexdef
             FROM pg_catalog.pg_indexes
            WHERE schemaname='public'
              AND indexname=ANY(%s)
            ORDER BY indexname""",
        (sorted(index_contract),),
    )
    indexes = {
        row.get("indexname"): dict(row or {})
        for row in (cursor.fetchall() or [])
    }
    if set(indexes) != set(index_contract):
        return False
    for name, (table, columns, predicate) in index_contract.items():
        definition = " ".join(str(indexes[name].get("indexdef") or "").split())
        if (
            indexes[name].get("tablename") != table
            or f"({columns})" not in definition
            or predicate not in definition
        ):
            return False
    return True


def _apply_guard(plan, expected_change_count, expected_plan_sha256):
    if (
        type(expected_change_count) is not int
        or expected_change_count != plan["changeCount"]
        or type(expected_plan_sha256) is not str
        or not _PLAN_SHA256_RE.fullmatch(expected_plan_sha256)
        or expected_plan_sha256 != plan["planSha256"]
    ):
        raise ValueError("accounting_schema_apply_guard_invalid") from None


def run_accounting_ownership_schema(
    connection,
    *,
    apply=False,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    plan = build_accounting_ownership_schema_plan()
    if apply:
        _apply_guard(plan, expected_change_count, expected_plan_sha256)
    cursor = None
    try:
        if not apply:
            connection.set_session(readonly=True, autocommit=False)
            cursor = connection.cursor()
            connection.rollback()
            result = copy.deepcopy(plan)
            result["rolledBack"] = True
            return result

        connection.set_session(
            readonly=False,
            autocommit=False,
            isolation_level="SERIALIZABLE",
        )
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        for item in _TABLES:
            cursor.execute(f"LOCK TABLE public.{item['table']} IN ACCESS EXCLUSIVE MODE")
        for change in plan["changes"]:
            cursor.execute(change["sql"])
        if not _schema_contract_is_exact(cursor):
            raise RuntimeError("accounting_schema_postcheck_failed") from None
        connection.commit()
        result = copy.deepcopy(plan)
        result.update({
            "dryRun": False,
            "schemaReady": True,
            "writesAttempted": plan["changeCount"],
            "rolledBack": False,
        })
        return result
    except BaseException:
        if cursor is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
