"""Fail-soft post-commit handoff for one exact revision-impact queue job."""

import json
import os
from collections.abc import Mapping

from psycopg2.extras import RealDictCursor

try:
    from backend.db import get_db
    from backend.features.agent_jobs.service import enqueue_agent_job
except ModuleNotFoundError:
    from db import get_db
    from features.agent_jobs.service import enqueue_agent_job

from .contract import (
    EVENT_TYPE,
    EstimateRevisionImpactContractError,
    build_estimate_revision_source,
)
from .job_contract import (
    JOB_TYPE,
    build_estimate_revision_impact_job_plan,
)
from .producer import prepare_estimate_revision_impact_job


ACTIVE_STATUS = "Активная"
FEATURE_FLAG = "ESTIMATE_REVISION_IMPACT_APPLY"
COMPANY_ALLOWLIST = "ESTIMATE_REVISION_IMPACT_COMPANY_IDS"
_JOB_STATES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
_QUEUE_REPORT_FIELDS = frozenset({
    "ok",
    "dryRun",
    "writesAttempted",
    "state",
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
    "jobType",
    "idempotencyKey",
    "jobId",
    "status",
})


def estimate_revision_impact_enabled(company_id):
    if (
        isinstance(company_id, bool)
        or not isinstance(company_id, int)
        or company_id <= 0
        or os.getenv(FEATURE_FLAG) != "true"
    ):
        return False
    raw_company_ids = os.getenv(COMPANY_ALLOWLIST) or ""
    parts = raw_company_ids.split(",") if raw_company_ids else []
    if not parts:
        return False
    enabled_company_ids = set()
    for part in parts:
        if not part.isdigit() or part.startswith("0"):
            return False
        normalized = int(part)
        if normalized <= 0:
            return False
        enabled_company_ids.add(normalized)
    return company_id in enabled_company_ids


def _safe_log(report, log_fn):
    try:
        log_fn(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass


def _close_quietly(resource):
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        pass


def _base_report(state, source=None):
    report = {
        "mode": "shadow",
        "state": state,
        "eventType": EVENT_TYPE,
        "enqueueAttempted": False,
        "writesAttempted": 0,
    }
    if source is not None:
        report.update({
            "companyId": source.company_id,
            "projectId": source.project_id,
            "estimateId": source.estimate_id,
            "jobType": JOB_TYPE,
        })
    return report


def _validated_queue_report(report, source, enqueue_attempted):
    if not isinstance(report, Mapping) or set(report) != _QUEUE_REPORT_FIELDS:
        raise ValueError("queue report is invalid")
    plan = build_estimate_revision_impact_job_plan(source)
    writes_attempted = report.get("writesAttempted")
    if (
        report.get("ok") is not True
        or report.get("dryRun") is not False
        or report.get("state") not in ("enqueued", "existing")
        or writes_attempted not in (0, 1)
        or enqueue_attempted != bool(writes_attempted)
        or (report.get("state") == "enqueued" and writes_attempted != 1)
        or report.get("companyId") != source.company_id
        or report.get("projectId") != source.project_id
        or report.get("estimateId") != source.estimate_id
        or report.get("sourceRevision") != source.source_revision
        or report.get("jobType") != plan.job_type
        or report.get("idempotencyKey") != plan.idempotency_key
        or report.get("status") not in _JOB_STATES
    ):
        raise ValueError("queue report does not match the activation")
    job_id = report.get("jobId")
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("queue report job id is invalid")
    return {
        "mode": "enqueue",
        "state": report["state"],
        "eventType": EVENT_TYPE,
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
        "jobType": plan.job_type,
        "enqueueAttempted": enqueue_attempted,
        "writesAttempted": writes_attempted,
        "jobId": job_id,
        "status": report["status"],
        "committed": True,
    }


def handoff_estimate_revision_impact_transition(
    *,
    previous_status,
    next_status,
    company_id,
    project_id,
    estimate_id,
    version,
    sections,
    enabled=None,
    connection_factory=get_db,
    prepare_job=prepare_estimate_revision_impact_job,
    enqueue_job=enqueue_agent_job,
    log_fn=print,
):
    """Observe after commit and optionally enqueue one source-bound job."""

    if next_status != ACTIVE_STATUS or previous_status == ACTIVE_STATUS:
        return None
    try:
        source = build_estimate_revision_source(
            company_id=company_id,
            project_id=project_id,
            estimate_id=estimate_id,
            version=version,
            sections=sections,
        )
    except EstimateRevisionImpactContractError:
        report = {
            **_base_report("rejected"),
            "reasonCode": "source_invalid",
        }
        _safe_log(report, log_fn)
        return report
    except Exception:
        report = {
            **_base_report("rejected"),
            "reasonCode": "shadow_unavailable",
        }
        _safe_log(report, log_fn)
        return report

    shadow_report = _base_report("planned", source)
    if enabled is None:
        enabled = estimate_revision_impact_enabled(source.company_id)
    if type(enabled) is not bool or not enabled:
        _safe_log(shadow_report, log_fn)
        return shadow_report

    connection = None
    cursor = None
    enqueue_attempted = False

    def tracked_enqueue(*args, **kwargs):
        nonlocal enqueue_attempted
        enqueue_attempted = True
        return enqueue_job(*args, **kwargs)

    try:
        if not callable(connection_factory) or not callable(prepare_job):
            raise ValueError("handoff dependencies are invalid")
        if not callable(enqueue_job):
            raise ValueError("enqueue dependency is invalid")
        connection = connection_factory()
        connection.set_session(
            readonly=False,
            autocommit=False,
            isolation_level="SERIALIZABLE",
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        queue_report = prepare_job(
            cursor,
            source,
            apply=True,
            enqueue_job=tracked_enqueue,
        )
        report = _validated_queue_report(
            queue_report,
            source,
            enqueue_attempted,
        )
        connection.commit()
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        report = {
            **shadow_report,
            "mode": "enqueue",
            "state": "failed",
            "enqueueAttempted": enqueue_attempted,
            "writesAttempted": 1 if enqueue_attempted else 0,
            "committed": False,
            "reasonCode": "queue_unavailable",
        }
    finally:
        _close_quietly(cursor)
        _close_quietly(connection)

    _safe_log(report, log_fn)
    return report


__all__ = [
    "COMPANY_ALLOWLIST",
    "FEATURE_FLAG",
    "estimate_revision_impact_enabled",
    "handoff_estimate_revision_impact_transition",
]
