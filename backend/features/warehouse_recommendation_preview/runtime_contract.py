"""Private DB-free selectors and disclosure contract for A9.3."""

from types import MappingProxyType
from typing import NamedTuple

from backend.features.warehouse_recommendation_preview import (
    content_contract as _content_contract,
)


_INPUT_INVALID = "warehouse_anomaly_runtime_input_invalid"
_AUTHENTICATION_REQUIRED = (
    "warehouse_anomaly_runtime_authentication_required"
)
_RESOURCE_NOT_FOUND = "warehouse_anomaly_runtime_resource_not_found"
_CONTRACT_INVALID = "warehouse_anomaly_runtime_contract_invalid"
_MAX_ID = 9223372036854775807
_AUTHENTICATION_FIELDS = frozenset({
    "authenticationKind", "sessionHash",
})
_BODY_FIELDS = frozenset({"projectId", "jobId", "selected"})
_SELECTION_FIELDS = frozenset({
    "subjectKind", "subjectId", "anomalyCode",
})
_INTERNAL_RESULT_FIELDS = frozenset({
    "warehouseAnomalyContentVersion",
    "ok",
    "dryRun",
    "writesAttempted",
    "previewOnly",
    "stockMovementAllowed",
    "inventoryAdjustmentAllowed",
    "applyAllowed",
    "state",
    "source",
    "candidate",
    "content",
    "blockers",
    "contentSha256",
    "readOnlyTransaction",
    "rolledBack",
})
_INTERNAL_SOURCE_FIELDS = frozenset({
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
    "reconciliationId",
    "baseEstimateId",
    "reconciliationStatus",
    "revalidatedRelevantEvidenceSha256",
})
_CANDIDATE_FIELDS = frozenset({
    "subjectKind", "subjectId", "anomalyCode", "recommendationCode",
})
_CONTENT_FIELDS = frozenset({"title", "finding", "nextSafeAction"})
_RECONCILIATION_STATUSES = frozenset({
    "Черновик", "На проверке", "Утверждена", "Отклонена",
})
_PUBLIC_BLOCKERS = MappingProxyType({
    "blocked": "warehouse_anomaly_preview_blocked",
    "stale": "warehouse_anomaly_preview_stale",
})
_SELECTION_RULES = MappingProxyType({
    "warehouse_invoice_request_mismatch": "warehouseInvoice",
    "warehouse_invoice_project_mismatch": "warehouseInvoice",
    "warehouse_invoice_delivery_mismatch": "warehouseInvoice",
    "warehouse_invoice_supplier_invoice_mismatch": "warehouseInvoice",
    "warehouse_invoice_items_invalid": "warehouseInvoice",
    "warehouse_receipt_invoice_mismatch": "warehouseHistory",
    "warehouse_receipt_line_invalid": "warehouseHistory",
    "warehouse_receipt_package_mismatch": "warehouseHistory",
    "warehouse_receipt_lot_invoice_mismatch": "receiptLot",
    "warehouse_receipt_lot_line_invalid": "receiptLot",
    "warehouse_receipt_lot_project_mismatch": "receiptLot",
    "warehouse_movement_invoice_mismatch": "warehouseMovement",
    "warehouse_movement_line_invalid": "warehouseMovement",
    "warehouse_movement_package_mismatch": "warehouseMovement",
    "warehouse_movement_lot_missing": "warehouseMovement",
    "warehouse_lot_movement_missing": "warehouseMovement",
    "warehouse_lot_movement_parent_mismatch": "lotMovement",
    "warehouse_lot_movement_source_mismatch": "lotMovement",
})


class _WarehouseAnomalyRuntimeContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _WarehouseAnomalySelection(NamedTuple):
    subject_kind: str
    subject_id: int
    anomaly_code: str


class _WarehouseAnomalyRuntimeClaims(NamedTuple):
    session_hash: str
    company_id: int
    project_id: int
    job_id: int
    selection: _WarehouseAnomalySelection


