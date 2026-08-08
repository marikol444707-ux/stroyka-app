"""Fail-closed read-only queue handler for one exact A7 combined report."""

from collections.abc import Mapping

from backend.db import get_db
from backend.features.agent_jobs.service import (
    AgentJobValidationError,
    serialize_safe_json_object,
)

from .combined_contract import (
    COMBINED_REPORT_VERSION,
    DOMAIN_ORDER,
    calculate_evidence_sha256,
)
from .combined_report import run_combined_impact_audit
from .job_contract import JOB_TYPE, source_from_job_payload


_REPORT_FIELDS = frozenset({
    "combinedReportVersion",
    "ok",
    "dryRun",
    "writesAttempted",
    "source",
    "domainOrder",
    "domains",
    "complete",
    "actionable",
    "reasonCounts",
    "evidenceSha256",
    "readOnlyTransaction",
    "rolledBack",
})


class EstimateRevisionImpactHandlerError(ValueError):
    pass


def _validated_result(report, source):
    if not isinstance(report, Mapping) or set(report) != _REPORT_FIELDS:
        raise EstimateRevisionImpactHandlerError("combined report is invalid")
    public_source = report.get("source")
    domains = report.get("domains")
    if (
        report.get("combinedReportVersion") != COMBINED_REPORT_VERSION
        or report.get("ok") is not True
        or report.get("dryRun") is not True
        or report.get("writesAttempted") != 0
        or report.get("readOnlyTransaction") is not True
        or report.get("rolledBack") is not True
        or type(report.get("complete")) is not bool
        or type(report.get("actionable")) is not bool
        or report.get("domainOrder") != list(DOMAIN_ORDER)
        or not isinstance(domains, Mapping)
        or tuple(domains) != DOMAIN_ORDER
        or not isinstance(public_source, Mapping)
        or public_source.get("companyId") != source.company_id
        or public_source.get("projectId") != source.project_id
        or public_source.get("estimateId") != source.estimate_id
        or public_source.get("sourceRevision") != source.source_revision
        or not isinstance(report.get("reasonCounts"), Mapping)
    ):
        raise EstimateRevisionImpactHandlerError(
            "combined report does not match the queued source"
        )
    try:
        evidence_sha256 = calculate_evidence_sha256(report)
    except Exception as exc:
        raise EstimateRevisionImpactHandlerError(
            "combined report evidence is invalid"
        ) from exc
    if report.get("evidenceSha256") != evidence_sha256:
        raise EstimateRevisionImpactHandlerError(
            "combined report evidence hash is invalid"
        )
    result = dict(report)
    try:
        serialize_safe_json_object(result, field="result")
    except AgentJobValidationError as exc:
        raise EstimateRevisionImpactHandlerError(
            "combined report cannot be stored safely"
        ) from exc
    return result


def build_estimate_revision_impact_handler(
    *,
    run_report=run_combined_impact_audit,
    connection_factory=get_db,
):
    if not callable(run_report) or not callable(connection_factory):
        raise EstimateRevisionImpactHandlerError(
            "handler dependencies must be callable"
        )
    run_report_dependency = run_report
    connection_factory_dependency = connection_factory

    def handle(context):
        if context.job_type != JOB_TYPE:
            raise EstimateRevisionImpactHandlerError(
                "handler received the wrong job type"
            )
        if (
            context.requested_by_user_id is not None
            or context.requested_by_role != "system"
        ):
            raise EstimateRevisionImpactHandlerError(
                "revision impact job must be system-owned"
            )
        try:
            source = source_from_job_payload(context.payload)
        except Exception as exc:
            raise EstimateRevisionImpactHandlerError(
                "revision impact payload is invalid"
            ) from exc
        if (
            context.owner_company_id != source.company_id
            or context.project_id != source.project_id
        ):
            raise EstimateRevisionImpactHandlerError(
                "queue scope does not match the revision source"
            )
        report = run_report_dependency(connection_factory_dependency, source)
        return _validated_result(report, source)

    return handle


handle_estimate_revision_impact = build_estimate_revision_impact_handler()


__all__ = [
    "EstimateRevisionImpactHandlerError",
    "build_estimate_revision_impact_handler",
    "handle_estimate_revision_impact",
]
