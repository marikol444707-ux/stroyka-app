"""Exact read-only A7 queue and shadow-canary readiness report."""

import argparse
import json
import sys
from collections.abc import Mapping

from psycopg2.extras import RealDictCursor

from backend.features.agent_jobs.readiness_report import build_report as build_agent_job_report

from .combined_contract import DOMAIN_ORDER
from .combined_report import collect_combined_impact_audit
from .contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    EstimateRevisionSource,
    validate_estimate_revision_source,
)
from .cutover_inventory import audit_cutover_inventory
from .handler import (
    EstimateRevisionImpactHandlerError,
    validate_estimate_revision_impact_result,
)
from .job_contract import build_estimate_revision_impact_job_plan


LEDGER_LIMIT = 100
_STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
_LEASE_FIELDS = (
    "locked_at",
    "locked_by",
    "lease_token",
    "lease_expires_at",
    "heartbeat_at",
)


def _decoded_object(value):
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def _positive_int(value):
    return type(value) is int and value > 0


def _lease_ready(row, status):
    values = [row.get(field) for field in _LEASE_FIELDS]
    if status == "running":
        return all(value not in (None, "") for value in values)
    return all(value is None for value in values)


def _job_issue(row, plan, source):
    if not isinstance(row, Mapping) or not _positive_int(row.get("id")):
        return "exact_job_identity_invalid"
    if (
        row.get("owner_scope") != "company"
        or row.get("company_id") != plan.company_id
        or row.get("project_id") != plan.project_id
        or row.get("project_scope_id") != plan.project_id
        or row.get("requested_by_user_id") is not None
        or row.get("requested_by_role") != plan.requested_by_role
    ):
        return "exact_job_scope_invalid"
    if (
        row.get("job_type") != plan.job_type
        or row.get("idempotency_key") != plan.idempotency_key
        or row.get("correlation_id") != plan.correlation_id
        or row.get("priority") != plan.priority
        or row.get("max_attempts") != plan.max_attempts
    ):
        return "exact_job_contract_invalid"
    payload = _decoded_object(row.get("payload_json"))
    if payload != dict(plan.payload):
        return "exact_job_payload_invalid"
    status = row.get("status")
    attempts = row.get("attempts")
    if (
        status not in _STATUSES
        or type(attempts) is not int
        or attempts < 0
        or attempts > plan.max_attempts
        or (status in {"running", "succeeded", "failed"} and attempts < 1)
        or not _lease_ready(row, status)
    ):
        return "exact_job_state_invalid"
    if status in {"failed", "cancelled"}:
        return "exact_job_terminal_failure"
    result = _decoded_object(row.get("result_json"))
    if status == "succeeded":
        try:
            validate_estimate_revision_impact_result(result, source)
        except EstimateRevisionImpactHandlerError:
            return "exact_job_result_invalid"
    elif result != {}:
        return "exact_job_result_invalid"
    return None


def collect_exact_job_ledger(cur, source):
    """Inspect only the deterministic idempotency identity for one A7 source."""

    if not isinstance(source, EstimateRevisionSource):
        raise EstimateRevisionImpactContractError("source contract is invalid")
    plan = build_estimate_revision_impact_job_plan(source)
    cur.execute(
        """
        SELECT id,owner_scope,company_id,project_id,project_scope_id,
               requested_by_user_id,requested_by_role,job_type,idempotency_key,
               correlation_id,payload_json,result_json,status,priority,attempts,
               max_attempts,locked_at,locked_by,lease_token,lease_expires_at,
               heartbeat_at
          FROM agent_jobs
         WHERE job_type=%s AND idempotency_key=%s
         ORDER BY id
         LIMIT %s
        """,
        (plan.job_type, plan.idempotency_key, LEDGER_LIMIT + 1),
    )
    rows = list(cur.fetchall())
    truncated = len(rows) > LEDGER_LIMIT
    visible = rows[:LEDGER_LIMIT]
    issues = []
    if truncated:
        issues.append({"reasonCode": "exact_job_scan_limit_exceeded"})
    if len(rows) > 1:
        issues.append({"reasonCode": "exact_job_duplicate"})
    for row in visible:
        reason = _job_issue(row, plan, source)
        if reason is not None:
            issues.append({
                "reasonCode": reason,
                "jobId": row.get("id") if _positive_int(row.get("id")) else None,
            })
    state = "absent" if not rows else str(rows[0].get("status") or "invalid")
    if issues:
        state = "blocked"
    job_ids = sorted(
        row["id"] for row in visible if _positive_int(row.get("id"))
    )
    ready = not issues and len(rows) <= 1
    return {
        "ledgerReady": ready,
        "exactPlanRequested": True,
        "exactPlanReady": ready,
        "state": state,
        "jobCount": len(rows),
        "jobIds": job_ids,
        "jobsTruncated": truncated,
        "issueCount": len(issues),
        "issues": issues[:LEDGER_LIMIT],
        "issuesTruncated": len(issues) > LEDGER_LIMIT,
    }


