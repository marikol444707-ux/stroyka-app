"""Cookie-only HTTP boundary for supplier-material capability review."""

import json
import re
from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError

from .material_capability_proof import SupplierMaterialCapabilityProofError
from .material_capability_runtime import MaterialCapabilityRuntimeError
from .material_capability_source_resolver import (
    MaterialCapabilitySourceResolverError,
)
from .material_capability_writer import MaterialCapabilityWriterError


_SELECTOR_INVALID = "supply_supplier_material_route_selector_invalid"
_CONFIRMATION_PAYLOAD_INVALID = (
    "supply_supplier_material_confirmation_payload_invalid"
)
_REVOCATION_PAYLOAD_INVALID = (
    "supply_supplier_material_revocation_payload_invalid"
)
_RUNTIME_FAILED = "supply_supplier_material_runtime_failed"
_CONFIRMATION_FIELDS = {
    "companySupplierLinkId", "supplierId", "confirmationSubjectSha256",
}
_RECEIPT_FIELDS = {
    "writeVersion", "ok", "eventKind", "state", "companyId",
    "companySupplierLinkId", "supplierId", "materialIdentitySha256",
    "confirmationSubjectSha256", "assertionId", "revokesAssertionId",
    "actorUserId", "actorMembershipId", "writesAttempted", "committed",
}
_POSITIVE_RE = re.compile(r"^[1-9][0-9]*$")
_NON_NEGATIVE_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_BODY_BYTES = 4096
_ABSENT_BODY = object()


def _path_int(value, *, allow_zero=False):
    if type(value) is not str:
        return None
    pattern = _NON_NEGATIVE_RE if allow_zero else _POSITIVE_RE
    if len(value) > 19 or pattern.fullmatch(value) is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed <= 9223372036854775807 else None


def _company_id(value, mode):
    if type(mode) is not str or mode != "company":
        return None
    return _path_int(value)


async def _json_body(request, *, absent_allowed=False):
    try:
        raw = await request.body()
    except Exception:
        return None, False
    if len(raw) > _MAX_BODY_BYTES:
        return None, False
    if not raw.strip():
        return (_ABSENT_BODY, True) if absent_allowed else (None, False)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, TypeError, ValueError, json.JSONDecodeError):
        return None, False
    return value, True


def _confirmation_payload(value):
    if type(value) is not dict or set(value) != _CONFIRMATION_FIELDS:
        return None
    link_id = value.get("companySupplierLinkId")
    supplier_id = value.get("supplierId")
    subject_sha256 = value.get("confirmationSubjectSha256")
    if (
        type(link_id) is not int
        or isinstance(link_id, bool)
        or link_id <= 0
        or type(supplier_id) is not int
        or isinstance(supplier_id, bool)
        or supplier_id <= 0
        or type(subject_sha256) is not str
        or _SHA256_RE.fullmatch(subject_sha256) is None
    ):
        return None
    return dict(value)


def _validated_bundle(value, selectors):
    if type(value) is not dict or set(value) != {
        "proof", "combinedReport", "selected",
    }:
        raise MaterialCapabilityRuntimeError(
            "supply_supplier_material_runtime_read_failed"
        )
    selected = value.get("selected")
    if (
        type(value.get("proof")) is not dict
        or type(value.get("combinedReport")) is not dict
        or type(selected) is not dict
        or selected != {
            "requestId": selectors["requestId"],
            "requestItemIndex": selectors["requestItemIndex"],
        }
    ):
        raise MaterialCapabilityRuntimeError(
            "supply_supplier_material_runtime_read_failed"
        )
    return value


