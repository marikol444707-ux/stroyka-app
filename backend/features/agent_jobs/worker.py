"""Short transaction primitives for the future agent worker process.

The runner must commit a claim before external work and use a new short
transaction for every heartbeat, completion, failure or recovery batch.
"""

import re
import uuid
from collections.abc import Mapping

try:
    from backend.features.agent_jobs.service import (
        JOB_TYPE_RE,
        AgentJobValidationError,
        serialize_safe_json_object,
    )
except ModuleNotFoundError:
    from features.agent_jobs.service import (
        JOB_TYPE_RE,
        AgentJobValidationError,
        serialize_safe_json_object,
    )


WORKER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")
LEASE_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")
SENSITIVE_ERROR_VALUE_RE = re.compile(
    r'''(?ix)
    (?P<key>["']?(?:
        password|passwd|(?:access|refresh)[ _-]?token|token|secret|
        api[ _-]?key|private[ _-]?key|client[ _-]?secret|
        signing[ _-]?key|authorization|cookie
    )["']?)
    (?:\s*[:=]\s*|\s+)(?:bearer\s+)?
    (?:"[^"]*"|'[^']*'|[^\s,;\}\]]+)
    ''',
)
BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


class AgentJobWorkerError(ValueError):
    pass


def _positive_int(value, field):
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobWorkerError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise AgentJobWorkerError(f"{field} must be a positive integer")
    return normalized


def _bounded_int(value, field, minimum, maximum):
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobWorkerError(f"{field} must be an integer") from exc
    if not minimum <= normalized <= maximum:
        raise AgentJobWorkerError(f"{field} must be between {minimum} and {maximum}")
    return normalized


def _worker_id(value):
    normalized = str(value or "").strip()
    if not WORKER_ID_RE.fullmatch(normalized):
        raise AgentJobWorkerError("worker_id has invalid format")
    return normalized


def _job_id(value):
    return _positive_int(value, "job_id")


def _lease_token(value):
    normalized = str(value or "").strip().lower()
    if not LEASE_TOKEN_RE.fullmatch(normalized):
        raise AgentJobWorkerError("lease_token has invalid format")
    return normalized


def _lease_seconds(value):
    return _bounded_int(value, "lease_seconds", 15, 3600)


def _retry_delay_seconds(value):
    return _bounded_int(value, "retry_delay_seconds", 1, 86400)


def _allowed_job_types(values):
    if isinstance(values, str) or not values:
        raise AgentJobWorkerError("allowed_job_types must not be empty")
    normalized = []
    for value in values:
        job_type = str(value or "").strip()
        if not JOB_TYPE_RE.fullmatch(job_type):
            raise AgentJobWorkerError("allowed_job_types contains an invalid job type")
        if job_type not in normalized:
            normalized.append(job_type)
    if not normalized:
        raise AgentJobWorkerError("allowed_job_types must not be empty")
    return normalized


def _public_row(row):
    return dict(row) if isinstance(row, Mapping) else row


def _error_summary(value):
    normalized = " ".join(str(value or "worker error").split())
    normalized = SENSITIVE_ERROR_VALUE_RE.sub(
        lambda match: f"{match.group('key')}=[REDACTED]",
        normalized,
    )
    normalized = BEARER_TOKEN_RE.sub("Bearer [REDACTED]", normalized)
    return normalized[:1000]


def claim_next_agent_job(
    cur,
    *,
    worker_id,
    allowed_job_types,
    lease_seconds=120,
):
    worker_id = _worker_id(worker_id)
    allowed_job_types = _allowed_job_types(allowed_job_types)
    lease_seconds = _lease_seconds(lease_seconds)
    lease_token = uuid.uuid4().hex
    cur.execute(
        """
        WITH candidate AS (
            SELECT id
              FROM agent_jobs
             WHERE status='queued'
               AND run_after<=NOW()
               AND attempts < max_attempts
               AND job_type = ANY(%s::text[])
             ORDER BY priority DESC, run_after, id
             FOR UPDATE SKIP LOCKED
             LIMIT 1
        )
        UPDATE agent_jobs AS job
           SET status='running',
               attempts=job.attempts+1,
               locked_by=%s,
               locked_at=NOW(),
               heartbeat_at=NOW(),
               lease_token=%s,
               lease_expires_at=NOW() + (%s * INTERVAL '1 second'),
               started_at=COALESCE(job.started_at,NOW()),
               completed_at=NULL,
               last_error='',
               updated_at=NOW()
          FROM candidate
         WHERE job.id=candidate.id
        RETURNING job.*
        """,
        (allowed_job_types, worker_id, lease_token, lease_seconds),
    )
    return _public_row(cur.fetchone())


