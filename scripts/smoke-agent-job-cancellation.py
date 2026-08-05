#!/usr/bin/env python3
"""Exercise queued cancellation and its audit in one rolled-back transaction."""

import json
import sys
import uuid
from pathlib import Path

import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import get_db  # noqa: E402
from backend.features.agent_jobs.cancellation_service import (  # noqa: E402
    cancel_queued_agent_job,
)
from backend.features.agent_jobs.service import enqueue_agent_job  # noqa: E402
from backend.features.audit_ownership.runtime import insert_audit_event  # noqa: E402


JOB_TYPE = "smoke.agent_job_cancellation"
LEADERSHIP_ROLES = ("директор", "зам_директора")


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _test_actor(cur):
    cur.execute(
        """
        SELECT m.company_id,m.user_id,m.role,COALESCE(u.name,'') AS user_name
          FROM user_company_roles m
          JOIN companies c ON c.id=m.company_id AND c.active IS TRUE
          JOIN users u ON u.id=m.user_id
         WHERE m.active IS TRUE AND m.role=ANY(%s::text[])
         ORDER BY m.company_id,m.user_id
         LIMIT 1
        """,
        (list(LEADERSHIP_ROLES),),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("agent cancellation smoke requires one active leadership membership")
    return dict(row)


def _enqueue(cur, actor, run_id, suffix):
    correlation_id = f"cancel-smoke-{suffix}-{run_id}"
    result = enqueue_agent_job(
        cur,
        company_id=actor["company_id"],
        requested_by_user_id=actor["user_id"],
        requested_by_role=actor["role"],
        job_type=JOB_TYPE,
        idempotency_key=f"{suffix}:{run_id}",
        correlation_id=correlation_id,
        payload={"smoke": True},
    )
    _require(result.get("created") is True, f"{suffix} smoke job was not created")
    return dict(result["job"]), correlation_id


def main():
    run_id = uuid.uuid4().hex
    audit_marker = f"agent job cancellation smoke {run_id}"
    correlation_ids = []
    report = {
        "ok": False,
        "table": "agent_jobs",
        "writesAttempted": 7,
        "rolledBack": False,
        "persistedAgentJobs": None,
        "persistedAuditRows": None,
        "steps": [],
    }
    failure = None
    conn = get_db()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        actor = _test_actor(cur)
        queued, queued_correlation = _enqueue(cur, actor, run_id, "queued")
        correlation_ids.append(queued_correlation)
        lease_token = uuid.uuid4().hex
        cur.execute(
            """
            UPDATE agent_jobs
               SET last_error='previous smoke diagnostic',
                   locked_by='orphaned-smoke-worker',locked_at=NOW(),
                   heartbeat_at=NOW(),lease_token=%s,
                   lease_expires_at=NOW()+INTERVAL '2 minutes'
             WHERE id=%s
            """,
            (lease_token, queued["id"]),
        )

        cancelled = cancel_queued_agent_job(
            cur,
            company_id=actor["company_id"],
            job_id=queued["id"],
            reason_code="user_request",
        )
        cancelled_job = dict(cancelled.get("job") or {})
        _require(cancelled.get("state") == "cancelled", "queued job was not cancelled")
        _require(cancelled_job.get("status") == "cancelled", "cancelled status was not stored")
        _require(cancelled_job.get("completed_at") is not None, "cancellation time is missing")
        _require(cancelled_job.get("locked_by") is None, "cancelled job kept worker ownership")
        _require(cancelled_job.get("lease_token") is None, "cancelled job kept a lease token")
        _require(
            cancelled_job.get("last_error") == "previous smoke diagnostic",
            "cancellation erased the previous diagnostic",
        )
        report["steps"].append("cancel_queued")

        audit = insert_audit_event(
            cur,
            user_id=actor["user_id"],
            user_name=actor["user_name"],
            user_role=actor["role"],
            action="cancel",
            entity_type="agent_job",
            entity_id=queued["id"],
            description=audit_marker,
            owner_scope="company",
            company_id=actor["company_id"],
        )
        owner = dict(audit.get("owner") or {})
        _require(owner.get("scope") == "company", "audit scope is not company")
        _require(
            int(owner.get("companyId") or 0) == int(actor["company_id"]),
            "audit company does not match the job company",
        )
        cur.execute(
            """SELECT action,entity_type,entity_id,owner_scope,company_id
                 FROM audit_log WHERE id=%s""",
            (audit["id"],),
        )
        audit_row = dict(cur.fetchone() or {})
        _require(
            audit_row.get("action") == "cancel"
            and audit_row.get("entity_type") == "agent_job"
            and int(audit_row.get("entity_id") or 0) == int(queued["id"])
            and audit_row.get("owner_scope") == "company"
            and int(audit_row.get("company_id") or 0) == int(actor["company_id"]),
            "stored cancellation audit is incomplete",
        )
        report["steps"].append("audit")

        running, running_correlation = _enqueue(cur, actor, run_id, "running")
        correlation_ids.append(running_correlation)
        cur.execute(
            """
            UPDATE agent_jobs
               SET status='running',attempts=1,locked_by='smoke-worker',
                   locked_at=NOW(),started_at=NOW(),lease_token=%s,
                   lease_expires_at=NOW()+INTERVAL '2 minutes'
             WHERE id=%s
            """,
            (uuid.uuid4().hex, running["id"]),
        )
        conflict = cancel_queued_agent_job(
            cur,
            company_id=actor["company_id"],
            job_id=running["id"],
            reason_code="user_request",
        )
        _require(conflict.get("state") == "conflict", "running job did not return conflict")
        cur.execute("SELECT status FROM agent_jobs WHERE id=%s", (running["id"],))
        running_status = str((cur.fetchone() or {}).get("status") or "")
        _require(running_status == "running", "running job status was changed")
        report["steps"].append("protect_running")
    except Exception as exc:
        failure = f"{type(exc).__name__}: {str(exc)[:500]}"
    finally:
        conn.rollback()
        report["rolledBack"] = True
        cur.close()
        conn.close()

    verify_conn = get_db()
    verify_cur = verify_conn.cursor()
    try:
        try:
            verify_cur.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE correlation_id=ANY(%s::text[])",
                (correlation_ids,),
            )
            report["persistedAgentJobs"] = int(verify_cur.fetchone()[0])
            verify_cur.execute(
                "SELECT COUNT(*) FROM audit_log WHERE description=%s",
                (audit_marker,),
            )
            report["persistedAuditRows"] = int(verify_cur.fetchone()[0])
        except Exception as exc:
            verify_conn.rollback()
            if failure is None:
                failure = f"cleanup verification failed: {type(exc).__name__}: {str(exc)[:400]}"
    finally:
        verify_cur.close()
        verify_conn.close()

    report["ok"] = (
        failure is None
        and report["persistedAgentJobs"] == 0
        and report["persistedAuditRows"] == 0
    )
    if failure:
        report["failure"] = failure
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
