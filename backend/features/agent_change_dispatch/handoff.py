"""Fail-soft post-commit handoff from estimate activation to the agent queue."""

import json
import os
from collections.abc import Mapping

from psycopg2.extras import RealDictCursor

try:
    from backend.db import get_db
except ModuleNotFoundError:
    from db import get_db

from .dispatch import dispatch_agent_change_plan
from .shadow import (
    ACTIVE_STATUS,
    _moscow_brief_date,
    build_estimate_activation_dispatch_plan,
    observe_estimate_activation_transition_shadow,
)


FEATURE_FLAG = "AGENT_CHANGE_DISPATCH_APPLY"
COMPANY_ALLOWLIST = "AGENT_CHANGE_DISPATCH_COMPANY_IDS"
_JOB_STATES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})


def agent_change_dispatch_enabled(company_id):
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


def _validated_dispatch_report(report, shadow_report):
    if not isinstance(report, Mapping):
        raise ValueError("dispatch report is invalid")
    job_id = report.get("jobId")
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("dispatch job id is invalid")
    if (
        report.get("ok") is not True
        or report.get("dryRun") is not False
        or report.get("state") not in ("enqueued", "existing")
        or report.get("enqueueAttempted") is not True
        or report.get("writesAttempted") != 1
        or report.get("companyId") != shadow_report.get("companyId")
        or report.get("projectId") != shadow_report.get("projectId")
        or report.get("jobType") != shadow_report.get("jobType")
        or report.get("briefDate") != shadow_report.get("briefDate")
        or report.get("status") not in _JOB_STATES
    ):
        raise ValueError("dispatch report does not match the activation")
    return dict(report)


def handoff_estimate_activation_transition(
    *,
    previous_status,
    next_status,
    company_id,
    project_id,
    estimate_id,
    version,
    sections,
    enabled=None,
    brief_date_provider=_moscow_brief_date,
    connection_factory=get_db,
    dispatch_plan=dispatch_agent_change_plan,
    log_fn=print,
):
    """Preserve shadow behavior unless explicit post-commit enqueue is enabled."""
    if next_status != ACTIVE_STATUS or previous_status == ACTIVE_STATUS:
        return None

    shadow_report = observe_estimate_activation_transition_shadow(
        previous_status=previous_status,
        next_status=next_status,
        company_id=company_id,
        project_id=project_id,
        estimate_id=estimate_id,
        version=version,
        sections=sections,
        brief_date_provider=brief_date_provider,
        log_fn=log_fn,
    )
    if shadow_report is None or shadow_report.get("state") != "planned":
        return shadow_report
    if enabled is None:
        enabled = agent_change_dispatch_enabled(company_id)
    if type(enabled) is not bool or not enabled:
        return shadow_report

    connection = None
    cursor = None
    enqueue_attempted = False
    try:
        plan = build_estimate_activation_dispatch_plan(
            company_id=company_id,
            project_id=project_id,
            estimate_id=estimate_id,
            version=version,
            sections=sections,
            brief_date=shadow_report["briefDate"],
        )
        connection = connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        enqueue_attempted = True
        dispatch_report = dispatch_plan(cursor, plan=plan, apply=True)
        dispatch_report = _validated_dispatch_report(
            dispatch_report,
            shadow_report,
        )
        connection.commit()
        report = {
            **shadow_report,
            **dispatch_report,
            "mode": "enqueue",
            "committed": True,
        }
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
            "reasonCode": "dispatch_unavailable",
        }
    finally:
        _close_quietly(cursor)
        _close_quietly(connection)

    _safe_log(report, log_fn)
    return report
