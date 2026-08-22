"""Default-off cookie/CSRF HTTP adapter for assignment/daily previews."""

import json
from typing import Optional

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError

from .assignment_projection import (
    AssignmentDraft,
    AssignmentDraftItem,
    AssignmentDraftScope,
    AssignmentDraftSummary,
)
from .projection import (
    AssignmentDailyDraftScope,
    DailyWorkDraft,
    DailyWorkDraftItem,
    DailyWorkDraftSummary,
)
from .runtime_preview import AssignmentDailyPreviewError
from .snapshot import AssignmentDailySnapshot, AssignmentDailySnapshotRequest


_MAX_ID = 9223372036854775807
_MAX_ALLOWED_COMPANIES = 100
_MAX_BODY_BYTES = 4096
_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, X-Company-Id, X-Company-Mode",
}
_INPUT_INVALID = "assignment_daily_snapshot_input_invalid"
_NOT_FOUND = "assignment_daily_preview_not_found"
_REVIEW_CODES = frozenset({
    "assignment_snapshot_source_not_found",
    "assignment_snapshot_source_ambiguous",
    "assignment_snapshot_payload_too_large",
    "assignment_snapshot_project_ambiguous",
    "assignment_snapshot_version_stale",
    "assignment_snapshot_source_invalid",
    "assignment_snapshot_lineage_invalid",
    "assignment_source_invalid",
    "assignment_source_duplicate",
    "assignment_lineage_invalid",
    "assignment_balance_invalid",
    "assignment_draft_scan_limit_exceeded",
    "daily_work_source_invalid",
    "daily_work_source_duplicate",
    "daily_work_scan_limit_exceeded",
})


def _response(content, status_code=200):
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=dict(_RESPONSE_HEADERS),
    )


def _error(status_code, detail):
    return _response({"detail": detail}, status_code)


def _valid_allowlist(value):
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
        and type(value.get("sessionHash")) is str
        and len(value["sessionHash"]) == 64
        and all(character in "0123456789abcdef" for character in value["sessionHash"])
    )


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


def _request_from_body(company_id, body):
    if type(body) is not dict or set(body) != {
        "projectId", "date", "estimateId", "estimateVersionId",
        "workPackage",
    }:
        raise ValueError("invalid body")
    try:
        return AssignmentDailySnapshotRequest(
            company_id=company_id,
            project_id=body["projectId"],
            date=body["date"],
            estimate_id=body["estimateId"],
            estimate_version_id=body["estimateVersionId"],
            work_package=body["workPackage"],
        )
    except (TypeError, ValueError):
        raise ValueError("invalid body") from None


def _exact_int(value, *, minimum=0):
    return type(value) is int and value >= minimum


def _exact_text(value):
    return type(value) is str


def _review(value):
    if (
        type(value) is not tuple
        or len(value) != len(set(value))
        or not all(
            _exact_text(item) and item in _REVIEW_CODES
            for item in value
        )
    ):
        raise ValueError("invalid preview")
    return list(value)


def _assignment_result(value, request):
    if (
        type(value) is not AssignmentDraft
        or value.state not in {"ready", "clear", "review_required"}
        or type(value.scope) is not AssignmentDraftScope
        or value.scope != AssignmentDraftScope(
            request.company_id,
            request.project_id,
            request.estimate_id,
            request.estimate_version_id,
            request.work_package,
        )
        or type(value.summary) is not AssignmentDraftSummary
        or type(value.items) is not tuple
    ):
        raise ValueError("invalid preview")
    items = []
    for item in value.items:
        if (
            type(item) is not AssignmentDraftItem
            or not all(_exact_int(getattr(item, field), minimum=1) for field in (
                "source_estimate_id", "source_estimate_version_id",
            ))
            or not all(_exact_int(getattr(item, field)) for field in (
                "section_index", "item_index",
            ))
            or not all(_exact_text(getattr(item, field)) for field in (
                "item_key", "section_name", "item_name", "unit",
                "estimate_quantity", "assigned_quantity",
                "available_quantity", "work_package",
            ))
            or item.source_estimate_id != request.estimate_id
            or item.source_estimate_version_id != request.estimate_version_id
            or item.work_package != request.work_package
            or item.assignee is not None
        ):
            raise ValueError("invalid preview")
        items.append({
            "sourceEstimateId": item.source_estimate_id,
            "sourceEstimateVersionId": item.source_estimate_version_id,
            "sectionIndex": item.section_index,
            "itemIndex": item.item_index,
            "itemKey": item.item_key,
            "sectionName": item.section_name,
            "itemName": item.item_name,
            "unit": item.unit,
            "estimateQuantity": item.estimate_quantity,
            "assignedQuantity": item.assigned_quantity,
            "availableQuantity": item.available_quantity,
            "workPackage": item.work_package,
            "assignee": None,
        })
    summary = value.summary
    if not all(_exact_int(getattr(summary, field)) for field in (
        "source_work_rows", "available_rows", "fully_assigned_rows",
    )):
        raise ValueError("invalid preview")
    review = _review(value.review_codes)
    if (
        (value.state == "ready" and (not items or review))
        or (value.state == "clear" and (items or review))
        or (value.state == "review_required" and (items or not review))
    ):
        raise ValueError("invalid preview")
    return {
        "state": value.state,
        "items": items,
        "summary": {
            "sourceWorkRows": summary.source_work_rows,
            "availableRows": summary.available_rows,
            "fullyAssignedRows": summary.fully_assigned_rows,
        },
        "review": review,
    }