def _validated_receipt(value, *, event_kind, company_id):
    if type(value) is not dict or set(value) != _RECEIPT_FIELDS:
        raise MaterialCapabilityWriterError(
            "supply_supplier_material_writer_write_failed"
        )
    state = value.get("state")
    idempotent_state = "already_" + event_kind
    positive_fields = (
        "companyId", "companySupplierLinkId", "supplierId", "assertionId",
        "actorUserId", "actorMembershipId",
    )
    revoke_id = value.get("revokesAssertionId")
    if (
        value.get("writeVersion") != 1
        or type(value.get("writeVersion")) is not int
        or value.get("ok") is not True
        or type(value.get("eventKind")) is not str
        or value.get("eventKind") != event_kind
        or value.get("companyId") != company_id
        or any(
            type(value.get(field)) is not int or value.get(field) <= 0
            for field in positive_fields
        )
        or type(value.get("materialIdentitySha256")) is not str
        or _SHA256_RE.fullmatch(value["materialIdentitySha256"]) is None
        or type(value.get("confirmationSubjectSha256")) is not str
        or _SHA256_RE.fullmatch(value["confirmationSubjectSha256"]) is None
        or (
            (event_kind == "confirmed" and revoke_id is not None)
            or (
                event_kind == "revoked"
                and (type(revoke_id) is not int or revoke_id <= 0)
            )
        )
        or type(state) is not str
        or state not in {event_kind, idempotent_state}
        or type(value.get("writesAttempted")) is not int
        or value.get("writesAttempted") != (0 if state == idempotent_state else 1)
        or value.get("committed") is not (state == event_kind)
    ):
        raise MaterialCapabilityWriterError(
            "supply_supplier_material_writer_write_failed"
        )
    return value


def _raise_public(exc):
    code = getattr(exc, "code", "")
    if isinstance(exc, CookieSessionAuthenticationError):
        status = 403 if code == "cookie_session_csrf_invalid" else 401
        raise HTTPException(status_code=status, detail=code)
    if isinstance(exc, MaterialCapabilitySourceResolverError):
        status = {
            "supply_supplier_material_source_input_invalid": 422,
            "supply_supplier_material_source_not_found": 404,
            "supply_supplier_material_source_invalid": 409,
        }.get(code, 500)
        detail = code if status != 500 else _RUNTIME_FAILED
        raise HTTPException(status_code=status, detail=detail)
    if isinstance(exc, SupplierMaterialCapabilityProofError):
        if code == "supply_supplier_material_schema_not_ready":
            raise HTTPException(status_code=503, detail=code)
        raise HTTPException(status_code=500, detail=_RUNTIME_FAILED)
    if isinstance(exc, MaterialCapabilityRuntimeError):
        status = {
            "supply_supplier_material_runtime_input_invalid": 422,
            "supply_supplier_material_runtime_authentication_required": 401,
        }.get(code, 500)
        detail = code if status != 500 else _RUNTIME_FAILED
        raise HTTPException(status_code=status, detail=detail)
    if isinstance(exc, MaterialCapabilityWriterError):
        status = {
            "supply_supplier_material_writer_input_invalid": 422,
            "supply_supplier_material_writer_authentication_required": 403,
            "supply_supplier_material_writer_target_invalid": 404,
            "supply_supplier_material_writer_subject_stale": 409,
            "supply_supplier_material_writer_subject_terminal": 409,
            "supply_supplier_material_writer_tenant_mismatch": 409,
            "supply_supplier_material_writer_evidence_invalid": 409,
            "supply_supplier_material_writer_write_conflict": 409,
            "supply_supplier_material_writer_schema_not_ready": 503,
            "supply_supplier_material_writer_commit_outcome_unknown": 503,
        }.get(code, 500)
        detail = code if status != 500 else _RUNTIME_FAILED
        raise HTTPException(status_code=status, detail=detail)
    raise HTTPException(status_code=500, detail=_RUNTIME_FAILED)


