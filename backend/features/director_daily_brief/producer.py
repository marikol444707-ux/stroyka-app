"""Explicit single-company producer for deterministic director daily briefs."""

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import date

from psycopg2.extras import RealDictCursor

from backend.db import get_db
from backend.features.agent_jobs.service import enqueue_agent_job


JOB_TYPE = "director.daily_brief"


class DirectorDailyBriefProducerError(ValueError):
    pass


def _positive_int(value, field):
    if isinstance(value, bool):
        raise DirectorDailyBriefProducerError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise DirectorDailyBriefProducerError(
            f"{field} must be a positive integer"
        ) from exc
    if normalized <= 0:
        raise DirectorDailyBriefProducerError(f"{field} must be a positive integer")
    return normalized


def _iso_date(value):
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise DirectorDailyBriefProducerError(
            "brief_date must be an ISO date"
        ) from exc
    if parsed.isoformat() != normalized:
        raise DirectorDailyBriefProducerError("brief_date must be an ISO date")
    return normalized


def _job_identity(brief_date):
    return {
        "idempotencyKey": f"daily:{brief_date}",
        "payload": {"briefDate": brief_date},
    }


def _public_job_state(row):
    if not isinstance(row, Mapping):
        raise DirectorDailyBriefProducerError("agent job result is invalid")
    job_id = _positive_int(row.get("id"), "job_id")
    status = str(row.get("status") or "").strip()
    if not status or len(status) > 40:
        raise DirectorDailyBriefProducerError("agent job status is invalid")
    return {"jobId": job_id, "status": status}


def prepare_director_daily_brief_job(
    cur,
    *,
    company_id,
    brief_date,
    apply=False,
    enqueue_job=enqueue_agent_job,
):
    """Plan or enqueue one idempotent company-wide brief for one explicit day."""
    company_id = _positive_int(company_id, "company_id")
    brief_date = _iso_date(brief_date)
    if type(apply) is not bool:
        raise DirectorDailyBriefProducerError("apply must be boolean")
    if not callable(enqueue_job):
        raise DirectorDailyBriefProducerError("enqueue_job must be callable")

    identity = _job_identity(brief_date)
    report = {
        "ok": True,
        "dryRun": not apply,
        "writesAttempted": 0,
        "companyId": company_id,
        "briefDate": brief_date,
        "jobType": JOB_TYPE,
    }

    cur.execute(
        """SELECT company.id
             FROM companies company
            WHERE company.id=%s AND company.active IS TRUE""",
        (company_id,),
    )
    if cur.fetchone() is None:
        raise DirectorDailyBriefProducerError("active company was not found")

    cur.execute(
        """SELECT id,status
             FROM agent_jobs
            WHERE company_id=%s AND project_scope_id=0
              AND job_type=%s AND idempotency_key=%s
            LIMIT 1""",
        (company_id, JOB_TYPE, identity["idempotencyKey"]),
    )
    existing = cur.fetchone()
    if existing is not None:
        report.update({"state": "existing", **_public_job_state(existing)})
        return report

    if not apply:
        report["state"] = "would_enqueue"
        return report

    report["writesAttempted"] = 1
    outcome = enqueue_job(
        cur,
        company_id=company_id,
        job_type=JOB_TYPE,
        idempotency_key=identity["idempotencyKey"],
        requested_by_role="system",
        payload=identity["payload"],
        correlation_id=f"daily-brief:{company_id}:{brief_date}",
        priority=5,
        max_attempts=3,
    )
    if not isinstance(outcome, Mapping):
        raise DirectorDailyBriefProducerError("enqueue result is invalid")
    report.update({
        "state": "enqueued" if outcome.get("created") is True else "existing",
        **_public_job_state(outcome.get("job")),
    })
    return report


def run_director_daily_brief_producer(
    *,
    company_id,
    brief_date,
    apply=False,
    connection_factory=get_db,
):
    """Run one producer transaction; dry-run always ends with a rollback."""
    connection = connection_factory()
    try:
        connection.set_session(readonly=not apply, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            report = prepare_director_daily_brief_job(
                cur,
                company_id=company_id,
                brief_date=brief_date,
                apply=apply,
            )
        if apply:
            connection.commit()
        else:
            connection.rollback()
        return report
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Plan or enqueue one deterministic director daily brief.",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--brief-date", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write one idempotent queued job. Without this flag the command is read-only.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        report = run_director_daily_brief_producer(
            company_id=args.company_id,
            brief_date=args.brief_date,
            apply=args.apply,
        )
    except DirectorDailyBriefProducerError as exc:
        report = {
            "ok": False,
            "dryRun": not args.apply,
            "errorType": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        report = {
            "ok": False,
            "dryRun": not args.apply,
            "errorType": type(exc).__name__,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
