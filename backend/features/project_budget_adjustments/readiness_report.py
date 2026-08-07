"""Rolled-back E6 budget-adjustment production readiness gate."""

import json

import psycopg2.extras

from .audit import build_budget_adjustment_readiness
from .cutover_inventory import audit_cutover_inventory
from .ledger_readiness import collect_receipt_ledger_readiness
from .schema import _load_catalog, build_schema_plan
from .writer_inventory import audit_writer_inventory


MAX_PROJECT_ROWS = 50000
MAX_RECONCILIATION_ROWS = 100000
REQUIRED_COLUMNS = {
    "projects": {"id", "company_id", "budget"},
    "estimates": {
        "id", "company_id", "project_id", "status", "smeta_type",
        "work_package",
    },
    "estimate_reconciliations": {
        "id", "base_estimate_id", "next_estimate_id", "status",
        "smeta_type", "work_package", "base_total", "next_total",
    },
}


def _base_failure(reason_code, *, schema_ready, missing_columns=()):
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "schemaReady": schema_ready,
        "missingColumns": list(missing_columns),
        "budgetColumn": {},
        "budgetColumnExact": False,
        "scanComplete": False,
        "dataReady": False,
        "budgetDataReady": False,
        "approvedSourcesReady": False,
        "readyForSchemaPlan": False,
        "summary": {},
        "issueCount": 1,
        "reasonCounts": {reason_code: 1},
        "issues": [{"reasonCode": reason_code}],
        "issuesTruncated": False,
        "readyCandidates": [],
        "readyCandidatesTruncated": False,
    }


def _column_contract(row):
    return {
        "dataType": row.get("data_type"),
        "udtName": row.get("udt_name"),
        "numericPrecision": row.get("numeric_precision"),
        "numericScale": row.get("numeric_scale"),
    }


def _budget_column_exact(contract):
    return bool(
        contract.get("dataType") == "numeric"
        and contract.get("udtName") == "numeric"
        and contract.get("numericPrecision") == 14
        and contract.get("numericScale") == 2
    )