def register_material_capability_runtime_module(app, deps):
    """Register the three reviewed routes only when explicitly enabled."""

    if deps.get("enabled") is not True:
        return None
    get_db = deps["get_db"]
    build_authentication = deps["build_cookie_session_authentication"]
    run_runtime_read = deps["run_material_capability_runtime_read"]
    confirm = deps["run_material_capability_confirmation_write"]
    revoke = deps["run_material_capability_revocation_write"]

    @app.get(
        "/supply-requests/{request_id}/items/{request_item_index}/"
        "material-capability-proof"
    )
    async def material_capability_proof_read(
        request_id: str,
        request_item_index: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_company_id: Optional[str] = Header(
            default=None, alias="X-Company-Id",
        ),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        company_id = _company_id(x_company_id, x_company_mode)
        parsed_request_id = _path_int(request_id)
        parsed_item_index = _path_int(request_item_index, allow_zero=True)
        if None in (company_id, parsed_request_id, parsed_item_index):
            raise HTTPException(status_code=422, detail=_SELECTOR_INVALID)
        try:
            authentication = build_authentication(
                request, authorization, None, require_csrf=False,
            )
            selectors = {
                "companyId": company_id,
                "requestId": parsed_request_id,
                "requestItemIndex": parsed_item_index,
            }
            bundle = _validated_bundle(
                run_runtime_read(get_db, authentication, selectors),
                selectors,
            )
            return bundle["proof"]
        except HTTPException:
            raise
        except Exception as exc:
            _raise_public(exc)

    @app.post(
        "/supply-requests/{request_id}/items/{request_item_index}/"
        "material-capability-confirmations"
    )
    async def material_capability_confirm(
        request_id: str,
        request_item_index: str,
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
        company_id = _company_id(x_company_id, x_company_mode)
        parsed_request_id = _path_int(request_id)
        parsed_item_index = _path_int(request_item_index, allow_zero=True)
        body, decoded = await _json_body(request)
        payload = _confirmation_payload(body) if decoded else None
        if (
            None in (company_id, parsed_request_id, parsed_item_index)
            or payload is None
        ):
            detail = (
                _SELECTOR_INVALID
                if None in (company_id, parsed_request_id, parsed_item_index)
                else _CONFIRMATION_PAYLOAD_INVALID
            )
            raise HTTPException(status_code=422, detail=detail)
        try:
            authentication = build_authentication(
                request,
                authorization,
                x_csrf_token,
                require_csrf=True,
            )
            selectors = {
                "companyId": company_id,
                "requestId": parsed_request_id,
                "requestItemIndex": parsed_item_index,
            }
            bundle = _validated_bundle(
                run_runtime_read(get_db, authentication, selectors),
                selectors,
            )
            receipt = _validated_receipt(
                confirm(
                    get_db,
                    bundle["combinedReport"],
                    bundle["selected"],
                    authentication,
                    {"companyId": company_id, **payload},
                ),
                event_kind="confirmed",
                company_id=company_id,
            )
            status = 200 if receipt["state"] == "already_confirmed" else 201
            return JSONResponse(status_code=status, content=receipt)
        except HTTPException:
            raise
        except Exception as exc:
            _raise_public(exc)

    @app.post(
        "/supplier-material-capability-confirmations/"
        "{confirmation_assertion_id}/revocations"
    )
    async def material_capability_revoke(
        confirmation_assertion_id: str,
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
        company_id = _company_id(x_company_id, x_company_mode)
        assertion_id = _path_int(confirmation_assertion_id)
        body, decoded = await _json_body(request, absent_allowed=True)
        if company_id is None or assertion_id is None:
            raise HTTPException(status_code=422, detail=_SELECTOR_INVALID)
        if not decoded or not (
            body is _ABSENT_BODY or (type(body) is dict and body == {})
        ):
            raise HTTPException(
                status_code=422, detail=_REVOCATION_PAYLOAD_INVALID,
            )
        try:
            authentication = build_authentication(
                request,
                authorization,
                x_csrf_token,
                require_csrf=True,
            )
            receipt = _validated_receipt(
                revoke(
                    get_db,
                    authentication,
                    {
                        "companyId": company_id,
                        "confirmationAssertionId": assertion_id,
                    },
                ),
                event_kind="revoked",
                company_id=company_id,
            )
            status = 200 if receipt["state"] == "already_revoked" else 201
            return JSONResponse(status_code=status, content=receipt)
        except HTTPException:
            raise
        except Exception as exc:
            _raise_public(exc)

    return None


__all__ = ["register_material_capability_runtime_module"]
