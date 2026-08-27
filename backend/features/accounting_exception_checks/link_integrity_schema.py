"""Pure additive schema plan preventing dangling accounting document links.

This module deliberately has no database factory or application registration.
Dry-run is the default; apply requires the exact frozen count and plan hash,
rechecks readiness under locks, and validates the committed catalog shape.
"""

import copy
import hashlib
import json
import re

import psycopg2.extras


_VERSION = "accounting-link-integrity-schema-v1"
_PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTRACTS = (
    {
        "table": "supplier_invoices",
        "constraint": "fk_a11_supplier_invoices_warehouse_invoice",
        "column": "warehouse_invoice_id",
        "target": "warehouse_invoices",
    },
    {
        "table": "warehouse_invoices",
        "constraint": "fk_a11_warehouse_invoices_supplier_invoice",
        "column": "supplier_invoice_id",
        "target": "supplier_invoices",
    },
)


def _change(contract):
    table = contract["table"]
    constraint = contract["constraint"]
    column = contract["column"]
    target = contract["target"]
    block = f"a11_link_{table}"
    return {
        "table": table,
        "sql": (
            f"DO ${block}$ BEGIN "
            "IF NOT EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_constraint "
            f"WHERE conname='{constraint}' "
            f"AND conrelid='public.{table}'::regclass"
            ") THEN "
            f"ALTER TABLE public.{table} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({column}) REFERENCES public.{target}(id) "
            "ON DELETE SET NULL DEFERRABLE INITIALLY IMMEDIATE; "
            f"END IF; END ${block}$"
        ),
    }


def _changes():
    return [_change(contract) for contract in _CONTRACTS]


def _plan_sha256(changes):
    payload = json.dumps(changes, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_accounting_link_integrity_schema_plan():
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


def _readiness(cursor):
    cursor.execute(
        """SELECT
              (SELECT COUNT(*)
                 FROM public.supplier_invoices supplier_invoice
                 LEFT JOIN public.warehouse_invoices warehouse_invoice
                   ON warehouse_invoice.id=supplier_invoice.warehouse_invoice_id
                WHERE supplier_invoice.warehouse_invoice_id IS NOT NULL
                  AND warehouse_invoice.id IS NULL)
                AS supplier_invoice_dangling_count,
              (SELECT COUNT(*)
                 FROM public.warehouse_invoices warehouse_invoice
                 LEFT JOIN public.supplier_invoices supplier_invoice
                   ON supplier_invoice.id=warehouse_invoice.supplier_invoice_id
                WHERE warehouse_invoice.supplier_invoice_id IS NOT NULL
                  AND supplier_invoice.id IS NULL)
                AS warehouse_invoice_dangling_count"""
    )
    row = dict(cursor.fetchone() or {})
    return {
        "supplierInvoiceDanglingCount": int(
            row.get("supplier_invoice_dangling_count") or 0
        ),
        "warehouseInvoiceDanglingCount": int(
            row.get("warehouse_invoice_dangling_count") or 0
        ),
    }


def _blockers(readiness):
    blockers = []
    if readiness["supplierInvoiceDanglingCount"]:
        blockers.append("supplier_invoice_links_dangling")
    if readiness["warehouseInvoiceDanglingCount"]:
        blockers.append("warehouse_invoice_links_dangling")
    return blockers


def _schema_contract_is_exact(cursor):
    names = [contract["constraint"] for contract in _CONTRACTS]
    cursor.execute(
        """SELECT source_namespace.nspname AS source_schema,
                  source_relation.relname AS source_table,
                  target_namespace.nspname AS target_schema,
                  target_relation.relname AS target_table,
                  constraint_row.conname,
                  constraint_row.contype,
                  constraint_row.convalidated,
                  constraint_row.condeferrable,
                  constraint_row.condeferred,
                  pg_catalog.pg_get_constraintdef(constraint_row.oid,TRUE)
                    AS definition
             FROM pg_catalog.pg_constraint constraint_row
             JOIN pg_catalog.pg_class source_relation
               ON source_relation.oid=constraint_row.conrelid
             JOIN pg_catalog.pg_namespace source_namespace
               ON source_namespace.oid=source_relation.relnamespace
             JOIN pg_catalog.pg_class target_relation
               ON target_relation.oid=constraint_row.confrelid
             JOIN pg_catalog.pg_namespace target_namespace
               ON target_namespace.oid=target_relation.relnamespace
            WHERE source_namespace.nspname='public'
              AND constraint_row.conname=ANY(%s)
            ORDER BY constraint_row.conname""",
        (names,),
    )
    rows = {
        row.get("conname"): dict(row or {})
        for row in (cursor.fetchall() or [])
    }
    if set(rows) != set(names):
        return False
    for contract in _CONTRACTS:
        row = rows[contract["constraint"]]
        definition = " ".join(str(row.get("definition") or "").split())
        target_reference = f"REFERENCES {contract['target']}(id)"
        qualified_target_reference = (
            f"REFERENCES public.{contract['target']}(id)"
        )
        if (
            row.get("source_schema") != "public"
            or row.get("source_table") != contract["table"]
            or row.get("target_schema") != "public"
            or row.get("target_table") != contract["target"]
            or row.get("contype") != "f"
            or row.get("convalidated") is not True
            or row.get("condeferrable") is not True
            or row.get("condeferred") is not False
            or f"FOREIGN KEY ({contract['column']})" not in definition
            or not (
                target_reference in definition
                or qualified_target_reference in definition
            )
            or "ON DELETE SET NULL" not in definition
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
        raise ValueError("accounting_link_integrity_apply_guard_invalid") from None


def _report(plan, readiness, *, schema_ready, applied):
    blockers = _blockers(readiness)
    report = copy.deepcopy(plan)
    report.update(readiness)
    report.update({
        "dryRun": not applied,
        "schemaReady": schema_ready,
        "readyForApply": not blockers,
        "blockers": blockers,
        "writesAttempted": plan["changeCount"] if applied else 0,
        "rolledBack": not applied,
    })
    return report


def run_accounting_link_integrity_schema(
    connection,
    *,
    apply=False,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    plan = build_accounting_link_integrity_schema_plan()
    if apply:
        _apply_guard(plan, expected_change_count, expected_plan_sha256)
    cursor = None
    try:
        if not apply:
            connection.set_session(readonly=True, autocommit=False)
            cursor = connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            readiness = _readiness(cursor)
            schema_ready = _schema_contract_is_exact(cursor)
            connection.rollback()
            return _report(
                plan, readiness, schema_ready=schema_ready, applied=False,
            )

        connection.set_session(
            readonly=False,
            autocommit=False,
            isolation_level="SERIALIZABLE",
        )
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        for contract in _CONTRACTS:
            cursor.execute(
                f"LOCK TABLE public.{contract['table']} IN ACCESS EXCLUSIVE MODE"
            )
        readiness = _readiness(cursor)
        if _blockers(readiness):
            raise RuntimeError("accounting_link_integrity_not_ready") from None
        for change in plan["changes"]:
            cursor.execute(change["sql"])
        if not _schema_contract_is_exact(cursor):
            raise RuntimeError("accounting_link_integrity_postcheck_failed") from None
        connection.commit()
        return _report(plan, readiness, schema_ready=True, applied=True)
    except BaseException:
        if cursor is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
