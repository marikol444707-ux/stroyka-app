#!/usr/bin/env python3
"""Exercise the agent job lifecycle in one transaction and roll it back."""

import json
import sys
import uuid
from pathlib import Path

import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import get_db  # noqa: E402
from backend.features.agent_jobs.worker import (  # noqa: E402
    claim_next_agent_job,
    complete_agent_job,
    fail_agent_job,
    heartbeat_agent_job,
    recover_expired_agent_jobs,
)


JOB_TYPE = "smoke.agent_job_worker"


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _test_company_id(cur):
    cur.execute(
        """
        SELECT company_id
          FROM user_company_roles
         WHERE active IS TRUE AND company_id>0
        UNION
        SELECT id AS company_id
          FROM managed_companies
         WHERE id>0
         ORDER BY company_id
         LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("agent worker smoke requires one company")
    return int(row["company_id"])


def _insert_job(
    cur,
    *,
    company_id,
    idempotency_key,
    correlation_id,
    max_attempts,
    status="queued",
    attempts=0,
    locked_by=None,
    expired=False,
):
    cur.execute(
        """
        INSERT INTO agent_jobs (
            owner_scope,company_id,requested_by_role,job_type,
            idempotency_key,correlation_id,payload_json,status,
            attempts,max_attempts,locked_by,locked_at,heartbeat_at,
            lease_token,lease_expires_at,run_after
        ) VALUES (
            'company',%s,'system',%s,%s,%s,'{}'::jsonb,%s,
            %s,%s,%s,
            CASE WHEN %s IS NULL THEN NULL ELSE NOW() END,
            CASE WHEN %s IS NULL THEN NULL ELSE NOW() END,
            CASE WHEN %s IS NULL THEN NULL ELSE %s END,
            CASE WHEN %s IS NULL THEN NULL
                 WHEN %s THEN NOW()-INTERVAL '1 minute'
                 ELSE NOW()+INTERVAL '2 minutes' END,
            NOW()
        )
        RETURNING *
        """,
        (
            company_id,
            JOB_TYPE,
            idempotency_key,
            correlation_id,
            status,
            attempts,
            max_attempts,
            locked_by,
            locked_by,
            locked_by,
            locked_by,
            uuid.uuid4().hex,
            locked_by,
            expired,
        ),
    )
    return dict(cur.fetchone())


def main():
    run_id = uuid.uuid4().hex
    correlation_ids = [f"worker-smoke-{run_id}", f"worker-smoke-stale-{run_id}"]
    worker_id = f"smoke-{run_id[:12]}"
    report = {
        "ok": False,
        "table": "agent_jobs",
        "writesAttempted": 9,
        "rolledBack": False,
        "persistedRows": None,
        "steps": [],
    }
    failure = None
    conn = get_db()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        company_id = _test_company_id(cur)
        created = _insert_job(
            cur,
            company_id=company_id,
            idempotency_key=f"lifecycle:{run_id}",
            correlation_id=correlation_ids[0],
            max_attempts=2,
        )
        job_id = int(created["id"])

        claimed = claim_next_agent_job(
            cur,
            worker_id=worker_id,
            allowed_job_types=(JOB_TYPE,),
            lease_seconds=120,
        )
        _require(
            claimed
            and int(claimed["id"]) == job_id
            and claimed["status"] == "running"
            and int(claimed["attempts"]) == 1
            and int(claimed["company_id"]) == company_id,
            "claim did not preserve the expected owner and attempt",
        )
        report["steps"].append("claim")

        heartbeat = heartbeat_agent_job(
            cur,
            job_id=job_id,
            worker_id=worker_id,
            lease_token=claimed["lease_token"],
            lease_seconds=120,
        )
        _require(heartbeat and heartbeat["status"] == "running", "heartbeat failed")
        report["steps"].append("heartbeat")

        retried = fail_agent_job(
            cur,
            job_id=job_id,
            worker_id=worker_id,
            lease_token=claimed["lease_token"],
            error="smoke retry",
            retry_delay_seconds=1,
        )
        _require(retried and retried["status"] == "queued", "retry was not queued")
        cur.execute("UPDATE agent_jobs SET run_after=NOW() WHERE id=%s", (job_id,))
        report["steps"].append("retry")

        claimed_again = claim_next_agent_job(
            cur,
            worker_id=worker_id,
            allowed_job_types=(JOB_TYPE,),
            lease_seconds=120,
        )
        _require(
            claimed_again
            and int(claimed_again["id"]) == job_id
            and int(claimed_again["attempts"]) == 2,
            "second claim did not consume the final attempt",
        )

        completed = complete_agent_job(
            cur,
            job_id=job_id,
            worker_id=worker_id,
            lease_token=claimed_again["lease_token"],
            result={"smoke": "ok"},
        )
        _require(
            completed
            and completed["status"] == "succeeded"
            and completed["locked_by"] is None,
            "completion did not release the lease",
        )
        report["steps"].append("complete")

        stale = _insert_job(
            cur,
            company_id=company_id,
            idempotency_key=f"stale:{run_id}",
            correlation_id=correlation_ids[1],
            max_attempts=3,
            status="running",
            attempts=1,
            locked_by="stale-worker",
            expired=True,
        )
        recovered = recover_expired_agent_jobs(
            cur,
            allowed_job_types=(JOB_TYPE,),
            retry_delay_seconds=1,
        )
        recovered_row = next(
            (row for row in recovered if int(row["id"]) == int(stale["id"])),
            None,
        )
        _require(
            recovered_row
            and recovered_row["status"] == "queued"
            and recovered_row["locked_by"] is None,
            "expired lease was not safely recovered",
        )
        report["steps"].append("recover_expired")
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
        verify_cur.execute(
            "SELECT COUNT(*) FROM agent_jobs WHERE correlation_id=ANY(%s::text[])",
            (correlation_ids,),
        )
        report["persistedRows"] = int(verify_cur.fetchone()[0])
    finally:
        verify_cur.close()
        verify_conn.close()

    report["ok"] = failure is None and report["persistedRows"] == 0
    if failure:
        report["failure"] = failure
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
