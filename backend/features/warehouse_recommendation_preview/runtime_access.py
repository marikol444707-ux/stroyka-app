"""Private same-cursor authorization and artifact access contracts."""

import json

from backend.features.agent_jobs.service import serialize_safe_json_object
from backend.features.estimate_revision_impact.handler import (
    validate_estimate_revision_impact_result,
)
from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
    source_from_job_payload,
)

from backend.features.warehouse_recommendation_preview import (
    runtime_contract as _runtime_contract,
)


_AUTHORIZATION_SQL = """
WITH actor AS MATERIALIZED (
    SELECT membership.id
      FROM public.user_sessions session
      JOIN public.users actor_user
        ON actor_user.id=session.user_id
      JOIN public.user_company_roles membership
        ON membership.user_id=actor_user.id
      JOIN public.companies company
        ON company.id=membership.company_id
      JOIN public.platform_accounts platform_account
        ON platform_account.id=company.platform_account_id
     WHERE session.session_hash=%s
       AND membership.company_id=%s
       AND session.revoked_at IS NULL
       AND session.expires_at>clock_timestamp()
       AND session.two_factor_passed IS TRUE
       AND actor_user.active IS TRUE
       AND actor_user.two_factor_enabled IS TRUE
       AND membership.role='директор'
       AND membership.active IS TRUE
       AND company.active IS TRUE
       AND membership.platform_account_id=company.platform_account_id
       AND platform_account.active IS TRUE
       AND platform_account.status='active'
     ORDER BY membership.id
     LIMIT %s
),
actor_count AS MATERIALIZED (
    SELECT COUNT(*)::bigint AS actor_count
      FROM actor
)
SELECT actor_count.actor_count,
       CASE
         WHEN actor_count.actor_count=1 THEN EXISTS (
             SELECT 1
               FROM public.projects project
              WHERE project.id=%s
                AND project.company_id=%s
         )
         ELSE FALSE
       END AS project_exists
  FROM actor_count
"""

_ARTIFACT_INVALID = "warehouse_anomaly_runtime_artifact_invalid"
_RESOURCE_NOT_FOUND = "warehouse_anomaly_runtime_resource_not_found"
_MAX_ARTIFACT_TRANSPORT_BYTES = 128 * 1024
_ARTIFACT_ROW_FIELDS = frozenset({
    "job_id",
    "owner_scope",
    "company_id",
    "project_id",
    "project_scope_id",
    "requested_by_user_id",
    "requested_by_role",
    "job_type",
    "idempotency_key",
    "correlation_id",
    "status",
    "priority",
    "attempts",
    "max_attempts",
    "started_at_present",
    "completed_at_present",
    "last_error_empty",
    "locked_at_null",
    "locked_by_null",
    "lease_token_null",
    "lease_expires_at_null",
    "heartbeat_at_null",
    "payload_json",
    "result_json",
    "payload_bytes",
    "result_bytes",
    "row_count",
    "payload_limit_exceeded",
    "result_limit_exceeded",
})
_ARTIFACT_BOOLEAN_FIELDS = frozenset({
    "started_at_present",
    "completed_at_present",
    "last_error_empty",
    "locked_at_null",
    "locked_by_null",
    "lease_token_null",
    "lease_expires_at_null",
    "heartbeat_at_null",
    "payload_limit_exceeded",
    "result_limit_exceeded",
})
_ARTIFACT_SQL = """
WITH limited AS MATERIALIZED (
    SELECT job.id AS job_id,
           job.owner_scope,
           job.company_id,
           job.project_id,
           job.project_scope_id,
           job.requested_by_user_id,
           job.requested_by_role,
           job.job_type,
           job.idempotency_key,
           job.correlation_id,
           job.status,
           job.priority,
           job.attempts,
           job.max_attempts,
           job.started_at IS NOT NULL AS started_at_present,
           job.completed_at IS NOT NULL AS completed_at_present,
           job.last_error='' AS last_error_empty,
           job.locked_at IS NULL AS locked_at_null,
           job.locked_by IS NULL AS locked_by_null,
           job.lease_token IS NULL AS lease_token_null,
           job.lease_expires_at IS NULL AS lease_expires_at_null,
           job.heartbeat_at IS NULL AS heartbeat_at_null,
           job.payload_json AS emitted_payload_json,
           job.result_json AS emitted_result_json
      FROM public.agent_jobs job
     WHERE job.id=%s
       AND job.company_id=%s
       AND job.project_id=%s
       AND job.owner_scope='company'
       AND job.job_type='estimate.revision_impact'
       AND job.status='succeeded'
       AND job.requested_by_user_id IS NULL
       AND job.requested_by_role='system'
     ORDER BY job.id
     LIMIT %s
),
sized AS MATERIALIZED (
    SELECT limited.*,
           COALESCE(
               octet_length(convert_to(emitted_payload_json::text,'UTF8')),
               0
           )::bigint AS payload_bytes,
           COALESCE(
               octet_length(convert_to(emitted_result_json::text,'UTF8')),
               0
           )::bigint AS result_bytes
      FROM limited
),
decided AS MATERIALIZED (
    SELECT sized.*,
           COUNT(*) OVER ()::bigint AS row_count,
           MAX(payload_bytes) OVER () AS max_payload_bytes,
           MAX(result_bytes) OVER () AS max_result_bytes
      FROM sized
),
classified AS MATERIALIZED (
    SELECT decided.*,
           max_payload_bytes>%s AS payload_limit_exceeded,
           max_result_bytes>%s AS result_limit_exceeded
      FROM decided
),
gated AS MATERIALIZED (
    SELECT classified.*,
           row_count=1
           AND payload_limit_exceeded IS FALSE
           AND result_limit_exceeded IS FALSE AS payload_allowed
      FROM classified
)
SELECT gated.job_id,
       gated.owner_scope,
       gated.company_id,
       gated.project_id,
       gated.project_scope_id,
       gated.requested_by_user_id,
       gated.requested_by_role,
       gated.job_type,
       gated.idempotency_key,
       gated.correlation_id,
       gated.status,
       gated.priority,
       gated.attempts,
       gated.max_attempts,
       gated.started_at_present,
       gated.completed_at_present,
       gated.last_error_empty,
       gated.locked_at_null,
       gated.locked_by_null,
       gated.lease_token_null,
       gated.lease_expires_at_null,
       gated.heartbeat_at_null,
       CASE WHEN gated.payload_allowed
            THEN gated.emitted_payload_json ELSE NULL END AS payload_json,
       CASE WHEN gated.payload_allowed
            THEN gated.emitted_result_json ELSE NULL END AS result_json,
       gated.payload_bytes,
       gated.result_bytes,
       gated.row_count,
       gated.payload_limit_exceeded,
       gated.result_limit_exceeded
  FROM gated
 ORDER BY gated.job_id
"""
_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)


