"""Separate single-job runner for the durable agent queue.

This module is intentionally independent from the FastAPI application. It
keeps every database operation short and never gives a handler a connection,
cursor, worker identity or lease token.
"""

import argparse
import json
import os
import re
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from psycopg2.extras import RealDictCursor

from backend.db import get_db
from backend.features.agent_jobs.handler_registry import (
    AgentJobContext,
    build_default_handler_registry,
)
from backend.features.agent_jobs.worker import (
    AgentJobWorkerError,
    WORKER_ID_RE,
    claim_next_agent_job,
    complete_agent_job,
    fail_agent_job,
    heartbeat_agent_job,
    recover_expired_agent_jobs,
)


_EVENT_FIELD_NAMES = {
    "allowed_job_types": "allowedJobTypes",
    "attempt": "attempt",
    "company_id": "companyId",
    "duration_ms": "durationMs",
    "error_type": "errorType",
    "job_id": "jobId",
    "job_type": "jobType",
    "max_attempts": "maxAttempts",
    "processed": "processed",
    "project_id": "projectId",
    "recovered_count": "recoveredCount",
    "status": "status",
    "worker_id": "workerId",
}


def emit_json_event(event, *, stream=None, **fields):
    """Write one allowlisted metadata-only JSON event."""
    output = stream or sys.stdout
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": str(event or "runner_event")[:80],
    }
    for source_name, target_name in _EVENT_FIELD_NAMES.items():
        value = fields.get(source_name)
        if value is not None:
            record[target_name] = value
    output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    output.flush()


def _bounded_int(value, field, minimum, maximum):
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobWorkerError(f"{field} must be an integer") from exc
    if not minimum <= normalized <= maximum:
        raise AgentJobWorkerError(f"{field} must be between {minimum} and {maximum}")
    return normalized


def _bounded_float(value, field, minimum, maximum):
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobWorkerError(f"{field} must be a number") from exc
    if not minimum <= normalized <= maximum:
        raise AgentJobWorkerError(f"{field} must be between {minimum} and {maximum}")
    return normalized


def build_worker_id(*, hostname=None, process_id=None):
    hostname = str(hostname or socket.gethostname() or "host").strip().lower()
    hostname = re.sub(r"[^a-z0-9_.-]+", "-", hostname).strip("-.") or "host"
    process_id = int(process_id if process_id is not None else os.getpid())
    normalized = f"agent-worker:{hostname[:80]}:{process_id}"
    if len(normalized) > 120:
        normalized = normalized[:120]
    if not WORKER_ID_RE.fullmatch(normalized):
        raise AgentJobWorkerError("worker_id has invalid format")
    return normalized


@dataclass(frozen=True)
class AgentJobRunnerConfig:
    worker_id: str
    lease_seconds: int = 120
    heartbeat_interval_seconds: int = 30
    poll_interval_seconds: float = 2.0
    retry_delay_seconds: int = 60
    recovery_interval_seconds: int = 60
    recovery_limit: int = 100

    def __post_init__(self):
        worker_id = str(self.worker_id or "").strip()
        if not WORKER_ID_RE.fullmatch(worker_id):
            raise AgentJobWorkerError("worker_id has invalid format")
        lease_seconds = _bounded_int(self.lease_seconds, "lease_seconds", 15, 3600)
        heartbeat_seconds = _bounded_int(
            self.heartbeat_interval_seconds,
            "heartbeat_interval_seconds",
            1,
            1800,
        )
        if heartbeat_seconds >= lease_seconds:
            raise AgentJobWorkerError("heartbeat interval must be shorter than the lease")
        poll_seconds = _bounded_float(
            self.poll_interval_seconds,
            "poll_interval_seconds",
            0.05,
            300,
        )
        retry_seconds = _bounded_int(
            self.retry_delay_seconds,
            "retry_delay_seconds",
            1,
            86400,
        )
        recovery_seconds = _bounded_int(
            self.recovery_interval_seconds,
            "recovery_interval_seconds",
            5,
            3600,
        )
        recovery_limit = _bounded_int(self.recovery_limit, "recovery_limit", 1, 500)
        object.__setattr__(self, "worker_id", worker_id)
        object.__setattr__(self, "lease_seconds", lease_seconds)
        object.__setattr__(self, "heartbeat_interval_seconds", heartbeat_seconds)
        object.__setattr__(self, "poll_interval_seconds", poll_seconds)
        object.__setattr__(self, "retry_delay_seconds", retry_seconds)
        object.__setattr__(self, "recovery_interval_seconds", recovery_seconds)
        object.__setattr__(self, "recovery_limit", recovery_limit)


