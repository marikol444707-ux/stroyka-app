"""Default-off HTTP boundary for one warehouse anomaly preview."""

import json
import threading
import time
from typing import Optional

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError
from backend.features.warehouse_recommendation_preview import (
    content_contract as _content_contract,
)


_MAX_ID = 9223372036854775807
_MAX_ALLOWED_COMPANIES = 100
_MAX_BODY_BYTES = 4096
_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, X-Company-Id, X-Company-Mode",
}
_AUTHENTICATION_REQUIRED = (
    "warehouse_anomaly_preview_authentication_required"
)
_REQUEST_FORBIDDEN = "warehouse_anomaly_preview_request_forbidden"
_NOT_FOUND = "warehouse_anomaly_preview_not_found"
_REQUEST_TOO_LARGE = "warehouse_anomaly_preview_request_too_large"
_MEDIA_TYPE_INVALID = "warehouse_anomaly_preview_media_type_invalid"
_REQUEST_INVALID = "warehouse_anomaly_preview_request_invalid"
_CONFLICT = "warehouse_anomaly_preview_conflict"
_BUSY = "warehouse_anomaly_preview_busy"
_UNAVAILABLE = "warehouse_anomaly_preview_unavailable"
_PUBLIC_FIELDS = frozenset({
    "warehouseAnomalyRuntimeVersion", "ok", "dryRun", "writesAttempted",
    "previewOnly", "stockMovementAllowed", "inventoryAdjustmentAllowed",
    "applyAllowed", "state", "candidate", "content", "blockers",
    "readOnlyTransaction", "rolledBack",
})
_CANDIDATE_FIELDS = frozenset({
    "subjectKind", "subjectId", "anomalyCode", "recommendationCode",
})
_PUBLIC_STATE_BLOCKERS = {
    "blocked": "warehouse_anomaly_preview_blocked",
    "stale": "warehouse_anomaly_preview_stale",
}
_TELEMETRY_OUTCOMES = ("ok", "busy", "deadline", "unavailable")
_TELEMETRY_DURATION_BUCKETS = (
    "le1s", "le5s", "le15s", "le35s", "gt35s",
)


class _WarehouseAnomalyPreviewTelemetry:
    """Keep only fixed, privacy-safe process aggregates."""

    __slots__ = (
        "_active", "_clock", "_durations", "_lock", "_outcomes",
    )

    def __init__(self, clock=time.monotonic):
        if not callable(clock):
            raise TypeError("telemetry clock is invalid")
        self._clock = clock
        self._lock = threading.Lock()
        self._active = 0
        self._outcomes = {
            outcome: 0 for outcome in _TELEMETRY_OUTCOMES
        }
        self._durations = {
            bucket: 0 for bucket in _TELEMETRY_DURATION_BUCKETS
        }

    def begin(self):
        started = self._clock()
        with self._lock:
            self._active += 1
        return started

    def finish(self, started, outcome):
        if outcome not in _TELEMETRY_OUTCOMES:
            outcome = "unavailable"
        elapsed = self._clock() - started
        if elapsed <= 1:
            bucket = "le1s"
        elif elapsed <= 5:
            bucket = "le5s"
        elif elapsed <= 15:
            bucket = "le15s"
        elif elapsed <= 35:
            bucket = "le35s"
        else:
            bucket = "gt35s"
        with self._lock:
            self._active -= 1
            self._outcomes[outcome] += 1
            self._durations[bucket] += 1

    def snapshot(self):
        with self._lock:
            return {
                "inFlight": int(self._active > 0),
                "outcomes": dict(self._outcomes),
                "durations": dict(self._durations),
            }


def _valid_company_allowlist(value):
    return (
        type(value) is frozenset
        and 0 < len(value) <= _MAX_ALLOWED_COMPANIES
        and all(type(item) is int and 0 < item <= _MAX_ID for item in value)
    )


