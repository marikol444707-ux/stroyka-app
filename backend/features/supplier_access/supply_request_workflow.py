"""Strict policy for the human supply-request workflow.

The module is deliberately pure: it performs no database access and no
business writes. Runtime routes use it to keep role, state-transition and
supplier-disclosure rules deterministic and independently testable.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


PRORAB_CONFIRM_ROLES = frozenset((
    "прораб",
    "главный_инженер",
))

LEADERSHIP_ROLES = frozenset((
    "директор",
    "зам_директора",
))

RFQ_DISPATCH_ROLES = frozenset((
    *LEADERSHIP_ROLES,
    "снабженец",
))

SUPPLIER_REQUEST_VISIBLE_FIELDS = (
    "id",
    "materialName",
    "quantity",
    "unit",
    "project",
    "companyId",
    "workPackage",
    "date",
    "status",
    "urgency",
    "category",
    "itemsJson",
    "createdAt",
)

_SUPPLIER_PRIVATE_ITEM_KEYS = frozenset((
    "estimateControl",
    "estimateLineage",
    "plannedSum",
    "plannedWorkSum",
    "price",
    "priceMaterial",
    "priceWork",
    "unitPrice",
    "lineTotal",
    "total",
    "sum",
    "amount",
    "cost",
    "budget",
    "vat",
    "vatAmount",
    "companyId",
    "projectId",
    "estimateId",
    "estimateItemKey",
    "sectionIndex",
    "itemIndex",
    "requestSource",
    "sourceType",
    "sourceId",
    "allocationId",
    "transferPlanId",
))

# Access requires the complete human approval chain.
#
# Recipient rows are authoritative. The selected_suppliers array remains
# only as a compatibility fallback for old requests that have no recipient
# rows at all. Thus visible_to_supplier=FALSE cannot be bypassed.
SUPPLIER_REQUEST_VISIBILITY_SQL = """
(
    supply_requests.prorab_confirmed_at IS NOT NULL
    AND supply_requests.director_approved_at IS NOT NULL
    AND (
        supply_requests.id IN (
            SELECT recipient.request_id
              FROM supply_request_recipients AS recipient
             WHERE recipient.visible_to_supplier=TRUE
               AND recipient.company_id=supply_requests.company_id
               AND (
                    recipient.target_supplier_id=ANY(%s)
                 OR recipient.supplier_id=ANY(%s)
                 OR COALESCE(
                        recipient.supplier_group_ids,
                        '{}'::int[]
                    ) && %s::int[]
               )
        )
        OR (
            NOT EXISTS (
                SELECT 1
                  FROM supply_request_recipients AS any_recipient
                 WHERE any_recipient.request_id=supply_requests.id
            )
            AND COALESCE(
                    supply_requests.selected_suppliers,
                    '{}'::int[]
                ) && %s::int[]
        )
    )
)
""".strip()


class SupplyRequestWorkflowViolation(ValueError):
    """A stable policy error suitable for conversion to HTTPException."""

    def __init__(self, detail: str, *, status_code: int):
        super().__init__(detail)
        self.detail = detail
        self.status_code = int(status_code)


def _normal_role(role: Any) -> str:
    return str(role or "").strip().casefold()


def _normal_status(status: Any) -> str:
    return str(status or "").strip() or "Новая"


def validate_supply_request_transition(
    *,
    action: str,
    role: Any,
    current_status: Any,
) -> None:
    """Validate one explicit human approval action."""

    role_value = _normal_role(role)
    status_value = _normal_status(current_status)

    if action == "confirm_prorab":
        if role_value not in PRORAB_CONFIRM_ROLES:
            raise SupplyRequestWorkflowViolation(
                "Подтвердить новую заявку может только прораб "
                "или главный инженер объекта",
                status_code=403,
            )
        if status_value != "Новая":
            raise SupplyRequestWorkflowViolation(
                "Прораб может подтверждать только новую заявку",
                status_code=409,
            )
        return

    if action == "approve_director":
        if role_value not in LEADERSHIP_ROLES:
            raise SupplyRequestWorkflowViolation(
                "Утвердить заявку может только директор "
                "или заместитель директора",
                status_code=403,
            )
        if status_value != "Подтверждена прорабом":
            raise SupplyRequestWorkflowViolation(
                "Директор может утвердить заявку только после "
                "подтверждения прорабом",
                status_code=409,
            )
        return

    raise SupplyRequestWorkflowViolation(
        "Неизвестное действие согласования заявки",
        status_code=400,
    )


def validate_rfq_dispatch_role(role: Any) -> None:
    """Allow dispatch only to leadership or the supply specialist."""

    if _normal_role(role) not in RFQ_DISPATCH_ROLES:
        raise SupplyRequestWorkflowViolation(
            "Отправить утверждённую заявку поставщикам может "
            "директор, заместитель директора или снабженец",
            status_code=403,
        )


def supplier_request_visibility_params(
    supplier_ids: Sequence[Any],
) -> list[list[int]]:
    """Return canonical parameters for the four SQL identity checks."""

    canonical = sorted({
        int(value)
        for value in supplier_ids
        if int(value) > 0
    })
    return [list(canonical) for _ in range(4)]


def _sanitize_supplier_item_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_supplier_item_value(item)
            for key, item in value.items()
            if str(key) not in _SUPPLIER_PRIVATE_ITEM_KEYS
            and not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [
            _sanitize_supplier_item_value(item)
            for item in value
        ]
    return value


def _parse_request_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    return []


def sanitize_supplier_request_response(
    row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the least-privilege supplier-facing request document."""

    source = dict(row or {})
    result = {
        field: source[field]
        for field in SUPPLIER_REQUEST_VISIBLE_FIELDS
        if field in source
    }

    if "itemsJson" in result:
        items = _parse_request_items(result.get("itemsJson"))
        result["itemsJson"] = json.dumps(
            _sanitize_supplier_item_value(items),
            ensure_ascii=False,
        )

    return result
