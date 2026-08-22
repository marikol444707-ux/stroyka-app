"""Pure preview of exact active-estimate work still available to assign."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from backend.features.brigade_lineage.source_item import is_estimate_work_item

from .projection import _bounded_text, _positive_int


MAX_ASSIGNMENT_DRAFT_ROWS = 100

_ACTIVE_STATUS = "Активная"
_ITEM_KEY_BYTES = 512
_SECTION_NAME_BYTES = 1024
_ITEM_NAME_BYTES = 4096
_UNIT_BYTES = 128
_WORK_PACKAGE_BYTES = 1024
_QUANTITY_BYTES = 64

_INPUT_INVALID = "assignment_draft_input_invalid"
_SOURCE_INVALID = "assignment_source_invalid"
_SOURCE_DUPLICATE = "assignment_source_duplicate"
_LINEAGE_INVALID = "assignment_lineage_invalid"
_BALANCE_INVALID = "assignment_balance_invalid"
_SCAN_LIMIT = "assignment_draft_scan_limit_exceeded"


class AssignmentDraftContractError(ValueError):
    """Fixed private error for malformed scope or source ownership."""


def _raise_input_invalid():
    raise AssignmentDraftContractError(_INPUT_INVALID) from None


def _non_negative_int(value):
    return value if type(value) is int and value >= 0 else None


def _canonical_decimal(value, *, positive):
    if type(value) not in (int, float, Decimal):
        return None
    if type(value) is float and not math.isfinite(value):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError):
        return None
    if not number.is_finite() or (positive and number <= 0):
        return None
    _sign, digits, exponent = number.as_tuple()
    if (
        len(digits) > _QUANTITY_BYTES
        or exponent > _QUANTITY_BYTES
        or exponent < -_QUANTITY_BYTES
    ):
        return None
    return number


def _render_decimal(number):
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if not rendered or len(rendered.encode("ascii")) > _QUANTITY_BYTES:
        return None
    return rendered


@dataclass(frozen=True)
class AssignmentDraftScope:
    company_id: int
    project_id: int
    estimate_id: int
    estimate_version_id: int
    work_package: str

    def __post_init__(self):
        work_package = _bounded_text(self.work_package, _WORK_PACKAGE_BYTES)
        if (
            _positive_int(self.company_id) is None
            or _positive_int(self.project_id) is None
            or _positive_int(self.estimate_id) is None
            or _positive_int(self.estimate_version_id) is None
            or work_package is None
            or work_package != self.work_package
        ):
            _raise_input_invalid()


@dataclass(frozen=True)
class AssignmentDraftItem:
    source_estimate_id: int
    source_estimate_version_id: int
    section_index: int
    item_index: int
    item_key: str
    section_name: str
    item_name: str
    unit: str
    estimate_quantity: str
    assigned_quantity: str
    available_quantity: str
    work_package: str
    assignee: object


@dataclass(frozen=True)
class AssignmentDraftSummary:
    source_work_rows: int
    available_rows: int
    fully_assigned_rows: int


@dataclass(frozen=True)
class AssignmentDraft:
    scope: AssignmentDraftScope
    state: str
    items: tuple
    summary: AssignmentDraftSummary
    review_codes: tuple


def _empty_draft(
    scope,
    state,
    review_codes=(),
    *,
    source_work_rows=0,
    fully_assigned_rows=0,
):
    return AssignmentDraft(
        scope=scope,
        state=state,
        items=(),
        summary=AssignmentDraftSummary(
            source_work_rows=source_work_rows,
            available_rows=0,
            fully_assigned_rows=fully_assigned_rows,
        ),
        review_codes=tuple(review_codes),
    )


def _fixed_source_matches(scope, row):
    return (
        _positive_int(row.get("company_id")) == scope.company_id
        and _positive_int(row.get("project_id")) == scope.project_id
        and _positive_int(row.get("estimate_id")) == scope.estimate_id
        and _positive_int(row.get("estimate_version_id"))
        == scope.estimate_version_id
        and type(row.get("estimate_status")) is str
        and row.get("estimate_status") == _ACTIVE_STATUS
        and row.get("is_template") is False
        and _bounded_text(row.get("work_package"), _WORK_PACKAGE_BYTES)
        == scope.work_package
    )


def build_assignment_draft(scope, rows):
    """Build a bounded immutable assignment preview with no guessed assignee."""

    if type(scope) is not AssignmentDraftScope:
        _raise_input_invalid()
    if type(rows) not in (list, tuple):
        _raise_input_invalid()
    if len(rows) > MAX_ASSIGNMENT_DRAFT_ROWS:
        return _empty_draft(scope, "review_required", (_SCAN_LIMIT,))

    items = []
    coordinates = set()
    item_keys = set()
    source_work_rows = 0
    fully_assigned_rows = 0
    source_invalid = False
    lineage_invalid = False
    duplicate = False
    balance_invalid = False

    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            source_invalid = True
            continue
        if not _fixed_source_matches(scope, raw_row):
            _raise_input_invalid()

        section_index = _non_negative_int(raw_row.get("section_index"))
        item_index = _non_negative_int(raw_row.get("item_index"))
        item_key = _bounded_text(raw_row.get("item_key"), _ITEM_KEY_BYTES)
        if section_index is None or item_index is None or item_key is None:
            source_invalid = True
            continue
        coordinate = (section_index, item_index)
        if coordinate in coordinates or item_key in item_keys:
            duplicate = True
            continue
        coordinates.add(coordinate)
        item_keys.add(item_key)

        if not is_estimate_work_item(raw_row):
            continue
        source_work_rows += 1

        if (
            raw_row.get("source_type") != "estimate"
            or type(raw_row.get("source_type")) is not str
            or type(raw_row.get("lineage_count")) is not int
            or raw_row.get("lineage_count") != 1
        ):
            lineage_invalid = True
            continue

        section_name = _bounded_text(
            raw_row.get("section_name"),
            _SECTION_NAME_BYTES,
        )
        item_name = _bounded_text(raw_row.get("item_name"), _ITEM_NAME_BYTES)
        unit = _bounded_text(raw_row.get("unit"), _UNIT_BYTES)
        estimate_quantity = _canonical_decimal(
            raw_row.get("quantity"),
            positive=True,
        )
        assigned_quantity = _canonical_decimal(
            raw_row.get("assigned_quantity"),
            positive=False,
        )
        if (
            section_name is None
            or item_name is None
            or unit is None
            or estimate_quantity is None
            or assigned_quantity is None
        ):
            source_invalid = True
            continue

        if assigned_quantity < 0 or assigned_quantity > estimate_quantity:
            balance_invalid = True
            continue
        available_quantity = estimate_quantity - assigned_quantity
        if available_quantity == 0:
            fully_assigned_rows += 1
            continue

        estimate_rendered = _render_decimal(estimate_quantity)
        assigned_rendered = _render_decimal(assigned_quantity)
        available_rendered = _render_decimal(available_quantity)
        if None in (estimate_rendered, assigned_rendered, available_rendered):
            source_invalid = True
            continue
        items.append(AssignmentDraftItem(
            source_estimate_id=scope.estimate_id,
            source_estimate_version_id=scope.estimate_version_id,
            section_index=section_index,
            item_index=item_index,
            item_key=item_key,
            section_name=section_name,
            item_name=item_name,
            unit=unit,
            estimate_quantity=estimate_rendered,
            assigned_quantity=assigned_rendered,
            available_quantity=available_rendered,
            work_package=scope.work_package,
            assignee=None,
        ))

    reason = None
    if duplicate:
        reason = _SOURCE_DUPLICATE
    elif lineage_invalid:
        reason = _LINEAGE_INVALID
    elif balance_invalid:
        reason = _BALANCE_INVALID
    elif source_invalid:
        reason = _SOURCE_INVALID
    if reason:
        return _empty_draft(scope, "review_required", (reason,))
    if not items:
        return _empty_draft(
            scope,
            "clear",
            source_work_rows=source_work_rows,
            fully_assigned_rows=fully_assigned_rows,
        )

    sorted_items = tuple(sorted(
        items,
        key=lambda item: (item.section_index, item.item_index, item.item_key),
    ))
    return AssignmentDraft(
        scope=scope,
        state="ready",
        items=sorted_items,
        summary=AssignmentDraftSummary(
            source_work_rows=source_work_rows,
            available_rows=len(sorted_items),
            fully_assigned_rows=fully_assigned_rows,
        ),
        review_codes=(),
    )


__all__ = []
