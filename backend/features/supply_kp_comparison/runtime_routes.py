"""Default-off HTTP adapter for one read-only supply comparison."""

import hashlib
import json
import re
from typing import Optional

from fastapi import Header, Query, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError

from .runtime_access import SupplyTechnicalComparisonAccessError
from .source_resolver import SOURCE_KINDS
from .technical_matcher import _REASON_MESSAGES


_MAX_ID = 9223372036854775807
_MAX_ALLOWED_COMPANIES = 100
_MAX_LINES = 100
_PATH = (
    "/supply-requests/{request_id}/technical-comparisons/"
    "{source_kind}/{source_id}"
)
_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, X-Company-Id, X-Company-Mode",
}
_AUTHENTICATION_REQUIRED = (
    "supply_technical_comparison_authentication_required"
)
_REQUEST_FORBIDDEN = "supply_technical_comparison_request_forbidden"
_REQUEST_INVALID = "supply_technical_comparison_request_invalid"
_NOT_FOUND = "supply_technical_comparison_not_found"
_UNAVAILABLE = "supply_technical_comparison_unavailable"
_DECIMAL_RE = re.compile(r"^(?:0|[1-9][0-9]{0,63})(?:\.[0-9]{1,12})?$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_LINE_FIELDS = frozenset({
    "name", "unit", "quantity", "workPackage", "category",
})
_SIGNATURE_FIELDS = frozenset({
    "normalizedName", "family", "dimensions", "diametersMm",
    "threadSizes", "threadGenders", "anglesDeg", "pnClasses",
    "sdrClasses", "reinforcement", "directions", "designFlags",
    "weightsG", "signatureSha256",
})
_RESULT_FIELDS = frozenset({
    "contractVersion", "status", "decision", "confidence",
    "confidenceBasisPoints", "reasonCodes", "reasons",
    "requiredSignature", "offeredSignature", "comparisonSha256",
    "writesAttempted", "modelCalls", "automaticApprovalAllowed",
})
_OUTER_FIELDS = frozenset({
    "ok", "dryRun", "contractVersion", "companyId", "projectId",
    "requestId", "sourceKind", "sourceId", "file",
    "requestedLineCount", "offeredLineCount", "comparisonCount",
    "comparisons", "resultSha256", "automaticApprovalAllowed",
    "writesAttempted", "modelCalls", "readOnlyTransaction", "rolledBack",
})


def _response(content, *, status_code=200, retry_after=None):
    headers = dict(_HEADERS)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _error(status_code, detail, *, retry_after=None):
    return _response(
        {"detail": detail}, status_code=status_code, retry_after=retry_after,
    )


def _valid_allowlist(value):
    return (
        type(value) is frozenset
        and 0 < len(value) <= _MAX_ALLOWED_COMPANIES
        and all(type(item) is int and 0 < item <= _MAX_ID for item in value)
    )


def _valid_roles(value):
    return (
        type(value) is tuple
        and 0 < len(value) <= 10
        and len(value) == len(set(value))
        and all(
            type(item) is str and 0 < len(item.encode("utf-8")) <= 64
            for item in value
        )
    )


def _id(value):
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


def _company_id(value, mode):
    if type(mode) is not str or mode != "company":
        return None
    return _id(value)


def _valid_authentication(value):
    return (
        type(value) is dict
        and set(value) == {"authenticationKind", "sessionHash"}
        and value.get("authenticationKind") == "cookie_session"
        and type(value.get("sessionHash")) is str
        and _SHA_RE.fullmatch(value["sessionHash"]) is not None
    )


def _bounded_text(value, maximum, *, allow_empty=False):
    return (
        type(value) is str
        and "\x00" not in value
        and (allow_empty or bool(value))
        and len(value.encode("utf-8")) <= maximum
    )


def _sha(value):
    return type(value) is str and _SHA_RE.fullmatch(value) is not None


def _canonical_sha(value):
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _public_line(value):
    if type(value) is not dict or set(value) != _LINE_FIELDS:
        raise ValueError
    if (
        not _bounded_text(value.get("name"), 4096)
        or not _bounded_text(value.get("unit"), 64)
        or type(value.get("quantity")) is not str
        or _DECIMAL_RE.fullmatch(value["quantity"]) is None
        or not _bounded_text(value.get("workPackage"), 512)
        or not _bounded_text(value.get("category"), 512, allow_empty=True)
    ):
        raise ValueError
    return {name: value[name] for name in _LINE_FIELDS}


