"""Pure preview-only projection of confirmed daily work facts."""

import datetime as _datetime
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


MAX_DAILY_WORK_ROWS = 100

_DESCRIPTION_BYTES = 4096
_UNIT_BYTES = 128
_RESPONSIBLE_NAME_BYTES = 512
_WORK_PACKAGE_BYTES = 1024
_QUANTITY_BYTES = 64
_CONFIRMED_STATUS = "Подтверждено"
_DEFAULT_WORK_PACKAGE = "Основная"

_INPUT_INVALID = "assignment_daily_draft_input_invalid"
_SOURCE_INVALID = "daily_work_source_invalid"
_SOURCE_DUPLICATE = "daily_work_source_duplicate"
_SCAN_LIMIT = "daily_work_scan_limit_exceeded"


class AssignmentDailyDraftContractError(ValueError):
    """Fixed private error for malformed scope or source ownership."""


def _raise_input_invalid():
    raise AssignmentDailyDraftContractError(_INPUT_INVALID) from None


def _positive_int(value):
    return value if type(value) is int and value > 0 else None


def _canonical_date(value):
    if type(value) is not str:
        return None
    try:
        parsed = _datetime.date.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.isoformat() == value else None


def _bounded_text(value, byte_limit, *, allow_empty=False):
    if type(value) is not str:
        return None
    cleaned = value.strip()
    if not cleaned and not allow_empty:
        return None
    if len(cleaned) > byte_limit:
        return None
    try:
        encoded = cleaned.encode("utf-8")
    except UnicodeError:
        return None
    if len(encoded) > byte_limit:
        return None
    return cleaned


def _canonical_quantity(value):
    if type(value) not in (int, float, Decimal):
        return None
    if type(value) is float and not math.isfinite(value):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError):
        return None
    if not number.is_finite() or number <= 0:
        return None
    _sign, digits, exponent = number.as_tuple()
    if (
        len(digits) > _QUANTITY_BYTES
        or exponent > _QUANTITY_BYTES
        or exponent < -_QUANTITY_BYTES
    ):
        return None
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if not rendered or len(rendered.encode("ascii")) > _QUANTITY_BYTES:
        return None
    return rendered


@dataclass(frozen=True)
class AssignmentDailyDraftScope:
    company_id: int
    project_id: int
    date: str

    def __post_init__(self):
        if (
            _positive_int(self.company_id) is None
            or _positive_int(self.project_id) is None
            or _canonical_date(self.date) is None
        ):
            _raise_input_invalid()


@dataclass(frozen=True)
class DailyWorkDraftItem:
    source_id: int
    description: str
    unit: str
    quantity: str
    responsible_id: Optional[int]
    responsible_name: str
    work_package: str
    status: str


@dataclass(frozen=True)
class DailyWorkDraftSummary:
    confirmed_rows: int
    work_packages: int
    responsible_people: int


@dataclass(frozen=True)
class DailyWorkDraft:
    scope: AssignmentDailyDraftScope
    state: str
    items: tuple
    summary: DailyWorkDraftSummary
    review_codes: tuple


def _empty_draft(scope, state, review_codes=()):
    return DailyWorkDraft(
        scope=scope,
        state=state,
        items=(),
        summary=DailyWorkDraftSummary(0, 0, 0),
        review_codes=tuple(review_codes),
    )


def _confirmed_item(row):
    source_id = _positive_int(row.get("id"))
    description = _bounded_text(row.get("description"), _DESCRIPTION_BYTES)
    unit = _bounded_text(row.get("unit"), _UNIT_BYTES)
    quantity = _canonical_quantity(row.get("quantity"))
    responsible_id = row.get("master_id")
    if responsible_id is not None:
        responsible_id = _positive_int(responsible_id)
        if responsible_id is None:
            return None
    responsible_name = _bounded_text(
        row.get("master_name") or "",
        _RESPONSIBLE_NAME_BYTES,
        allow_empty=True,
    )
    raw_package = row.get("work_package")
    if raw_package is None or raw_package == "":
        work_package = _DEFAULT_WORK_PACKAGE
    else:
        work_package = _bounded_text(raw_package, _WORK_PACKAGE_BYTES)
    if (
        source_id is None
        or description is None
        or unit is None
        or quantity is None
        or responsible_name is None
        or (responsible_id is None and not responsible_name)
        or work_package is None
    ):
        return None
    return DailyWorkDraftItem(
        source_id=source_id,
        description=description,
        unit=unit,
        quantity=quantity,
        responsible_id=responsible_id,
        responsible_name=responsible_name,
        work_package=work_package,
        status=_CONFIRMED_STATUS,
    )


def build_daily_work_draft(scope, rows):
    """Build one immutable, bounded preview without mutating source rows."""

    if type(scope) is not AssignmentDailyDraftScope:
        _raise_input_invalid()
    if type(rows) not in (list, tuple):
        _raise_input_invalid()
    if len(rows) > MAX_DAILY_WORK_ROWS:
        return _empty_draft(scope, "review_required", (_SCAN_LIMIT,))

    confirmed_rows = []
    seen_ids = set()
    duplicate = False
    invalid = False
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            invalid = True
            continue
        company_id = _positive_int(raw_row.get("company_id"))
        project_id = _positive_int(raw_row.get("project_id"))
        row_date = _canonical_date(raw_row.get("date"))
        if (
            company_id != scope.company_id
            or project_id != scope.project_id
            or row_date != scope.date
        ):
            _raise_input_invalid()

        status = raw_row.get("status")
        if type(status) is not str:
            invalid = True
            continue
        if status != _CONFIRMED_STATUS:
            continue

        item = _confirmed_item(raw_row)
        if item is None:
            invalid = True
            continue
        if item.source_id in seen_ids:
            duplicate = True
            continue
        seen_ids.add(item.source_id)
        confirmed_rows.append(item)

    if duplicate:
        return _empty_draft(scope, "review_required", (_SOURCE_DUPLICATE,))
    if invalid:
        return _empty_draft(scope, "review_required", (_SOURCE_INVALID,))
    if not confirmed_rows:
        return _empty_draft(scope, "clear")

    items = tuple(sorted(confirmed_rows, key=lambda item: item.source_id))
    work_packages = len({item.work_package for item in items})
    responsible_people = len({
        item.responsible_name.casefold()
        if item.responsible_name
        else "id:" + str(item.responsible_id)
        for item in items
    })
    return DailyWorkDraft(
        scope=scope,
        state="ready",
        items=items,
        summary=DailyWorkDraftSummary(
            confirmed_rows=len(items),
            work_packages=work_packages,
            responsible_people=responsible_people,
        ),
        review_codes=(),
    )


__all__ = []
