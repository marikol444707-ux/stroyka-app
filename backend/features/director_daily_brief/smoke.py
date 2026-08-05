"""Controlled production smoke for one deterministic director daily brief."""

import json
import os
import re
import uuid
from collections.abc import Mapping
from datetime import date

from psycopg2.extras import RealDictCursor

from backend.db import get_db
from backend.features.agent_jobs.handler_registry import AgentJobHandlerRegistry
from backend.features.agent_jobs.runner import AgentJobRunner, AgentJobRunnerConfig
from backend.features.agent_jobs.service import enqueue_agent_job
from backend.features.director_daily_brief.handler import handle_director_daily_brief


JOB_TYPE = "director.daily_brief"
LEADERSHIP_ROLES = ("директор", "зам_директора")
SECTION_KEYS = (
    "overdue",
    "shortages",
    "documents",
    "estimateDeviations",
    "payments",
    "tasks",
)
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")


class ControlledDailyBriefSmokeError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise ControlledDailyBriefSmokeError(message)


def _normalized_email(value):
    normalized = str(value or "").strip().casefold()
    if not normalized or len(normalized) > 254 or "@" not in normalized:
        raise ControlledDailyBriefSmokeError("SMOKE_EMAIL must be a valid account email")
    return normalized


def _normalized_company_id(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ControlledDailyBriefSmokeError("SMOKE_COMPANY_ID must be positive")
    try:
        company_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ControlledDailyBriefSmokeError(
            "SMOKE_COMPANY_ID must be positive"
        ) from exc
    if company_id <= 0:
        raise ControlledDailyBriefSmokeError("SMOKE_COMPANY_ID must be positive")
    return company_id


def _normalized_brief_date(value):
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ControlledDailyBriefSmokeError(
            "SMOKE_BRIEF_DATE must be an ISO date"
        ) from exc
    if parsed.isoformat() != normalized:
        raise ControlledDailyBriefSmokeError("SMOKE_BRIEF_DATE must be an ISO date")
    return normalized


def _transaction(connection_factory, operation):
    connection = connection_factory()
    try:
        connection.autocommit = False
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            result = operation(cursor)
        connection.commit()
        return result
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _create_job(
    *,
    email,
    company_id,
    brief_date,
    correlation_id,
    run_id,
    connection_factory=get_db,
):
    def create(cursor):
        params = [email, list(LEADERSHIP_ROLES)]
        company_filter = ""
        if company_id is not None:
            company_filter = "AND membership.company_id=%s"
            params.append(company_id)
        cursor.execute(
            f"""
            SELECT membership.company_id,membership.user_id,membership.role
              FROM user_company_roles membership
              JOIN users account ON account.id=membership.user_id
              JOIN companies company
                ON company.id=membership.company_id AND company.active IS TRUE
             WHERE LOWER(account.email)=LOWER(%s)
               AND membership.active IS TRUE
               AND membership.role=ANY(%s::text[])
               {company_filter}
             ORDER BY membership.company_id
            """,
            tuple(params),
        )
        memberships = [dict(row) for row in cursor.fetchall()]
        _require(
            len(memberships) == 1,
            "SMOKE_EMAIL must resolve to exactly one active leadership company; "
            "set SMOKE_COMPANY_ID when needed",
        )
        actor = memberships[0]
        cursor.execute(
            """
            SELECT COUNT(*) AS count
              FROM agent_jobs
             WHERE company_id=%s AND job_type=%s
               AND status IN ('queued','running')
            """,
            (actor["company_id"], JOB_TYPE),
        )
        active_count = int((cursor.fetchone() or {}).get("count") or 0)
        _require(
            active_count == 0,
            "controlled smoke refused because an active daily brief already exists",
        )
        created = enqueue_agent_job(
            cursor,
            company_id=actor["company_id"],
            requested_by_user_id=actor["user_id"],
            requested_by_role=actor["role"],
            job_type=JOB_TYPE,
            idempotency_key=f"smoke:{brief_date}:{run_id}",
            correlation_id=correlation_id,
            payload={"briefDate": brief_date},
            priority=10,
            max_attempts=1,
        )
        _require(created.get("created") is True, "controlled smoke job was not created")
        job = dict(created["job"])
        return {"id": int(job["id"]), "companyId": int(actor["company_id"])}

    return _transaction(connection_factory, create)


def _run_job(*, connection_factory=get_db):
    registry = AgentJobHandlerRegistry(((JOB_TYPE, handle_director_daily_brief),))
    runner = AgentJobRunner(
        registry=registry,
        connection_factory=connection_factory,
        config=AgentJobRunnerConfig(
            worker_id=f"daily-brief-smoke:{uuid.uuid4().hex[:12]}",
            lease_seconds=120,
            heartbeat_interval_seconds=30,
        ),
        emit_event=lambda event, **fields: None,
    )
    return runner.run_once()


def _load_job(correlation_id, *, connection_factory=get_db):
    def load(cursor):
        cursor.execute(
            """
            SELECT id,status,result_json
              FROM agent_jobs
             WHERE correlation_id=%s AND job_type=%s
            """,
            (correlation_id, JOB_TYPE),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        result = row.get("result_json") or {}
        if isinstance(result, str):
            result = json.loads(result)
        return {
            "id": int(row["id"]),
            "status": str(row.get("status") or ""),
            "result": result,
        }

    return _transaction(connection_factory, load)


def _cleanup_job(correlation_id, *, connection_factory=get_db):
    def cleanup(cursor):
        cursor.execute(
            "DELETE FROM agent_jobs WHERE correlation_id=%s AND job_type=%s",
            (correlation_id, JOB_TYPE),
        )
        cursor.execute(
            "SELECT COUNT(*) AS count FROM agent_jobs WHERE correlation_id=%s",
            (correlation_id,),
        )
        return int((cursor.fetchone() or {}).get("count") or 0)

    return _transaction(connection_factory, cleanup)


def _validated_result(stored, *, expected_job_id, brief_date):
    _require(isinstance(stored, Mapping), "completed smoke job is missing")
    _require(int(stored.get("id") or 0) == expected_job_id, "wrong smoke job was loaded")
    _require(stored.get("status") == "succeeded", "smoke job did not succeed")
    result = stored.get("result")
    _require(isinstance(result, Mapping), "smoke result must be an object")
    _require(result.get("schemaVersion") == 1, "unexpected brief schema version")
    _require(result.get("briefDate") == brief_date, "brief date changed during execution")
    _require(
        result.get("mode") == "deterministic_read_only",
        "brief mode is not deterministic read-only",
    )
    sections = result.get("sections")
    _require(isinstance(sections, list), "brief sections must be a list")
    _require(
        tuple(section.get("key") for section in sections if isinstance(section, Mapping))
        == SECTION_KEYS,
        "brief section contract changed",
    )
    for section in sections:
        _require(isinstance(section.get("items"), list), "brief section items must be a list")
        _require(len(section["items"]) <= 12, "brief section exceeded its item cap")
    _require(isinstance(result.get("summary"), Mapping), "brief summary is missing")
    _require(isinstance(result.get("sourceCounts"), Mapping), "brief source counts are missing")
    return {
        "sectionKeys": list(SECTION_KEYS),
        "sectionStatuses": [section.get("status") for section in sections],
        "sectionCounts": [int(section.get("count") or 0) for section in sections],
    }


def run_controlled_smoke(
    *,
    email,
    brief_date,
    company_id=None,
    create_job=_create_job,
    run_job=_run_job,
    load_job=_load_job,
    cleanup_job=_cleanup_job,
    run_id=None,
):
    email = _normalized_email(email)
    company_id = _normalized_company_id(company_id)
    brief_date = _normalized_brief_date(brief_date)
    run_id = str(run_id or uuid.uuid4().hex)
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ControlledDailyBriefSmokeError("run_id has invalid format")
    correlation_id = f"daily-brief-smoke-{run_id}"
    report = {
        "ok": False,
        "jobType": JOB_TYPE,
        "briefDate": brief_date,
        "businessWritesAttempted": 0,
        "queueLifecycle": ["enqueue", "claim", "complete", "cleanup"],
        "persistedAgentJobs": None,
    }
    failure = None
    try:
        created = create_job(
            email=email,
            company_id=company_id,
            brief_date=brief_date,
            correlation_id=correlation_id,
            run_id=run_id,
        )
        job_id = int(created["id"])
        report["jobId"] = job_id
        report["companyId"] = int(created["companyId"])
        outcome = run_job()
        _require(
            outcome.processed is True
            and outcome.status == "succeeded"
            and int(outcome.job_id or 0) == job_id,
            "runner did not complete the exact controlled smoke job",
        )
        stored = load_job(correlation_id)
        report.update(_validated_result(
            stored,
            expected_job_id=job_id,
            brief_date=brief_date,
        ))
    except Exception as exc:
        failure = exc
    finally:
        try:
            report["persistedAgentJobs"] = int(cleanup_job(correlation_id))
        except Exception as cleanup_exc:
            if failure is None:
                failure = cleanup_exc
            report["persistedAgentJobs"] = None

    report["ok"] = failure is None and report["persistedAgentJobs"] == 0
    if failure is not None:
        report["failureType"] = type(failure).__name__
        report["failedStage"] = "controlled_daily_brief"
    return report


def main():
    report = run_controlled_smoke(
        email=os.getenv("SMOKE_EMAIL"),
        company_id=os.getenv("SMOKE_COMPANY_ID"),
        brief_date=os.getenv("SMOKE_BRIEF_DATE") or date.today().isoformat(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