def _public_signature(value):
    if type(value) is not dict or set(value) != _SIGNATURE_FIELDS:
        raise ValueError
    if (
        not _bounded_text(value.get("normalizedName"), 4096, allow_empty=True)
        or not _bounded_text(value.get("family"), 128, allow_empty=True)
        or not _sha(value.get("signatureSha256"))
    ):
        raise ValueError
    result = {
        "normalizedName": value["normalizedName"],
        "family": value["family"],
    }
    for name in (
        "dimensions", "diametersMm", "threadSizes", "threadGenders",
        "pnClasses", "sdrClasses", "reinforcement", "directions",
        "designFlags", "weightsG",
    ):
        items = value.get(name)
        if (
            type(items) is not list
            or len(items) > 100
            or not all(_bounded_text(item, 256) for item in items)
        ):
            raise ValueError
        result[name] = list(items)
    angles = value.get("anglesDeg")
    if (
        type(angles) is not list
        or len(angles) > 100
        or not all(type(item) is int and 0 <= item <= 360 for item in angles)
    ):
        raise ValueError
    result["anglesDeg"] = list(angles)
    result["signatureSha256"] = value["signatureSha256"]
    return result


def _public_pair_result(value):
    if type(value) is not dict or set(value) != _RESULT_FIELDS:
        raise ValueError
    basis = value.get("confidenceBasisPoints")
    reason_codes = value.get("reasonCodes")
    expected_reasons = None
    if type(reason_codes) is list and len(reason_codes) <= 50:
        try:
            expected_reasons = [_REASON_MESSAGES[code] for code in reason_codes]
        except Exception:
            expected_reasons = None
    if (
        value.get("contractVersion") != 1
        or value.get("status") not in {"ok", "review", "blocked"}
        or value.get("decision") not in {
            "exact", "comparable", "review_required", "incompatible",
        }
        or type(basis) is not int
        or not 0 <= basis <= 10000
        or type(value.get("confidence")) not in (int, float)
        or value["confidence"] != round(basis / 10000, 4)
        or expected_reasons is None
        or value.get("reasons") != expected_reasons
        or not _sha(value.get("comparisonSha256"))
        or value.get("writesAttempted") != 0
        or value.get("modelCalls") != 0
        or value.get("automaticApprovalAllowed") is not False
    ):
        raise ValueError
    return {
        "contractVersion": 1,
        "status": value["status"],
        "decision": value["decision"],
        "confidence": value["confidence"],
        "confidenceBasisPoints": basis,
        "reasonCodes": list(reason_codes),
        "reasons": list(expected_reasons),
        "requiredSignature": _public_signature(value.get("requiredSignature")),
        "offeredSignature": _public_signature(value.get("offeredSignature")),
        "comparisonSha256": value["comparisonSha256"],
        "writesAttempted": 0,
        "modelCalls": 0,
        "automaticApprovalAllowed": False,
    }


