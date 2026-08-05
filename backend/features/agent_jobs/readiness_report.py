import json

import psycopg2.extras

try:
    from backend.db import get_db
except ModuleNotFoundError:
    from db import get_db


REQUIRED_COLUMNS = (
    "id",
    "owner_scope",
    "company_id",
    "project_id",
    "project_scope_id",
    "requested_by_user_id",
    "requested_by_role",
    "job_type",
    "idempotency_key",
    "correlation_id",
    "payload_json",
    "result_json",
    "status",
    "priority",
    "attempts",
    "max_attempts",
    "run_after",
    "locked_at",
    "locked_by",
    "lease_token",
    "lease_expires_at",
    "heartbeat_at",
    "started_at",
    "completed_at",
    "last_error",
    "created_at",
    "updated_at",
)
REQUIRED_INDEXES = (
    "idx_agent_jobs_claim",
    "idx_agent_jobs_lease",
    "idx_agent_jobs_owner",
    "idx_agent_jobs_correlation",
)
REQUIRED_CONSTRAINTS = (
    "uq_agent_jobs_idempotency",
)


def build_report(cur):
    cur.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema=current_schema() AND table_name='agent_jobs'
         ORDER BY ordinal_position
        """
    )
    columns = {row["column_name"] for row in cur.fetchall()}
    missing_columns = [name for name in REQUIRED_COLUMNS if name not in columns]
    base = {
        "ok": True,
        "dryRun": True,
        "table": "agent_jobs",
        "writesAttempted": 0,
        "tableExists": bool(columns),
        "missingColumns": missing_columns,
        "missingIndexes": list(REQUIRED_INDEXES),
        "missingConstraints": list(REQUIRED_CONSTRAINTS),
        "summary": {
            "total": 0,
            "invalidOwner": 0,
            "invalidStatus": 0,
            "invalidLeaseState": 0,
        },
        "readyForWorker": False,
    }
    if missing_columns:
        return base

    cur.execute(
        """
        SELECT indexname
          FROM pg_indexes
         WHERE schemaname=current_schema() AND tablename='agent_jobs'
         ORDER BY indexname
        """
    )
    indexes = {row["indexname"] for row in cur.fetchall()}
    missing_indexes = [name for name in REQUIRED_INDEXES if name not in indexes]
    cur.execute(
        """
        SELECT constraint_name
          FROM information_schema.table_constraints
         WHERE table_schema=current_schema()
           AND table_name='agent_jobs'
           AND constraint_type='UNIQUE'
         ORDER BY constraint_name
        """
    )
    constraints = {row["constraint_name"] for row in cur.fetchall()}
    missing_constraints = [
        name for name in REQUIRED_CONSTRAINTS if name not in constraints
    ]
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (
                   WHERE owner_scope<>'company' OR company_id IS NULL OR company_id<=0
               ) AS invalid_owner,
               COUNT(*) FILTER (
                   WHERE status NOT IN ('queued','running','succeeded','failed','cancelled')
               ) AS invalid_status,
               COUNT(*) FILTER (
                   WHERE (
                       status='running'
                       AND (
                           COALESCE(locked_by,'')=''
                           OR COALESCE(lease_token,'')=''
                           OR locked_at IS NULL
                           OR heartbeat_at IS NULL
                           OR lease_expires_at IS NULL
                       )
                   ) OR (
                       status<>'running'
                       AND (
                           locked_by IS NOT NULL
                           OR lease_token IS NOT NULL
                           OR locked_at IS NOT NULL
                           OR heartbeat_at IS NOT NULL
                           OR lease_expires_at IS NOT NULL
                       )
                   )
               ) AS invalid_lease_state
          FROM agent_jobs
        """
    )
    row = cur.fetchone() or {}
    summary = {
        "total": int(row.get("total") or 0),
        "invalidOwner": int(row.get("invalid_owner") or 0),
        "invalidStatus": int(row.get("invalid_status") or 0),
        "invalidLeaseState": int(row.get("invalid_lease_state") or 0),
    }
    base.update({
        "missingIndexes": missing_indexes,
        "missingConstraints": missing_constraints,
        "summary": summary,
        "readyForWorker": not missing_indexes
        and not missing_constraints
        and summary["invalidOwner"] == 0
        and summary["invalidStatus"] == 0
        and summary["invalidLeaseState"] == 0,
    })
    return base


def main():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        print(json.dumps(build_report(cur), ensure_ascii=False, indent=2))
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