def _inventory_ready(report):
    return bool(
        isinstance(report, Mapping)
        and report.get("ok") is True
        and report.get("dryRun") is True
        and report.get("writesAttempted") == 0
        and report.get("writerInventoryReady") is True
        and report.get("runtimeInventoryReady") is True
    )


def _agent_schema_ready(report):
    return bool(
        isinstance(report, Mapping)
        and report.get("ok") is True
        and report.get("dryRun") is True
        and report.get("writesAttempted") == 0
        and report.get("readyForWorker") is True
    )


def _combined_summary(report):
    domains = report.get("domains") or {}
    return {
        "combinedReportVersion": report["combinedReportVersion"],
        "complete": report["complete"],
        "actionable": report["actionable"],
        "reasonCounts": dict(report["reasonCounts"]),
        "evidenceSha256": report["evidenceSha256"],
        "domains": {
            name: {
                "state": domains[name]["state"],
                "complete": domains[name]["complete"],
            }
            for name in DOMAIN_ORDER
        },
    }


def _validated_source(source):
    if isinstance(source, EstimateRevisionSource):
        source = {
            "schemaVersion": source.schema_version,
            "eventType": source.event_type,
            "companyId": source.company_id,
            "projectId": source.project_id,
            "estimateId": source.estimate_id,
            "sourceRevision": source.source_revision,
        }
    return validate_estimate_revision_source(source)


def run_readiness_report(
    connection_factory,
    source,
    *,
    collect_combined=collect_combined_impact_audit,
    build_agent_schema=build_agent_job_report,
    audit_inventory=audit_cutover_inventory,
):
    """Run the exact shadow cutover gate and always roll its DB transaction back."""

    source = _validated_source(source)
    if not all(callable(value) for value in (
        connection_factory,
        collect_combined,
        build_agent_schema,
        audit_inventory,
    )):
        raise ValueError("readiness dependencies must be callable")

    inventory = audit_inventory()
    conn = connection_factory()
    cur = None
    try:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        combined = collect_combined(cur, source)
        agent_schema = build_agent_schema(cur)
        ledger = collect_exact_job_ledger(cur, source)
        conn.rollback()
    except BaseException:
        conn.rollback()
        raise
    finally:
        if cur is not None and hasattr(cur, "close"):
            cur.close()
        conn.close()

    combined_ready = True
    try:
        validated_combined = validate_estimate_revision_impact_result(
            {
                **combined,
                "readOnlyTransaction": True,
                "rolledBack": True,
            },
            source,
        )
        combined_audit = _combined_summary(validated_combined)
    except (EstimateRevisionImpactHandlerError, TypeError, ValueError):
        combined_ready = False
        combined_audit = {
            "combinedReportVersion": None,
            "complete": False,
            "actionable": False,
            "reasonCounts": {"combined_report_invalid": 1},
            "evidenceSha256": None,
            "domains": {},
        }

    inventory_ready = _inventory_ready(inventory)
    schema_ready = _agent_schema_ready(agent_schema)
    ledger_ready = bool(ledger.get("ledgerReady"))
    ready = combined_ready and inventory_ready and schema_ready and ledger_ready
    plan = build_estimate_revision_impact_job_plan(source)
    return {
        "ok": True,
        "dryRun": True,
        "readOnlyTransaction": True,
        "writesAttempted": 0,
        "source": dict(plan.payload),
        "combinedReportReady": combined_ready,
        "combinedAudit": combined_audit,
        "agentJobSchemaReady": schema_ready,
        "agentJobSchemaAudit": agent_schema,
        "ledgerReady": ledger_ready,
        "ledgerAudit": ledger,
        "writerInventoryReady": inventory_ready,
        "writerInventory": inventory,
        "readyForCanary": ready,
        "rolledBack": True,
    }


def build_parser():
    parser = argparse.ArgumentParser(
        description="Read-only exact estimate revision-impact canary readiness audit",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    return parser


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
    args = build_parser().parse_args(argv)
    try:
        source = _source_from_args(args)
        from backend.db import get_db
        report = run_readiness_report(get_db, source)
    except EstimateRevisionImpactContractError as exc:
        build_parser().error(str(exc))
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "dryRun": True,
            "errorType": type(exc).__name__,
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("readyForCanary") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "collect_exact_job_ledger",
    "run_readiness_report",
]