def heartbeat_agent_job(
    cur,
    *,
    job_id,
    worker_id,
    lease_token,
    lease_seconds=120,
):
    job_id = _job_id(job_id)
    worker_id = _worker_id(worker_id)
    lease_token = _lease_token(lease_token)
    lease_seconds = _lease_seconds(lease_seconds)
    cur.execute(
        """
        UPDATE agent_jobs
           SET heartbeat_at=NOW(),
               lease_expires_at=NOW() + (%s * INTERVAL '1 second'),
               updated_at=NOW()
         WHERE id=%s AND status='running' AND locked_by=%s AND lease_token=%s
           AND lease_expires_at>=NOW()
        RETURNING *
        """,
        (lease_seconds, job_id, worker_id, lease_token),
    )
    return _public_row(cur.fetchone())


def complete_agent_job(cur, *, job_id, worker_id, lease_token, result=None):
    job_id = _job_id(job_id)
    worker_id = _worker_id(worker_id)
    lease_token = _lease_token(lease_token)
    try:
        result_json = serialize_safe_json_object(result, field="result")
    except AgentJobValidationError as exc:
        raise AgentJobWorkerError(str(exc)) from exc
    cur.execute(
        """
        UPDATE agent_jobs
           SET status='succeeded',
               result_json=%s::jsonb,
               completed_at=NOW(),
               locked_by=NULL,
               locked_at=NULL,
               lease_token=NULL,
               lease_expires_at=NULL,
               heartbeat_at=NULL,
               last_error='',
               updated_at=NOW()
         WHERE id=%s AND status='running' AND locked_by=%s AND lease_token=%s
           AND lease_expires_at>=NOW()
        RETURNING *
        """,
        (result_json, job_id, worker_id, lease_token),
    )
    return _public_row(cur.fetchone())


def fail_agent_job(
    cur,
    *,
    job_id,
    worker_id,
    lease_token,
    error,
    retry_delay_seconds=60,
):
    job_id = _job_id(job_id)
    worker_id = _worker_id(worker_id)
    lease_token = _lease_token(lease_token)
    retry_delay_seconds = _retry_delay_seconds(retry_delay_seconds)
    cur.execute(
        """
        UPDATE agent_jobs
           SET status=CASE
                   WHEN attempts < max_attempts THEN 'queued'
                   ELSE 'failed'
               END,
               run_after=CASE
                   WHEN attempts < max_attempts
                   THEN NOW() + (
                       LEAST(86400, %s * (1 << GREATEST(attempts - 1, 0)))
                       * INTERVAL '1 second'
                   )
                   ELSE run_after
               END,
               completed_at=CASE
                   WHEN attempts < max_attempts THEN NULL
                   ELSE NOW()
               END,
               last_error=%s,
               locked_by=NULL,
               locked_at=NULL,
               lease_token=NULL,
               lease_expires_at=NULL,
               heartbeat_at=NULL,
               updated_at=NOW()
         WHERE id=%s AND status='running' AND locked_by=%s AND lease_token=%s
           AND lease_expires_at>=NOW()
        RETURNING *
        """,
        (
            retry_delay_seconds,
            _error_summary(error),
            job_id,
            worker_id,
            lease_token,
        ),
    )
    return _public_row(cur.fetchone())


def recover_expired_agent_jobs(
    cur,
    *,
    allowed_job_types,
    retry_delay_seconds=30,
    recovery_limit=100,
):
    allowed_job_types = _allowed_job_types(allowed_job_types)
    retry_delay_seconds = _retry_delay_seconds(retry_delay_seconds)
    recovery_limit = _bounded_int(recovery_limit, "recovery_limit", 1, 500)
    cur.execute(
        """
        WITH expired AS (
            SELECT id
              FROM agent_jobs
             WHERE status='running'
               AND lease_expires_at IS NOT NULL
               AND lease_expires_at < NOW()
               AND job_type = ANY(%s::text[])
             ORDER BY lease_expires_at, id
             FOR UPDATE SKIP LOCKED
             LIMIT %s
        )
        UPDATE agent_jobs AS job
           SET status=CASE
                   WHEN job.attempts < job.max_attempts THEN 'queued'
                   ELSE 'failed'
               END,
               run_after=CASE
                   WHEN job.attempts < job.max_attempts
                   THEN NOW() + (
                       LEAST(86400, %s * (1 << GREATEST(job.attempts - 1, 0)))
                       * INTERVAL '1 second'
                   )
                   ELSE job.run_after
               END,
               completed_at=CASE
                   WHEN job.attempts < job.max_attempts THEN NULL
                   ELSE NOW()
               END,
               last_error='worker lease expired',
               locked_by=NULL,
               locked_at=NULL,
               lease_token=NULL,
               lease_expires_at=NULL,
               heartbeat_at=NULL,
               updated_at=NOW()
          FROM expired
         WHERE job.id=expired.id
        RETURNING job.*
        """,
        (allowed_job_types, recovery_limit, retry_delay_seconds),
    )
    return [_public_row(row) for row in cur.fetchall()]