def _company_id(value, mode):
    if (
        type(mode) is not str
        or mode != "company"
        or type(value) is not str
        or not value
        or len(value) > 19
        or value[0] not in "123456789"
        or not value.isascii()
        or not value.isdecimal()
    ):
        return None
    parsed = int(value)
    return parsed if parsed <= _MAX_ID else None


def _valid_authentication(value):
    return (
        type(value) is dict
        and set(value) == {"authenticationKind", "sessionHash"}
        and value.get("authenticationKind") == "cookie_session"
        and type(value.get("authenticationKind")) is str
        and _lowercase_sha256(value.get("sessionHash"))
    )


def _lowercase_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _response(content, *, status_code=200, retry_after=None):
    headers = dict(_RESPONSE_HEADERS)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


def _error(status_code, detail, *, retry_after=None):
    return _response(
        {"detail": detail},
        status_code=status_code,
        retry_after=retry_after,
    )


def _validated_public_result(value, selection):
    if (
        type(value) is not dict
        or set(value) != _PUBLIC_FIELDS
        or type(value.get("warehouseAnomalyRuntimeVersion")) is not int
        or value["warehouseAnomalyRuntimeVersion"] != 1
        or value.get("ok") is not True
        or value.get("dryRun") is not True
        or type(value.get("writesAttempted")) is not int
        or value["writesAttempted"] != 0
        or value.get("previewOnly") is not True
        or value.get("stockMovementAllowed") is not False
        or value.get("inventoryAdjustmentAllowed") is not False
        or value.get("applyAllowed") is not False
        or value.get("readOnlyTransaction") is not True
        or value.get("rolledBack") is not True
        or type(value.get("state")) is not str
        or value["state"] not in {"preview_ready", "blocked", "stale"}
    ):
        raise ValueError("invalid public result")
    candidate = value.get("candidate")
    if (
        type(candidate) is not dict
        or set(candidate) != _CANDIDATE_FIELDS
        or type(candidate.get("subjectKind")) is not str
        or type(candidate.get("subjectId")) is not int
        or not 0 < candidate["subjectId"] <= _MAX_ID
        or type(candidate.get("anomalyCode")) is not str
        or type(candidate.get("recommendationCode")) is not str
        or _content_contract._SELECTION_RULES.get(candidate["anomalyCode"])
        != candidate["subjectKind"]
        or _content_contract._ANOMALY_RECOMMENDATION_RULES.get(
            candidate["anomalyCode"]
        ) != candidate["recommendationCode"]
        or {
            "subjectKind": candidate["subjectKind"],
            "subjectId": candidate["subjectId"],
            "anomalyCode": candidate["anomalyCode"],
        } != selection
    ):
        raise ValueError("invalid public result")
    state = value["state"]
    if state == "preview_ready":
        if (
            type(value.get("content")) is not dict
            or value["content"] != _content_contract._fixed_content(candidate)
            or type(value.get("blockers")) is not list
            or value["blockers"] != []
        ):
            raise ValueError("invalid public result")
        content = dict(value["content"])
        blockers = []
    else:
        expected_blocker = _PUBLIC_STATE_BLOCKERS[state]
        if (
            value.get("content") is not None
            or type(value.get("blockers")) is not list
            or value["blockers"] != [expected_blocker]
        ):
            raise ValueError("invalid public result")
        content = None
        blockers = [expected_blocker]
    return {
        **value,
        "candidate": dict(candidate),
        "content": content,
        "blockers": blockers,
    }


def _fixed_error_code(error):
    try:
        state = object.__getattribute__(error, "__dict__")
    except Exception:
        return None
    if type(state) is not dict:
        return None
    code = state.get("code")
    return code if type(code) is str else None


def _runtime_failure(error):
    code = _fixed_error_code(error)
    if code == "warehouse_anomaly_runtime_input_invalid":
        return _error(422, _REQUEST_INVALID)
    if code == "warehouse_anomaly_runtime_authentication_required":
        return _error(401, _AUTHENTICATION_REQUIRED)
    if code == "warehouse_anomaly_runtime_resource_not_found":
        return _error(404, _NOT_FOUND)
    if code == "warehouse_anomaly_runtime_artifact_invalid":
        return _error(409, _CONFLICT)
    if code == "warehouse_anomaly_runtime_busy":
        return _error(429, _BUSY, retry_after=10)
    return _error(503, _UNAVAILABLE, retry_after=30)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


