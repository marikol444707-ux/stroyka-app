"""Read-only operational report for the separate agent-job worker."""

import json

import psycopg2.extras

from backend.db import get_db
from backend.features.agent_jobs.handler_registry import (
    build_default_handler_registry,
)
from backend.features.agent_jobs.readiness_report import build_report as build_schema_report
from backend.features.agent_jobs.service import JOB_TYPE_RE


MODEL_FREE_JOB_TYPES = frozenset({
    "system.worker_probe",
    "director.daily_brief",
    "estimate.revision_impact",
})


def _count(row, name):
    return int((row or {}).get(name) or 0)


def _rounded_optional(row, name):
    value = (row or {}).get(name)
    return None if value is None else int(round(float(value)))


def _elapsed_seconds(row, name):
    value = (row or {}).get(name)
    return None if value is None else max(0, int(float(value)))


def _normalize_job_types(values):
    normalized = tuple(dict.fromkeys(str(value or "").strip() for value in values))
    if not normalized or any(not JOB_TYPE_RE.fullmatch(value) for value in normalized):
        raise ValueError("allowed_job_types must contain valid job types")
    return normalized


def build_operational_report(cur, *, allowed_job_types):
    """Return bounded queue health metadata without reading job contents."""
    allowed = _normalize_job_types(allowed_job_types)
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (
                   WHERE status='queued' AND run_after<=NOW()
               ) AS queued_due,
               COUNT(*) FILTER (
                   WHERE status='queued' AND run_after>NOW()
               ) AS queued_delayed,
               COUNT(*) FILTER (WHERE status='running') AS running,
               COUNT(*) FILTER (
                   WHERE status='running' AND lease_expires_at<NOW()
               ) AS expired_running,
               COUNT(*) FILTER (WHERE status='failed') AS failed,
               COUNT(*) FILTER (WHERE status='succeeded') AS succeeded,
               COUNT(*) FILTER (WHERE status='cancelled') AS cancelled,
               COUNT(*) FILTER (
                   WHERE status='queued'
                     AND run_after<=NOW()
                     AND NOT (job_type=ANY(%s))
               ) AS disallowed_due,
               EXTRACT(EPOCH FROM (
                   NOW()-MIN(run_after) FILTER (
                       WHERE status='queued' AND run_after<=NOW()
                   )
               )) AS oldest_due_age_seconds,
               COUNT(*) FILTER (
                   WHERE status='succeeded'
                     AND completed_at>=NOW()-INTERVAL '24 hours'
               ) AS recent_succeeded,
               COUNT(*) FILTER (
                   WHERE status='failed'
                     AND updated_at>=NOW()-INTERVAL '24 hours'
               ) AS recent_failed,
               PERCENTILE_CONT(0.95) WITHIN GROUP (
                   ORDER BY EXTRACT(EPOCH FROM (completed_at-started_at))*1000
               ) FILTER (
                   WHERE status='succeeded'
                     AND completed_at>=NOW()-INTERVAL '24 hours'
                     AND started_at IS NOT NULL
                     AND completed_at>=started_at
               ) AS recent_p95_duration_ms
          FROM agent_jobs
        """,
        (list(allowed),),
    )
    row = cur.fetchone() or {}
    untracked_types = sorted(set(allowed) - MODEL_FREE_JOB_TYPES)
    model_cost = {
        "state": "untracked" if untracked_types else "notApplicable",
        "rubles": None if untracked_types else 0,
        "untrackedJobTypes": untracked_types,
    }
    queue = {
        "total": _count(row, "total"),
        "due": _count(row, "queued_due"),
        "delayed": _count(row, "queued_delayed"),
        "running": _count(row, "running"),
        "expiredLeases": _count(row, "expired_running"),
        "failed": _count(row, "failed"),
        "succeeded": _count(row, "succeeded"),
        "cancelled": _count(row, "cancelled"),
        "disallowedDue": _count(row, "disallowed_due"),
        "oldestDueAgeSeconds": _elapsed_seconds(row, "oldest_due_age_seconds"),
    }
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "workerMode": "singleJob",
        "allowedJobTypes": list(allowed),
        "readyForWorker": (
            queue["expiredLeases"] == 0
            and queue["disallowedDue"] == 0
            and model_cost["state"] == "notApplicable"
        ),
        "queue": queue,
        "recent24h": {
            "succeeded": _count(row, "recent_succeeded"),
            "failed": _count(row, "recent_failed"),
            "p95DurationMs": _rounded_optional(row, "recent_p95_duration_ms"),
        },
        "modelCost": model_cost,
    }


def build_worker_report(cur, *, allowed_job_types):
    """Combine canonical schema readiness with current queue health."""
    schema = build_schema_report(cur)
    report = build_operational_report(cur, allowed_job_types=allowed_job_types)
    operationally_ready = report["readyForWorker"]
    schema_ready = bool(schema.get("readyForWorker"))
    report.update({
        "readyForWorker": schema_ready and operationally_ready,
        "schemaReady": schema_ready,
        "operationallyReady": operationally_ready,
        "schema": schema,
    })
    return report


def main():
    registry = build_default_handler_registry()
    connection = get_db()
    cursor = None
    try:
        connection.set_session(
            isolation_level="REPEATABLE READ",
            readonly=True,
            autocommit=False,
        )
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        report = build_worker_report(
            cursor,
            allowed_job_types=registry.job_types,
        )
        connection.rollback()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
