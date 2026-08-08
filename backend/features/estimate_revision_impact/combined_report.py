"""Read-only collector and operator command for the combined A7.4 report."""

import argparse
import json

import psycopg2.extras

from .assignment_projection import collect_assignment_impact_audit
from .combined_contract import (
    COMBINED_REPORT_VERSION,
    DOMAIN_ORDER,
    build_combined_report,
    calculate_evidence_sha256,
)
from .contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    EstimateRevisionSource,
    validate_estimate_revision_source,
)
from .economics_projection import collect_economics_impact_audit
from .material_projection import collect_material_impact_audit
from .supply_warehouse_audit import collect_supply_warehouse_impact_audit


def _default_collectors(preview_builder):
    return {
        "assignment": collect_assignment_impact_audit,
        "material": collect_material_impact_audit,
        "supply_warehouse": collect_supply_warehouse_impact_audit,
        "economics": lambda cur, source: collect_economics_impact_audit(
            cur, source, preview_builder=preview_builder,
        ),
    }


def _expected_source_identity(source):
    return {
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
        "sourceRevision": source.source_revision,
    }


def collect_combined_impact_audit(
    cur,
    source,
    *,
    collectors=None,
    preview_builder=None,
):
    """Run all domain collectors on one caller-owned transaction cursor."""

    if collectors is None:
        if preview_builder is None:
            from backend.features.project_budget_adjustments.preview_service import (
                build_budget_adjustment_preview,
            )
            preview_builder = build_budget_adjustment_preview
        collectors = _default_collectors(preview_builder)
    if not isinstance(collectors, dict) or set(collectors) != {
        "assignment", "material", "supply_warehouse", "economics",
    }:
        raise ValueError("combined collectors do not match the contract")

    reports = {
        name: collectors[name](cur, source)
        for name in ("assignment", "material", "supply_warehouse", "economics")
    }
    reports = {
        name: report if isinstance(report, dict) else {}
        for name, report in reports.items()
    }
    source_context = reports["assignment"].get("source")
    expected = _expected_source_identity(source)
    source_mismatch = not isinstance(source_context, dict) or any(
        report.get("source") != source_context
        or any(
            (report.get("source") or {}).get(key) != value
            for key, value in expected.items()
        )
        for report in reports.values()
    )
    report = build_combined_report(
        source_context,
        assignment=reports["assignment"].get("assignmentImpact"),
        material=reports["material"].get("materialImpact"),
        supply_warehouse=reports["supply_warehouse"].get("supplyWarehouseImpact"),
        economics=reports["economics"].get("economicsImpact"),
    )
    if source_mismatch:
        report["complete"] = False
        report["actionable"] = False
        report["reasonCounts"] = {"combined_source_context_mismatch": 1}
        for domain in report["domains"].values():
            domain["complete"] = False
            domain["state"] = "incomplete"
        report["evidenceSha256"] = calculate_evidence_sha256(report)
    return report


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


def run_combined_impact_audit(
    get_db,
    source,
    *,
    collectors=None,
    preview_builder=None,
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
        report = collect_combined_impact_audit(
            cur,
            source,
            collectors=collectors,
            preview_builder=preview_builder,
        )
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
        description="Read-only combined exact estimate revision impact audit",
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
    report = run_combined_impact_audit(get_db, source)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMBINED_REPORT_VERSION",
    "DOMAIN_ORDER",
    "build_combined_report",
    "collect_combined_impact_audit",
    "run_combined_impact_audit",
]
