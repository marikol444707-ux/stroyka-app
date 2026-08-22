"""Default-off cookie/CSRF HTTP boundary for reviewed human actions."""

import json
import math
import re
import threading
import time
from collections import deque
from typing import Optional

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError

from .contract import ACTION_KIND as _ACTION_KIND
from .contract import ACTION_POLICIES as _ACTION_POLICIES


_MAX_ID = 9223372036854775807
_MAX_ALLOWED_COMPANIES = 1
_MAX_BODY_BYTES = 4096
_MAX_HISTORY_LIMIT = 100
_SUBJECT_KINDS = frozenset(_ACTION_POLICIES[_ACTION_KIND].subject_kinds)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$"
)
_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, X-Company-Id, X-Company-Mode",
}
_AUTHENTICATION_REQUIRED = "human_approved_action_authentication_required"
_REQUEST_FORBIDDEN = "human_approved_action_request_forbidden"
_NOT_FOUND = "human_approved_action_not_found"
_REQUEST_TOO_LARGE = "human_approved_action_request_too_large"
_MEDIA_TYPE_INVALID = "human_approved_action_media_type_invalid"
_REQUEST_INVALID = "human_approved_action_request_invalid"
_CONFLICT = "human_approved_action_conflict"
_BUSY = "human_approved_action_busy"
_UNAVAILABLE = "human_approved_action_unavailable"
_PROPOSAL_FIELDS = frozenset({
    "humanActionReceiptVersion", "state", "actionKind", "proposalId",
    "proposalSha256", "companyId", "projectId", "sourceJobId",
    "subjectKind", "subjectId", "actorUserId", "actorMembershipId",
    "expiresAt", "writesAttempted", "committed", "idempotent",
})
_DECISION_FIELDS = frozenset({
    "humanActionReceiptVersion", "state", "actionKind", "proposalId",
    "proposalSha256", "companyId", "projectId", "sourceJobId",
    "subjectKind", "subjectId", "actorUserId", "actorMembershipId",
    "eventId", "auditEventId", "writesAttempted", "committed",
    "idempotent",
})
_HISTORY_FIELDS = frozenset({
    "humanActionHistoryVersion", "companyId", "projectId", "items",
    "nextBeforeId",
})
_HISTORY_ITEM_FIELDS = frozenset({
    "eventId", "eventKind", "proposalId", "proposalSha256",
    "actionKind", "sourceJobId", "subjectKind", "subjectId",
    "actorUserId", "actorMembershipId", "occurredAt", "eventSha256",
})


class _GateLease:
    __slots__ = ("_released", "_semaphore")

    def __init__(self, semaphore):
        self._semaphore = semaphore
        self._released = False

    def release(self):
        if not self._released:
            self._released = True
            self._semaphore.release()


class _HumanActionRouteGate:
    """Bound route attempts without retaining payload or actor data."""

    __slots__ = ("_clock", "_lock", "_recent", "_slot")

    def __init__(self, clock=time.monotonic):
        if not callable(clock):
            raise TypeError("gate clock is invalid")
        self._clock = clock
        self._lock = threading.Lock()
        self._recent = {}
        self._slot = threading.BoundedSemaphore(1)

    def try_acquire(self, company_id, operation):
        if not _positive_int(company_id) or operation not in {
            "proposal", "decision", "history",
        }:
            raise ValueError("gate input is invalid")
        if not self._slot.acquire(blocking=False):
            return None, "busy", 1
        try:
            now = self._clock()
            if type(now) not in {int, float} or not math.isfinite(now):
                raise ValueError("gate clock is invalid")
            bucket = "mutation" if operation in {
                "proposal", "decision",
            } else "history"
            key = (company_id, bucket)
            limit = 10 if bucket == "mutation" else 30
            with self._lock:
                recent = self._recent.setdefault(key, deque())
                boundary = now - 60.0
                while recent and recent[0] <= boundary:
                    recent.popleft()
                if len(recent) >= limit:
                    retry_after = max(
                        1, int(math.ceil(recent[0] + 60.0 - now)),
                    )
                    self._slot.release()
                    return None, "rate", retry_after
                recent.append(now)
            return _GateLease(self._slot), None, None
        except BaseException:
            self._slot.release()
            raise


def _positive_int(value):
    return type(value) is int and 0 < value <= _MAX_ID


def _sha256(value):
    return type(value) is str and _SHA256_RE.fullmatch(value) is not None


def _timestamp(value):
    return type(value) is str and _TIMESTAMP_RE.fullmatch(value) is not None


