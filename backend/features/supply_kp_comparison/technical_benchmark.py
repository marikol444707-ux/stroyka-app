"""Pure benchmark harness for the A8.5 technical matcher.

The harness accepts already-frozen human labels and never changes matcher
rules, files or business data. It reports false-safe and dangerous errors
separately so an attractive average accuracy cannot hide an unsafe decision.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping

from .technical_matcher import (
    LEGACY_BLOCKED,
    LEGACY_OK,
    LEGACY_REVIEW,
    TechnicalComparisonError,
    classify_supplier_pair,
)


BENCHMARK_VERSION = 1
MAX_CASES = 10_000
_ERROR = "supply_technical_benchmark_invalid"
_EXPECTED_STATUSES = frozenset({LEGACY_OK, LEGACY_REVIEW, LEGACY_BLOCKED})


class TechnicalBenchmarkError(ValueError):
    def __init__(self):
        self.code = _ERROR
        super().__init__(self.code)


def _fail() -> None:
    raise TechnicalBenchmarkError() from None


def _text(value, *, limit: int, allow_empty: bool = False) -> str:
    if type(value) is not str or "\x00" in value:
        _fail()
    result = value.strip()
    if not allow_empty and not result:
        _fail()
    if len(result.encode("utf-8")) > limit:
        _fail()
    return result


def _names(value) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or len(value) > 100:
        _fail()
    return [_text(item, limit=4 * 1024) for item in value]


def _sha256(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _case(value: Mapping) -> dict:
    if not isinstance(value, Mapping):
        _fail()
    expected = _text(value.get("expectedStatus"), limit=32)
    if expected not in _EXPECTED_STATUSES:
        _fail()
    return {
        "caseId": _text(value.get("caseId"), limit=160),
        "canonicalName": _text(value.get("canonicalName"), limit=4 * 1024),
        "unit": _text(value.get("unit") or "", limit=64, allow_empty=True),
        "category": _text(
            value.get("category") or "",
            limit=512,
            allow_empty=True,
        ),
        "supplier1Names": _names(value.get("supplier1Names") or []),
        "supplier2Names": _names(value.get("supplier2Names") or []),
        "expectedStatus": expected,
    }


def run_technical_benchmark(cases) -> dict:
    if isinstance(cases, (str, bytes)) or not isinstance(cases, (list, tuple)):
        _fail()
    if not 1 <= len(cases) <= MAX_CASES:
        _fail()
    normalized = [_case(case) for case in cases]
    case_ids = [case["caseId"] for case in normalized]
    if len(case_ids) != len(set(case_ids)):
        _fail()

    confusion = Counter()
    results = []
    for case in normalized:
        try:
            predicted = classify_supplier_pair(
                case["canonicalName"],
                case["unit"],
                case["supplier1Names"],
                case["supplier2Names"],
                category=case["category"],
            )
        except TechnicalComparisonError as exc:
            raise TechnicalBenchmarkError() from exc
        expected = case["expectedStatus"]
        confusion[(expected, predicted.status)] += 1
        results.append(
            {
                "caseId": case["caseId"],
                "expectedStatus": expected,
                "predictedStatus": predicted.status,
                "correct": expected == predicted.status,
                "confidenceBasisPoints": predicted.confidence_basis_points,
                "reasonCodes": list(predicted.reason_codes),
                "comparisonSha256": predicted.comparison_sha256,
            }
        )

    false_safe = [
        result
        for result in results
        if result["expectedStatus"] in {LEGACY_REVIEW, LEGACY_BLOCKED}
        and result["predictedStatus"] == LEGACY_OK
    ]
    dangerous = [
        result
        for result in results
        if result["expectedStatus"] == LEGACY_BLOCKED
        and result["predictedStatus"] == LEGACY_OK
    ]
    mismatches = [result for result in results if not result["correct"]]
    correct_count = len(results) - len(mismatches)
    accuracy_basis_points = round(correct_count * 10_000 / len(results))
    confusion_map = {
        f"{expected}->{predicted}": count
        for (expected, predicted), count in sorted(confusion.items())
    }
    report_without_hash = {
        "benchmarkVersion": BENCHMARK_VERSION,
        "totalCases": len(results),
        "correctCases": correct_count,
        "accuracyBasisPoints": accuracy_basis_points,
        "falseSafeCount": len(false_safe),
        "dangerousErrorCount": len(dangerous),
        "confusion": confusion_map,
        "mismatches": mismatches,
        "results": results,
        "writesAttempted": 0,
        "modelCalls": 0,
    }
    return {
        **report_without_hash,
        "benchmarkSha256": _sha256(report_without_hash),
    }


__all__ = [
    "BENCHMARK_VERSION",
    "TechnicalBenchmarkError",
    "run_technical_benchmark",
]
