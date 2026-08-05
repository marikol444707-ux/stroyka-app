from collections.abc import Mapping


CANCELLATION_REASONS = {
    "user_request": "отменено руководителем",
    "duplicate": "дубликат задачи",
    "superseded": "заменено новой задачей",
    "invalid_input": "ошибочные исходные данные",
    "no_longer_needed": "задача больше не требуется",
}


class AgentJobCancellationError(ValueError):
    pass


def _positive_int(value, field):
    if isinstance(value, bool):
        raise AgentJobCancellationError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobCancellationError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise AgentJobCancellationError(f"{field} must be a positive integer")
    return normalized


def _reason_code(value):
    normalized = str(value or "user_request").strip().lower()
    if normalized not in CANCELLATION_REASONS:
        raise AgentJobCancellationError("reasonCode is not supported")
    return normalized


def cancellation_reason_label(reason_code):
    return CANCELLATION_REASONS[_reason_code(reason_code)]


def _row(row):
    return dict(row) if isinstance(row, Mapping) else row


def cancel_queued_agent_job(cur, *, company_id, job_id, reason_code="user_request"):
    company_id = _positive_int(company_id, "company_id")
    job_id = _positive_int(job_id, "job_id")
    reason_code = _reason_code(reason_code)

    cur.execute(
        """
        UPDATE agent_jobs
           SET status='cancelled',
               completed_at=NOW(),
               locked_by=NULL,
               locked_at=NULL,
               lease_token=NULL,
               lease_expires_at=NULL,
               heartbeat_at=NULL,
               updated_at=NOW()
         WHERE id=%s AND company_id=%s AND status='queued'
        RETURNING *
        """,
        (job_id, company_id),
    )
    cancelled = _row(cur.fetchone())
    if cancelled is not None:
        return {
            "state": "cancelled",
            "job": cancelled,
            "reasonCode": reason_code,
        }

    cur.execute(
        "SELECT status FROM agent_jobs WHERE id=%s AND company_id=%s",
        (job_id, company_id),
    )
    existing = _row(cur.fetchone())
    if existing is None:
        return {"state": "not_found", "reasonCode": reason_code}
    return {
        "state": "conflict",
        "currentStatus": str(existing.get("status") or ""),
        "reasonCode": reason_code,
    }