def _validated_public_result(value, selectors):
    if type(value) is not dict or set(value) != _OUTER_FIELDS:
        raise ValueError
    if (
        value.get("ok") is not True
        or value.get("dryRun") is not True
        or value.get("contractVersion") != 1
        or value.get("companyId") != selectors["company_id"]
        or value.get("projectId") != selectors["project_id"]
        or value.get("requestId") != selectors["request_id"]
        or value.get("sourceKind") != selectors["source_kind"]
        or value.get("sourceId") != selectors["source_id"]
        or value.get("automaticApprovalAllowed") is not False
        or value.get("writesAttempted") != 0
        or value.get("modelCalls") != 0
        or value.get("readOnlyTransaction") is not True
        or value.get("rolledBack") is not True
    ):
        raise ValueError
    file_value = value.get("file")
    if (
        type(file_value) is not dict
        or set(file_value) != {
            "id", "contentUrl", "context", "originalName", "contentType",
        }
        or file_value.get("id") != selectors["file_id"]
        or file_value.get("contentUrl")
        != "/tenant-files/{}/content".format(selectors["file_id"])
        or not _bounded_text(file_value.get("context"), 100)
        or not _bounded_text(
            file_value.get("originalName"), 1024, allow_empty=True,
        )
        or not _bounded_text(
            file_value.get("contentType"), 255, allow_empty=True,
        )
    ):
        raise ValueError
    comparisons = value.get("comparisons")
    count = value.get("comparisonCount")
    if (
        type(comparisons) is not list
        or type(count) is not int
        or not 1 <= count <= _MAX_LINES
        or len(comparisons) != count
        or value.get("requestedLineCount") != count
        or value.get("offeredLineCount") != count
    ):
        raise ValueError
    public_comparisons = []
    hashes = []
    for index, item in enumerate(comparisons, start=1):
        if (
            type(item) is not dict
            or set(item) != {"lineNumber", "required", "offered", "result"}
            or item.get("lineNumber") != index
        ):
            raise ValueError
        pair = _public_pair_result(item.get("result"))
        hashes.append(pair["comparisonSha256"])
        public_comparisons.append({
            "lineNumber": index,
            "required": _public_line(item.get("required")),
            "offered": _public_line(item.get("offered")),
            "result": pair,
        })
    expected_hash = _canonical_sha({
        "contractVersion": 1,
        "companyId": selectors["company_id"],
        "projectId": selectors["project_id"],
        "requestId": selectors["request_id"],
        "sourceKind": selectors["source_kind"],
        "sourceId": selectors["source_id"],
        "fileId": selectors["file_id"],
        "comparisonHashes": hashes,
    })
    if value.get("resultSha256") != expected_hash:
        raise ValueError
    return {
        "ok": True,
        "dryRun": True,
        "contractVersion": 1,
        "companyId": selectors["company_id"],
        "projectId": selectors["project_id"],
        "requestId": selectors["request_id"],
        "sourceKind": selectors["source_kind"],
        "sourceId": selectors["source_id"],
        "file": {
            "id": file_value["id"],
            "contentUrl": file_value["contentUrl"],
            "context": file_value["context"],
            "originalName": file_value["originalName"],
            "contentType": file_value["contentType"],
        },
        "requestedLineCount": count,
        "offeredLineCount": count,
        "comparisonCount": count,
        "comparisons": public_comparisons,
        "resultSha256": expected_hash,
        "automaticApprovalAllowed": False,
        "writesAttempted": 0,
        "modelCalls": 0,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }


def register_supply_technical_comparison_routes(app, deps):
    """Register one exact GET resource only for an enabled allowlist."""

    if deps.get("enabled") is not True:
        return None
    allowed_company_ids = deps.get("allowed_company_ids")
    allowed_roles = deps.get("allowed_roles")
    if not _valid_allowlist(allowed_company_ids) or not _valid_roles(allowed_roles):
        return None

    get_db = deps["get_db"]
    build_authentication = deps["build_cookie_session_authentication"]
    run_comparison = deps["run_authorized_supply_technical_comparison"]

    @app.get(_PATH)
    def get_supply_technical_comparison(
        request_id: str,
        source_kind: str,
        source_id: str,
        request: Request,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        file_id: Optional[str] = Query(default=None, alias="fileId"),
        authorization: Optional[str] = Header(default=None),
        x_company_id: Optional[str] = Header(
            default=None, alias="X-Company-Id",
        ),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        selectors = {
            "company_id": _company_id(x_company_id, x_company_mode),
            "project_id": _id(project_id),
            "request_id": _id(request_id),
            "source_kind": source_kind,
            "source_id": _id(source_id),
            "file_id": _id(file_id),
        }
        if (
            None in selectors.values()
            or request.query_params.getlist("projectId") != [project_id]
            or request.query_params.getlist("fileId") != [file_id]
            or request.headers.getlist("X-Company-Id") != [x_company_id]
            or request.headers.getlist("X-Company-Mode") != [x_company_mode]
            or type(source_kind) is not str
            or source_kind not in SOURCE_KINDS
        ):
            return _error(422, _REQUEST_INVALID)
        try:
            authentication = build_authentication(
                request,
                authorization,
                None,
                require_csrf=False,
            )
        except CookieSessionAuthenticationError as error:
            if error.code == "cookie_session_csrf_invalid":
                return _error(403, _REQUEST_FORBIDDEN)
            return _error(401, _AUTHENTICATION_REQUIRED)
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if not _valid_authentication(authentication):
            return _error(503, _UNAVAILABLE, retry_after=30)
        if selectors["company_id"] not in allowed_company_ids:
            return _error(404, _NOT_FOUND)
        try:
            result = run_comparison(
                get_db,
                authentication,
                allowed_roles,
                **selectors,
            )
            public = _validated_public_result(result, selectors)
        except MemoryError:
            raise
        except SupplyTechnicalComparisonAccessError as error:
            if error.code == "supply_technical_comparison_access_not_found":
                return _error(404, _NOT_FOUND)
            return _error(503, _UNAVAILABLE, retry_after=30)
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        return _response(public)

    return None


__all__ = []
