"""Fail-closed registry and input boundary for background job handlers."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Optional

from backend.features.agent_jobs.service import (
    JOB_TYPE_RE,
    AgentJobValidationError,
    serialize_safe_json_object,
)
from backend.features.director_daily_brief.handler import handle_director_daily_brief


class AgentJobHandlerRegistryError(ValueError):
    pass


def _positive_int(value, field, *, required=True):
    if value is None and not required:
        return None
    if type(value) is not int or value <= 0:
        raise AgentJobHandlerRegistryError(f"{field} must be a positive integer")
    return value


def _bounded_text(value, field, limit, *, required=False):
    normalized = str(value or "").strip()
    if required and not normalized:
        raise AgentJobHandlerRegistryError(f"{field} is required")
    if len(normalized) > limit:
        raise AgentJobHandlerRegistryError(f"{field} is too long")
    return normalized


def _deep_freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(nested) for key, nested in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class AgentJobContext:
    job_id: int
    owner_company_id: int
    project_id: Optional[int]
    requested_by_user_id: Optional[int]
    requested_by_role: str
    job_type: str
    correlation_id: str
    payload: Mapping
    attempt: int
    max_attempts: int

    @classmethod
    def from_claimed_row(cls, row):
        if not isinstance(row, Mapping):
            raise AgentJobHandlerRegistryError("claimed job must be a mapping")
        job_type = _bounded_text(row.get("job_type"), "job_type", 80, required=True)
        if not JOB_TYPE_RE.fullmatch(job_type):
            raise AgentJobHandlerRegistryError("job_type has invalid format")
        payload = row.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise AgentJobHandlerRegistryError("payload_json must be valid JSON") from exc
        try:
            payload_json = serialize_safe_json_object(payload, field="payload")
        except AgentJobValidationError as exc:
            raise AgentJobHandlerRegistryError(str(exc)) from exc
        return cls(
            job_id=_positive_int(row.get("id"), "id"),
            owner_company_id=_positive_int(row.get("company_id"), "company_id"),
            project_id=_positive_int(row.get("project_id"), "project_id", required=False),
            requested_by_user_id=_positive_int(
                row.get("requested_by_user_id"),
                "requested_by_user_id",
                required=False,
            ),
            requested_by_role=_bounded_text(
                row.get("requested_by_role"),
                "requested_by_role",
                100,
            ),
            job_type=job_type,
            correlation_id=_bounded_text(
                row.get("correlation_id"),
                "correlation_id",
                80,
                required=True,
            ),
            payload=_deep_freeze(json.loads(payload_json)),
            attempt=_positive_int(row.get("attempts"), "attempts"),
            max_attempts=_positive_int(row.get("max_attempts"), "max_attempts"),
        )


class AgentJobHandlerRegistry:
    def __init__(self, entries):
        handlers = {}
        for job_type, handler in entries:
            normalized = str(job_type or "").strip()
            if not JOB_TYPE_RE.fullmatch(normalized):
                raise AgentJobHandlerRegistryError("handler job type has invalid format")
            if normalized in handlers:
                raise AgentJobHandlerRegistryError("handler job type is registered twice")
            if not callable(handler):
                raise AgentJobHandlerRegistryError("handler must be callable")
            handlers[normalized] = handler
        if not handlers:
            raise AgentJobHandlerRegistryError("handler registry must not be empty")
        self._handlers = MappingProxyType(handlers)

    @property
    def handlers(self):
        return self._handlers

    @property
    def job_types(self):
        return tuple(self._handlers)

    def get(self, job_type):
        return self._handlers.get(str(job_type or "").strip())


def _worker_probe_handler(context):
    del context
    return {"ok": True, "workerReady": True}


def build_default_handler_registry():
    """Return only handlers that are safe to execute in the current release."""
    return AgentJobHandlerRegistry((
        ("system.worker_probe", _worker_probe_handler),
        ("director.daily_brief", handle_director_daily_brief),
    ))