def _raise_fixed_error(error):
    try:
        raise error from None
    except _WarehouseAnomalyRuntimeContractError as raised:
        raised.__context__ = None
        raise


def _fail(code=_INPUT_INVALID):
    _raise_fixed_error(_WarehouseAnomalyRuntimeContractError(code))


def _lowercase_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _positive_id(value):
    return type(value) is int and 0 < value <= _MAX_ID


def _company_header_id(value):
    if (
        type(value) is not str
        or not value
        or len(value) > 19
        or value[0] not in "123456789"
        or not value.isascii()
        or not value.isdecimal()
    ):
        _fail()
    parsed = int(value)
    if parsed > _MAX_ID:
        _fail()
    return parsed


def _parse_warehouse_anomaly_runtime_claims(
    authentication,
    *,
    company_mode,
    company_id,
    body,
):
    """Return detached immutable claims for a future unregistered runner."""

    if (
        type(authentication) is not dict
        or set(authentication) != _AUTHENTICATION_FIELDS
        or type(authentication.get("authenticationKind")) is not str
        or authentication["authenticationKind"] != "cookie_session"
        or not _lowercase_sha256(authentication.get("sessionHash"))
        or type(company_mode) is not str
        or company_mode != "company"
        or type(body) is not dict
        or set(body) != _BODY_FIELDS
    ):
        _fail()

    selected = body.get("selected")
    if (
        not _positive_id(body.get("projectId"))
        or not _positive_id(body.get("jobId"))
        or type(selected) is not dict
        or set(selected) != _SELECTION_FIELDS
        or type(selected.get("subjectKind")) is not str
        or not _positive_id(selected.get("subjectId"))
        or type(selected.get("anomalyCode")) is not str
        or _SELECTION_RULES.get(selected["anomalyCode"])
        != selected["subjectKind"]
    ):
        _fail()

    return _WarehouseAnomalyRuntimeClaims(
        session_hash=authentication["sessionHash"],
        company_id=_company_header_id(company_id),
        project_id=body["projectId"],
        job_id=body["jobId"],
        selection=_WarehouseAnomalySelection(
            subject_kind=selected["subjectKind"],
            subject_id=selected["subjectId"],
            anomaly_code=selected["anomalyCode"],
        ),
    )


def _valid_runtime_claims(value):
    return (
        type(value) is _WarehouseAnomalyRuntimeClaims
        and _lowercase_sha256(value.session_hash)
        and _positive_id(value.company_id)
        and _positive_id(value.project_id)
        and _positive_id(value.job_id)
        and type(value.selection) is _WarehouseAnomalySelection
        and type(value.selection.subject_kind) is str
        and _positive_id(value.selection.subject_id)
        and type(value.selection.anomaly_code) is str
        and _SELECTION_RULES.get(value.selection.anomaly_code)
        == value.selection.subject_kind
    )


def _authorize_warehouse_anomaly_runtime_claims(claims, outcome):
    """Apply actor-before-project precedence to one future small SQL row."""

    if not _valid_runtime_claims(claims):
        _fail(_CONTRACT_INVALID)
    if (
        type(outcome) is not dict
        or set(outcome) != {"actor_count", "project_exists"}
        or type(outcome.get("actor_count")) is not int
        or outcome["actor_count"] not in (0, 1, 2)
        or type(outcome.get("project_exists")) is not bool
    ):
        _fail(_CONTRACT_INVALID)
    if outcome["actor_count"] != 1:
        _fail(_AUTHENTICATION_REQUIRED)
    if outcome["project_exists"] is not True:
        _fail(_RESOURCE_NOT_FOUND)
    return claims


