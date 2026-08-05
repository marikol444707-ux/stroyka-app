"""One-company schedule adapter for the controlled director daily brief cycle."""

import argparse
import json
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from backend.features.director_daily_brief.controlled_cycle import (
    DirectorDailyBriefCycleError,
    run_director_daily_brief_cycle,
)
from backend.features.director_daily_brief.producer import (
    JOB_TYPE,
    DirectorDailyBriefProducerError,
)


MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")
SAFE_STATUS_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class DirectorDailyBriefScheduleError(ValueError):
    pass


def _positive_int(value, field):
    if isinstance(value, bool):
        raise DirectorDailyBriefScheduleError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise DirectorDailyBriefScheduleError(
            f"{field} must be a positive integer"
        ) from exc
    if normalized <= 0:
        raise DirectorDailyBriefScheduleError(f"{field} must be a positive integer")
    return normalized


def _bounded_write_count(value, field):
    if type(value) is not int or value < 0 or value > 1:
        raise DirectorDailyBriefScheduleError(f"{field} is invalid")
    return value


def _safe_status(value, field):
    normalized = str(value or "").strip()
    if not SAFE_STATUS_RE.fullmatch(normalized):
        raise DirectorDailyBriefScheduleError(f"{field} is invalid")
    return normalized


def _utc_now():
    return datetime.now(timezone.utc)


def resolve_moscow_brief_date(*, now_provider=_utc_now):
    if not callable(now_provider):
        raise DirectorDailyBriefScheduleError("clock dependency is invalid")
    now = now_provider()
    if not isinstance(now, datetime):
        raise DirectorDailyBriefScheduleError("clock value is invalid")
    if now.tzinfo is None or now.utcoffset() is None:
        raise DirectorDailyBriefScheduleError("clock value must include a timezone")
    return now.astimezone(MOSCOW_TIMEZONE).date().isoformat()


def _normalize_runner_report(value):
    if not isinstance(value, Mapping):
        raise DirectorDailyBriefScheduleError("runner result is invalid")
    attempted = value.get("attempted")
    if type(attempted) is not bool:
        raise DirectorDailyBriefScheduleError("runner attempted state is invalid")
    result = {"attempted": attempted}
    if not attempted:
        return result

    processed = value.get("processed")
    if type(processed) is not bool:
        raise DirectorDailyBriefScheduleError("runner processed state is invalid")
    result.update({
        "processed": processed,
        "status": _safe_status(value.get("status"), "runner status"),
    })
    return result


def _normalize_cycle_report(report, *, company_id, brief_date, apply):
    if not isinstance(report, Mapping) or type(report.get("ok")) is not bool:
        raise DirectorDailyBriefScheduleError("controlled cycle result is invalid")
    if report.get("dryRun") is not (not apply):
        raise DirectorDailyBriefScheduleError("controlled cycle dry-run state is invalid")
    if _positive_int(report.get("companyId"), "cycle company_id") != company_id:
        raise DirectorDailyBriefScheduleError("controlled cycle company does not match")
    if str(report.get("briefDate") or "") != brief_date:
        raise DirectorDailyBriefScheduleError("controlled cycle date does not match")
    if report.get("jobType") != JOB_TYPE:
        raise DirectorDailyBriefScheduleError("controlled cycle job type does not match")
    business_writes = _bounded_write_count(
        report.get("businessWritesAttempted"),
        "business write count",
    )
    if business_writes != 0:
        raise DirectorDailyBriefScheduleError("business write boundary was violated")

    normalized = {
        "ok": report["ok"],
        "dryRun": not apply,
        "businessWritesAttempted": 0,
        "producerWritesAttempted": _bounded_write_count(
            report.get("producerWritesAttempted"),
            "producer write count",
        ),
        "companyId": company_id,
        "briefDate": brief_date,
        "jobType": JOB_TYPE,
        "producerState": _safe_status(
            report.get("producerState"),
            "producer state",
        ),
        "state": _safe_status(report.get("state"), "cycle state"),
        "runner": _normalize_runner_report(report.get("runner")),
    }
    if report.get("jobId") is not None:
        normalized["jobId"] = _positive_int(report.get("jobId"), "job_id")
    if report.get("jobStatus") is not None:
        normalized["jobStatus"] = _safe_status(
            report.get("jobStatus"),
            "job status",
        )
    return normalized


def run_scheduled_director_daily_brief(
    *,
    company_id,
    apply=False,
    now_provider=_utc_now,
    run_cycle=run_director_daily_brief_cycle,
):
    """Plan or run one brief for the current Moscow business date."""
    company_id = _positive_int(company_id, "company_id")
    if type(apply) is not bool:
        raise DirectorDailyBriefScheduleError("apply must be boolean")
    if not callable(run_cycle):
        raise DirectorDailyBriefScheduleError("controlled cycle dependency is invalid")

    brief_date = resolve_moscow_brief_date(now_provider=now_provider)
    report = run_cycle(
        company_id=company_id,
        brief_date=brief_date,
        apply=apply,
    )
    return _normalize_cycle_report(
        report,
        company_id=company_id,
        brief_date=brief_date,
        apply=apply,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Plan or run one deterministic director daily brief for today's "
            "Europe/Moscow date."
        ),
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run the controlled one-job cycle. Without this flag it is read-only.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        report = run_scheduled_director_daily_brief(
            company_id=args.company_id,
            apply=args.apply,
        )
    except (
        DirectorDailyBriefScheduleError,
        DirectorDailyBriefCycleError,
        DirectorDailyBriefProducerError,
    ) as exc:
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
