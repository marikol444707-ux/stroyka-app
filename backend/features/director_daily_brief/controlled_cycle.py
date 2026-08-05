"""Controlled producer-to-runner cycle for one company and one brief date."""

import argparse
import json
import re
import sys
from collections.abc import Mapping

from backend.features.agent_jobs.handler_registry import AgentJobHandlerRegistry
from backend.features.agent_jobs.runner import (
    AgentJobRunOutcome,
    AgentJobRunner,
    build_runner_config_from_environment,
    emit_json_event,
)
from backend.features.director_daily_brief.producer import (
    JOB_TYPE,
    DirectorDailyBriefProducerError,
    run_director_daily_brief_producer,
)
from backend.features.director_daily_brief.handler import handle_director_daily_brief


SAFE_STATUS_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
PRODUCER_STATES = frozenset(("would_enqueue", "enqueued", "existing"))


class DirectorDailyBriefCycleError(ValueError):
    pass


def _positive_int(value, field):
    if isinstance(value, bool):
        raise DirectorDailyBriefCycleError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise DirectorDailyBriefCycleError(
            f"{field} must be a positive integer"
        ) from exc
    if normalized <= 0:
        raise DirectorDailyBriefCycleError(f"{field} must be a positive integer")
    return normalized


def _safe_status(value, field):
    normalized = str(value or "").strip()
    if not SAFE_STATUS_RE.fullmatch(normalized):
        raise DirectorDailyBriefCycleError(f"{field} is invalid")
    return normalized


def _normalize_producer_report(report, *, company_id, brief_date, apply):
    if not isinstance(report, Mapping) or report.get("ok") is not True:
        raise DirectorDailyBriefCycleError("producer result is invalid")
    if report.get("dryRun") is not (not apply):
        raise DirectorDailyBriefCycleError("producer dry-run state is invalid")
    if _positive_int(report.get("companyId"), "producer company_id") != company_id:
        raise DirectorDailyBriefCycleError("producer company does not match")
    if str(report.get("briefDate") or "") != brief_date:
        raise DirectorDailyBriefCycleError("producer brief date does not match")
    if report.get("jobType") != JOB_TYPE:
        raise DirectorDailyBriefCycleError("producer job type does not match")
    state = str(report.get("state") or "")
    if state not in PRODUCER_STATES:
        raise DirectorDailyBriefCycleError("producer state is invalid")
    try:
        writes_attempted = int(report.get("writesAttempted", -1))
    except (TypeError, ValueError) as exc:
        raise DirectorDailyBriefCycleError(
            "producer write count is invalid"
        ) from exc
    if writes_attempted < 0 or writes_attempted > 1:
        raise DirectorDailyBriefCycleError("producer write count is invalid")

    normalized = {
        "state": state,
        "writesAttempted": writes_attempted,
    }
    if report.get("jobId") is not None:
        normalized["jobId"] = _positive_int(report.get("jobId"), "job_id")
        normalized["status"] = _safe_status(report.get("status"), "job status")
    return normalized


def build_director_daily_brief_handler_registry():
    return AgentJobHandlerRegistry(((JOB_TYPE, handle_director_daily_brief),))


def run_exact_director_daily_brief_job(job_id):
    def emit_stderr(event, **fields):
        emit_json_event(event, stream=sys.stderr, **fields)

    runner = AgentJobRunner(
        registry=build_director_daily_brief_handler_registry(),
        config=build_runner_config_from_environment(),
        emit_event=emit_stderr,
    )
    return runner.run_once(job_id=job_id)


def run_director_daily_brief_cycle(
    *,
    company_id,
    brief_date,
    apply=False,
    producer=run_director_daily_brief_producer,
    run_exact_job=run_exact_director_daily_brief_job,
):
    """Plan or execute one recoverable exact-job daily brief cycle."""
    company_id = _positive_int(company_id, "company_id")
    brief_date = str(brief_date or "").strip()
    if type(apply) is not bool:
        raise DirectorDailyBriefCycleError("apply must be boolean")
    if not callable(producer) or not callable(run_exact_job):
        raise DirectorDailyBriefCycleError("cycle dependency is invalid")

    producer_report = producer(
        company_id=company_id,
        brief_date=brief_date,
        apply=apply,
    )
    prepared = _normalize_producer_report(
        producer_report,
        company_id=company_id,
        brief_date=brief_date,
        apply=apply,
    )
    report = {
        "ok": True,
        "dryRun": not apply,
        "businessWritesAttempted": 0,
        "producerWritesAttempted": prepared["writesAttempted"],
        "companyId": company_id,
        "briefDate": brief_date,
        "jobType": JOB_TYPE,
        "producerState": prepared["state"],
        "runner": {"attempted": False},
    }

    if not apply:
        report["state"] = "planned"
        if "jobId" in prepared:
            report.update({
                "jobId": prepared["jobId"],
                "jobStatus": prepared["status"],
            })
        return report

    if "jobId" not in prepared:
        raise DirectorDailyBriefCycleError("applied producer returned no job")
    job_id = prepared["jobId"]
    job_status = prepared["status"]
    report.update({"jobId": job_id, "jobStatus": job_status})

    if job_status == "succeeded":
        report["state"] = "already_succeeded"
        return report
    if job_status != "queued":
        report.update({"ok": False, "state": "not_runnable"})
        return report

    outcome = run_exact_job(job_id)
    if not isinstance(outcome, AgentJobRunOutcome):
        raise DirectorDailyBriefCycleError("runner result is invalid")
    if outcome.processed and outcome.job_id != job_id:
        raise DirectorDailyBriefCycleError("runner job does not match")
    if not outcome.processed and outcome.job_id not in (None, job_id):
        raise DirectorDailyBriefCycleError("runner job does not match")
    if not outcome.processed:
        report.update({
            "ok": False,
            "state": "not_claimed",
            "runner": {
                "attempted": True,
                "processed": False,
                "status": "not_claimed",
            },
        })
        return report

    runner_status = _safe_status(outcome.status, "runner status")
    report["runner"] = {
        "attempted": True,
        "processed": True,
        "status": runner_status,
    }
    report["jobStatus"] = runner_status
    if runner_status == "succeeded":
        report["state"] = "succeeded"
        return report
    report.update({"ok": False, "state": "runner_incomplete"})
    return report


def build_parser():
    parser = argparse.ArgumentParser(
        description="Plan or run one exact deterministic director daily brief.",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--brief-date", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Enqueue and run one exact job. Without this flag the command is read-only.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        report = run_director_daily_brief_cycle(
            company_id=args.company_id,
            brief_date=args.brief_date,
            apply=args.apply,
        )
    except (DirectorDailyBriefCycleError, DirectorDailyBriefProducerError) as exc:
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
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