async def _json_body(request):
    chunks = []
    size = 0
    async for chunk in request.stream():
        if type(chunk) is not bytes:
            raise ValueError("invalid body")
        size += len(chunk)
        if size > _MAX_BODY_BYTES:
            raise OverflowError("body too large")
        chunks.append(chunk)
    return json.loads(
        b"".join(chunks).decode("utf-8"),
        object_pairs_hook=_unique_object,
    )


def register_warehouse_anomaly_preview_routes(app, deps):
    """Register the reviewed route only for an exact enabled configuration."""

    if deps.get("enabled") is not True:
        return None
    allowed_company_ids = deps.get("allowed_company_ids")
    if not _valid_company_allowlist(allowed_company_ids):
        return None

    db_config = dict(deps["db_config"])
    build_authentication = deps["build_cookie_session_authentication"]
    parse_claims = deps["parse_warehouse_anomaly_runtime_claims"]
    run_preview = deps["run_warehouse_anomaly_runtime_preview"]
    telemetry = deps.get("telemetry")
    if type(telemetry) is not _WarehouseAnomalyPreviewTelemetry:
        telemetry = _WarehouseAnomalyPreviewTelemetry()

    @app.post("/warehouse-anomaly-previews")
    async def create_warehouse_anomaly_preview(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(
            default=None, alias="X-CSRF-Token",
        ),
        x_company_id: Optional[str] = Header(
            default=None, alias="X-Company-Id",
        ),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        if request.headers.get("content-type") != "application/json":
            return _error(415, _MEDIA_TYPE_INVALID)
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _REQUEST_INVALID)
        try:
            authentication = build_authentication(
                request,
                authorization,
                x_csrf_token,
                require_csrf=True,
            )
        except CookieSessionAuthenticationError as error:
            if error.code == "cookie_session_csrf_invalid":
                return _error(403, _REQUEST_FORBIDDEN)
            return _error(401, _AUTHENTICATION_REQUIRED)
        except MemoryError:
            raise
        except Exception as error:
            return _runtime_failure(error)
        if not _valid_authentication(authentication):
            return _error(503, _UNAVAILABLE, retry_after=30)
        if company_id not in allowed_company_ids:
            return _error(404, _NOT_FOUND)
        try:
            body = await _json_body(request)
        except MemoryError:
            raise
        except OverflowError:
            return _error(413, _REQUEST_TOO_LARGE)
        except Exception:
            return _error(422, _REQUEST_INVALID)
        try:
            parse_claims(
                authentication,
                company_mode=x_company_mode,
                company_id=x_company_id,
                body=body,
            )
        except MemoryError:
            raise
        except Exception as error:
            if _fixed_error_code(error) == (
                "warehouse_anomaly_runtime_input_invalid"
            ):
                return _error(422, _REQUEST_INVALID)
            return _error(503, _UNAVAILABLE, retry_after=30)
        started = telemetry.begin()
        outcome = "unavailable"
        try:
            try:
                result = run_preview(
                    dict(db_config),
                    authentication,
                    company_mode=x_company_mode,
                    company_id=x_company_id,
                    body=body,
                )
                result = _validated_public_result(result, body["selected"])
            except MemoryError:
                raise
            except Exception as error:
                code = _fixed_error_code(error)
                if code == "warehouse_anomaly_runtime_busy":
                    outcome = "busy"
                elif code == "warehouse_anomaly_runtime_deadline_exceeded":
                    outcome = "deadline"
                return _runtime_failure(error)
            response = _response(result)
            outcome = "ok"
            return response
        finally:
            telemetry.finish(started, outcome)

    return None


__all__ = []
