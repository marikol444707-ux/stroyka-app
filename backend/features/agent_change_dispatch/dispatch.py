"""Dry-run-first adapter from a validated change plan to the agent queue."""

from collections.abc import Mapping

from ..agent_jobs.service import enqueue_agent_job
from .contract import (
    AgentChangeContractError,
    validate_agent_dispatch_plan,
)


_JOB_STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})


class AgentChangeDispatchError(ValueError):
    pass


def _public_job_state(outcome, plan):
    if not isinstance(outcome, Mapping) or type(outcome.get("created")) is not bool:
        raise AgentChangeDispatchError("enqueue result is invalid")
    row = outcome.get("job")
    if not isinstance(row, Mapping):
        raise AgentChangeDispatchError("enqueue job is invalid")

    job_id = row.get("id")
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise AgentChangeDispatchError("enqueue job id is invalid")
    status = row.get("status")
    if status not in _JOB_STATUSES:
        raise AgentChangeDispatchError("enqueue job status is invalid")
    if (
        row.get("company_id") != plan.company_id
        or row.get("project_id") != plan.project_id
        or row.get("job_type") != plan.job_type
        or row.get("idempotency_key") != plan.idempotency_key
    ):
        raise AgentChangeDispatchError("enqueue job does not match the dispatch plan")
    return {"jobId": job_id, "status": status}


def dispatch_agent_change_plan(
    cur,
    *,
    plan,
    apply=False,
    enqueue_job=enqueue_agent_job,
):
    """Plan by default; enqueue exactly once only after explicit apply."""
    if type(apply) is not bool:
        raise AgentChangeDispatchError("apply must be boolean")
    if not callable(enqueue_job):
        raise AgentChangeDispatchError("enqueue_job must be callable")
    try:
        plan = validate_agent_dispatch_plan(plan)
    except AgentChangeContractError as exc:
        raise AgentChangeDispatchError("dispatch plan is invalid") from exc

    brief_date = plan.payload[0][1]
    report = {
        "ok": True,
        "dryRun": not apply,
        "state": "would_enqueue",
        "enqueueAttempted": False,
        "writesAttempted": 0,
        "companyId": plan.company_id,
        "projectId": plan.source_project_id,
        "jobType": plan.job_type,
        "briefDate": brief_date,
    }
    if not apply:
        return report

    report.update({"enqueueAttempted": True, "writesAttempted": 1})
    outcome = enqueue_job(
        cur,
        company_id=plan.company_id,
        project_id=plan.project_id,
        job_type=plan.job_type,
        idempotency_key=plan.idempotency_key,
        requested_by_role=plan.requested_by_role,
        payload=dict(plan.payload),
        correlation_id=plan.correlation_id,
        priority=plan.priority,
        max_attempts=plan.max_attempts,
    )
    job_state = _public_job_state(outcome, plan)
    report.update({
        "state": "enqueued" if outcome["created"] is True else "existing",
        **job_state,
    })
    return report
