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


def collect_baseline_audit(
    cur,
    source,
    *,
    max_reconciliation_rows=MAX_RECONCILIATION_ROWS,
    max_issues=DEFAULT_MAX_ISSUES,
):
    """Collect one exact source boundary with hard limits and no mutations."""

    source = _validated_source(source)
    report = _base_report(source)
    max_reconciliation_rows = max(0, min(
        MAX_RECONCILIATION_ROWS,
        int(max_reconciliation_rows),
    ))

    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(REQUIRED_COLUMNS),),
    )
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in (cur.fetchall() or [])
    }
    missing = sorted(
        table + "." + column
        for table, columns in REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )
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
        """SELECT id AS estimate_id,company_id,project_id,version,
                  CASE
                    WHEN octet_length(COALESCE(sections_json::text,'')) <= %s
                    THEN sections_json
                    ELSE NULL
                  END AS sections_json,
                  octet_length(COALESCE(sections_json::text,''))
                      AS sections_bytes,
                  COALESCE(status,'Черновик') AS status,
                  COALESCE(is_template,FALSE) AS is_template,
                  COALESCE(smeta_type,'Заказчик') AS smeta_type,
                  work_package
             FROM public.estimates
            WHERE id=%s AND company_id=%s AND project_id=%s
            ORDER BY id
            LIMIT %s""",
        (
            MAX_CANONICAL_SOURCE_BYTES,
            source.estimate_id,
            source.company_id,
            source.project_id,
            2,
        ),
    )
    estimates = [dict(row or {}) for row in (cur.fetchall() or [])]
    report["summary"]["estimateRows"] = len(estimates)
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
    estimate_reason = _estimate_reason(estimates[0], source)
    if estimate_reason:
        return _fail(
            report,
            source,
            estimate_reason,
            max_issues=max_issues,
        )

    cur.execute(
        """SELECT r.id AS reconciliation_id,
                  r.status AS reconciliation_status,
                  COALESCE(r.smeta_type,'Заказчик')
                      AS reconciliation_smeta_type,
                  r.work_package AS reconciliation_work_package,
                  r.base_estimate_id,r.next_estimate_id,
                  p.id AS project_id,p.company_id AS project_company_id,
                  b.company_id AS base_company_id,
                  b.project_id AS base_project_id,
                  COALESCE(b.smeta_type,'Заказчик') AS base_smeta_type,
                  b.work_package AS base_work_package,
                  n.company_id AS next_company_id,
                  n.project_id AS next_project_id,
                  COALESCE(n.status,'Черновик') AS next_status,
                  COALESCE(n.is_template,FALSE) AS next_is_template,
                  COALESCE(n.smeta_type,'Заказчик') AS next_smeta_type,
                  n.work_package AS next_work_package
             FROM public.estimate_reconciliations r
             LEFT JOIN public.estimates b ON b.id=r.base_estimate_id
             LEFT JOIN public.estimates n ON n.id=r.next_estimate_id
             LEFT JOIN public.projects p ON p.id=n.project_id
            WHERE r.next_estimate_id=%s
              AND n.id=%s AND n.company_id=%s AND n.project_id=%s
            ORDER BY r.id DESC
            LIMIT %s""",
        (
            source.estimate_id,
            source.estimate_id,
            source.company_id,
            source.project_id,
            max_reconciliation_rows + 1,
        ),
    )
    reconciliations = [dict(row or {}) for row in (cur.fetchall() or [])]
    report["summary"]["reconciliationRows"] = len(reconciliations)
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
