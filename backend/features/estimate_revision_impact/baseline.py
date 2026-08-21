"""Bounded read-only A7.1 source and reconciliation baseline audit."""

import argparse
import json

import psycopg2.extras

from .contract import (
    EVENT_TYPE,
    MAX_CANONICAL_SOURCE_BYTES,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    EstimateRevisionSource,
    build_source_revision,
    validate_estimate_revision_source,
)
from .schema_probe import collect_missing_columns
from .resource_limits import (
    MAX_COLLECTOR_VARIABLE_BYTES,
    MAX_JSON_QUERY_BYTES,
    MAX_TEXT_FIELD_BYTES,
    MAX_TEXT_QUERY_AGGREGATE_BYTES,
    _BOUNDED_OVERFLOW,
    _VariableByteBudget,
    _VariableByteLimitError,
    _accept_bounded_rows,
)


DEFAULT_MAX_ISSUES = 100
MAX_RECONCILIATION_ROWS = 100
KNOWN_RECONCILIATION_STATUSES = frozenset({
    "Черновик",
    "На проверке",
    "Утверждена",
    "Отклонена",
})
REQUIRED_COLUMNS = {
    "projects": {"id", "company_id"},
    "estimates": {
        "id",
        "company_id",
        "project_id",
        "version",
        "sections_json",
        "status",
        "is_template",
        "smeta_type",
        "work_package",
    },
    "estimate_reconciliations": {
        "id",
        "base_estimate_id",
        "next_estimate_id",
        "status",
        "smeta_type",
        "work_package",
    },
}

