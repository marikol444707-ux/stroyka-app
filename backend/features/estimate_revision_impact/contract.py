"""Pure A7 source identity contract for one activated estimate revision."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

try:
    from backend.features.agent_change_dispatch.shadow import (
        build_estimate_activation_source_revision,
    )
except ModuleNotFoundError:
    from features.agent_change_dispatch.shadow import (
        build_estimate_activation_source_revision,
    )


EVENT_TYPE = "estimate.version_activated"
REPORT_VERSION = 1
MAX_VERSION_LENGTH = 100
MAX_SECTIONS = 5000
MAX_ITEMS = 50000
MAX_CANONICAL_SOURCE_BYTES = 4 * 1024 * 1024

_SOURCE_FIELDS = frozenset({
    "schemaVersion",
    "eventType",
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
})
_SOURCE_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class EstimateRevisionImpactContractError(ValueError):
    """Fixed contract error that never includes estimate business content."""


@dataclass(frozen=True)
class EstimateRevisionSource:
    schema_version: int
    event_type: str
    company_id: int
    project_id: int
    estimate_id: int
    source_revision: str


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EstimateRevisionImpactContractError(
            field + " must be a positive integer"
        )
    return value


def _validated_version(value):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > MAX_VERSION_LENGTH
    ):
        raise EstimateRevisionImpactContractError("estimate version is invalid")
    return value


def _validated_sections(value):
    if not isinstance(value, list) or len(value) > MAX_SECTIONS:
        raise EstimateRevisionImpactContractError("estimate sections are invalid")
    item_count = 0
    for section in value:
        if not isinstance(section, dict):
            raise EstimateRevisionImpactContractError(
                "estimate sections are invalid"
            )
        items = section.get("items") or []
        if not isinstance(items, list):
            raise EstimateRevisionImpactContractError(
                "estimate sections are invalid"
            )
        item_count += len(items)
        if item_count > MAX_ITEMS or any(
            not isinstance(item, dict) for item in items
        ):
            raise EstimateRevisionImpactContractError(
                "estimate sections are invalid"
            )
    return value


def build_source_revision(version, sections):
    """Return the same canonical revision identity used by A6 activation."""

    version = _validated_version(version)
    sections = _validated_sections(sections)
    try:
        return build_estimate_activation_source_revision(
            version,
            sections,
            max_canonical_bytes=MAX_CANONICAL_SOURCE_BYTES,
        )
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError) as exc:
        raise EstimateRevisionImpactContractError(
            "estimate sections are invalid"
        ) from exc


def validate_estimate_revision_source(value):
    if not isinstance(value, Mapping) or set(value) != _SOURCE_FIELDS:
        raise EstimateRevisionImpactContractError(
            "source fields do not match the contract"
        )
    if value.get("schemaVersion") != REPORT_VERSION or isinstance(
        value.get("schemaVersion"), bool
    ):
        raise EstimateRevisionImpactContractError(
            "source schema version is not supported"
        )
    if value.get("eventType") != EVENT_TYPE:
        raise EstimateRevisionImpactContractError("source event type is invalid")
    source_revision = value.get("sourceRevision")
    if (
        not isinstance(source_revision, str)
        or not _SOURCE_REVISION_RE.fullmatch(source_revision)
    ):
        raise EstimateRevisionImpactContractError("source revision is invalid")
    return EstimateRevisionSource(
        schema_version=REPORT_VERSION,
        event_type=EVENT_TYPE,
        company_id=_positive_int(value.get("companyId"), "company_id"),
        project_id=_positive_int(value.get("projectId"), "project_id"),
        estimate_id=_positive_int(value.get("estimateId"), "estimate_id"),
        source_revision=source_revision,
    )


def build_estimate_revision_source(
    *,
    company_id,
    project_id,
    estimate_id,
    version,
    sections,
):
    return validate_estimate_revision_source({
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": company_id,
        "projectId": project_id,
        "estimateId": estimate_id,
        "sourceRevision": build_source_revision(version, sections),
    })


__all__ = [
    "EVENT_TYPE",
    "REPORT_VERSION",
    "EstimateRevisionImpactContractError",
    "EstimateRevisionSource",
    "build_estimate_revision_source",
    "build_source_revision",
    "validate_estimate_revision_source",
]
