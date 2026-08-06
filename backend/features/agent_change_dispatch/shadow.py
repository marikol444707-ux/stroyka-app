"""Metadata-only shadow observation for estimate activation events.

The observer never enqueues work and never touches business storage. Its output
is intentionally bounded so estimate contents and queue identities cannot leak
through application logs or API responses.
"""

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .contract import (
    AgentChangeContractError,
    build_agent_dispatch_plan,
    validate_agent_change_event,
)


EVENT_TYPE = "estimate.version_activated"
ACTIVE_STATUS = "Активная"
MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")


def _moscow_brief_date():
    return datetime.now(MOSCOW_TIMEZONE).date().isoformat()


def _canonical_source_revision(version, sections):
    if not isinstance(version, str) or not version or len(version) > 100:
        raise ValueError("estimate version is invalid")
    if not isinstance(sections, list):
        raise ValueError("estimate sections are invalid")
    canonical = json.dumps(
        {"sections": sections, "version": version},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _base_report(state):
    return {
        "mode": "shadow",
        "state": state,
        "eventType": EVENT_TYPE,
        "enqueueAttempted": False,
        "writesAttempted": 0,
    }


def _write_metadata_log(report, log_fn):
    try:
        log_fn(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass


def observe_estimate_activation_shadow(
    *,
    company_id,
    project_id,
    estimate_id,
    version,
    sections,
    brief_date_provider=_moscow_brief_date,
    log_fn=print,
):
    """Plan one activation dispatch in shadow mode and emit safe metadata."""
    try:
        if not callable(brief_date_provider):
            raise ValueError("brief date provider is invalid")
        source_revision = _canonical_source_revision(version, sections)
        event = validate_agent_change_event({
            "schemaVersion": 1,
            "eventType": EVENT_TYPE,
            "companyId": company_id,
            "projectId": project_id,
            "sourceType": "estimate",
            "sourceId": estimate_id,
            "sourceRevision": source_revision,
        })
        plan = build_agent_dispatch_plan(
            event,
            brief_date=brief_date_provider(),
        )
        report = {
            **_base_report("planned"),
            "companyId": event.company_id,
            "projectId": event.project_id,
            "sourceType": event.source_type,
            "sourceId": event.source_id,
            "jobType": plan.job_type,
            "briefDate": dict(plan.payload)["briefDate"],
        }
    except AgentChangeContractError:
        report = {**_base_report("rejected"), "reasonCode": "contract_rejected"}
    except (TypeError, ValueError):
        report = {**_base_report("rejected"), "reasonCode": "source_invalid"}
    except Exception:
        report = {**_base_report("rejected"), "reasonCode": "shadow_unavailable"}

    _write_metadata_log(report, log_fn)
    return report


def observe_estimate_activation_transition_shadow(
    *,
    previous_status,
    next_status,
    **activation,
):
    """Observe only a real transition into the active estimate state."""
    if next_status != ACTIVE_STATUS or previous_status == ACTIVE_STATUS:
        return None
    return observe_estimate_activation_shadow(**activation)
