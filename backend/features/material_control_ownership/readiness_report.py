"""Rolled-back E5 active-estimate material-control ownership audit."""

import json

import psycopg2.extras

from .audit import build_owner_readiness
from .inventory import audit_runtime_inventory


MAX_PROJECT_ROWS = 50000
MAX_ACTIVE_ESTIMATE_ROWS = 100000
REQUIRED_COLUMNS = {
    "projects": {"id", "company_id", "name", "archived"},
    "estimates": {
        "id",
        "company_id",
        "project_id",
        "project_name",
        "status",
        "is_template",
        "smeta_type",
        "work_package",
    },
}


def _scan_limit_report(reason_code):
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": False,
        "dataReady": False,
        "summary": {},
        "issueCount": 1,
        "reasonCounts": {reason_code: 1},
        "issues": [{"reasonCode": reason_code}],
        "issuesTruncated": False,
        "nameCollisions": [],
        "nameCollisionsTruncated": False,
    }


def _schema_not_ready_report(missing_columns):
    reason = "material_control_owner_schema_not_ready"
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "schemaReady": False,
        "missingColumns": list(missing_columns),
        "scanComplete": False,
        "dataReady": False,
        "summary": {},
        "issueCount": 1,
        "reasonCounts": {reason: 1},
        "issues": [{"reasonCode": reason}],
        "issuesTruncated": False,
        "nameCollisions": [],
        "nameCollisionsTruncated": False,
    }


def collect_owner_readiness(
    cur,
    *,
    max_project_rows=MAX_PROJECT_ROWS,
    max_estimate_rows=MAX_ACTIVE_ESTIMATE_ROWS,
):
    """Load only owner metadata with hard row limits."""

    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(REQUIRED_COLUMNS),),
    )
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in (cur.fetchall() or [])
    }
    missing = sorted(
        table + "." + column
        for table, columns in REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )
    if missing:
        return _schema_not_ready_report(missing)

    cur.execute(
        """SELECT id AS project_id,company_id,name AS project_name,
                  COALESCE(archived,FALSE) AS archived
             FROM public.projects
            ORDER BY id
            LIMIT %s""",
        (max_project_rows + 1,),
    )
    projects = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(projects) > max_project_rows:
        return _scan_limit_report("active_project_scan_limit_exceeded")

    cur.execute(
        """SELECT id AS estimate_id,company_id,project_id,project_name,
                  COALESCE(smeta_type,'Заказчик') AS estimate_kind,
                  COALESCE(NULLIF(work_package,''),'Основная') AS work_package
             FROM public.estimates
            WHERE status='Активная'
              AND COALESCE(is_template,FALSE)=FALSE
              AND COALESCE(smeta_type,'Заказчик') IN ('Заказчик','Материалы')
            ORDER BY id
            LIMIT %s""",
        (max_estimate_rows + 1,),
    )
    estimates = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(estimates) > max_estimate_rows:
        return _scan_limit_report("active_estimate_scan_limit_exceeded")

    report = build_owner_readiness(projects, estimates)
    report["schemaReady"] = True
    report["missingColumns"] = []
    report["scanComplete"] = True
    return report


def run_readiness_report(
    get_db,
    *,
    collect_data=collect_owner_readiness,
    collect_inventory=audit_runtime_inventory,
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
        data = collect_data(cur)
        conn.rollback()
        inventory = collect_inventory()
        audit_ok = bool(data.get("ok") and inventory.get("ok"))
        ready = bool(
            audit_ok
            and data.get("dataReady")
            and inventory.get("runtimeInventoryReady")
        )
        return {
            "ok": audit_ok,
            "dryRun": True,
            "readOnlyTransaction": True,
            "writesAttempted": 0,
            "dataReady": bool(data.get("dataReady")),
            "dataAudit": data,
            "runtimeInventoryReady": bool(
                inventory.get("runtimeInventoryReady")
            ),
            "runtimeInventory": inventory,
            "readyForCutover": ready,
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
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
