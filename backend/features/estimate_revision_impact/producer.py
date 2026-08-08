"""Explicit dry-run-first producer for one exact A7 revision-impact job."""

import argparse
import json
import sys
from collections.abc import Mapping

from psycopg2.extras import RealDictCursor

from backend.db import get_db
from backend.features.agent_jobs.service import enqueue_agent_job

from .baseline import collect_baseline_audit
from .contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    EstimateRevisionSource,
    validate_estimate_revision_source,
)
from .job_contract import (
    EstimateRevisionImpactJobContractError,
    build_estimate_revision_impact_job_plan,
    validate_estimate_revision_impact_job_plan,
)


_BASELINE_SOURCE_FIELDS = frozenset({
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
    "reconciliationId",
    "baseEstimateId",
    "reconciliationStatus",
})


class EstimateRevisionImpactProducerError(ValueError):
    pass


def _validated_plan(source):
    if not isinstance(source, EstimateRevisionSource):
        raise EstimateRevisionImpactProducerError(
            "source must be validated before queue planning"
        )
    try:
        return validate_estimate_revision_impact_job_plan(
            build_estimate_revision_impact_job_plan(source)
        )
    except (EstimateRevisionImpactContractError,
            EstimateRevisionImpactJobContractError) as exc:
        raise EstimateRevisionImpactProducerError(
            "source contract is invalid"
        ) from exc


def _validate_baseline(report, plan):
    if not isinstance(report, Mapping):
        raise EstimateRevisionImpactProducerError(
            "source baseline is invalid"
        )
    baseline_source = report.get("source")
    expected = dict(plan.payload)
    if (
        report.get("ok") is not True
        or report.get("dryRun") is not True
        or report.get("writesAttempted") != 0
        or report.get("sourceReady") is not True
        or report.get("readyForDomainScan") is not True
        or not isinstance(baseline_source, Mapping)
        or set(baseline_source) != _BASELINE_SOURCE_FIELDS
        or baseline_source.get("companyId") != expected["companyId"]
        or baseline_source.get("projectId") != expected["projectId"]
        or baseline_source.get("estimateId") != expected["estimateId"]
        or baseline_source.get("sourceRevision") != expected["sourceRevision"]
    ):
        raise EstimateRevisionImpactProducerError(
            "source is not ready for revision-impact queueing"
        )


def _positive_int(value, field):
    if isinstance(value, bool):
        raise EstimateRevisionImpactProducerError(
            f"{field} must be a positive integer"
        )
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise EstimateRevisionImpactProducerError(
            f"{field} must be a positive integer"
        ) from exc
    if normalized <= 0:
        raise EstimateRevisionImpactProducerError(
            f"{field} must be a positive integer"
        )
    return normalized


def _public_job_state(row, plan):
    if not isinstance(row, Mapping):
        raise EstimateRevisionImpactProducerError("agent job result is invalid")
    status = str(row.get("status") or "").strip()
    if (
        row.get("company_id") != plan.company_id
        or row.get("project_scope_id") != plan.project_id
        or row.get("job_type") != plan.job_type
        or row.get("idempotency_key") != plan.idempotency_key
        or not status
        or len(status) > 40
    ):
        raise EstimateRevisionImpactProducerError(
            "agent job result does not match the queue plan"
        )
    return {
        "jobId": _positive_int(row.get("id"), "job_id"),
        "status": status,
    }


def prepare_estimate_revision_impact_job(
    cur,
    source,
    *,
    apply=False,
    collect_baseline=collect_baseline_audit,
    enqueue_job=enqueue_agent_job,
):
    """Revalidate and plan or enqueue one exact idempotent A7 job."""

    plan = _validated_plan(source)
    if type(apply) is not bool:
        raise EstimateRevisionImpactProducerError("apply must be boolean")
    if not callable(collect_baseline) or not callable(enqueue_job):
        raise EstimateRevisionImpactProducerError(
            "producer dependencies must be callable"
        )

    baseline = collect_baseline(cur, source)
    _validate_baseline(baseline, plan)
    report = {
        "ok": True,
        "dryRun": not apply,
        "writesAttempted": 0,
        "state": "would_enqueue",
        "companyId": plan.company_id,
        "projectId": plan.project_id,
        "estimateId": source.estimate_id,
        "sourceRevision": source.source_revision,
        "jobType": plan.job_type,
        "idempotencyKey": plan.idempotency_key,
    }

    cur.execute(
        """SELECT id,status,company_id,project_scope_id,
                  job_type,idempotency_key
             FROM agent_jobs
            WHERE company_id=%s AND project_scope_id=%s
              AND job_type=%s AND idempotency_key=%s
            LIMIT 1""",
        (
            plan.company_id,
            plan.project_id,
            plan.job_type,
            plan.idempotency_key,
        ),
    )
    existing = cur.fetchone()
    if existing is not None:
        report.update({"state": "existing", **_public_job_state(existing, plan)})
        return report
    if not apply:
        return report

    report["writesAttempted"] = 1
    outcome = enqueue_job(
        cur,
        company_id=plan.company_id,
        project_id=plan.project_id,
        job_type=plan.job_type,
        idempotency_key=plan.idempotency_key,
        requested_by_role=plan.requested_by_role,
        payload=dict(plan.payload),
        correlation_id=plan.correlation_id,
        priority=plan.priority,
        max_attempts=plan.max_attempts,
    )
    if not isinstance(outcome, Mapping) or type(outcome.get("created")) is not bool:
        raise EstimateRevisionImpactProducerError("enqueue result is invalid")
    report.update({
        "state": "enqueued" if outcome["created"] else "existing",
        **_public_job_state(outcome.get("job"), plan),
    })
    return report


def run_estimate_revision_impact_producer(
    source,
    *,
    apply=False,
    connection_factory=get_db,
    collect_baseline=collect_baseline_audit,
    enqueue_job=enqueue_agent_job,
):
    """Run one bounded producer transaction; dry-run always rolls back."""

    if not callable(connection_factory):
        raise EstimateRevisionImpactProducerError(
            "connection_factory must be callable"
        )
    connection = connection_factory()
    try:
        connection.set_session(
            readonly=not apply,
            autocommit=False,
            isolation_level="SERIALIZABLE" if apply else "REPEATABLE READ",
        )
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            report = prepare_estimate_revision_impact_job(
                cur,
                source,
                apply=apply,
                collect_baseline=collect_baseline,
                enqueue_job=enqueue_job,
            )
        if apply:
            connection.commit()
        else:
            connection.rollback()
        return report
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Plan or enqueue one exact estimate revision-impact job.",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write one idempotent queued job. Without this flag the command is read-only.",
    )
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
        report = run_estimate_revision_impact_producer(
            source,
            apply=args.apply,
        )
    except (EstimateRevisionImpactContractError,
            EstimateRevisionImpactProducerError) as exc:
        report = {
            "ok": False,
            "dryRun": not args.apply,
            "errorType": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        report = {
            "ok": False,
            "dryRun": not args.apply,
            "errorType": type(exc).__name__,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EstimateRevisionImpactProducerError",
    "build_parser",
    "main",
    "prepare_estimate_revision_impact_job",
    "run_estimate_revision_impact_producer",
]
