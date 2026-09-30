"""Dry-run-first producer for optional daily-brief explanation jobs."""

from collections.abc import Mapping

from backend.features.agent_jobs.service import enqueue_agent_job

from .explanation_handler import JOB_TYPE
from .query_service import public_director_daily_brief


class DirectorDailyBriefExplanationProducerError(ValueError):
    pass


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DirectorDailyBriefExplanationProducerError(f"{field} must be a positive integer")
    return value


def _job_state(row):
    if not isinstance(row, Mapping):
        raise DirectorDailyBriefExplanationProducerError("agent job result is invalid")
    job_id = _positive_int(row.get("id"), "job_id")
    status = row.get("status")
    if not isinstance(status, str) or not status or len(status) > 40:
        raise DirectorDailyBriefExplanationProducerError("agent job status is invalid")
    return {"jobId": job_id, "status": status}


def prepare_daily_brief_explanation_job(
    cur,
    *,
    company_id,
    source_job_id,
    enabled=False,
    apply=False,
    enqueue_job=enqueue_agent_job,
):
    company_id = _positive_int(company_id, "company_id")
    source_job_id = _positive_int(source_job_id, "source_job_id")
    if type(enabled) is not bool or type(apply) is not bool or not callable(enqueue_job):
        raise DirectorDailyBriefExplanationProducerError("producer controls are invalid")

    cur.execute(
        """SELECT id,result_json
             FROM agent_jobs
            WHERE id=%s AND company_id=%s AND project_id IS NULL
              AND job_type='director.daily_brief' AND status='succeeded'
              AND completed_at IS NOT NULL AND result_json IS NOT NULL
            LIMIT 1""",
        (source_job_id, company_id),
    )
    source = cur.fetchone()
    if not isinstance(source, Mapping) or source.get("id") != source_job_id:
        raise DirectorDailyBriefExplanationProducerError("daily brief source was not found")
    public_director_daily_brief(source.get("result_json"))

    idempotency_key = f"daily-explanation:{source_job_id}"
    cur.execute(
        """SELECT id,status FROM agent_jobs
            WHERE company_id=%s AND project_scope_id=0
              AND job_type=%s AND idempotency_key=%s LIMIT 1""",
        (company_id, JOB_TYPE, idempotency_key),
    )
    existing = cur.fetchone()
    report = {
        "ok": True,
        "dryRun": not apply,
        "writesAttempted": 0,
        "companyId": company_id,
        "sourceJobId": source_job_id,
        "jobType": JOB_TYPE,
    }
    if existing is not None:
        report.update({"state": "existing", **_job_state(existing)})
        return report
    if not enabled:
        report["state"] = "disabled"
        return report
    if not apply:
        report["state"] = "would_enqueue"
        return report

    report["writesAttempted"] = 1
    outcome = enqueue_job(
        cur,
        company_id=company_id,
        job_type=JOB_TYPE,
        idempotency_key=idempotency_key,
        requested_by_role="system",
        payload={"sourceJobId": source_job_id},
        correlation_id=f"daily-explanation:{company_id}:{source_job_id}",
        priority=6,
        max_attempts=2,
    )
    if not isinstance(outcome, Mapping):
        raise DirectorDailyBriefExplanationProducerError("enqueue result is invalid")
    report.update({
        "state": "enqueued" if outcome.get("created") is True else "existing",
        **_job_state(outcome.get("job")),
    })
    return report