_TARGET_FIELD_SPECS = (
    ("version", "field_version_bytes", "text", MAX_TEXT_FIELD_BYTES, True),
    (
        "sections_json",
        "field_sections_json_bytes",
        "json",
        MAX_CANONICAL_SOURCE_BYTES,
        True,
    ),
    ("status", "field_status_bytes", "text", MAX_TEXT_FIELD_BYTES, False),
    (
        "smeta_type",
        "field_smeta_type_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "work_package",
        "field_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
)
_RECONCILIATION_FIELD_SPECS = (
    (
        "reconciliation_status",
        "field_reconciliation_status_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "reconciliation_smeta_type",
        "field_reconciliation_smeta_type_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "reconciliation_work_package",
        "field_reconciliation_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "base_smeta_type",
        "field_base_smeta_type_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "base_work_package",
        "field_base_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "next_status",
        "field_next_status_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "next_smeta_type",
        "field_next_smeta_type_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "next_work_package",
        "field_next_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
)


def _positive_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _source_dict(source):
    return {
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
        "sourceRevision": source.source_revision,
    }


def _validated_source(source):
    if not isinstance(source, EstimateRevisionSource):
        raise EstimateRevisionImpactContractError("source contract is invalid")
    return validate_estimate_revision_source({
        "schemaVersion": source.schema_version,
        "eventType": source.event_type,
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
        "sourceRevision": source.source_revision,
    })


def _base_report(source):
    return {
        "reportVersion": REPORT_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": True,
        "sourceReady": False,
        "readyForDomainScan": False,
        "source": _source_dict(source),
        "summary": {"estimateRows": 0, "reconciliationRows": 0},
        "issueCount": 0,
        "reasonCounts": {},
        "issues": [],
        "issuesTruncated": False,
    }


def _fail(report, source, reason_code, *, max_issues, scan_complete=True):
    report["scanComplete"] = bool(scan_complete)
    report["sourceReady"] = False
    report["readyForDomainScan"] = False
    report["issueCount"] = 1
    report["reasonCounts"] = {reason_code: 1}
    issue = {
        "reasonCode": reason_code,
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
    }
    issue_limit = max(0, min(DEFAULT_MAX_ISSUES, int(max_issues)))
    report["issues"] = [issue] if issue_limit else []
    report["issuesTruncated"] = not bool(issue_limit)
    return report


def _estimate_reason(row, source):
    if (
        _positive_int(row.get("estimate_id")) != source.estimate_id
        or _positive_int(row.get("company_id")) != source.company_id
        or _positive_int(row.get("project_id")) != source.project_id
    ):
        return "impact_source_owner_mismatch"
    if _text(row.get("status")) != "Активная":
        return "impact_estimate_not_active"
    if row.get("is_template") is not False:
        return "impact_estimate_template"
    if (_text(row.get("smeta_type")) or "Заказчик") != "Заказчик":
        return "impact_estimate_not_customer"
    work_package = _text(row.get("work_package"))
    if not work_package or len(work_package) > 100:
        return "impact_estimate_package_invalid"
    sections_bytes = row.get("sections_bytes")
    if sections_bytes is not None:
        if (
            isinstance(sections_bytes, bool)
            or not isinstance(sections_bytes, int)
            or sections_bytes < 0
        ):
            return "impact_estimate_snapshot_invalid"
        if sections_bytes > MAX_CANONICAL_SOURCE_BYTES:
            return "impact_estimate_snapshot_too_large"
    version = row.get("version")
    sections = row.get("sections_json")
    try:
        sections = json.loads(sections) if isinstance(sections, str) else sections
        stored_revision = build_source_revision(version, sections)
    except (
        EstimateRevisionImpactContractError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
        ValueError,
        UnicodeError,
        OverflowError,
    ):
        return "impact_estimate_snapshot_invalid"
    if stored_revision != source.source_revision:
        return "source_revision_mismatch"
    return None


def _reconciliation_reason(row, source):
    reconciliation_id = _positive_int(row.get("reconciliation_id"))
    base_estimate_id = _positive_int(row.get("base_estimate_id"))
    next_estimate_id = _positive_int(row.get("next_estimate_id"))
    if reconciliation_id is None:
        return "impact_reconciliation_id_invalid"
    if (
        base_estimate_id is None
        or next_estimate_id != source.estimate_id
        or base_estimate_id == next_estimate_id
    ):
        return "impact_reconciliation_estimate_pair_invalid"
    owner = (source.company_id, source.project_id)
    if (
        owner != (
            _positive_int(row.get("project_company_id")),
            _positive_int(row.get("project_id")),
        )
        or owner != (
            _positive_int(row.get("base_company_id")),
            _positive_int(row.get("base_project_id")),
        )
        or owner != (
            _positive_int(row.get("next_company_id")),
            _positive_int(row.get("next_project_id")),
        )
    ):
        return "impact_reconciliation_owner_mismatch"
    if {
        _text(row.get("reconciliation_smeta_type")) or "Заказчик",
        _text(row.get("base_smeta_type")) or "Заказчик",
        _text(row.get("next_smeta_type")) or "Заказчик",
    } != {"Заказчик"}:
        return "impact_reconciliation_not_customer"
    packages = {
        _text(row.get("reconciliation_work_package")),
        _text(row.get("base_work_package")),
        _text(row.get("next_work_package")),
    }
    if "" in packages or len(packages) != 1:
        return "impact_reconciliation_package_mismatch"
    if _text(row.get("next_status")) != "Активная" or row.get(
        "next_is_template"
    ) is not False:
        return "impact_reconciliation_next_not_active"
    if _text(row.get("reconciliation_status")) not in KNOWN_RECONCILIATION_STATUSES:
        return "impact_reconciliation_status_invalid"
    return None


def _collect_baseline_audit(
    cur,
    source,
    variable_budget,
    *,
    max_reconciliation_rows=MAX_RECONCILIATION_ROWS,
    max_issues=DEFAULT_MAX_ISSUES,
):
    """Collect one exact source boundary with hard limits and no mutations."""

    source = _validated_source(source)
    if type(variable_budget) is not _VariableByteBudget:
        raise _VariableByteLimitError("variable byte metadata is invalid")
    remaining_bytes = variable_budget.remaining_bytes
    if (
        type(remaining_bytes) is not int
        or remaining_bytes < 0
        or remaining_bytes > MAX_COLLECTOR_VARIABLE_BYTES
    ):
        raise _VariableByteLimitError("variable byte metadata is invalid")
    report = _base_report(source)
    max_reconciliation_rows = max(0, min(
        MAX_RECONCILIATION_ROWS,
        int(max_reconciliation_rows),
    ))

    missing = collect_missing_columns(cur, REQUIRED_COLUMNS)
    if missing:
        report["schemaReady"] = False
        report["missingColumns"] = missing
        return _fail(
            report,
            source,
            "estimate_revision_impact_schema_not_ready",
            max_issues=max_issues,
            scan_complete=False,
        )

    cur.execute(
        """SELECT bounded.estimate_id,bounded.company_id,bounded.project_id,
                  bounded.version,bounded.sections_json,bounded.sections_bytes,
                  bounded.status,bounded.is_template,bounded.smeta_type,
                  bounded.work_package,bounded.field_version_bytes,
                  bounded.field_sections_json_bytes,
                  bounded.field_status_bytes,bounded.field_smeta_type_bytes,
                  bounded.field_work_package_bytes,bounded.query_json_bytes,
                  bounded.query_text_bytes,bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT e.id AS estimate_id,e.company_id,e.project_id,
                        e.version AS emitted_version,
                        e.sections_json::text AS emitted_sections_json,
                        COALESCE(e.status,'Черновик') AS emitted_status,
                        COALESCE(e.is_template,FALSE) AS is_template,
                        COALESCE(e.smeta_type,'Заказчик') AS emitted_smeta_type,
                        e.work_package AS emitted_work_package
                   FROM public.estimates e
                  WHERE e.id=%s AND e.company_id=%s AND e.project_id=%s
                  ORDER BY e.id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_version,'UTF8'
                        )),0)::bigint AS field_version_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_sections_json,'UTF8'
                        )),0)::bigint AS field_sections_json_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_status,'UTF8'
                        )),0)::bigint AS field_status_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_smeta_type,'UTF8'
                        )),0)::bigint AS field_smeta_type_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_work_package,'UTF8'
                        )),0)::bigint AS field_work_package_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_version_bytes) OVER ()
                            AS max_field_version_bytes,
                        MAX(field_sections_json_bytes) OVER ()
                            AS max_field_sections_json_bytes,
                        MAX(field_status_bytes) OVER ()
                            AS max_field_status_bytes,
                        MAX(field_smeta_type_bytes) OVER ()
                            AS max_field_smeta_type_bytes,
                        MAX(field_work_package_bytes) OVER ()
                            AS max_field_work_package_bytes,
                        COALESCE(SUM(field_sections_json_bytes) OVER (),0)::bigint
                            AS query_json_bytes,
                        COALESCE(SUM(
                            field_version_bytes::bigint
                            + field_status_bytes::bigint
                            + field_smeta_type_bytes::bigint
                            + field_work_package_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        (query_json_bytes + query_text_bytes)::bigint
                            AS query_variable_bytes,
                        (
                          max_field_sections_json_bytes <= %s
                          AND max_field_version_bytes <= %s
                          AND max_field_status_bytes <= %s
                          AND max_field_smeta_type_bytes <= %s
                          AND max_field_work_package_bytes <= %s
                          AND query_json_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_json_bytes + query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.estimate_id,decided.company_id,
                      decided.project_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_version ELSE NULL END AS version,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_sections_json ELSE NULL
                      END AS sections_json,
                      decided.field_sections_json_bytes AS sections_bytes,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_status ELSE NULL END AS status,
                      decided.is_template,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_smeta_type ELSE NULL
                      END AS smeta_type,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_work_package ELSE NULL
                      END AS work_package,
                      decided.field_version_bytes,
                      decided.field_sections_json_bytes,
                      decided.field_status_bytes,
                      decided.field_smeta_type_bytes,
                      decided.field_work_package_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.estimate_id""",
        (
            source.estimate_id,
            source.company_id,
            source.project_id,
            2,
            MAX_CANONICAL_SOURCE_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_JSON_QUERY_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            1,
            1,
            1,
        ),
    )
    estimates = [dict(row or {}) for row in (cur.fetchall() or [])]
    report["summary"]["estimateRows"] = len(estimates)
    try:
        for estimate in estimates:
            if (
                type(estimate.get("sections_bytes")) is not int
                or estimate.get("sections_bytes") < 0
                or estimate.get("sections_bytes")
                != estimate.get("field_sections_json_bytes")
            ):
                raise _VariableByteLimitError(
                    "variable byte metadata is invalid"
                )
        estimate_state, estimates, _estimate_overflow_fields = (
            _accept_bounded_rows(
                estimates,
                variable_budget,
                scan_limit=1,
                field_specs=_TARGET_FIELD_SPECS,
            )
        )
    except _VariableByteLimitError:
        return _fail(
            report,
            source,
            "impact_estimate_snapshot_invalid",
            max_issues=max_issues,
        )
    if not estimates:
        return _fail(
            report,
            source,
            "impact_source_not_found",
            max_issues=max_issues,
        )
    if len(estimates) != 1:
        return _fail(
            report,
            source,
            "impact_source_ambiguous",
            max_issues=max_issues,
        )
    if estimate_state == _BOUNDED_OVERFLOW:
        fixed_estimate_reason = _estimate_reason(estimates[0], source)
        if fixed_estimate_reason == "impact_source_owner_mismatch":
            return _fail(
                report,
                source,
                fixed_estimate_reason,
                max_issues=max_issues,
            )
        return _fail(
            report,
            source,
            "impact_estimate_snapshot_too_large",
            max_issues=max_issues,
        )
    estimate_reason = _estimate_reason(estimates[0], source)
    if estimate_reason:
        return _fail(
            report,
            source,
            estimate_reason,
            max_issues=max_issues,
        )

    cur.execute(
        """SELECT bounded.reconciliation_id,
                  bounded.reconciliation_status,
                  bounded.reconciliation_smeta_type,
                  bounded.reconciliation_work_package,
                  bounded.base_estimate_id,bounded.next_estimate_id,
                  bounded.project_id,bounded.project_company_id,
                  bounded.base_company_id,bounded.base_project_id,
                  bounded.base_smeta_type,bounded.base_work_package,
                  bounded.next_company_id,bounded.next_project_id,
                  bounded.next_status,bounded.next_is_template,
                  bounded.next_smeta_type,bounded.next_work_package,
                  bounded.field_reconciliation_status_bytes,
                  bounded.field_reconciliation_smeta_type_bytes,
                  bounded.field_reconciliation_work_package_bytes,
                  bounded.field_base_smeta_type_bytes,
                  bounded.field_base_work_package_bytes,
                  bounded.field_next_status_bytes,
                  bounded.field_next_smeta_type_bytes,
                  bounded.field_next_work_package_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT r.id AS reconciliation_id,
                        r.status AS emitted_reconciliation_status,
                        COALESCE(r.smeta_type,'Заказчик')
                            AS emitted_reconciliation_smeta_type,
                        r.work_package
                            AS emitted_reconciliation_work_package,
                        r.base_estimate_id,r.next_estimate_id,
                        p.id AS project_id,
                        p.company_id AS project_company_id,
                        b.company_id AS base_company_id,
                        b.project_id AS base_project_id,
                        COALESCE(b.smeta_type,'Заказчик')
                            AS emitted_base_smeta_type,
                        b.work_package AS emitted_base_work_package,
                        n.company_id AS next_company_id,
                        n.project_id AS next_project_id,
                        COALESCE(n.status,'Черновик') AS emitted_next_status,
                        COALESCE(n.is_template,FALSE) AS next_is_template,
                        COALESCE(n.smeta_type,'Заказчик')
                            AS emitted_next_smeta_type,
                        n.work_package AS emitted_next_work_package
                   FROM public.estimate_reconciliations r
                   LEFT JOIN public.estimates b ON b.id=r.base_estimate_id
                   LEFT JOIN public.estimates n ON n.id=r.next_estimate_id
                   LEFT JOIN public.projects p ON p.id=n.project_id
                  WHERE r.next_estimate_id=%s
                    AND n.id=%s AND n.company_id=%s AND n.project_id=%s
                  ORDER BY r.id DESC
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_reconciliation_status,'UTF8'
                        )),0)::bigint
                            AS field_reconciliation_status_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_reconciliation_smeta_type,'UTF8'
                        )),0)::bigint
                            AS field_reconciliation_smeta_type_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_reconciliation_work_package,'UTF8'
                        )),0)::bigint
                            AS field_reconciliation_work_package_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_base_smeta_type,'UTF8'
                        )),0)::bigint AS field_base_smeta_type_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_base_work_package,'UTF8'
                        )),0)::bigint AS field_base_work_package_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_next_status,'UTF8'
                        )),0)::bigint AS field_next_status_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_next_smeta_type,'UTF8'
                        )),0)::bigint AS field_next_smeta_type_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_next_work_package,'UTF8'
                        )),0)::bigint AS field_next_work_package_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_reconciliation_status_bytes) OVER ()
                            AS max_field_reconciliation_status_bytes,
                        MAX(field_reconciliation_smeta_type_bytes) OVER ()
                            AS max_field_reconciliation_smeta_type_bytes,
                        MAX(field_reconciliation_work_package_bytes) OVER ()
                            AS max_field_reconciliation_work_package_bytes,
                        MAX(field_base_smeta_type_bytes) OVER ()
                            AS max_field_base_smeta_type_bytes,
                        MAX(field_base_work_package_bytes) OVER ()
                            AS max_field_base_work_package_bytes,
                        MAX(field_next_status_bytes) OVER ()
                            AS max_field_next_status_bytes,
                        MAX(field_next_smeta_type_bytes) OVER ()
                            AS max_field_next_smeta_type_bytes,
                        MAX(field_next_work_package_bytes) OVER ()
                            AS max_field_next_work_package_bytes,
                        COALESCE(SUM(
                            field_reconciliation_status_bytes::bigint
                            + field_reconciliation_smeta_type_bytes::bigint
                            + field_reconciliation_work_package_bytes::bigint
                            + field_base_smeta_type_bytes::bigint
                            + field_base_work_package_bytes::bigint
                            + field_next_status_bytes::bigint
                            + field_next_smeta_type_bytes::bigint
                            + field_next_work_package_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        0::bigint AS query_json_bytes,
                        query_text_bytes::bigint AS query_variable_bytes,
                        (
                          max_field_reconciliation_status_bytes <= %s
                          AND max_field_reconciliation_smeta_type_bytes <= %s
                          AND max_field_reconciliation_work_package_bytes <= %s
                          AND max_field_base_smeta_type_bytes <= %s
                          AND max_field_base_work_package_bytes <= %s
                          AND max_field_next_status_bytes <= %s
                          AND max_field_next_smeta_type_bytes <= %s
                          AND max_field_next_work_package_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.reconciliation_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_reconciliation_status ELSE NULL
                      END AS reconciliation_status,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_reconciliation_smeta_type
                           ELSE NULL END AS reconciliation_smeta_type,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_reconciliation_work_package
                           ELSE NULL END AS reconciliation_work_package,
                      decided.base_estimate_id,decided.next_estimate_id,
                      decided.project_id,decided.project_company_id,
                      decided.base_company_id,decided.base_project_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_base_smeta_type ELSE NULL
                      END AS base_smeta_type,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_base_work_package ELSE NULL
                      END AS base_work_package,
                      decided.next_company_id,decided.next_project_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_next_status ELSE NULL
                      END AS next_status,
                      decided.next_is_template,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_next_smeta_type ELSE NULL
                      END AS next_smeta_type,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_next_work_package ELSE NULL
                      END AS next_work_package,
                      decided.field_reconciliation_status_bytes,
                      decided.field_reconciliation_smeta_type_bytes,
                      decided.field_reconciliation_work_package_bytes,
                      decided.field_base_smeta_type_bytes,
                      decided.field_base_work_package_bytes,
                      decided.field_next_status_bytes,
                      decided.field_next_smeta_type_bytes,
                      decided.field_next_work_package_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.reconciliation_id DESC""",
        (
            source.estimate_id,
            source.estimate_id,
            source.company_id,
            source.project_id,
            max_reconciliation_rows + 1,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            max_reconciliation_rows,
            max_reconciliation_rows,
            max_reconciliation_rows,
        ),
    )
    reconciliations = [dict(row or {}) for row in (cur.fetchall() or [])]
    report["summary"]["reconciliationRows"] = len(reconciliations)
    reconciliation_state, reconciliations, overflow_fields = (
        _accept_bounded_rows(
            reconciliations,
            variable_budget,
            scan_limit=max_reconciliation_rows,
            field_specs=_RECONCILIATION_FIELD_SPECS,
        )
    )
    if len(reconciliations) > max_reconciliation_rows:
        return _fail(
            report,
            source,
            "impact_reconciliation_scan_limit_exceeded",
            max_issues=max_issues,
            scan_complete=False,
        )
    if not reconciliations:
        return _fail(
            report,
            source,
            "impact_reconciliation_not_found",
            max_issues=max_issues,
        )
    if len(reconciliations) != 1:
        return _fail(
            report,
            source,
            "impact_reconciliation_ambiguous",
            max_issues=max_issues,
        )
    if reconciliation_state == _BOUNDED_OVERFLOW:
        fixed_reconciliation_reason = _reconciliation_reason(
            reconciliations[0],
            source,
        )
        if fixed_reconciliation_reason in {
            "impact_reconciliation_id_invalid",
            "impact_reconciliation_estimate_pair_invalid",
            "impact_reconciliation_owner_mismatch",
        }:
            return _fail(
                report,
                source,
                fixed_reconciliation_reason,
                max_issues=max_issues,
            )
        overflow_fields = set(overflow_fields)
        if overflow_fields.intersection({
            "reconciliation_smeta_type",
            "base_smeta_type",
            "next_smeta_type",
        }):
            overflow_reason = "impact_reconciliation_not_customer"
        elif overflow_fields.intersection({
            "reconciliation_work_package",
            "base_work_package",
            "next_work_package",
        }):
            overflow_reason = "impact_reconciliation_package_mismatch"
        elif "next_status" in overflow_fields:
            overflow_reason = "impact_reconciliation_next_not_active"
        elif "reconciliation_status" in overflow_fields:
            overflow_reason = "impact_reconciliation_status_invalid"
        else:
            raise _VariableByteLimitError(
                "variable byte metadata is invalid"
            )
        return _fail(
            report,
            source,
            overflow_reason,
            max_issues=max_issues,
        )
    reconciliation = reconciliations[0]
    reconciliation_reason = _reconciliation_reason(reconciliation, source)
    if reconciliation_reason:
        return _fail(
            report,
            source,
            reconciliation_reason,
            max_issues=max_issues,
        )

    report["source"].update({
        "reconciliationId": reconciliation["reconciliation_id"],
        "baseEstimateId": reconciliation["base_estimate_id"],
        "reconciliationStatus": _text(
            reconciliation.get("reconciliation_status")
        ),
    })
    report["sourceReady"] = True
    report["readyForDomainScan"] = True
    return report


def collect_baseline_audit(
    cur,
    source,
    *,
    max_reconciliation_rows=MAX_RECONCILIATION_ROWS,
    max_issues=DEFAULT_MAX_ISSUES,
):
    """Collect one exact source boundary with a fresh private byte budget."""

    return _collect_baseline_audit(
        cur,
        source,
        _VariableByteBudget(),
        max_reconciliation_rows=max_reconciliation_rows,
        max_issues=max_issues,
    )


def run_baseline_audit(
    get_db,
    source,
    *,
    collect_data=collect_baseline_audit,
):
    source = _validated_source(source)
    conn = get_db()
    cur = None
    try:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        report = collect_data(cur, source)
        conn.rollback()
        report["readOnlyTransaction"] = True
        report["rolledBack"] = True
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None and hasattr(cur, "close"):
            cur.close()
        conn.close()


def _source_from_args(args):
    return validate_estimate_revision_source({
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": args.company_id,
        "projectId": args.project_id,
        "estimateId": args.estimate_id,
        "sourceRevision": args.source_revision,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only exact estimate revision impact baseline audit",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    try:
        source = _source_from_args(args)
    except EstimateRevisionImpactContractError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_baseline_audit(get_db, source)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("readyForDomainScan") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_MAX_ISSUES",
    "MAX_RECONCILIATION_ROWS",
    "REQUIRED_COLUMNS",
    "collect_baseline_audit",
    "run_baseline_audit",
]
