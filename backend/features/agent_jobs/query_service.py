from collections.abc import Mapping


AGENT_JOB_STATUSES = frozenset({
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
})
PUBLIC_JOB_COLUMNS = """
    id,company_id,project_id,requested_by_user_id,requested_by_role,
    job_type,correlation_id,status,priority,attempts,max_attempts,run_after,
    heartbeat_at,lease_expires_at,started_at,completed_at,last_error,
    created_at,updated_at
"""


class AgentJobQueryError(ValueError):
    pass


def _positive_int(value, field, *, optional=False):
    if optional and value in (None, ""):
        return None
    if isinstance(value, bool):
        raise AgentJobQueryError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobQueryError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise AgentJobQueryError(f"{field} must be a positive integer")
    return normalized


def _limit(value):
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobQueryError("limit must be an integer") from exc
    if not 1 <= normalized <= 100:
        raise AgentJobQueryError("limit must be between 1 and 100")
    return normalized


def _status(value):
    normalized = str(value or "").strip().lower()
    if normalized and normalized not in AGENT_JOB_STATUSES:
        raise AgentJobQueryError("status is not supported")
    return normalized


def _time(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _public_error(value):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    if normalized == "worker lease expired":
        return "Аренда задачи истекла; задача возвращена в очередь"
    return "Ошибка выполнения задачи; подробности доступны в серверном журнале"


def public_agent_job(row):
    if not isinstance(row, Mapping):
        return None
    return {
        "id": row.get("id"),
        "companyId": row.get("company_id"),
        "projectId": row.get("project_id"),
        "requestedByUserId": row.get("requested_by_user_id"),
        "requestedByRole": row.get("requested_by_role") or "",
        "jobType": row.get("job_type") or "",
        "correlationId": row.get("correlation_id") or "",
        "status": row.get("status") or "",
        "priority": row.get("priority"),
        "attempts": row.get("attempts"),
        "maxAttempts": row.get("max_attempts"),
        "runAfter": _time(row.get("run_after")),
        "heartbeatAt": _time(row.get("heartbeat_at")),
        "leaseExpiresAt": _time(row.get("lease_expires_at")),
        "startedAt": _time(row.get("started_at")),
        "completedAt": _time(row.get("completed_at")),
        "lastError": _public_error(row.get("last_error")),
        "createdAt": _time(row.get("created_at")),
        "updatedAt": _time(row.get("updated_at")),
    }


def list_agent_jobs(
    cur,
    *,
    company_id,
    status="",
    project_id=None,
    before_id=None,
    limit=25,
):
    company_id = _positive_int(company_id, "company_id")
    project_id = _positive_int(project_id, "project_id", optional=True)
    before_id = _positive_int(before_id, "before_id", optional=True)
    status = _status(status)
    limit = _limit(limit)

    where = ["company_id=%s"]
    params = [company_id]
    if project_id is not None:
        where.append("project_id=%s")
        params.append(project_id)
    if status:
        where.append("status=%s")
        params.append(status)
    if before_id is not None:
        where.append("id<%s")
        params.append(before_id)
    params.append(limit + 1)
    cur.execute(
        f"""SELECT {PUBLIC_JOB_COLUMNS}
              FROM agent_jobs
             WHERE {' AND '.join(where)}
             ORDER BY id DESC
             LIMIT %s""",
        tuple(params),
    )
    rows = list(cur.fetchall() or [])
    page = rows[:limit]
    items = [public_agent_job(row) for row in page]
    items = [item for item in items if item is not None]
    return {
        "items": items,
        "nextBeforeId": items[-1]["id"] if len(rows) > limit and items else None,
    }


def get_agent_job(cur, *, company_id, job_id):
    company_id = _positive_int(company_id, "company_id")
    job_id = _positive_int(job_id, "job_id")
    cur.execute(
        f"""SELECT {PUBLIC_JOB_COLUMNS}
              FROM agent_jobs
             WHERE id=%s AND company_id=%s""",
        (job_id, company_id),
    )
    return public_agent_job(cur.fetchone())