def _daily_result(value, request):
    if (
        type(value) is not DailyWorkDraft
        or value.state not in {"ready", "clear", "review_required"}
        or type(value.scope) is not AssignmentDailyDraftScope
        or value.scope != AssignmentDailyDraftScope(
            request.company_id,
            request.project_id,
            request.date,
        )
        or type(value.summary) is not DailyWorkDraftSummary
        or type(value.items) is not tuple
    ):
        raise ValueError("invalid preview")
    items = []
    for item in value.items:
        if (
            type(item) is not DailyWorkDraftItem
            or not _exact_int(item.source_id, minimum=1)
            or (
                item.responsible_id is not None
                and not _exact_int(item.responsible_id, minimum=1)
            )
            or not all(_exact_text(getattr(item, field)) for field in (
                "description", "unit", "quantity", "responsible_name",
                "work_package", "status",
            ))
        ):
            raise ValueError("invalid preview")
        items.append({
            "sourceId": item.source_id,
            "description": item.description,
            "unit": item.unit,
            "quantity": item.quantity,
            "responsibleId": item.responsible_id,
            "responsibleName": item.responsible_name,
            "workPackage": item.work_package,
            "status": item.status,
        })
    summary = value.summary
    if not all(_exact_int(getattr(summary, field)) for field in (
        "confirmed_rows", "work_packages", "responsible_people",
    )):
        raise ValueError("invalid preview")
    review = _review(value.review_codes)
    if (
        (value.state == "ready" and (not items or review))
        or (value.state == "clear" and (items or review))
        or (value.state == "review_required" and (items or not review))
    ):
        raise ValueError("invalid preview")
    return {
        "state": value.state,
        "items": items,
        "summary": {
            "confirmedRows": summary.confirmed_rows,
            "workPackages": summary.work_packages,
            "responsiblePeople": summary.responsible_people,
        },
        "review": review,
    }


def _public_result(value, request):
    if (
        type(value) is not AssignmentDailySnapshot
        or value.request != request
        or value.state not in {"ready", "clear", "review_required"}
    ):
        raise ValueError("invalid preview")
    assignment = _assignment_result(value.assignment_draft, request)
    daily = _daily_result(value.daily_work_draft, request)
    review = _review(value.review_codes)
    if (
        (
            value.state == "ready"
            and (
                review
                or "review_required" in (assignment["state"], daily["state"])
                or "ready" not in (assignment["state"], daily["state"])
            )
        )
        or (
            value.state == "clear"
            and (
                review
                or assignment["state"] != "clear"
                or daily["state"] != "clear"
            )
        )
        or (
            value.state == "review_required"
            and not (
                review
                or "review_required" in (assignment["state"], daily["state"])
            )
        )
    ):
        raise ValueError("invalid preview")
    return {
        "version": 1,
        "state": value.state,
        "companyId": request.company_id,
        "projectId": request.project_id,
        "date": request.date,
        "assignmentDraft": assignment,
        "dailyWorkDraft": daily,
        "review": review,
        "previewOnly": True,
        "applyAllowed": False,
        "writesAttempted": 0,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }


def _error_code(error):
    if type(error) is AssignmentDailyPreviewError and len(error.args) == 1:
        return error.args[0] if type(error.args[0]) is str else None
    return None


def register_assignment_daily_draft_preview_routes(app, deps):
    """Register one POST preview only for an exact enabled allowlist."""

    if deps.get("enabled") is not True:
        return None
    allowed_company_ids = deps.get("allowed_company_ids")
    if not _valid_allowlist(allowed_company_ids):
        return None

    get_db = deps["get_db"]
    build_authentication = deps["build_cookie_session_authentication"]
    run_preview = deps["run_authorized_assignment_daily_snapshot"]

    @app.post("/assignment-daily-draft-previews")
    async def create_assignment_daily_draft_preview(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
    ):
        if request.headers.get("content-type") != "application/json":
            return _error(415, "assignment_daily_preview_media_type_invalid")
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _INPUT_INVALID)
        try:
            authentication = build_authentication(
                request,
                authorization,
                x_csrf_token,
                require_csrf=True,
            )
        except CookieSessionAuthenticationError as error:
            if error.code == "cookie_session_csrf_invalid":
                return _error(403, "assignment_daily_preview_request_forbidden")
            return _error(401, "assignment_daily_preview_authentication_required")
        except MemoryError:
            raise
        except Exception:
            return _error(503, "assignment_daily_preview_unavailable")
        if not _valid_authentication(authentication):
            return _error(503, "assignment_daily_preview_unavailable")
        if company_id not in allowed_company_ids:
            return _error(404, _NOT_FOUND)
        try:
            body = await _json_body(request)
            snapshot_request = _request_from_body(company_id, body)
        except MemoryError:
            raise
        except OverflowError:
            return _error(413, "assignment_daily_preview_request_too_large")
        except Exception:
            return _error(422, _INPUT_INVALID)
        try:
            result = run_preview(
                get_db,
                dict(authentication),
                snapshot_request,
            )
            public = _public_result(result, snapshot_request)
        except MemoryError:
            raise
        except Exception as error:
            code = _error_code(error)
            if code == _NOT_FOUND:
                return _error(404, _NOT_FOUND)
            if code == _INPUT_INVALID:
                return _error(422, _INPUT_INVALID)
            return _error(503, "assignment_daily_preview_unavailable")
        return _response(public)

    return None


__all__ = []
