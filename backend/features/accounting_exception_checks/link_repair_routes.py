"""Strict default-off HTTP boundary for A11.9 link repair preview/apply."""

import json
import math
import threading
import time
from collections import deque
from typing import Optional

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError


PATH = "/accounting-exception-link-repairs"
_MAX_ID = 9223372036854775807
_MAX_ALLOWED_COMPANIES = 100
_MAX_BODY_BYTES = 1024
_CONFIRMATION = "APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS"
_PROOFS = frozenset({"reciprocal", "delivery", "request", "identity"})
_PREVIEW_FIELDS = frozenset({
    "version", "companyId", "state", "repairCount", "unresolvedCount",
    "proofCounts", "planSha256", "blockers",
})
_APPLY_FIELDS = frozenset({
    "ok", "appliedCount", "unresolvedCount", "planSha256",
})
_BODY_FIELDS = frozenset({
    "confirm", "expectedRepairCount", "expectedPlanSha256",
})
_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, X-Company-Id, X-Company-Mode",
}
_AUTHENTICATION_REQUIRED = "accounting_link_repair_authentication_required"
_REQUEST_FORBIDDEN = "accounting_link_repair_request_forbidden"
_NOT_FOUND = "accounting_link_repair_not_found"
_REQUEST_INVALID = "accounting_link_repair_request_invalid"
_MEDIA_TYPE_INVALID = "accounting_link_repair_media_type_invalid"
_REQUEST_TOO_LARGE = "accounting_link_repair_request_too_large"
_CONFLICT = "accounting_link_repair_conflict"
_BUSY = "accounting_link_repair_busy"
_UNAVAILABLE = "accounting_link_repair_unavailable"


class _Lease:
    __slots__ = ("_released", "_slot")

    def __init__(self, slot):
        self._slot = slot
        self._released = False

    def release(self):
        if not self._released:
            self._released = True
            self._slot.release()


class _RouteGate:
    """Bound requests without retaining payload, session or actor data."""

    __slots__ = ("_clock", "_lock", "_recent", "_slot")

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._recent = {}
        self._slot = threading.BoundedSemaphore(1)

    def try_acquire(self, company_id, operation):
        if not _positive_int(company_id) or operation not in {"preview", "apply"}:
            raise ValueError("invalid gate input")
        if not self._slot.acquire(blocking=False):
            return None, 1
        try:
            now = self._clock()
            if type(now) not in {int, float} or not math.isfinite(now):
                raise ValueError("invalid gate clock")
            limit = 30 if operation == "preview" else 5
            key = (company_id, operation)
            with self._lock:
                recent = self._recent.setdefault(key, deque())
                boundary = now - 60.0
                while recent and recent[0] <= boundary:
                    recent.popleft()
                if len(recent) >= limit:
                    retry_after = max(1, int(math.ceil(recent[0] + 60.0 - now)))
                    self._slot.release()
                    return None, retry_after
                recent.append(now)
            return _Lease(self._slot), None
        except BaseException:
            self._slot.release()
            raise


def _positive_int(value):
    return type(value) is int and 0 < value <= _MAX_ID


def _sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_allowlist(value):
    return (
        type(value) is frozenset
        and 0 < len(value) <= _MAX_ALLOWED_COMPANIES
        and all(_positive_int(item) for item in value)
    )


def _valid_finance_roles(value):
    return (
        type(value) is tuple
        and 0 < len(value) <= 10
        and len(value) == len(set(value))
        and all(type(role) is str and 0 < len(role) <= 64 for role in value)
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
        and _sha256(value.get("sessionHash"))
    )