def _valid_company_allowlist(value):
    return (
        type(value) is frozenset
        and 0 < len(value) <= _MAX_ALLOWED_COMPANIES
        and all(_positive_int(item) for item in value)
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
        {"detail": detail},
        status_code=status_code,
        retry_after=retry_after,
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
            raise ValueError("invalid body")
        size += len(chunk)
        if size > _MAX_BODY_BYTES:
            raise OverflowError("body too large")
        chunks.append(chunk)
    return json.loads(
        b"".join(chunks).decode("utf-8"),
        object_pairs_hook=_unique_object,
    )


def _fixed_error_code(error):
    try:
        state = object.__getattribute__(error, "__dict__")
    except Exception:
        return None
    if type(state) is not dict:
        return None
    code = state.get("code")
    return code if type(code) is str else None


def _kernel_failure(error):
    code = _fixed_error_code(error)
    if code == "human_action_kernel_input_invalid":
        return _error(422, _REQUEST_INVALID)
    if code == "human_action_kernel_authentication_required":
        return _error(401, _AUTHENTICATION_REQUIRED)
    if code == "human_action_kernel_proposal_not_found":
        return _error(404, _NOT_FOUND)
    if code in {
        "human_action_kernel_source_stale",
        "human_action_kernel_proposal_expired",
        "human_action_kernel_proposal_conflict",
        "human_action_kernel_write_conflict",
    }:
        return _error(409, _CONFLICT)
    return _error(503, _UNAVAILABLE, retry_after=30)


def _base_receipt_valid(value, fields):
    return (
        type(value) is dict
        and set(value) == fields
        and value.get("humanActionReceiptVersion") == 1
        and type(value.get("humanActionReceiptVersion")) is int
        and value.get("actionKind") == _ACTION_KIND
        and all(_positive_int(value.get(field)) for field in (
            "proposalId", "companyId", "projectId", "sourceJobId",
            "subjectId", "actorUserId", "actorMembershipId",
        ))
        and value.get("subjectKind") in _SUBJECT_KINDS
        and _sha256(value.get("proposalSha256"))
        and type(value.get("writesAttempted")) is int
        and value["writesAttempted"] >= 0
        and value.get("committed") is True
        and type(value.get("idempotent")) is bool
    )


def _public_proposal(value, company_id, body):
    if (
        not _base_receipt_valid(value, _PROPOSAL_FIELDS)
        or value.get("state") != "proposed"
        or value.get("companyId") != company_id
        or type(body) is not dict
        or type(body.get("selected")) is not dict
        or value.get("projectId") != body.get("projectId")
        or value.get("sourceJobId") != body.get("jobId")
        or value.get("subjectKind") != body["selected"].get("subjectKind")
        or value.get("subjectId") != body["selected"].get("subjectId")
        or not _timestamp(value.get("expiresAt"))
        or value.get("writesAttempted") not in {0, 2}
        or (value["idempotent"] is True) != (value["writesAttempted"] == 0)
    ):
        raise ValueError("invalid proposal receipt")
    return dict(value)


def _public_decision(value, company_id):
    if (
        not _base_receipt_valid(value, _DECISION_FIELDS)
        or value.get("state") not in {"applied", "rejected"}
        or value.get("companyId") != company_id
        or not _positive_int(value.get("eventId"))
        or (
            value["state"] == "applied"
            and not _positive_int(value.get("auditEventId"))
        )
        or (
            value["state"] == "rejected"
            and value.get("auditEventId") is not None
        )
        or value.get("writesAttempted") not in {0, 1, 3}
        or (value["idempotent"] is True) != (value["writesAttempted"] == 0)
    ):
        raise ValueError("invalid decision receipt")
    return dict(value)


def _public_history(value, company_id, project_id, limit):
    if (
        type(value) is not dict
        or set(value) != _HISTORY_FIELDS
        or value.get("humanActionHistoryVersion") != 1
        or type(value.get("humanActionHistoryVersion")) is not int
        or value.get("companyId") != company_id
        or value.get("projectId") != project_id
        or type(value.get("items")) is not list
        or len(value["items"]) > limit
        or (
            value.get("nextBeforeId") is not None
            and not _positive_int(value["nextBeforeId"])
        )
    ):
        raise ValueError("invalid history")
    items = []
    previous_id = None
    for item in value["items"]:
        if (
            type(item) is not dict
            or set(item) != _HISTORY_ITEM_FIELDS
            or not all(_positive_int(item.get(field)) for field in (
                "eventId", "proposalId", "sourceJobId", "subjectId",
                "actorUserId", "actorMembershipId",
            ))
            or (previous_id is not None and item["eventId"] >= previous_id)
            or item.get("eventKind") not in {
                "proposed", "approved", "rejected", "applied",
                "apply_failed",
            }
            or item.get("actionKind") != _ACTION_KIND
            or item.get("subjectKind") not in _SUBJECT_KINDS
            or not _sha256(item.get("proposalSha256"))
            or not _sha256(item.get("eventSha256"))
            or not _timestamp(item.get("occurredAt"))
        ):
            raise ValueError("invalid history")
        previous_id = item["eventId"]
        items.append(dict(item))
    if value.get("nextBeforeId") is not None and (
        not items or value["nextBeforeId"] != items[-1]["eventId"]
    ):
        raise ValueError("invalid history")
    return {**value, "items": items}


def _history_query(request):
    try:
        pairs = list(request.query_params.multi_items())
    except Exception:
        return None
    values = {}
    allowed = {"projectId", "limit", "beforeId"}
    for key, value in pairs:
        if key not in allowed or key in values or type(value) is not str:
            return None
        values[key] = value
    if "projectId" not in values:
        return None
    project_id = _canonical_query_id(values["projectId"])
    page_limit = _canonical_query_id(values.get("limit", "50"))
    before_event_id = (
        None
        if "beforeId" not in values
        else _canonical_query_id(values["beforeId"])
    )
    if (
        project_id is None
        or page_limit is None
        or page_limit > _MAX_HISTORY_LIMIT
        or ("beforeId" in values and before_event_id is None)
    ):
        return None
    return project_id, page_limit, before_event_id


def _authenticate(
    build_authentication,
    request,
    authorization,
    csrf_token,
):
    try:
        authentication = build_authentication(
            request,
            authorization,
            csrf_token,
            require_csrf=True,
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


def register_human_approved_action_routes(app, deps):
    """Register three exact routes only for a strict enabled allowlist."""

    if deps.get("enabled") is not True:
        return None
    allowed_company_ids = deps.get("allowed_company_ids")
    if not _valid_company_allowlist(allowed_company_ids):
        return None

    get_db = deps["get_db"]
    build_authentication = deps["build_cookie_session_authentication"]
    create_proposal = deps["create_review_acknowledgement_proposal"]
    decide = deps["decide_review_acknowledgement"]
    list_history = deps["list_review_acknowledgement_history"]
    gate = deps.get("gate")
    if type(gate) is not _HumanActionRouteGate:
        gate = _HumanActionRouteGate()

    @app.post("/human-approved-actions/proposals")
    async def create_human_action_proposal(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        if request.headers.get("content-type") != "application/json":
            return _error(415, _MEDIA_TYPE_INVALID)
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _REQUEST_INVALID)
        authentication, failure = _authenticate(
            build_authentication, request, authorization, x_csrf_token,
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
        try:
            lease, _reason, retry_after = gate.try_acquire(
                company_id, "proposal",
            )
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if lease is None:
            return _error(429, _BUSY, retry_after=retry_after)
        try:
            try:
                result = create_proposal(
                    get_db,
                    dict(authentication),
                    company_mode=x_company_mode,
                    company_id=x_company_id,
                    body=body,
                )
                return _response(_public_proposal(result, company_id, body))
            except MemoryError:
                raise
            except Exception as error:
                return _kernel_failure(error)
        finally:
            lease.release()

    @app.post("/human-approved-actions/decisions")
    async def decide_human_action(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        if request.headers.get("content-type") != "application/json":
            return _error(415, _MEDIA_TYPE_INVALID)
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _REQUEST_INVALID)
        authentication, failure = _authenticate(
            build_authentication, request, authorization, x_csrf_token,
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
        try:
            lease, _reason, retry_after = gate.try_acquire(
                company_id, "decision",
            )
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if lease is None:
            return _error(429, _BUSY, retry_after=retry_after)
        try:
            try:
                result = decide(
                    get_db,
                    dict(authentication),
                    body,
                    company_mode=x_company_mode,
                    company_id=x_company_id,
                )
                return _response(_public_decision(result, company_id))
            except MemoryError:
                raise
            except Exception as error:
                return _kernel_failure(error)
        finally:
            lease.release()

    @app.get("/human-approved-actions/history")
    def get_human_action_history(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        company_id = _company_id(x_company_id, x_company_mode)
        query = _history_query(request)
        if company_id is None or query is None:
            return _error(422, _REQUEST_INVALID)
        project_id, page_limit, before_event_id = query
        authentication, failure = _authenticate(
            build_authentication, request, authorization, x_csrf_token,
        )
        if failure is not None:
            return failure
        if company_id not in allowed_company_ids:
            return _error(404, _NOT_FOUND)
        try:
            lease, _reason, retry_after = gate.try_acquire(
                company_id, "history",
            )
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if lease is None:
            return _error(429, _BUSY, retry_after=retry_after)
        try:
            try:
                result = list_history(
                    get_db,
                    dict(authentication),
                    company_mode=x_company_mode,
                    company_id=x_company_id,
                    project_id=project_id,
                    before_event_id=before_event_id,
                    limit=page_limit,
                )
                return _response(_public_history(
                    result, company_id, project_id, page_limit,
                ))
            except MemoryError:
                raise
            except Exception as error:
                return _kernel_failure(error)
        finally:
            lease.release()

    return None


def _canonical_query_id(value):
    if (
        type(value) is not str
        or not value
        or len(value) > 19
        or value[0] not in "123456789"
        or not value.isascii()
        or not value.isdecimal()
    ):
        return None
    parsed = int(value)
    return parsed if parsed <= _MAX_ID else None


__all__ = []