@dataclass(frozen=True)
class AgentJobRunOutcome:
    processed: bool
    status: str
    job_id: Optional[int] = None


def _run_transaction(connection_factory, operation):
    connection = connection_factory()
    try:
        connection.autocommit = False
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            result = operation(cur)
        connection.commit()
        return result
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


class LeaseHeartbeat:
    def __init__(
        self,
        *,
        connection_factory,
        job_id,
        worker_id,
        lease_token,
        lease_seconds,
        interval_seconds,
        emit_event,
    ):
        self.connection_factory = connection_factory
        self.job_id = job_id
        self.worker_id = worker_id
        self.lease_token = lease_token
        self.lease_seconds = lease_seconds
        self.interval_seconds = interval_seconds
        self.emit_event = emit_event
        self._stop_event = threading.Event()
        self._lost_lease = threading.Event()
        self._thread = None

    @property
    def lost_lease(self):
        return self._lost_lease.is_set()

    def beat_once(self):
        try:
            updated = _run_transaction(
                self.connection_factory,
                lambda cur: heartbeat_agent_job(
                    cur,
                    job_id=self.job_id,
                    worker_id=self.worker_id,
                    lease_token=self.lease_token,
                    lease_seconds=self.lease_seconds,
                ),
            )
        except Exception as exc:
            self.emit_event(
                "job_heartbeat_error",
                job_id=self.job_id,
                error_type=type(exc).__name__,
            )
            return None
        if updated is None:
            self._lost_lease.set()
            self.emit_event("job_heartbeat_lease_lost", job_id=self.job_id)
            return False
        return True

    def _run(self):
        while not self._stop_event.wait(self.interval_seconds):
            if self.beat_once() is False:
                return

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name=f"agent-heartbeat-{self.job_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=max(1, min(self.interval_seconds, 5)))


class AgentJobRunner:
    def __init__(
        self,
        *,
        registry,
        connection_factory=get_db,
        config,
        emit_event=emit_json_event,
        heartbeat_factory=LeaseHeartbeat,
        monotonic=time.monotonic,
    ):
        if not registry.job_types:
            raise AgentJobWorkerError("handler registry must not be empty")
        self.registry = registry
        self.connection_factory = connection_factory
        self.config = config
        self.emit_event = emit_event
        self.heartbeat_factory = heartbeat_factory
        self.monotonic = monotonic

    def _job_event(self, event, job, **fields):
        self.emit_event(
            event,
            job_id=job.get("id"),
            company_id=job.get("company_id"),
            project_id=job.get("project_id"),
            job_type=job.get("job_type"),
            attempt=job.get("attempts"),
            max_attempts=job.get("max_attempts"),
            **fields,
        )

    def _claim_once(self):
        return _run_transaction(
            self.connection_factory,
            lambda cur: claim_next_agent_job(
                cur,
                worker_id=self.config.worker_id,
                allowed_job_types=self.registry.job_types,
                lease_seconds=self.config.lease_seconds,
            ),
        )

    def _fail_claimed_job(self, job, error, started_at):
        failed = _run_transaction(
            self.connection_factory,
            lambda cur: fail_agent_job(
                cur,
                job_id=job["id"],
                worker_id=self.config.worker_id,
                lease_token=job["lease_token"],
                error=f"runner handler error: {type(error).__name__}",
                retry_delay_seconds=self.config.retry_delay_seconds,
            ),
        )
        duration_ms = int((self.monotonic() - started_at) * 1000)
        if failed is None:
            self._job_event("job_lease_lost", job, duration_ms=duration_ms)
            return AgentJobRunOutcome(True, "lease_lost", job["id"])
        status = str(failed.get("status") or "failed")
        self._job_event(
            "job_failed",
            job,
            status=status,
            duration_ms=duration_ms,
            error_type=type(error).__name__,
        )
        return AgentJobRunOutcome(True, status, job["id"])

    def run_once(self):
        job = self._claim_once()
        if job is None:
            return AgentJobRunOutcome(False, "idle")
        started_at = self.monotonic()
        self._job_event("job_claimed", job, status="running")
        handler = self.registry.get(job.get("job_type"))
        if handler is None:
            return self._fail_claimed_job(
                job,
                AgentJobWorkerError("claimed job has no registered handler"),
                started_at,
            )
        try:
            context = AgentJobContext.from_claimed_row(job)
        except Exception as exc:
            return self._fail_claimed_job(job, exc, started_at)

        heartbeat = self.heartbeat_factory(
            connection_factory=self.connection_factory,
            job_id=job["id"],
            worker_id=self.config.worker_id,
            lease_token=job["lease_token"],
            lease_seconds=self.config.lease_seconds,
            interval_seconds=self.config.heartbeat_interval_seconds,
            emit_event=self.emit_event,
        )
        heartbeat.start()
        try:
            result = handler(context)
        except Exception as exc:
            heartbeat.stop()
            return self._fail_claimed_job(job, exc, started_at)
        heartbeat.stop()
        if getattr(heartbeat, "lost_lease", False):
            self._job_event(
                "job_lease_lost",
                job,
                duration_ms=int((self.monotonic() - started_at) * 1000),
            )
            return AgentJobRunOutcome(True, "lease_lost", job["id"])
        try:
            completed = _run_transaction(
                self.connection_factory,
                lambda cur: complete_agent_job(
                    cur,
                    job_id=job["id"],
                    worker_id=self.config.worker_id,
                    lease_token=job["lease_token"],
                    result=result,
                ),
            )
        except AgentJobWorkerError as exc:
            return self._fail_claimed_job(job, exc, started_at)
        duration_ms = int((self.monotonic() - started_at) * 1000)
        if completed is None:
            self._job_event("job_lease_lost", job, duration_ms=duration_ms)
            return AgentJobRunOutcome(True, "lease_lost", job["id"])
        self._job_event(
            "job_succeeded",
            job,
            status="succeeded",
            duration_ms=duration_ms,
        )
        return AgentJobRunOutcome(True, "succeeded", job["id"])

    def recover_once(self):
        recovered = _run_transaction(
            self.connection_factory,
            lambda cur: recover_expired_agent_jobs(
                cur,
                allowed_job_types=self.registry.job_types,
                retry_delay_seconds=self.config.retry_delay_seconds,
                recovery_limit=self.config.recovery_limit,
            ),
        )
        if recovered:
            self.emit_event(
                "jobs_recovered",
                recovered_count=len(recovered),
                worker_id=self.config.worker_id,
            )
        return len(recovered)

    def run_forever(self, *, stop_event=None):
        stop_event = stop_event or threading.Event()
        next_recovery = self.monotonic()
        while not stop_event.is_set():
            now = self.monotonic()
            if now >= next_recovery:
                try:
                    self.recover_once()
                except Exception as exc:
                    self.emit_event("runner_recovery_error", error_type=type(exc).__name__)
                next_recovery = now + self.config.recovery_interval_seconds
            try:
                outcome = self.run_once()
            except Exception as exc:
                self.emit_event("runner_cycle_error", error_type=type(exc).__name__)
                outcome = AgentJobRunOutcome(False, "error")
            if not outcome.processed:
                stop_event.wait(self.config.poll_interval_seconds)