def _validated_internal_source(value, *, ready):
    source_revision = (
        value.get("sourceRevision") if type(value) is dict else None
    )
    if (
        type(value) is not dict
        or set(value) != _INTERNAL_SOURCE_FIELDS
        or any(
            not _positive_id(value.get(name))
            for name in (
                "companyId", "projectId", "estimateId",
                "reconciliationId", "baseEstimateId",
            )
        )
        or type(source_revision) is not str
        or not source_revision.startswith("sha256:")
        or not _lowercase_sha256(source_revision[len("sha256:"):])
        or type(value.get("reconciliationStatus")) is not str
        or value["reconciliationStatus"] not in _RECONCILIATION_STATUSES
        or value["baseEstimateId"] == value["estimateId"]
        or (
            ready
            and not _lowercase_sha256(
                value.get("revalidatedRelevantEvidenceSha256")
            )
        )
        or (
            not ready
            and value.get("revalidatedRelevantEvidenceSha256") is not None
        )
    ):
        _fail(_CONTRACT_INVALID)
    return value


def _validated_internal_candidate(value):
    if (
        type(value) is not dict
        or set(value) != _CANDIDATE_FIELDS
        or type(value.get("subjectKind")) is not str
        or not _positive_id(value.get("subjectId"))
        or type(value.get("anomalyCode")) is not str
        or type(value.get("recommendationCode")) is not str
        or _SELECTION_RULES.get(value["anomalyCode"])
        != value["subjectKind"]
        or _content_contract._ANOMALY_RECOMMENDATION_RULES.get(
            value["anomalyCode"]
        ) != value["recommendationCode"]
    ):
        _fail(_CONTRACT_INVALID)
    return dict(value)


def _public_warehouse_anomaly_runtime_projection(value):
    """Remove all private lineage/provenance fields from one A9.2 result."""

    try:
        if (
            type(value) is not dict
            or set(value) != _INTERNAL_RESULT_FIELDS
            or type(value.get("warehouseAnomalyContentVersion")) is not int
            or value["warehouseAnomalyContentVersion"] != 1
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
            or value["state"] not in {
                "preview_ready", "blocked", "stale",
            }
        ):
            _fail(_CONTRACT_INVALID)

        state = value["state"]
        ready = state == "preview_ready"
        source = _validated_internal_source(
            value.get("source"), ready=ready,
        )
        candidate = _validated_internal_candidate(value.get("candidate"))
        blockers = value.get("blockers")
        content = value.get("content")
        content_sha256 = value.get("contentSha256")

        if ready:
            expected_content = _content_contract._fixed_content(candidate)
            if (
                type(content) is not dict
                or set(content) != _CONTENT_FIELDS
                or content != expected_content
                or type(blockers) is not list
                or blockers != []
                or not _lowercase_sha256(content_sha256)
                or content_sha256 != _content_contract._canonical_sha256({
                    "warehouseAnomalyContentVersion": 1,
                    "source": source,
                    "candidate": candidate,
                    "content": expected_content,
                })
            ):
                _fail(_CONTRACT_INVALID)
            public_content = dict(expected_content)
            public_blockers = []
        else:
            if (
                content is not None
                or content_sha256 is not None
                or type(blockers) is not list
                or len(blockers) != 1
                or type(blockers[0]) is not str
                or blockers[0] not in _content_contract._CONTENT_BLOCKERS[state]
            ):
                _fail(_CONTRACT_INVALID)
            public_content = None
            public_blockers = [_PUBLIC_BLOCKERS[state]]

        return {
            "warehouseAnomalyRuntimeVersion": 1,
            "ok": True,
            "dryRun": True,
            "writesAttempted": 0,
            "previewOnly": True,
            "stockMovementAllowed": False,
            "inventoryAdjustmentAllowed": False,
            "applyAllowed": False,
            "state": state,
            "candidate": candidate,
            "content": public_content,
            "blockers": public_blockers,
            "readOnlyTransaction": True,
            "rolledBack": True,
        }
    except MemoryError:
        raise
    except _WarehouseAnomalyRuntimeContractError:
        raise
    except Exception:
        _fail(_CONTRACT_INVALID)


__all__ = []