def _authorize_warehouse_anomaly_runtime_access(cur, claims):
    """Authorize one immutable claim set using the caller-owned cursor."""

    if not _runtime_contract._valid_runtime_claims(claims):
        _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)
    if (
        cur is None
        or not callable(getattr(cur, "execute", None))
        or not callable(getattr(cur, "fetchall", None))
    ):
        _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)

    cur.execute(
        _AUTHORIZATION_SQL,
        (
            claims.session_hash,
            claims.company_id,
            2,
            claims.project_id,
            claims.company_id,
        ),
    )
    rows = cur.fetchall()
    if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
        _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)
    return _runtime_contract._authorize_warehouse_anomaly_runtime_claims(
        claims,
        rows[0],
    )


def _artifact_contract_invalid():
    _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)


def _artifact_invalid():
    _runtime_contract._fail(_ARTIFACT_INVALID)


def _valid_artifact_row_shape(row):
    return (
        type(row) is dict
        and set(row) == _ARTIFACT_ROW_FIELDS
        and all(type(row.get(name)) is bool for name in _ARTIFACT_BOOLEAN_FIELDS)
        and all(
            type(row.get(name)) is int and row[name] >= 0
            for name in ("payload_bytes", "result_bytes", "row_count")
        )
        and all(
            type(row.get(name)) is int
            for name in (
                "job_id",
                "company_id",
                "project_id",
                "project_scope_id",
                "priority",
                "attempts",
                "max_attempts",
            )
        )
        and (
            row.get("requested_by_user_id") is None
            or type(row.get("requested_by_user_id")) is int
        )
        and all(
            type(row.get(name)) is str and bool(row[name])
            for name in (
                "owner_scope",
                "requested_by_role",
                "job_type",
                "idempotency_key",
                "correlation_id",
                "status",
            )
        )
    )


