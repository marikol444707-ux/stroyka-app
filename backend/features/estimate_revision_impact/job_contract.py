"""Pure exact-source contract for one queued A7 revision-impact run."""

import hashlib
import json
from dataclasses import dataclass
from typing import Tuple

from .contract import (
    EstimateRevisionImpactContractError,
    EstimateRevisionSource,
    validate_estimate_revision_source,
)


JOB_TYPE = "estimate.revision_impact"
REQUESTED_BY_ROLE = "system"
PRIORITY = 4
MAX_ATTEMPTS = 3


class EstimateRevisionImpactJobContractError(ValueError):
    pass


@dataclass(frozen=True)
class EstimateRevisionImpactJobPlan:
    company_id: int
    project_id: int
    job_type: str
    idempotency_key: str
    correlation_id: str
    requested_by_role: str
    payload: Tuple[Tuple[str, object], ...]
    priority: int
    max_attempts: int


def _source_payload(source):
    return {
        "schemaVersion": source.schema_version,
        "eventType": source.event_type,
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
        "sourceRevision": source.source_revision,
    }


def _validated_source(source):
    if not isinstance(source, EstimateRevisionSource):
        raise EstimateRevisionImpactJobContractError(
            "source must be validated before job planning"
        )
    try:
        return validate_estimate_revision_source(_source_payload(source))
    except EstimateRevisionImpactContractError as exc:
        raise EstimateRevisionImpactJobContractError(
            "source contract is invalid"
        ) from exc


def source_from_job_payload(payload):
    try:
        return validate_estimate_revision_source(payload)
    except EstimateRevisionImpactContractError as exc:
        raise EstimateRevisionImpactJobContractError(
            "job payload does not match the source contract"
        ) from exc


def build_estimate_revision_impact_job_plan(source):
    source = _validated_source(source)
    payload = _source_payload(source)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()[:32]
    identity = "revision-impact:" + digest
    return EstimateRevisionImpactJobPlan(
        company_id=source.company_id,
        project_id=source.project_id,
        job_type=JOB_TYPE,
        idempotency_key=identity,
        correlation_id=identity,
        requested_by_role=REQUESTED_BY_ROLE,
        payload=tuple(payload.items()),
        priority=PRIORITY,
        max_attempts=MAX_ATTEMPTS,
    )


def validate_estimate_revision_impact_job_plan(plan):
    if not isinstance(plan, EstimateRevisionImpactJobPlan):
        raise EstimateRevisionImpactJobContractError("job plan is invalid")
    try:
        payload = dict(plan.payload)
    except (TypeError, ValueError) as exc:
        raise EstimateRevisionImpactJobContractError(
            "job plan payload is invalid"
        ) from exc
    source = source_from_job_payload(payload)
    expected = build_estimate_revision_impact_job_plan(source)
    if plan != expected:
        raise EstimateRevisionImpactJobContractError(
            "job plan does not match the source contract"
        )
    return plan


__all__ = [
    "JOB_TYPE",
    "EstimateRevisionImpactJobContractError",
    "EstimateRevisionImpactJobPlan",
    "build_estimate_revision_impact_job_plan",
    "source_from_job_payload",
    "validate_estimate_revision_impact_job_plan",
]
