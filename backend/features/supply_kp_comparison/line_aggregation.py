"""Deterministic aggregation of split supplier-offer lines.

The functions in this module are pure and use :class:`decimal.Decimal` for all
quantity and money arithmetic. They never infer package conversion factors.
Only explicit safe unit conversions (for example tonnes to kilograms) are
performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from types import MappingProxyType
from typing import Mapping

from .technical_matcher import build_technical_signature, normalize_name, normalize_unit


AGGREGATION_VERSION = 1
MAX_LINES = 1_000
MAX_TEXT_BYTES = 4 * 1024
MONEY_TOLERANCE = Decimal("0.05")
PRICE_QUANTUM = Decimal("0.000001")
MAX_ABSOLUTE_NUMBER = Decimal("1000000000000000000")

_ERROR_INVALID = "supply_line_aggregation_invalid"
_ERROR_ARITHMETIC = "supply_line_aggregation_arithmetic_mismatch"

_SAFE_UNIT_CONVERSIONS = MappingProxyType(
    {
        "т": ("кг", Decimal("1000")),
        "кг": ("кг", Decimal("1")),
        "г": ("кг", Decimal("0.001")),
        "м": ("м", Decimal("1")),
        "см": ("м", Decimal("0.01")),
        "мм": ("м", Decimal("0.001")),
        "м2": ("м2", Decimal("1")),
        "м3": ("м3", Decimal("1")),
        "л": ("л", Decimal("1")),
        "шт": ("шт", Decimal("1")),
        "компл": ("компл", Decimal("1")),
        "уп": ("уп", Decimal("1")),
    }
)


class SupplyLineAggregationError(ValueError):
    """A fixed-code, non-leaking aggregation failure."""

    def __init__(self, code: str = _ERROR_INVALID):
        if code not in {_ERROR_INVALID, _ERROR_ARITHMETIC}:
            code = _ERROR_INVALID
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NormalizedSupplyLine:
    source_line_id: str
    sku: str
    name: str
    normalized_name: str
    manufacturer: str
    work_package: str
    unit: str
    quantity: Decimal
    price_per_unit: Decimal
    total_price: Decimal
    signature_sha256: str


@dataclass(frozen=True)
class AggregatedSupplyLine:
    aggregation_key_sha256: str
    source_line_ids: tuple[str, ...]
    source_names: tuple[str, ...]
    sku: str
    name: str
    normalized_name: str
    manufacturer: str
    work_package: str
    unit: str
    quantity: Decimal
    price_per_unit: Decimal
    total_price: Decimal
    technical_signature_sha256: str

    def to_dict(self) -> dict:
        return {
            "aggregationKeySha256": self.aggregation_key_sha256,
            "sourceLineIds": list(self.source_line_ids),
            "sourceNames": list(self.source_names),
            "sku": self.sku,
            "name": self.name,
            "normalizedName": self.normalized_name,
            "manufacturer": self.manufacturer,
            "workPackage": self.work_package,
            "unit": self.unit,
            "quantity": _decimal_text(self.quantity),
            "pricePerUnit": _decimal_text(self.price_per_unit),
            "totalPrice": _money_text(self.total_price),
            "technicalSignatureSha256": self.technical_signature_sha256,
        }


@dataclass(frozen=True)
class SupplyLineAggregationResult:
    source_line_count: int
    aggregated_line_count: int
    lines: tuple[AggregatedSupplyLine, ...]
    aggregation_sha256: str
    writes_attempted: int = 0
    model_calls: int = 0

    def to_dict(self) -> dict:
        return {
            "aggregationVersion": AGGREGATION_VERSION,
            "sourceLineCount": self.source_line_count,
            "aggregatedLineCount": self.aggregated_line_count,
            "lines": [line.to_dict() for line in self.lines],
            "aggregationSha256": self.aggregation_sha256,
            "writesAttempted": self.writes_attempted,
            "modelCalls": self.model_calls,
        }


def _fail(code: str = _ERROR_INVALID) -> None:
    raise SupplyLineAggregationError(code) from None


def _text(value, *, max_bytes: int = MAX_TEXT_BYTES, allow_empty: bool = True) -> str:
    if value is None and allow_empty:
        return ""
    if type(value) is not str or "\x00" in value:
        _fail()
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not allow_empty and not normalized:
        _fail()
    if len(normalized.encode("utf-8")) > max_bytes:
        _fail()
    return normalized


def _decimal(value, *, required: bool, positive: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            _fail()
        return None
    if isinstance(value, bool):
        _fail()
    if isinstance(value, Decimal):
        result = value
    elif type(value) in (int, float, str):
        rendered = str(value).strip().replace(" ", "").replace(",", ".")
        if not rendered or len(rendered) > 80:
            _fail()
        try:
            result = Decimal(rendered)
        except (InvalidOperation, ValueError):
            _fail()
    else:
        _fail()
    if (
        not result.is_finite()
        or result < 0
        or result > MAX_ABSOLUTE_NUMBER
        or (positive and result <= 0)
    ):
        _fail()
    return result


def _decimal_text(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    return "0" if rendered == "-0" else rendered


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def _canonical_sha256(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_key_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("ё", "е")).strip()


def _base_unit(unit: str) -> tuple[str, Decimal]:
    normalized = normalize_unit(unit)
    return _SAFE_UNIT_CONVERSIONS.get(normalized, (normalized, Decimal("1")))


def _line_value(line: Mapping, *names):
    for name in names:
        if name in line and line.get(name) not in (None, ""):
            return line.get(name)
    return None


def normalize_supply_line(line: Mapping, *, fallback_source_line_id: str) -> NormalizedSupplyLine:
    if not isinstance(line, Mapping):
        _fail()
    name = _text(
        _line_value(line, "materialName", "name"),
        allow_empty=False,
    )
    raw_unit = _text(_line_value(line, "unit") or "", max_bytes=64)
    base_unit, quantity_factor = _base_unit(raw_unit)
    if not base_unit:
        _fail()

    raw_quantity = _decimal(
        _line_value(line, "quantity", "qty"),
        required=True,
        positive=True,
    )
    raw_price = _decimal(
        _line_value(line, "pricePerUnit", "price_per_unit", "price"),
        required=False,
    )
    raw_total = _decimal(
        _line_value(line, "totalPrice", "total_price", "total", "amount"),
        required=False,
    )
    if raw_price is None and raw_total is None:
        _fail()

    quantity = raw_quantity * quantity_factor
    total_price = raw_total if raw_total is not None else raw_price * raw_quantity
    if raw_price is not None and raw_total is not None:
        expected_total = raw_price * raw_quantity
        if abs(expected_total - raw_total) > MONEY_TOLERANCE:
            _fail(_ERROR_ARITHMETIC)
    price_per_unit = total_price / quantity

    source_line_id = _text(
        _line_value(line, "sourceLineId", "source_line_id", "id")
        or fallback_source_line_id,
        max_bytes=256,
        allow_empty=False,
    )
    sku = _text(_line_value(line, "sku", "article", "vendorCode") or "", max_bytes=512)
    manufacturer = _text(
        _line_value(line, "manufacturer", "brand") or "",
        max_bytes=512,
    )
    work_package = _text(
        _line_value(line, "workPackage", "work_package") or "",
        max_bytes=512,
    )
    signature = build_technical_signature(name)
    return NormalizedSupplyLine(
        source_line_id=source_line_id,
        sku=_normalized_key_text(sku),
        name=name,
        normalized_name=normalize_name(name),
        manufacturer=_normalized_key_text(manufacturer),
        work_package=_normalized_key_text(work_package),
        unit=base_unit,
        quantity=quantity,
        price_per_unit=price_per_unit,
        total_price=total_price,
        signature_sha256=signature.signature_sha256,
    )


def _aggregation_key(line: NormalizedSupplyLine) -> tuple[str, ...]:
    # Name and technical signature both remain in the key. This deliberately
    # avoids merging merely similar products or different brands automatically.
    return (
        line.normalized_name,
        line.signature_sha256,
        line.unit,
        line.sku,
        line.manufacturer,
        line.work_package,
    )


def aggregate_supply_lines(lines) -> SupplyLineAggregationResult:
    if isinstance(lines, (str, bytes)) or not isinstance(lines, (list, tuple)):
        _fail()
    if not 1 <= len(lines) <= MAX_LINES:
        _fail()

    normalized = tuple(
        normalize_supply_line(line, fallback_source_line_id=f"line-{index + 1}")
        for index, line in enumerate(lines)
    )
    grouped = {}
    for line in normalized:
        grouped.setdefault(_aggregation_key(line), []).append(line)

    aggregated = []
    for key in sorted(grouped):
        group = grouped[key]
        quantity = sum((line.quantity for line in group), Decimal("0"))
        total_price = sum((line.total_price for line in group), Decimal("0"))
        if quantity <= 0:
            _fail()
        price_per_unit = (total_price / quantity).quantize(
            PRICE_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        source_line_ids = tuple(sorted({line.source_line_id for line in group}))
        source_names = tuple(sorted({line.name for line in group}, key=lambda value: (value.casefold(), value)))
        first = min(
            group,
            key=lambda line: (line.name.casefold(), line.name, line.source_line_id),
        )
        key_payload = {
            "normalizedName": first.normalized_name,
            "technicalSignatureSha256": first.signature_sha256,
            "unit": first.unit,
            "sku": first.sku,
            "manufacturer": first.manufacturer,
            "workPackage": first.work_package,
        }
        aggregated.append(
            AggregatedSupplyLine(
                aggregation_key_sha256=_canonical_sha256(key_payload),
                source_line_ids=source_line_ids,
                source_names=source_names,
                sku=first.sku,
                name=first.name,
                normalized_name=first.normalized_name,
                manufacturer=first.manufacturer,
                work_package=first.work_package,
                unit=first.unit,
                quantity=quantity,
                price_per_unit=price_per_unit,
                total_price=total_price,
                technical_signature_sha256=first.signature_sha256,
            )
        )

    aggregate_payload = {
        "aggregationVersion": AGGREGATION_VERSION,
        "sourceLineCount": len(normalized),
        "lines": [line.to_dict() for line in aggregated],
    }
    return SupplyLineAggregationResult(
        source_line_count=len(normalized),
        aggregated_line_count=len(aggregated),
        lines=tuple(aggregated),
        aggregation_sha256=_canonical_sha256(aggregate_payload),
    )


__all__ = [
    "AGGREGATION_VERSION",
    "AggregatedSupplyLine",
    "NormalizedSupplyLine",
    "SupplyLineAggregationError",
    "SupplyLineAggregationResult",
    "aggregate_supply_lines",
    "normalize_supply_line",
]
