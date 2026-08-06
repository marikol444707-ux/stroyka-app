"""Pure, fail-closed contract for future event-driven agent checks.

This module validates and plans dispatch only. It performs no SQL, queue write,
model call, message delivery, business mutation or background execution.
"""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Optional, Tuple


class AgentChangeContractError(ValueError):
    pass


@dataclass(frozen=True)
class AgentChangeEvent:
    schema_version: int
    event_type: str
    company_id: int
    project_id: int
    source_type: str
    source_id: int
    source_revision: str


@dataclass(frozen=True)
class AgentDispatchPlan:
    company_id: int
    project_id: Optional[int]
    event_type: str
    source_project_id: int
    source_type: str
    source_id: int
    source_revision: str
    job_type: str
    idempotency_key: str
    correlation_id: str
    requested_by_role: str
    payload: Tuple[Tuple[str, str], ...]
    priority: int
    max_attempts: int


_EVENT_FIELDS = frozenset({
    "schemaVersion",
    "eventType",
    "companyId",
    "projectId",
    "sourceType",
    "sourceId",
    "sourceRevision",
})

_EVENT_POLICIES = MappingProxyType({
    "estimate.version_activated": MappingProxyType({
        "sourceType": "estimate",
        "jobType": "director.daily_brief",
        "priority": 4,
        "maxAttempts": 3,
    }),
})

_SOURCE_REVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AgentChangeContractError(f"{field} must be a positive integer")
    return value


def _exact_text(value, field, limit):
    if not isinstance(value, str):
        raise AgentChangeContractError(f"{field} must be text")
    if not value or value != value.strip() or len(value) > limit:
        raise AgentChangeContractError(f"{field} is invalid")
    return value


def validate_agent_change_event(value):
    if not isinstance(value, Mapping):
        raise AgentChangeContractError("event must be an object")
    if set(value) != _EVENT_FIELDS:
        raise AgentChangeContractError("event fields do not match the contract")

    schema_version = value.get("schemaVersion")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise AgentChangeContractError("schema version is not supported")
    if schema_version != 1:
        raise AgentChangeContractError("schema version is not supported")

    event_type = _exact_text(value.get("eventType"), "event type", 80)
    policy = _EVENT_POLICIES.get(event_type)
    if policy is None:
        raise AgentChangeContractError("event type is not allowed")

    source_type = _exact_text(value.get("sourceType"), "source type", 40)
    if source_type != policy["sourceType"]:
        raise AgentChangeContractError("source type does not match the event type")

    source_revision = _exact_text(
        value.get("sourceRevision"),
        "source revision",
        120,
    )
    if not _SOURCE_REVISION_RE.fullmatch(source_revision):
        raise AgentChangeContractError("source revision is invalid")

    return AgentChangeEvent(
        schema_version=1,
        event_type=event_type,
        company_id=_positive_int(value.get("companyId"), "company_id"),
        project_id=_positive_int(value.get("projectId"), "project_id"),
        source_type=source_type,
        source_id=_positive_int(value.get("sourceId"), "source_id"),
        source_revision=source_revision,
    )


def _validated_brief_date(value):
    if not isinstance(value, str) or not value:
        raise AgentChangeContractError("brief date is invalid")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AgentChangeContractError("brief date is invalid") from exc
    if parsed.isoformat() != value:
        raise AgentChangeContractError("brief date is invalid")
    return value


def build_agent_dispatch_plan(event, *, brief_date):
    if not isinstance(event, AgentChangeEvent):
        raise AgentChangeContractError("event must be validated before dispatch")
    event = validate_agent_change_event({
        "schemaVersion": event.schema_version,
        "eventType": event.event_type,
        "companyId": event.company_id,
        "projectId": event.project_id,
        "sourceType": event.source_type,
        "sourceId": event.source_id,
        "sourceRevision": event.source_revision,
    })
    policy = _EVENT_POLICIES.get(event.event_type)
    if policy is None or policy["sourceType"] != event.source_type:
        raise AgentChangeContractError("event policy is unavailable")
    brief_date = _validated_brief_date(brief_date)

    identity = "|".join((
        str(event.schema_version),
        event.event_type,
        str(event.company_id),
        str(event.project_id),
        event.source_type,
        str(event.source_id),
        event.source_revision,
        brief_date,
    ))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]

    return AgentDispatchPlan(
        company_id=event.company_id,
        project_id=None,
        event_type=event.event_type,
        source_project_id=event.project_id,
        source_type=event.source_type,
        source_id=event.source_id,
        source_revision=event.source_revision,
        job_type=policy["jobType"],
        idempotency_key=f"change:{event.event_type}:{digest}",
        correlation_id=f"change:{digest}",
        requested_by_role="system",
        payload=(("briefDate", brief_date),),
        priority=policy["priority"],
        max_attempts=policy["maxAttempts"],
    )


def validate_agent_dispatch_plan(plan):
    if not isinstance(plan, AgentDispatchPlan):
        raise AgentChangeContractError("dispatch plan is invalid")
    if (
        not isinstance(plan.payload, tuple)
        or len(plan.payload) != 1
        or not isinstance(plan.payload[0], tuple)
        or len(plan.payload[0]) != 2
        or plan.payload[0][0] != "briefDate"
    ):
        raise AgentChangeContractError("dispatch plan payload is invalid")

    event = validate_agent_change_event({
        "schemaVersion": 1,
        "eventType": plan.event_type,
        "companyId": plan.company_id,
        "projectId": plan.source_project_id,
        "sourceType": plan.source_type,
        "sourceId": plan.source_id,
        "sourceRevision": plan.source_revision,
    })
    expected = build_agent_dispatch_plan(
        event,
        brief_date=plan.payload[0][1],
    )
    if plan != expected:
        raise AgentChangeContractError("dispatch plan does not match the contract")
    return plan