def _response(content, *, status_code=200, retry_after=None):
    headers = dict(_RESPONSE_HEADERS)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _error(status_code, detail, *, retry_after=None):
    return _response(
        {"detail": detail}, status_code=status_code, retry_after=retry_after,
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


async def _json_body(request):
    chunks = []
    size = 0
    async for chunk in request.stream():
        if type(chunk) is not bytes:
            raise ValueError("invalid chunk")
        size += len(chunk)
        if size > _MAX_BODY_BYTES:
            raise OverflowError("body too large")
        chunks.append(chunk)
    return json.loads(
        b"".join(chunks).decode("utf-8"), object_pairs_hook=_unique_object,
    )


def _valid_body(value):
    return (
        type(value) is dict
        and set(value) == _BODY_FIELDS
        and value.get("confirm") == _CONFIRMATION
        and type(value.get("expectedRepairCount")) is int
        and 1 <= value["expectedRepairCount"] <= 100
        and _sha256(value.get("expectedPlanSha256"))
    )


def _public_preview(value, company_id):
    if (
        type(value) is not dict
        or set(value) != _PREVIEW_FIELDS
        or value.get("version") != "accounting-exception-link-repair-v2"
        or value.get("companyId") != company_id
        or value.get("state") not in {"clear", "ready", "blocked"}
        or type(value.get("repairCount")) is not int
        or not 0 <= value["repairCount"] <= 100
        or type(value.get("unresolvedCount")) is not int
        or not 0 <= value["unresolvedCount"] <= 2000
        or not _sha256(value.get("planSha256"))
        or type(value.get("blockers")) is not list
    ):
        raise ValueError("invalid preview")
    counts = value.get("proofCounts")
    if (
        type(counts) is not dict
        or set(counts) != _PROOFS
        or any(type(count) is not int or count < 0 for count in counts.values())
        or sum(counts.values()) != value["repairCount"]
    ):
        raise ValueError("invalid preview")
    if value["state"] == "ready":
        valid_state = value["repairCount"] > 0 and value["blockers"] == []
    elif value["state"] == "clear":
        valid_state = value["repairCount"] == 0 and value["blockers"] == []
    else:
        valid_state = (
            value["repairCount"] == 0
            and value["blockers"] == ["accounting_link_repair_plan_too_large"]
        )
    if not valid_state:
        raise ValueError("invalid preview")
    return {
        "version": value["version"],
        "companyId": company_id,
        "state": value["state"],
        "repairCount": value["repairCount"],
        "unresolvedCount": value["unresolvedCount"],
        "proofCounts": {
            proof: counts[proof]
            for proof in ("reciprocal", "delivery", "request", "identity")
        },
        "planSha256": value["planSha256"],
        "blockers": list(value["blockers"]),
    }


def _public_apply(value, company_id, expected_count, expected_sha256):
    del company_id
    if (
        type(value) is not dict
        or set(value) != _APPLY_FIELDS
        or value.get("ok") is not True
        or value.get("appliedCount") != expected_count
        or type(value.get("unresolvedCount")) is not int
        or not 0 <= value["unresolvedCount"] <= 2000
        or value.get("planSha256") != expected_sha256
    ):
        raise ValueError("invalid apply result")
    return dict(value)


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
    if code == "accounting_link_repair_input_invalid":
        return _error(422, _REQUEST_INVALID)
    if code == "accounting_link_repair_authentication_required":
        return _error(401, _AUTHENTICATION_REQUIRED)
    if code == "accounting_link_repair_request_forbidden":
        return _error(403, _REQUEST_FORBIDDEN)
    if code in {
        "accounting_link_repair_plan_stale",
        "accounting_link_repair_plan_blocked",
    }:
        return _error(409, _CONFLICT)
    if code == "accounting_link_repair_busy":
        return _error(429, _BUSY, retry_after=1)
    return _error(503, _UNAVAILABLE, retry_after=30)


def _authenticate(
    build_authentication, request, authorization, csrf_token, *, require_csrf,
):
    try:
        authentication = build_authentication(
            request,
            authorization,
            csrf_token,
            require_csrf=require_csrf,
        )
    except CookieSessionAuthenticationError as error:
        if error.code == "cookie_session_csrf_invalid":
            return None, _error(403, _REQUEST_FORBIDDEN)
        return None, _error(401, _AUTHENTICATION_REQUIRED)
    except MemoryError:
        raise
    except Exception:
        return None, _error(503, _UNAVAILABLE, retry_after=30)
    if not _valid_authentication(authentication):
        return None, _error(503, _UNAVAILABLE, retry_after=30)
    return authentication, None


def register_accounting_link_repair_routes(app, deps):
    """Register exact GET/POST routes only behind the existing A11 gates."""

    if deps.get("enabled") is not True:
        return None
    allowed_company_ids = deps.get("allowed_company_ids")
    finance_roles = deps.get("finance_roles")
    if not _valid_allowlist(allowed_company_ids) or not _valid_finance_roles(finance_roles):
        return None

    get_db = deps["get_db"]
    build_authentication = deps["build_cookie_session_authentication"]
    run_preview = deps["preview_accounting_link_repairs"]
    run_apply = deps["apply_accounting_link_repairs"]
    gate = deps.get("gate")
    if type(gate) is not _RouteGate:
        gate = _RouteGate()

    @app.get(PATH)
    def get_accounting_link_repair_preview(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
    ):
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _REQUEST_INVALID)
        authentication, failure = _authenticate(
            build_authentication,
            request,
            authorization,
            None,
            require_csrf=False,
        )
        if failure is not None:
            return failure
        if company_id not in allowed_company_ids:
            return _error(404, _NOT_FOUND)
        try:
            lease, retry_after = gate.try_acquire(company_id, "preview")
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if lease is None:
            return _error(429, _BUSY, retry_after=retry_after)
        try:
            try:
                result = run_preview(
                    get_db, dict(authentication), company_id, finance_roles,
                )
                return _response(_public_preview(result, company_id))
            except MemoryError:
                raise
            except Exception as error:
                return _runtime_failure(error)
        finally:
            lease.release()

    @app.post(PATH)
    async def apply_accounting_link_repair_plan(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
    ):
        if request.headers.get("content-type") != "application/json":
            return _error(415, _MEDIA_TYPE_INVALID)
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _REQUEST_INVALID)
        authentication, failure = _authenticate(
            build_authentication,
            request,
            authorization,
            x_csrf_token,
            require_csrf=True,
        )
        if failure is not None:
            return failure
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
        if not _valid_body(body):
            return _error(422, _REQUEST_INVALID)
        try:
            lease, retry_after = gate.try_acquire(company_id, "apply")
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if lease is None:
            return _error(429, _BUSY, retry_after=retry_after)
        try:
            try:
                result = run_apply(
                    get_db,
                    dict(authentication),
                    company_id,
                    finance_roles,
                    expected_repair_count=body["expectedRepairCount"],
                    expected_plan_sha256=body["expectedPlanSha256"],
                )
                return _response(_public_apply(
                    result,
                    company_id,
                    body["expectedRepairCount"],
                    body["expectedPlanSha256"],
                ))
            except MemoryError:
                raise
            except Exception as error:
                return _runtime_failure(error)
        finally:
            lease.release()

    return None


__all__ = []