def _environment_number(name, default, caster):
    value = os.getenv(name)
    return caster(value) if value not in (None, "") else default


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Run the separate agent job worker")
    parser.add_argument("--once", action="store_true", help="recover and process at most one job")
    parser.add_argument("--worker-id", default=os.getenv("AGENT_JOB_WORKER_ID") or build_worker_id())
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    config = AgentJobRunnerConfig(
        worker_id=args.worker_id,
        lease_seconds=_environment_number("AGENT_JOB_LEASE_SECONDS", 120, int),
        heartbeat_interval_seconds=_environment_number(
            "AGENT_JOB_HEARTBEAT_SECONDS",
            30,
            int,
        ),
        poll_interval_seconds=_environment_number("AGENT_JOB_POLL_SECONDS", 2.0, float),
        retry_delay_seconds=_environment_number("AGENT_JOB_RETRY_SECONDS", 60, int),
        recovery_interval_seconds=_environment_number(
            "AGENT_JOB_RECOVERY_SECONDS",
            60,
            int,
        ),
        recovery_limit=_environment_number("AGENT_JOB_RECOVERY_LIMIT", 100, int),
    )
    registry = build_default_handler_registry()
    runner = AgentJobRunner(registry=registry, config=config)
    stop_event = threading.Event()

    def request_stop(signum, frame):
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    emit_json_event(
        "runner_started",
        worker_id=config.worker_id,
        allowed_job_types=registry.job_types,
    )
    if args.once:
        try:
            runner.recover_once()
            outcome = runner.run_once()
        except Exception as exc:
            emit_json_event("runner_cycle_error", error_type=type(exc).__name__)
            emit_json_event(
                "runner_stopped",
                worker_id=config.worker_id,
                processed=False,
                status="error",
            )
            return 1
        emit_json_event(
            "runner_stopped",
            worker_id=config.worker_id,
            processed=outcome.processed,
            status=outcome.status,
        )
        return 0
    runner.run_forever(stop_event=stop_event)
    emit_json_event("runner_stopped", worker_id=config.worker_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