def collect_baseline_readiness(
    cur,
    *,
    max_project_rows=MAX_PROJECT_ROWS,
    max_reconciliation_rows=MAX_RECONCILIATION_ROWS,
):
    """Read bounded owner/source metadata and no estimate business payload."""

    cur.execute(
        """SELECT table_name,column_name,data_type,udt_name,
                  numeric_precision,numeric_scale
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(REQUIRED_COLUMNS),),
    )
    schema_rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in schema_rows
    }
    missing = sorted(
        table + "." + column
        for table, columns in REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )
    if missing:
        return _base_failure(
            "project_budget_adjustment_schema_not_ready",
            schema_ready=False,
            missing_columns=missing,
        )

    budget_row = next(
        row for row in schema_rows
        if row.get("table_name") == "projects"
        and row.get("column_name") == "budget"
    )
    budget_column = _column_contract(budget_row)

    cur.execute(
        """SELECT id AS project_id,company_id,budget AS project_budget
             FROM public.projects
            ORDER BY id
            LIMIT %s""",
        (max_project_rows + 1,),
    )
    projects = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(projects) > max_project_rows:
        report = _base_failure(
            "project_budget_scan_limit_exceeded",
            schema_ready=True,
        )
        report["budgetColumn"] = budget_column
        report["budgetColumnExact"] = _budget_column_exact(budget_column)
        return report

    cur.execute(
        """SELECT r.id AS reconciliation_id,p.company_id,p.id AS project_id,
                  r.status,r.smeta_type,r.work_package,
                  r.base_estimate_id,r.next_estimate_id,
                  r.base_total,r.next_total,
                  b.company_id AS base_company_id,
                  b.project_id AS base_project_id,
                  b.smeta_type AS base_smeta_type,
                  b.work_package AS base_work_package,
                  n.company_id AS next_company_id,
                  n.project_id AS next_project_id,
                  n.smeta_type AS next_smeta_type,
                  n.work_package AS next_work_package,
                  n.status AS next_status
             FROM public.estimate_reconciliations r
             LEFT JOIN public.estimates b ON b.id=r.base_estimate_id
             LEFT JOIN public.estimates n ON n.id=r.next_estimate_id
             LEFT JOIN public.projects p ON p.id=b.project_id
            ORDER BY r.id
            LIMIT %s""",
        (max_reconciliation_rows + 1,),
    )
    reconciliations = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(reconciliations) > max_reconciliation_rows:
        report = _base_failure(
            "budget_adjustment_reconciliation_scan_limit_exceeded",
            schema_ready=True,
        )
        report["budgetColumn"] = budget_column
        report["budgetColumnExact"] = _budget_column_exact(budget_column)
        return report

    report = build_budget_adjustment_readiness(projects, reconciliations)
    report.update({
        "schemaReady": True,
        "missingColumns": [],
        "budgetColumn": budget_column,
        "budgetColumnExact": _budget_column_exact(budget_column),
        "scanComplete": True,
        "readyForSchemaPlan": bool(report.get("dataReady")),
    })
    return report


def collect_schema_readiness(cur):
    """Return the strict E6 catalog result without exposing SQL definitions."""

    plan = build_schema_plan(_load_catalog(cur))
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "schemaReady": bool(plan.get("schemaReady")),
        "budgetColumnExact": bool(plan.get("budgetColumnExact")),
        "readyForApply": bool(plan.get("readyForApply")),
        "changeCount": len(plan.get("changes") or []),
        "changes": [
            item.get("name") for item in (plan.get("changes") or [])
        ],
        "blockers": list(plan.get("blockers") or []),
    }


def _schema_blocked_ledger_report():
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "scanComplete": False,
        "ledgerReady": False,
        "validReceipts": 0,
        "summary": {},
        "issueCount": 1,
        "reasonCounts": {"budget_adjustment_schema_not_ready": 1},
        "issues": [{"reasonCode": "budget_adjustment_schema_not_ready"}],
        "issuesTruncated": False,
    }


def run_readiness_report(
    get_db,
    *,
    collect_schema=collect_schema_readiness,
    collect_data=collect_baseline_readiness,
    collect_ledger=collect_receipt_ledger_readiness,
    collect_inventory=audit_writer_inventory,
    collect_cutover=audit_cutover_inventory,
):
    conn = get_db()
    cur = None
    try:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        schema = collect_schema(cur)
        data = collect_data(cur)
        ledger = (
            collect_ledger(cur)
            if schema.get("schemaReady")
            else _schema_blocked_ledger_report()
        )
        conn.rollback()
        inventory = collect_inventory()
        cutover = collect_cutover()
        audit_ok = bool(data.get("ok") and inventory.get("ok"))
        inventory_ready = bool(inventory.get("writerInventoryReady"))
        route_ready = bool(cutover.get("routeInventoryReady"))
        integration_ready = bool(cutover.get("integrationInventoryReady"))
        ready = bool(
            schema.get("ok")
            and schema.get("schemaReady")
            and schema.get("budgetColumnExact")
            and data.get("ok")
            and data.get("schemaReady")
            and data.get("budgetColumnExact")
            and data.get("dataReady")
            and ledger.get("ok")
            and ledger.get("ledgerReady")
            and inventory.get("ok")
            and inventory_ready
            and cutover.get("ok")
            and route_ready
            and integration_ready
        )
        return {
            "ok": ready,
            "dryRun": True,
            "readOnlyTransaction": True,
            "writesAttempted": 0,
            "schemaReady": bool(
                schema.get("schemaReady") and data.get("schemaReady")
            ),
            "budgetColumnExact": bool(
                schema.get("budgetColumnExact")
                and data.get("budgetColumnExact")
            ),
            "dataReady": bool(data.get("dataReady")),
            "ledgerReady": bool(ledger.get("ledgerReady")),
            "writerInventoryReady": inventory_ready,
            "routeInventoryReady": route_ready,
            "integrationInventoryReady": integration_ready,
            "readyForSchemaPlan": bool(
                audit_ok
                and data.get("readyForSchemaPlan")
                and inventory_ready
            ),
            "readyForCutover": ready,
            "schemaAudit": schema,
            "baselineAudit": data,
            "ledgerAudit": ledger,
            "writerInventory": inventory,
            "cutoverInventory": cutover,
            "rolledBack": True,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None and hasattr(cur, "close"):
            cur.close()
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_readiness_report(get_db)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("readyForCutover") else 1


if __name__ == "__main__":
    raise SystemExit(main())