def _validate_artifact_transport_rows(rows):
    if type(rows) is not list or len(rows) > 2:
        _artifact_contract_invalid()
    if not rows:
        _runtime_contract._fail(_RESOURCE_NOT_FOUND)
    if not all(_valid_artifact_row_shape(row) for row in rows):
        _artifact_contract_invalid()

    expected_count = len(rows)
    payload_overflow = max(row["payload_bytes"] for row in rows) > (
        _MAX_ARTIFACT_TRANSPORT_BYTES
    )
    result_overflow = max(row["result_bytes"] for row in rows) > (
        _MAX_ARTIFACT_TRANSPORT_BYTES
    )
    for row in rows:
        if (
            row["row_count"] != expected_count
            or row["payload_limit_exceeded"] is not payload_overflow
            or row["result_limit_exceeded"] is not result_overflow
        ):
            _artifact_contract_invalid()
        payloads_hidden = (
            row["payload_json"] is None and row["result_json"] is None
        )
        if expected_count != 1 or payload_overflow or result_overflow:
            if not payloads_hidden:
                _artifact_contract_invalid()
        elif (
            type(row["payload_json"]) is not dict
            or type(row["result_json"]) is not dict
        ):
            _artifact_contract_invalid()

    if expected_count != 1:
        _runtime_contract._fail(_RESOURCE_NOT_FOUND)
    if payload_overflow or result_overflow:
        _artifact_invalid()
    return rows[0]


def _validate_artifact_lifecycle(row, claims):
    if (
        row["job_id"] != claims.job_id
        or row["owner_scope"] != "company"
        or row["company_id"] != claims.company_id
        or row["project_id"] != claims.project_id
        or row["project_scope_id"] != claims.project_id
        or row["requested_by_user_id"] is not None
        or row["requested_by_role"] != "system"
        or row["job_type"] != "estimate.revision_impact"
        or row["status"] != "succeeded"
        or row["priority"] != 4
        or row["max_attempts"] != 3
        or not 1 <= row["attempts"] <= row["max_attempts"]
        or row["started_at_present"] is not True
        or row["completed_at_present"] is not True
        or row["last_error_empty"] is not True
        or row["locked_at_null"] is not True
        or row["locked_by_null"] is not True
        or row["lease_token_null"] is not True
        or row["lease_expires_at_null"] is not True
        or row["heartbeat_at_null"] is not True
    ):
        _artifact_invalid()


def _read_warehouse_anomaly_runtime_artifact(cur, claims):
    """Read one bounded exact job row from the caller-owned cursor."""

    if not _runtime_contract._valid_runtime_claims(claims):
        _artifact_contract_invalid()
    if (
        cur is None
        or not callable(getattr(cur, "execute", None))
        or not callable(getattr(cur, "fetchall", None))
    ):
        _artifact_contract_invalid()

    cur.execute(
        _ARTIFACT_SQL,
        (
            claims.job_id,
            claims.company_id,
            claims.project_id,
            2,
            _MAX_ARTIFACT_TRANSPORT_BYTES,
            _MAX_ARTIFACT_TRANSPORT_BYTES,
        ),
    )
    row = _validate_artifact_transport_rows(cur.fetchall())
    _validate_artifact_lifecycle(row, claims)
    return dict(row)


def _detached_safe_json_object(value, field):
    serialized = serialize_safe_json_object(value, field=field)
    detached = json.loads(serialized)
    if type(detached) is not dict:
        raise ValueError("artifact json must be an object")
    return detached


def _resolve_warehouse_anomaly_runtime_artifact(cur, claims):
    """Return one detached A9.2 input from an exact bounded job row."""

    row = _read_warehouse_anomaly_runtime_artifact(cur, claims)
    try:
        payload = _detached_safe_json_object(row["payload_json"], "payload")
        source = source_from_job_payload(payload)
        plan = build_estimate_revision_impact_job_plan(source)
        if (
            source.company_id != claims.company_id
            or source.project_id != claims.project_id
            or plan.company_id != row["company_id"]
            or plan.project_id != row["project_id"]
            or plan.job_type != row["job_type"]
            or plan.idempotency_key != row["idempotency_key"]
            or plan.correlation_id != row["correlation_id"]
            or plan.requested_by_role != row["requested_by_role"]
            or plan.priority != row["priority"]
            or plan.max_attempts != row["max_attempts"]
            or dict(plan.payload) != payload
        ):
            raise ValueError("artifact plan mismatch")

        stored_result = _detached_safe_json_object(
            row["result_json"], "result",
        )
        validated_result = validate_estimate_revision_impact_result(
            stored_result,
            source,
        )
        report = _detached_safe_json_object(validated_result, "result")
        selection = {
            "subjectKind": claims.selection.subject_kind,
            "subjectId": claims.selection.subject_id,
            "anomalyCode": claims.selection.anomaly_code,
        }
        return {
            "combinedReport": report,
            "selected": selection,
        }
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _artifact_invalid()


__all__ = []
