"""Deterministic technical comparison for construction supply lines.

This module is intentionally pure:

* no database access;
* no HTTP or filesystem access;
* no model/provider calls;
* no business writes.

It provides the first A8.5.1 slice for comparing supplier nomenclature. Hard
engineering conflicts always win over fuzzy text similarity. Ambiguous or
missing evidence fails closed to ``review_required``.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from types import MappingProxyType
from typing import Iterable


CONTRACT_VERSION = 1
MAX_NAME_BYTES = 4 * 1024
MAX_CATEGORY_BYTES = 512
MAX_UNIT_BYTES = 64
MAX_SUPPLIER_LINES = 100

LEGACY_OK = "ok"
LEGACY_REVIEW = "review"
LEGACY_BLOCKED = "blocked"

DECISION_EXACT = "exact"
DECISION_COMPARABLE = "comparable"
DECISION_REVIEW_REQUIRED = "review_required"
DECISION_INCOMPATIBLE = "incompatible"

_INVALID = "supply_technical_comparison_invalid"

_REASON_MESSAGES = MappingProxyType(
    {
        "ONLY_ONE_SUPPLIER_QUOTED": "Only one supplier has a quoted line",
        "PRODUCT_FAMILY_CONFLICT": "Product family conflict between compared lines",
        "THREAD_GENDER_CONFLICT": "Thread gender conflict between compared lines",
        "ANGLE_CONFLICT": "Angle specification conflict",
        "DIRECTION_OR_DESIGN_DIFFERS": "Direction or design differs between compared lines",
        "PACKAGING_OR_WEIGHT_DIFFERS": "Packaging or weight differs",
        "DRY_SIPHON_DESIGN_DIFFERS": "Dry-siphon design differs",
        "ECCENTRICITY_DIFFERS": "Transition geometry differs: eccentricity is specified in one line only",
        "SEWER_APPLICATION_DIFFERS": "Sewer application or specification differs",
        "COMPATIBLE_ENGINEERING_SIGNATURE": "Compatible engineering signature",
        "MODEL_SENSITIVE_FAMILY": "Model-sensitive product family requires confirmation",
        "WEAK_NOMENCLATURE_MATCH": "Weak nomenclature match",
        "SAME_FAMILY_NO_CRITICAL_CONFLICT": "Same product family and no detected critical conflict",
        "INSUFFICIENT_TECHNICAL_EVIDENCE": "Insufficient evidence for automatic technical equivalence",
        "UNIT_CONFLICT": "Units are not directly comparable",
        "DIMENSION_CONFLICT": "Critical dimensions differ",
        "DIAMETER_CONFLICT": "Nominal or outside diameter differs",
        "THREAD_SIZE_CONFLICT": "Thread size differs",
        "PRESSURE_CLASS_BELOW_REQUIRED": "Offered pressure class is below the required class",
        "PRESSURE_CLASS_ABOVE_REQUIRED": "Offered pressure class is higher and requires compatibility confirmation",
        "PRESSURE_CLASS_MISSING": "Required pressure class is not stated in the offered line",
        "SDR_WEAKER_THAN_REQUIRED": "Offered SDR indicates a thinner wall than required",
        "SDR_DIFFERS": "SDR differs and requires compatibility confirmation",
        "SDR_MISSING": "Required SDR is not stated in the offered line",
        "REINFORCEMENT_CONFLICT": "Pipe reinforcement differs",
        "REINFORCEMENT_MISSING": "Required reinforcement is not stated in the offered line",
        "REQUIRED_DIMENSION_MISSING": "Required dimension is not stated in the offered line",
        "REQUIRED_DIAMETER_MISSING": "Required diameter is not stated in the offered line",
        "REQUIRED_THREAD_SIZE_MISSING": "Required thread size is not stated in the offered line",
        "REQUIRED_THREAD_GENDER_MISSING": "Required thread gender is not stated in the offered line",
        "REQUIRED_ANGLE_MISSING": "Required angle is not stated in the offered line",
        "EXACT_NORMALIZED_NAME": "Names and units match after deterministic normalization",
    }
)

_STOP_WORDS = frozenset(
    {
        "арт",
        "артикул",
        "товар",
        "материал",
        "оборудование",
        "шт",
        "штук",
        "штука",
        "метр",
        "метров",
        "пог",
        "м",
        "мм",
        "см",
        "комплект",
        "компл",
    }
)

_UNIT_ALIASES = MappingProxyType(
    {
        "шт.": "шт",
        "штука": "шт",
        "штук": "шт",
        "ед": "шт",
        "ед.": "шт",
        "pcs": "шт",
        "pc": "шт",
        "м.п.": "м",
        "пог.м": "м",
        "пог.м.": "м",
        "п.м": "м",
        "п.м.": "м",
        "погонныйметр": "м",
        "метр": "м",
        "метров": "м",
        "м2": "м2",
        "м²": "м2",
        "кв.м": "м2",
        "кв.м.": "м2",
        "м3": "м3",
        "м³": "м3",
        "куб.м": "м3",
        "куб.м.": "м3",
        "кг.": "кг",
        "килограмм": "кг",
        "килограммов": "кг",
        "тонна": "т",
        "тонн": "т",
        "т.": "т",
        "комплект": "компл",
        "комплектов": "компл",
        "уп.": "уп",
        "упаковка": "уп",
        "упаковок": "уп",
    }
)

_FAMILY_RULES = (
    ("radiator_kit", ("набор", "радиатор")),
    ("trap", ("трап",)),
    ("insulation", ("изоляция", "оболочка")),
    ("repair_coupling", ("муфта ремонт",)),
    ("bypass", ("обвод", "скоба")),
    ("ball_valve", ("кран шаровый",)),
    ("water_meter", ("счетчик",)),
    (
        "sewer_pipe",
        (
            "труба канализа",
            "труба пп для наружной канализа",
            "труба пп для внутренней канализа",
        ),
    ),
    ("ppr_pipe", ("труба pp r", "труба ppr", "труба kalde")),
    ("elbow", ("отвод", "угольник")),
    ("tee", ("тройник",)),
    ("transition", ("переход",)),
    ("plug", ("заглушка",)),
    ("union", ("сгон", "американка")),
    ("valve", ("вентиль", "клапан")),
    ("sealant", ("сантехмастер", "гель")),
    ("lubricant", ("смазка",)),
    ("paste_flax", ("паста", "лен")),
    ("bracket", ("кронштейн",)),
    ("coupling", ("муфта",)),
)

_MODEL_SENSITIVE_FAMILIES = frozenset(
    {"trap", "water_meter", "sewer_pipe", "ball_valve", "valve"}
)


class TechnicalComparisonError(ValueError):
    """One fixed non-leaking validation error."""

    def __init__(self):
        self.code = _INVALID
        super().__init__(self.code)


@dataclass(frozen=True)
class NameMatchResult:
    confidence_basis_points: int
    method: str
    requires_technical_review: bool

    @property
    def confidence(self) -> float:
        return round(self.confidence_basis_points / 10_000, 4)


@dataclass(frozen=True)
class TechnicalSignature:
    normalized_name: str
    family: str
    dimensions: tuple[str, ...]
    diameters_mm: tuple[str, ...]
    thread_sizes: tuple[str, ...]
    thread_genders: tuple[str, ...]
    angles_deg: tuple[int, ...]
    pn_classes: tuple[str, ...]
    sdr_classes: tuple[str, ...]
    reinforcement: tuple[str, ...]
    directions: tuple[str, ...]
    design_flags: tuple[str, ...]
    weights_g: tuple[str, ...]
    signature_sha256: str

    def to_dict(self) -> dict:
        return {
            "normalizedName": self.normalized_name,
            "family": self.family,
            "dimensions": list(self.dimensions),
            "diametersMm": list(self.diameters_mm),
            "threadSizes": list(self.thread_sizes),
            "threadGenders": list(self.thread_genders),
            "anglesDeg": list(self.angles_deg),
            "pnClasses": list(self.pn_classes),
            "sdrClasses": list(self.sdr_classes),
            "reinforcement": list(self.reinforcement),
            "directions": list(self.directions),
            "designFlags": list(self.design_flags),
            "weightsG": list(self.weights_g),
            "signatureSha256": self.signature_sha256,
        }


@dataclass(frozen=True)
class TechnicalPairResult:
    status: str
    decision: str
    confidence_basis_points: int
    reason_codes: tuple[str, ...]
    comparison_sha256: str
    writes_attempted: int = 0
    model_calls: int = 0

    @property
    def confidence(self) -> float:
        return round(self.confidence_basis_points / 10_000, 4)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(_REASON_MESSAGES[code] for code in self.reason_codes)

    def to_dict(self) -> dict:
        return {
            "contractVersion": CONTRACT_VERSION,
            "status": self.status,
            "decision": self.decision,
            "confidence": self.confidence,
            "confidenceBasisPoints": self.confidence_basis_points,
            "reasonCodes": list(self.reason_codes),
            "reasons": list(self.reasons),
            "comparisonSha256": self.comparison_sha256,
            "writesAttempted": self.writes_attempted,
            "modelCalls": self.model_calls,
            "automaticApprovalAllowed": False,
        }


@dataclass(frozen=True)
class TechnicalLineResult:
    status: str
    decision: str
    confidence_basis_points: int
    reason_codes: tuple[str, ...]
    required_signature: TechnicalSignature
    offered_signature: TechnicalSignature
    comparison_sha256: str
    writes_attempted: int = 0
    model_calls: int = 0

    @property
    def confidence(self) -> float:
        return round(self.confidence_basis_points / 10_000, 4)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(_REASON_MESSAGES[code] for code in self.reason_codes)

    def to_dict(self) -> dict:
        return {
            "contractVersion": CONTRACT_VERSION,
            "status": self.status,
            "decision": self.decision,
            "confidence": self.confidence,
            "confidenceBasisPoints": self.confidence_basis_points,
            "reasonCodes": list(self.reason_codes),
            "reasons": list(self.reasons),
            "requiredSignature": self.required_signature.to_dict(),
            "offeredSignature": self.offered_signature.to_dict(),
            "comparisonSha256": self.comparison_sha256,
            "writesAttempted": self.writes_attempted,
            "modelCalls": self.model_calls,
            "automaticApprovalAllowed": False,
        }


def _fail() -> None:
    raise TechnicalComparisonError() from None


def _bounded_text(value, *, max_bytes: int, allow_empty: bool = False) -> str:
    if type(value) is not str or "\x00" in value:
        _fail()
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not allow_empty and not normalized:
        _fail()
    if len(normalized.encode("utf-8")) > max_bytes:
        _fail()
    return normalized


def _bounded_names(values: Iterable[str], field: str) -> tuple[str, ...]:
    del field
    if isinstance(values, str) or not isinstance(values, (list, tuple)):
        _fail()
    if len(values) > MAX_SUPPLIER_LINES:
        _fail()
    result = []
    for value in values:
        normalized = _bounded_text(
            value,
            max_bytes=MAX_NAME_BYTES,
            allow_empty=True,
        )
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def _canonical_sha256(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal_string(value: str) -> str:
    try:
        number = Decimal(value.replace(",", "."))
    except (InvalidOperation, AttributeError):
        _fail()
    if not number.is_finite() or number < 0:
        _fail()
    rendered = format(number.normalize(), "f")
    return "0" if rendered == "-0" else rendered


def normalize_unit(unit: str) -> str:
    raw = _bounded_text(unit, max_bytes=MAX_UNIT_BYTES, allow_empty=True)
    compact = re.sub(r"\s+", "", raw.lower().replace("ё", "е"))
    return _UNIT_ALIASES.get(compact, compact)


def normalize_name(value: str) -> str:
    value = _bounded_text(value, max_bytes=MAX_NAME_BYTES)
    value = value.lower().replace("ё", "е")
    value = value.replace("½", "1/2").replace("¾", "3/4").replace("¼", "1/4")
    value = re.sub(r"\bоболочк(?:а|и|у|ой|е)?\b", "изоляция", value)
    value = value.replace("×", "x")
    # Cyrillic х is converted only when it is a dimension separator. This must
    # not corrupt Russian words such as "переход".
    value = re.sub(r"(?<=\d)\s*х\s*(?=\d)", "x", value)
    value = re.sub(r"(?<=\d)\s*[/x-]\s*(?=\d)", "x", value)
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    value = re.sub(r"[\(\)\[\],;:_/\\\-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    tokens = []
    for token in value.split():
        clean = token.strip(". ")
        if clean and clean not in _STOP_WORDS:
            tokens.append(clean)
    return " ".join(tokens)


def numeric_signature(value: str) -> tuple[str, ...]:
    normalized = normalize_name(value)
    return tuple(re.findall(r"\d+(?:\.\d+)?", normalized))


def dimension_signature(value: str) -> tuple[str, ...]:
    """Extract dimension-like pairs while ignoring pack/length annotations."""

    raw = _bounded_text(value, max_bytes=MAX_NAME_BYTES).lower().replace("ё", "е")
    raw = raw.replace("×", "x")
    raw = re.sub(r"(?<=\d)\s*х\s*(?=\d)", "x", raw)
    raw = re.sub(r"(?<=\d),(?=\d)", ".", raw)
    result = []
    for match in re.finditer(
        r"(?<!\d)(\d+(?:\.\d+)?)\s*[/x]\s*(\d+(?:\.\d+)?)(?!\d)",
        raw,
    ):
        suffix = raw[match.end() : match.end() + 12]
        prefix = raw[max(0, match.start() - 10) : match.start()]
        if re.match(r"\s*(?:м|метр)(?:/|\s)*(?:п|уп|упак)", suffix):
            continue
        if re.search(r"(?:l|длина)\s*=\s*$", prefix):
            continue
        first = _decimal_string(match.group(1))
        second = _decimal_string(match.group(2))
        pair = f"{first}x{second}"
        # Fractions such as 1/2 are thread sizes, not dimensions.
        if first in {"1", "2", "3"} and second in {"2", "4", "8"}:
            continue
        if pair not in result:
            result.append(pair)
    return tuple(sorted(result))


def _text(value: str) -> str:
    value = _bounded_text(value, max_bytes=MAX_NAME_BYTES, allow_empty=True)
    return value.lower().replace("ё", "е").replace("×", "x")


def _joined_unique(values: tuple[str, ...]) -> str:
    return " | ".join(values)


def _family(value: str) -> str:
    normalized = normalize_name(value)
    if "набор" in normalized and "радиатор" in normalized:
        return "radiator_kit"
    for family, needles in _FAMILY_RULES:
        if all(needle in normalized for needle in needles) if family == "radiator_kit" else any(
            needle in normalized for needle in needles
        ):
            return family
    return ""


def _stripped(value: str) -> str:
    text = _text(value)
    text = re.sub(r"(?<=\d)\s*х\s*(?=\d)", "x", text)
    text = re.sub(r"\([^)]*(?:\bуп\.?|\bк\.|м/п)[^)]*\)", " ", text)
    text = re.sub(r"\bарт\.?\s*\d+\b", " ", text)
    return re.sub(r"\s+", " ", text)


def _dimensions(value: str) -> tuple[str, ...]:
    text = _stripped(value).replace(",", ".")
    result = []
    for match in re.finditer(
        r"(?<!\d)(\d+(?:\.\d+)?)(?:\s*[x/*]\s*(\d+(?:\.\d+)?))(?:\s*[x/*]\s*(\d+(?:\.\d+)?))?",
        text,
    ):
        parts = [part for part in match.groups() if part]
        if len(parts) == 2 and parts[0] in {"1", "3"} and parts[1] in {"2", "4", "8"}:
            continue
        if len(parts) >= 2:
            signature = "x".join(_decimal_string(part) for part in parts)
            if signature not in result:
                result.append(signature)
    return tuple(sorted(result))


def _diameters(value: str) -> tuple[str, ...]:
    text = _stripped(value).replace(",", ".")
    result = {
        _decimal_string(number)
        for number in re.findall(
            r"(?:\bd\s*=\s*|\bdn\s*[-=]?\s*|\bdu\s*[-=]?\s*|\bdy\s*[-=]?\s*|\bду\s*[-=]?\s*|ø\s*|⌀\s*|\bф\s*)(\d+(?:\.\d+)?)",
            text,
        )
    }
    return tuple(sorted(result, key=Decimal))


def _thread_sizes(value: str) -> tuple[str, ...]:
    text = _stripped(value)
    values = re.findall(
        r"(?<!\d)(1\s+1/2|1\s+1/4|3/4|1/2|1/4|3/8)(?=\s*(?:\"|'|дюйм|\b))",
        text,
    )
    values.extend(
        re.findall(
            r"(?<![\d/])(1|2)(?![\d/])(?=\s*(?:\"|'|дюйм))",
            text,
        )
    )
    normalized = []
    for item in values:
        item = re.sub(r"\s+", " ", item.strip())
        if item not in normalized:
            normalized.append(item)
    return tuple(sorted(normalized))


def _thread_genders(value: str) -> tuple[str, ...]:
    text = _text(value)
    # Keep multiplicity: ВР/ВР is different evidence from one ВР marker.
    normalized = re.sub(r"внутренн(?:яя|ей|юю|ая)?\s+резьб(?:а|ой|у)?", " вр ", text)
    normalized = re.sub(r"наружн(?:ая|ой|ую)?\s+резьб(?:а|ой|у)?", " нр ", normalized)
    tokens = re.findall(
        r"(?<![а-яa-z0-9])(?:вр|в/р|в\.р\.?|вн|нр|н/р|н\.р\.?)(?![а-яa-z0-9])",
        normalized,
    )
    result = []
    for token in tokens:
        result.append("female" if token.startswith(("в", "вн")) else "male")
    # Legacy shorthands used by supplier documents.
    for token, gender in (("вн/вн", "female"), ("в-в", "female")):
        if token in normalized and result.count(gender) < 2:
            result.extend([gender] * (2 - result.count(gender)))
    return tuple(sorted(result))


def _angles(value: str) -> tuple[int, ...]:
    text = _text(value)
    result = {
        int(number)
        for number in re.findall(r"(?<!\d)(45|90)\s*(?:°|гр\.?|град)", text)
    }
    if _family(value) == "elbow":
        result.update(
            int(number)
            for number in re.findall(r"(?<!\d)(45|90)(?!\d)", text)
        )
    return tuple(sorted(result))


def _pn(value: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                _decimal_string(number)
                for number in re.findall(
                    r"\b(?:pn|ру)\s*[-=]?\s*(\d+(?:[.,]\d+)?)",
                    _stripped(value),
                )
            },
            key=Decimal,
        )
    )


def _sdr(value: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                _decimal_string(number)
                for number in re.findall(
                    r"\bsdr\s*[-=]?\s*(\d+(?:[.,]\d+)?)",
                    _stripped(value),
                )
            },
            key=Decimal,
        )
    )


def _reinforcement(value: str) -> tuple[str, ...]:
    text = _stripped(value)
    result = []
    if any(marker in text for marker in ("fiber", "стекловолок", "фибров")):
        result.append("fiber")
    if any(marker in text for marker in ("алюмин", "aluminium", "aluminum")):
        result.append("aluminium")
    if "неармирован" in text or "без армирован" in text:
        result.append("none")
    if "армирован" in text and not result:
        result.append("unspecified")
    return tuple(sorted(set(result)))


def _weights(value: str) -> tuple[str, ...]:
    text = _text(value)
    result = {
        _decimal_string(number)
        for number in re.findall(
            r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:г|гр)\b",
            text,
        )
    }
    return tuple(sorted(result, key=Decimal))


def _directions(value: str) -> tuple[str, ...]:
    text = _text(value)
    result = set()
    if "вертикал" in text or "прямой выход" in text:
        result.add("vertical")
    if "горизонт" in text or "угловой выход" in text:
        result.add("horizontal")
    if "угловой" in text and "выход" not in text:
        result.add("angled")
    if "прямой" in text and "выход" not in text:
        result.add("straight")
    return tuple(sorted(result))


def _design_flags(value: str) -> tuple[str, ...]:
    text = _text(value)
    result = set()
    if "сух" in text and "сифон" in text:
        result.add("dry_siphon")
    if "эксцентр" in text:
        result.add("eccentric")
    if "наружной канализа" in text:
        result.add("external_sewer")
    if "внутренней канализа" in text:
        result.add("internal_sewer")
    if "с фильтр" in text:
        result.add("with_filter")
    if "без кроншт" in text:
        result.add("without_brackets")
    if "запорн" in text:
        result.add("shutoff")
    return tuple(sorted(result))


def build_technical_signature(value: str) -> TechnicalSignature:
    value = _bounded_text(value, max_bytes=MAX_NAME_BYTES)
    payload = {
        "normalizedName": normalize_name(value),
        "family": _family(value),
        "dimensions": list(_dimensions(value)),
        "diametersMm": list(_diameters(value)),
        "threadSizes": list(_thread_sizes(value)),
        "threadGenders": list(_thread_genders(value)),
        "anglesDeg": list(_angles(value)),
        "pnClasses": list(_pn(value)),
        "sdrClasses": list(_sdr(value)),
        "reinforcement": list(_reinforcement(value)),
        "directions": list(_directions(value)),
        "designFlags": list(_design_flags(value)),
        "weightsG": list(_weights(value)),
    }
    signature_sha256 = _canonical_sha256(payload)
    return TechnicalSignature(
        normalized_name=payload["normalizedName"],
        family=payload["family"],
        dimensions=tuple(payload["dimensions"]),
        diameters_mm=tuple(payload["diametersMm"]),
        thread_sizes=tuple(payload["threadSizes"]),
        thread_genders=tuple(payload["threadGenders"]),
        angles_deg=tuple(payload["anglesDeg"]),
        pn_classes=tuple(payload["pnClasses"]),
        sdr_classes=tuple(payload["sdrClasses"]),
        reinforcement=tuple(payload["reinforcement"]),
        directions=tuple(payload["directions"]),
        design_flags=tuple(payload["designFlags"]),
        weights_g=tuple(payload["weightsG"]),
        signature_sha256=signature_sha256,
    )


def match_names(
    requested: str,
    offered: str,
    requested_unit: str,
    offered_unit: str,
) -> NameMatchResult:
    requested = _bounded_text(requested, max_bytes=MAX_NAME_BYTES)
    offered = _bounded_text(offered, max_bytes=MAX_NAME_BYTES)
    if normalize_unit(requested_unit) != normalize_unit(offered_unit):
        return NameMatchResult(0, "fuzzy", True)

    requested_raw = requested.lower()
    offered_raw = offered.lower()
    if requested_raw == offered_raw:
        return NameMatchResult(10_000, "exact", False)

    requested_normalized = normalize_name(requested)
    offered_normalized = normalize_name(offered)
    if requested_normalized == offered_normalized:
        return NameMatchResult(9_900, "normalized", False)

    requested_numbers = numeric_signature(requested)
    offered_numbers = numeric_signature(offered)
    requested_dimensions = dimension_signature(requested)
    offered_dimensions = dimension_signature(offered)
    shared_dimension = bool(
        requested_dimensions
        and offered_dimensions
        and set(requested_dimensions).intersection(offered_dimensions)
    )
    number_conflict = bool(
        requested_numbers
        and offered_numbers
        and requested_numbers != offered_numbers
        and not shared_dimension
    )

    sequence_score = SequenceMatcher(
        None,
        requested_normalized,
        offered_normalized,
    ).ratio()
    requested_tokens = set(requested_normalized.split())
    offered_tokens = set(offered_normalized.split())
    jaccard = len(requested_tokens.intersection(offered_tokens)) / max(
        len(requested_tokens.union(offered_tokens)),
        1,
    )
    score = 0.65 * sequence_score + 0.35 * jaccard
    if (
        requested_numbers
        and offered_numbers
        and requested_numbers == offered_numbers
    ) or shared_dimension:
        score = min(1.0, score + 0.20)
    if number_conflict:
        score = min(score, 0.62)
    basis_points = max(0, min(10_000, round(score * 10_000)))
    return NameMatchResult(
        basis_points,
        "fuzzy",
        number_conflict or basis_points < 9_000,
    )


def _dn_thread_equivalent(first: str, second: str) -> bool:
    mapping = {
        "15": "1/2",
        "20": "3/4",
        "25": "1",
        "32": "1 1/4",
        "40": "1 1/2",
        "50": "2",
    }
    first_diameters = _diameters(first)
    second_diameters = _diameters(second)
    first_threads = _thread_sizes(first)
    second_threads = _thread_sizes(second)
    return any(mapping.get(diameter) in second_threads for diameter in first_diameters) or any(
        mapping.get(diameter) in first_threads for diameter in second_diameters
    )


def _canonical_diameter(value: str) -> str:
    match = re.search(
        r"(?:\bd\s*=?\s*|\bdu\s*|\bду\s*)(\d+(?:[.,]\d+)?)",
        _text(value),
    )
    return _decimal_string(match.group(1)) if match else ""


def _contains_number(value: str, number: str) -> bool:
    return bool(
        re.search(
            rf"(?<!\d){re.escape(number)}(?!\d)",
            _text(value).replace(",", "."),
        )
    )


def _signature_compatible(
    canonical: str,
    first: str,
    second: str,
    family: str,
    category: str,
) -> bool:
    category = category.lower()
    first_dimensions = set(_dimensions(first))
    second_dimensions = set(_dimensions(second))
    first_diameters = set(_diameters(first))
    second_diameters = set(_diameters(second))
    first_threads = set(_thread_sizes(first))
    second_threads = set(_thread_sizes(second))
    first_reinforcement = _reinforcement(first)
    second_reinforcement = _reinforcement(second)
    if (
        first_reinforcement
        and second_reinforcement
        and first_reinforcement != second_reinforcement
    ):
        return _pair_result(
            status=LEGACY_BLOCKED,
            decision=DECISION_INCOMPATIBLE,
            confidence_basis_points=confidence,
            reason_codes=("REINFORCEMENT_CONFLICT",),
            hash_payload=hash_payload,
        )

    first_angles = set(_angles(first))
    second_angles = set(_angles(second))
    first_genders = set(_thread_genders(first))
    second_genders = set(_thread_genders(second))

    if "теплоизоля" in category or family == "insulation":
        return bool(first_dimensions and first_dimensions == second_dimensions)

    if "трубы pp-r" in category or family == "ppr_pipe":
        return bool(
            first_dimensions
            and first_dimensions == second_dimensions
            and (not _pn(first) or not _pn(second) or _pn(first) == _pn(second))
            and (not _sdr(first) or not _sdr(second) or _sdr(first) == _sdr(second))
            and _reinforcement(first) == _reinforcement(second)
        )

    if "фитинги pp-r" in category or family in {
        "coupling",
        "elbow",
        "tee",
        "plug",
        "transition",
        "bypass",
    }:
        if first_dimensions and second_dimensions and first_dimensions != second_dimensions:
            return False
        if first_diameters and second_diameters and first_diameters != second_diameters:
            return False
        if first_threads and second_threads and first_threads != second_threads:
            return False
        if first_angles and second_angles and first_angles != second_angles:
            return False
        if first_genders and second_genders and first_genders != second_genders:
            return False
        canonical_diameter = _canonical_diameter(canonical)
        anchor = bool(
            (first_dimensions and second_dimensions)
            or (first_diameters and second_diameters)
            or (first_threads and second_threads)
            or (first_angles and second_angles)
            or (
                canonical_diameter
                and _contains_number(first, canonical_diameter)
                and _contains_number(second, canonical_diameter)
            )
        )
        return anchor or family == "bypass"

    if family in {"repair_coupling", "union"}:
        canonical_diameter = _canonical_diameter(canonical)
        return bool(
            (first_diameters and first_diameters == second_diameters)
            or (
                canonical_diameter
                and _contains_number(first, canonical_diameter)
                and _contains_number(second, canonical_diameter)
            )
            or (first_threads and first_threads == second_threads)
            or _dn_thread_equivalent(first, second)
        )

    if family == "sealant":
        return bool(_weights(first) and _weights(first) == _weights(second))

    if family == "radiator_kit":
        return bool(
            ((_thread_sizes(first) == _thread_sizes(second) and _thread_sizes(first)) or _dn_thread_equivalent(first, second))
            and (("без кроншт" in _text(first)) == ("без кроншт" in _text(second)))
        )

    if family == "valve":
        return bool(
            ((_thread_sizes(first) and _thread_sizes(first) == _thread_sizes(second)) or _dn_thread_equivalent(first, second))
            and _directions(first) == _directions(second)
            and (("запорн" in _text(first)) == ("запорн" in _text(second)))
        )

    return False


def _dedupe_codes(codes: Iterable[str]) -> tuple[str, ...]:
    result = []
    for code in codes:
        if code not in _REASON_MESSAGES:
            _fail()
        if code not in result:
            result.append(code)
    return tuple(result)


def _pair_result(
    *,
    status: str,
    decision: str,
    confidence_basis_points: int,
    reason_codes: Iterable[str],
    hash_payload: dict,
) -> TechnicalPairResult:
    if status not in {LEGACY_OK, LEGACY_REVIEW, LEGACY_BLOCKED}:
        _fail()
    if decision not in {
        DECISION_EXACT,
        DECISION_COMPARABLE,
        DECISION_REVIEW_REQUIRED,
        DECISION_INCOMPATIBLE,
    }:
        _fail()
    reason_codes = _dedupe_codes(reason_codes)
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "status": status,
        "decision": decision,
        "confidenceBasisPoints": confidence_basis_points,
        "reasonCodes": list(reason_codes),
        **hash_payload,
    }
    return TechnicalPairResult(
        status=status,
        decision=decision,
        confidence_basis_points=confidence_basis_points,
        reason_codes=reason_codes,
        comparison_sha256=_canonical_sha256(payload),
    )


def classify_supplier_pair(
    canonical_name: str,
    unit: str,
    supplier_1_names: Iterable[str],
    supplier_2_names: Iterable[str],
    *,
    category: str | None = None,
) -> TechnicalPairResult:
    """Classify whether two supplier quotations are technically comparable.

    ``status`` preserves the v0.9 calibration labels (``ok/review/blocked``),
    while ``decision`` exposes the integration-safe vocabulary.
    """

    canonical_name = _bounded_text(canonical_name, max_bytes=MAX_NAME_BYTES)
    unit = _bounded_text(unit, max_bytes=MAX_UNIT_BYTES, allow_empty=True)
    category = _bounded_text(
        category or "",
        max_bytes=MAX_CATEGORY_BYTES,
        allow_empty=True,
    )
    first_names = _bounded_names(supplier_1_names, "supplier_1_names")
    second_names = _bounded_names(supplier_2_names, "supplier_2_names")
    first = _joined_unique(first_names)
    second = _joined_unique(second_names)
    hash_payload = {
        "canonicalName": canonical_name,
        "unit": normalize_unit(unit),
        "category": category,
        "supplier1SignatureSha256": (
            build_technical_signature(first).signature_sha256 if first else ""
        ),
        "supplier2SignatureSha256": (
            build_technical_signature(second).signature_sha256 if second else ""
        ),
    }

    if not first or not second:
        return _pair_result(
            status=LEGACY_REVIEW,
            decision=DECISION_REVIEW_REQUIRED,
            confidence_basis_points=10_000,
            reason_codes=("ONLY_ONE_SUPPLIER_QUOTED",),
            hash_payload=hash_payload,
        )

    canonical_family = _family(canonical_name)
    first_family = _family(first)
    second_family = _family(second)
    first_match = match_names(canonical_name, first, unit, unit)
    second_match = match_names(canonical_name, second, unit, unit)
    confidence = min(
        first_match.confidence_basis_points,
        second_match.confidence_basis_points,
    )

    if first_family and second_family and first_family != second_family:
        return _pair_result(
            status=LEGACY_BLOCKED,
            decision=DECISION_INCOMPATIBLE,
            confidence_basis_points=confidence,
            reason_codes=("PRODUCT_FAMILY_CONFLICT",),
            hash_payload=hash_payload,
        )

    first_gender_signature = _thread_genders(first)
    second_gender_signature = _thread_genders(second)
    if (
        first_gender_signature
        and second_gender_signature
        and first_gender_signature != second_gender_signature
    ):
        return _pair_result(
            status=LEGACY_BLOCKED,
            decision=DECISION_INCOMPATIBLE,
            confidence_basis_points=confidence,
            reason_codes=("THREAD_GENDER_CONFLICT",),
            hash_payload=hash_payload,
        )

    first_reinforcement = _reinforcement(first)
    second_reinforcement = _reinforcement(second)
    if (
        first_reinforcement
        and second_reinforcement
        and first_reinforcement != second_reinforcement
    ):
        return _pair_result(
            status=LEGACY_BLOCKED,
            decision=DECISION_INCOMPATIBLE,
            confidence_basis_points=confidence,
            reason_codes=("REINFORCEMENT_CONFLICT",),
            hash_payload=hash_payload,
        )

    first_angles = set(_angles(first))
    second_angles = set(_angles(second))
    if first_angles and second_angles and first_angles != second_angles:
        return _pair_result(
            status=LEGACY_BLOCKED,
            decision=DECISION_INCOMPATIBLE,
            confidence_basis_points=confidence,
            reason_codes=("ANGLE_CONFLICT",),
            hash_payload=hash_payload,
        )

    reason_codes = []
    if _directions(first) and _directions(second) and _directions(first) != _directions(second):
        reason_codes.append("DIRECTION_OR_DESIGN_DIFFERS")
    if _weights(first) and _weights(second) and _weights(first) != _weights(second):
        reason_codes.append("PACKAGING_OR_WEIGHT_DIFFERS")
    first_text = _text(first)
    second_text = _text(second)
    if (("сух" in first_text and "сифон" in first_text) != ("сух" in second_text and "сифон" in second_text)):
        reason_codes.append("DRY_SIPHON_DESIGN_DIFFERS")
    pair_family = canonical_family or first_family or second_family
    if pair_family == "transition" and (("эксцентр" in first_text) != ("эксцентр" in second_text)):
        reason_codes.append("ECCENTRICITY_DIFFERS")
    if pair_family == "sewer_pipe" and (("наружной канализа" in first_text) != ("наружной канализа" in second_text)):
        reason_codes.append("SEWER_APPLICATION_DIFFERS")

    if _signature_compatible(
        canonical_name,
        first,
        second,
        pair_family,
        category,
    ) and not reason_codes:
        return _pair_result(
            status=LEGACY_OK,
            decision=DECISION_COMPARABLE,
            confidence_basis_points=max(confidence, 9_400),
            reason_codes=("COMPATIBLE_ENGINEERING_SIGNATURE",),
            hash_payload=hash_payload,
        )

    if canonical_family in _MODEL_SENSITIVE_FAMILIES:
        reason_codes.append("MODEL_SENSITIVE_FAMILY")
    if confidence < 7_200:
        reason_codes.append("WEAK_NOMENCLATURE_MATCH")
    if reason_codes:
        return _pair_result(
            status=LEGACY_REVIEW,
            decision=DECISION_REVIEW_REQUIRED,
            confidence_basis_points=confidence,
            reason_codes=reason_codes,
            hash_payload=hash_payload,
        )
    if first_family and second_family and first_family == second_family and confidence >= 7_200:
        return _pair_result(
            status=LEGACY_OK,
            decision=DECISION_COMPARABLE,
            confidence_basis_points=confidence,
            reason_codes=("SAME_FAMILY_NO_CRITICAL_CONFLICT",),
            hash_payload=hash_payload,
        )
    return _pair_result(
        status=LEGACY_REVIEW,
        decision=DECISION_REVIEW_REQUIRED,
        confidence_basis_points=confidence,
        reason_codes=("INSUFFICIENT_TECHNICAL_EVIDENCE",),
        hash_payload=hash_payload,
    )


def _line_result(
    *,
    status: str,
    decision: str,
    confidence_basis_points: int,
    reason_codes: Iterable[str],
    required_signature: TechnicalSignature,
    offered_signature: TechnicalSignature,
    required_unit: str,
    offered_unit: str,
    category: str,
) -> TechnicalLineResult:
    reason_codes = _dedupe_codes(reason_codes)
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "status": status,
        "decision": decision,
        "confidenceBasisPoints": confidence_basis_points,
        "reasonCodes": list(reason_codes),
        "requiredSignatureSha256": required_signature.signature_sha256,
        "offeredSignatureSha256": offered_signature.signature_sha256,
        "requiredUnit": normalize_unit(required_unit),
        "offeredUnit": normalize_unit(offered_unit),
        "category": category,
    }
    return TechnicalLineResult(
        status=status,
        decision=decision,
        confidence_basis_points=confidence_basis_points,
        reason_codes=reason_codes,
        required_signature=required_signature,
        offered_signature=offered_signature,
        comparison_sha256=_canonical_sha256(payload),
    )


def _missing_required_codes(required: TechnicalSignature, offered: TechnicalSignature) -> list[str]:
    codes = []
    checks = (
        (required.dimensions, offered.dimensions, "REQUIRED_DIMENSION_MISSING"),
        (required.diameters_mm, offered.diameters_mm, "REQUIRED_DIAMETER_MISSING"),
        (required.thread_sizes, offered.thread_sizes, "REQUIRED_THREAD_SIZE_MISSING"),
        (required.thread_genders, offered.thread_genders, "REQUIRED_THREAD_GENDER_MISSING"),
        (required.angles_deg, offered.angles_deg, "REQUIRED_ANGLE_MISSING"),
    )
    for required_values, offered_values, code in checks:
        if required_values and not offered_values:
            codes.append(code)
    if required.pn_classes and not offered.pn_classes:
        codes.append("PRESSURE_CLASS_MISSING")
    if required.sdr_classes and not offered.sdr_classes:
        codes.append("SDR_MISSING")
    if required.reinforcement and not offered.reinforcement:
        codes.append("REINFORCEMENT_MISSING")
    return codes


def compare_required_to_offer(
    required_name: str,
    offered_name: str,
    *,
    required_unit: str = "",
    offered_unit: str = "",
    category: str | None = None,
) -> TechnicalLineResult:
    """Compare one requested material line with one offered line.

    The function is fail-closed: missing required attributes or uncertain
    model-sensitive families return ``review_required``. Fuzzy similarity can
    never override a detected engineering conflict.
    """

    required_name = _bounded_text(required_name, max_bytes=MAX_NAME_BYTES)
    offered_name = _bounded_text(offered_name, max_bytes=MAX_NAME_BYTES)
    required_unit = _bounded_text(
        required_unit,
        max_bytes=MAX_UNIT_BYTES,
        allow_empty=True,
    )
    offered_unit = _bounded_text(
        offered_unit,
        max_bytes=MAX_UNIT_BYTES,
        allow_empty=True,
    )
    category = _bounded_text(
        category or "",
        max_bytes=MAX_CATEGORY_BYTES,
        allow_empty=True,
    )

    required = build_technical_signature(required_name)
    offered = build_technical_signature(offered_name)
    name_match = match_names(
        required_name,
        offered_name,
        required_unit,
        offered_unit,
    )
    hard_conflicts = []
    review_reasons = []

    if normalize_unit(required_unit) != normalize_unit(offered_unit):
        review_reasons.append("UNIT_CONFLICT")

    if required.family and offered.family and required.family != offered.family:
        hard_conflicts.append("PRODUCT_FAMILY_CONFLICT")

    comparable_sets = (
        (required.dimensions, offered.dimensions, "DIMENSION_CONFLICT"),
        (required.diameters_mm, offered.diameters_mm, "DIAMETER_CONFLICT"),
        (required.thread_sizes, offered.thread_sizes, "THREAD_SIZE_CONFLICT"),
        (required.angles_deg, offered.angles_deg, "ANGLE_CONFLICT"),
    )
    for required_values, offered_values, code in comparable_sets:
        if required_values and offered_values and set(required_values).isdisjoint(offered_values):
            hard_conflicts.append(code)

    if (
        required.thread_genders
        and offered.thread_genders
        and required.thread_genders != offered.thread_genders
    ):
        hard_conflicts.append("THREAD_GENDER_CONFLICT")

    if required.reinforcement and offered.reinforcement and required.reinforcement != offered.reinforcement:
        hard_conflicts.append("REINFORCEMENT_CONFLICT")

    if required.pn_classes and offered.pn_classes:
        required_pn = max(Decimal(value) for value in required.pn_classes)
        offered_pn = max(Decimal(value) for value in offered.pn_classes)
        if offered_pn < required_pn:
            hard_conflicts.append("PRESSURE_CLASS_BELOW_REQUIRED")
        elif offered_pn > required_pn:
            review_reasons.append("PRESSURE_CLASS_ABOVE_REQUIRED")

    if required.sdr_classes and offered.sdr_classes:
        required_sdr = min(Decimal(value) for value in required.sdr_classes)
        offered_sdr = min(Decimal(value) for value in offered.sdr_classes)
        if offered_sdr > required_sdr:
            hard_conflicts.append("SDR_WEAKER_THAN_REQUIRED")
        elif offered_sdr < required_sdr:
            review_reasons.append("SDR_DIFFERS")

    required_flags = set(required.design_flags)
    offered_flags = set(offered.design_flags)
    if bool(required_flags.intersection({"external_sewer"})) != bool(
        offered_flags.intersection({"external_sewer"})
    ) and (required.family or offered.family) == "sewer_pipe":
        hard_conflicts.append("SEWER_APPLICATION_DIFFERS")
    if bool("dry_siphon" in required_flags) != bool("dry_siphon" in offered_flags):
        review_reasons.append("DRY_SIPHON_DESIGN_DIFFERS")
    if bool("eccentric" in required_flags) != bool("eccentric" in offered_flags):
        review_reasons.append("ECCENTRICITY_DIFFERS")
    if required.directions and offered.directions and required.directions != offered.directions:
        review_reasons.append("DIRECTION_OR_DESIGN_DIFFERS")
    if required.weights_g and offered.weights_g and required.weights_g != offered.weights_g:
        review_reasons.append("PACKAGING_OR_WEIGHT_DIFFERS")

    review_reasons.extend(_missing_required_codes(required, offered))

    if hard_conflicts:
        return _line_result(
            status=LEGACY_BLOCKED,
            decision=DECISION_INCOMPATIBLE,
            confidence_basis_points=name_match.confidence_basis_points,
            reason_codes=hard_conflicts,
            required_signature=required,
            offered_signature=offered,
            required_unit=required_unit,
            offered_unit=offered_unit,
            category=category,
        )

    exact_normalized = (
        required.normalized_name == offered.normalized_name
        and normalize_unit(required_unit) == normalize_unit(offered_unit)
    )
    if exact_normalized and not review_reasons:
        return _line_result(
            status=LEGACY_OK,
            decision=DECISION_EXACT,
            confidence_basis_points=max(name_match.confidence_basis_points, 9_900),
            reason_codes=("EXACT_NORMALIZED_NAME",),
            required_signature=required,
            offered_signature=offered,
            required_unit=required_unit,
            offered_unit=offered_unit,
            category=category,
        )

    family = required.family or offered.family
    signature_ok = _signature_compatible(
        required_name,
        required_name,
        offered_name,
        family,
        category,
    )
    if family in _MODEL_SENSITIVE_FAMILIES:
        review_reasons.append("MODEL_SENSITIVE_FAMILY")
    if name_match.confidence_basis_points < 7_200:
        review_reasons.append("WEAK_NOMENCLATURE_MATCH")

    if review_reasons:
        return _line_result(
            status=LEGACY_REVIEW,
            decision=DECISION_REVIEW_REQUIRED,
            confidence_basis_points=name_match.confidence_basis_points,
            reason_codes=review_reasons,
            required_signature=required,
            offered_signature=offered,
            required_unit=required_unit,
            offered_unit=offered_unit,
            category=category,
        )

    if signature_ok:
        return _line_result(
            status=LEGACY_OK,
            decision=DECISION_COMPARABLE,
            confidence_basis_points=max(name_match.confidence_basis_points, 9_400),
            reason_codes=("COMPATIBLE_ENGINEERING_SIGNATURE",),
            required_signature=required,
            offered_signature=offered,
            required_unit=required_unit,
            offered_unit=offered_unit,
            category=category,
        )

    if required.family and required.family == offered.family and name_match.confidence_basis_points >= 7_200:
        return _line_result(
            status=LEGACY_REVIEW,
            decision=DECISION_REVIEW_REQUIRED,
            confidence_basis_points=name_match.confidence_basis_points,
            reason_codes=("INSUFFICIENT_TECHNICAL_EVIDENCE",),
            required_signature=required,
            offered_signature=offered,
            required_unit=required_unit,
            offered_unit=offered_unit,
            category=category,
        )

    return _line_result(
        status=LEGACY_REVIEW,
        decision=DECISION_REVIEW_REQUIRED,
        confidence_basis_points=name_match.confidence_basis_points,
        reason_codes=("INSUFFICIENT_TECHNICAL_EVIDENCE",),
        required_signature=required,
        offered_signature=offered,
        required_unit=required_unit,
        offered_unit=offered_unit,
        category=category,
    )


__all__ = [
    "CONTRACT_VERSION",
    "DECISION_COMPARABLE",
    "DECISION_EXACT",
    "DECISION_INCOMPATIBLE",
    "DECISION_REVIEW_REQUIRED",
    "LEGACY_BLOCKED",
    "LEGACY_OK",
    "LEGACY_REVIEW",
    "NameMatchResult",
    "TechnicalComparisonError",
    "TechnicalLineResult",
    "TechnicalPairResult",
    "TechnicalSignature",
    "build_technical_signature",
    "classify_supplier_pair",
    "compare_required_to_offer",
    "dimension_signature",
    "match_names",
    "normalize_name",
    "normalize_unit",
    "numeric_signature",
]
