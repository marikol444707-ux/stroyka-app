"""Pure additive schema plan preventing dangling accounting document links.

This module deliberately has no database factory, application registration or
apply runner.  It only freezes the two nullable foreign-key changes so a later
dry-run/apply slice can inspect production readiness before executing DDL.
"""

import copy
import hashlib
import json


_VERSION = "accounting-link-integrity-schema-v1"
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
