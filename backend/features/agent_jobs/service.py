import json
import re
import uuid
from collections.abc import Mapping


JOB_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,79}$")
MAX_PAYLOAD_BYTES = 64 * 1024
SENSITIVE_PAYLOAD_KEYS = {
    "apikey",
    "authorization",
    "cookie",
    "password",
    "passwd",
    "privatekey",
}


class AgentJobValidationError(ValueError):
    pass


def _contains_sensitive_key(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if (
                normalized_key in SENSITIVE_PAYLOAD_KEYS
                or normalized_key.endswith("secret")
                or normalized_key.endswith("token")
            ):
                return True
            if _contains_sensitive_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _positive_int(value, field, *, required=False):
    if value is None or value == "":
        if required:
            raise AgentJobValidationError(f"{field} is required")
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobValidationError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise AgentJobValidationError(f"{field} must be a positive integer")
    return normalized


def _bounded_text(value, field, limit, *, required=False):
    normalized = str(value or "").strip()
    if required and not normalized:
        raise AgentJobValidationError(f"{field} is required")
    if len(normalized) > limit:
        raise AgentJobValidationError(f"{field} is too long")
    return normalized


def _bounded_int(value, field, minimum, maximum, default):
    if value is None or value == "":
        return default
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentJobValidationError(f"{field} must be an integer") from exc
    if not minimum <= normalized <= maximum:
        raise AgentJobValidationError(f"{field} must be between {minimum} and {maximum}")
    return normalized


def _json_payload(payload):
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise AgentJobValidationError("payload must be an object")
    if _contains_sensitive_key(payload):
        raise AgentJobValidationError("payload contains a sensitive field")
    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AgentJobValidationError("payload must be JSON serializable") from exc
    if len(serialized.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise AgentJobValidationError("payload is too large")
    return serialized


def _public_row(row):
    return dict(row) if isinstance(row, Mapping) else row


def enqueue_agent_job(
    cur,
    *,
    company_id,
    job_type,
    idempotency_key,
    project_id=None,
    requested_by_user_id=None,
    requested_by_role="",
    payload=None,
    correlation_id="",
    priority=5,
    max_attempts=3,
):
    company_id = _positive_int(company_id, "company_id", required=True)
    project_id = _positive_int(project_id, "project_id")
    requested_by_user_id = _positive_int(requested_by_user_id, "requested_by_user_id")
    job_type = _bounded_text(job_type, "job_type", 80, required=True)
    if not JOB_TYPE_RE.fullmatch(job_type):
        raise AgentJobValidationError("job_type has invalid format")
    idempotency_key = _bounded_text(idempotency_key, "idempotency_key", 180, required=True)
    requested_by_role = _bounded_text(requested_by_role, "requested_by_role", 100)
    if requested_by_user_id is None and requested_by_role not in ("", "system"):
        raise AgentJobValidationError(
            "requested_by_user_id is required for a human role"
        )
    correlation_id = _bounded_text(correlation_id, "correlation_id", 80) or str(uuid.uuid4())
    payload_json = _json_payload(payload)
    priority = _bounded_int(priority, "priority", 1, 10, 5)
    max_attempts = _bounded_int(max_attempts, "max_attempts", 1, 10, 3)

    if project_id is not None:
        cur.execute(
            "SELECT id FROM projects WHERE id=%s AND company_id=%s",
            (project_id, company_id),
        )
        if cur.fetchone() is None:
            raise AgentJobValidationError("project_id does not belong to company_id")

    if requested_by_user_id is not None:
        if not requested_by_role:
            raise AgentJobValidationError(
                "requested_by_role is required for a user-requested job"
            )
        cur.execute(
            """
            SELECT role
              FROM user_company_roles
             WHERE user_id=%s AND company_id=%s AND role=%s AND active IS TRUE
             LIMIT 1
            """,
            (requested_by_user_id, company_id, requested_by_role),
        )
        if cur.fetchone() is None:
            raise AgentJobValidationError(
                "requested_by_user_id does not have this active company role"
            )

    cur.execute(
        """
        INSERT INTO agent_jobs (
            owner_scope,company_id,project_id,requested_by_user_id,
            requested_by_role,job_type,idempotency_key,correlation_id,
            payload_json,status,priority,max_attempts
        ) VALUES (
            'company',%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'queued',%s,%s
        )
        ON CONFLICT ON CONSTRAINT uq_agent_jobs_idempotency DO NOTHING
        RETURNING *
        """,
        (
            company_id,
            project_id,
            requested_by_user_id,
            requested_by_role,
            job_type,
            idempotency_key,
            correlation_id,
            payload_json,
            priority,
            max_attempts,
        ),
    )
    row = cur.fetchone()
    if row is not None:
        return {"created": True, "job": _public_row(row)}

    cur.execute(
        """
        SELECT * FROM agent_jobs
         WHERE company_id=%s AND project_scope_id=%s
           AND job_type=%s AND idempotency_key=%s
        """,
        (company_id, project_id or 0, job_type, idempotency_key),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("agent job idempotency conflict without an existing row")
    return {"created": False, "job": _public_row(row)}
