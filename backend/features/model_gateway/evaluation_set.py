"""Strict offline evaluation-set contract; never calls a model or production data."""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


MODEL_EVALUATION_SET_INVALID = "model_evaluation_set_invalid"
_MAX_FILE_BYTES = 64 * 1024
_CASE_ID_RE = re.compile(r"^hw-[0-9]{3}$")
_WORK_ID_RE = re.compile(r"^w[0-9]{1,2}$")
_PII_PATTERNS = (
    re.compile(r"https?://|www\.", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?:\d[\s()+.-]*){6,}"),
    re.compile(
        r"\b(?:инн|кпп|огрн|паспорт|телефон|e-mail|email|адрес)\b",
        re.IGNORECASE,
    ),
)


class ModelEvaluationSetError(ValueError):
    def __init__(self):
        self.code = MODEL_EVALUATION_SET_INVALID
        super().__init__(self.code)


def _fail():
    raise ModelEvaluationSetError() from None


def _exact_dict(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        _fail()
    return value


def _number(value, *, minimum, maximum):
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail()
    normalized = float(value)
    if not minimum <= normalized <= maximum:
        _fail()
    return normalized


def _bounded_name(value):
    if (
        type(value) is not str
        or value != value.strip()
        or not 3 <= len(value) <= 200
        or any(ord(character) < 32 for character in value)
        or any(pattern.search(value) for pattern in _PII_PATTERNS)
    ):
        _fail()
    return value


@dataclass(frozen=True)
class EvaluationThresholds:
    minimum_exact_match_rate: float
    maximum_false_negative_rate: float
    maximum_false_positive_rate: float
    maximum_p95_latency_ms: int
    maximum_average_output_tokens: int
    minimum_token_coverage_rate: float


@dataclass(frozen=True)
class EvaluationWork:
    work_id: str
    name: str


@dataclass(frozen=True)
class HiddenWorksEvaluationCase:
    case_id: str
    works: tuple
    expected_hidden_ids: tuple


@dataclass(frozen=True)
class ModelEvaluationSet:
    version: str
    capability: str
    source: str
    thresholds: EvaluationThresholds
    cases: tuple

    @property
    def canonical_document(self):
        return {
            "version": self.version,
            "capability": self.capability,
            "source": self.source,
            "thresholds": {
                "minimumExactMatchRate": self.thresholds.minimum_exact_match_rate,
                "maximumFalseNegativeRate": self.thresholds.maximum_false_negative_rate,
                "maximumFalsePositiveRate": self.thresholds.maximum_false_positive_rate,
                "maximumP95LatencyMs": self.thresholds.maximum_p95_latency_ms,
                "maximumAverageOutputTokens": self.thresholds.maximum_average_output_tokens,
                "minimumTokenCoverageRate": self.thresholds.minimum_token_coverage_rate,
            },
            "cases": [
                {
                    "id": case.case_id,
                    "works": [
                        {"id": work.work_id, "name": work.name}
                        for work in case.works
                    ],
                    "expectedHiddenIds": list(case.expected_hidden_ids),
                }
                for case in self.cases
            ],
        }

    @property
    def sha256(self):
        encoded = json.dumps(
            self.canonical_document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _validated_thresholds(value):
    value = _exact_dict(value, (
        "minimumExactMatchRate", "maximumFalseNegativeRate",
        "maximumFalsePositiveRate", "maximumP95LatencyMs",
        "maximumAverageOutputTokens", "minimumTokenCoverageRate",
    ))
    exact = _number(value["minimumExactMatchRate"], minimum=0.92, maximum=1)
    false_negative = _number(
        value["maximumFalseNegativeRate"], minimum=0, maximum=0,
    )
    false_positive = _number(
        value["maximumFalsePositiveRate"], minimum=0, maximum=0.1,
    )
    latency = value["maximumP95LatencyMs"]
    output_tokens = value["maximumAverageOutputTokens"]
    if type(latency) is not int or not 100 <= latency <= 15_000:
        _fail()
    if type(output_tokens) is not int or not 1 <= output_tokens <= 500:
        _fail()
    coverage = _number(
        value["minimumTokenCoverageRate"], minimum=0.95, maximum=1,
    )
    return EvaluationThresholds(
        exact, false_negative, false_positive, latency, output_tokens, coverage,
    )


def _validated_case(value):
    value = _exact_dict(value, ("id", "works", "expectedHiddenIds"))
    case_id = value["id"]
    if type(case_id) is not str or _CASE_ID_RE.fullmatch(case_id) is None:
        _fail()
    if type(value["works"]) is not list or not 2 <= len(value["works"]) <= 12:
        _fail()
    works = []
    for raw_work in value["works"]:
        raw_work = _exact_dict(raw_work, ("id", "name"))
        work_id = raw_work["id"]
        if type(work_id) is not str or _WORK_ID_RE.fullmatch(work_id) is None:
            _fail()
        works.append(EvaluationWork(work_id, _bounded_name(raw_work["name"])))
    ids = [work.work_id for work in works]
    names = [work.name.casefold() for work in works]
    if len(ids) != len(set(ids)) or len(names) != len(set(names)):
        _fail()
    expected = value["expectedHiddenIds"]
    if (
        type(expected) is not list
        or any(type(item) is not str for item in expected)
        or len(expected) != len(set(expected))
        or not set(expected).issubset(ids)
    ):
        _fail()
    return HiddenWorksEvaluationCase(case_id, tuple(works), tuple(expected))


def validate_evaluation_document(document):
    document = _exact_dict(
        document,
        ("version", "capability", "source", "thresholds", "cases"),
    )
    if (
        document["version"] != "model-evaluation-v1"
        or document["capability"] != "hidden_works_detection"
        or document["source"] != "synthetic"
        or type(document["cases"]) is not list
        or not 10 <= len(document["cases"]) <= 100
    ):
        _fail()
    thresholds = _validated_thresholds(document["thresholds"])
    cases = tuple(_validated_case(case) for case in document["cases"])
    case_ids = [case.case_id for case in cases]
    positives = sum(len(case.expected_hidden_ids) for case in cases)
    negatives = sum(len(case.works) - len(case.expected_hidden_ids) for case in cases)
    if len(case_ids) != len(set(case_ids)) or positives < 10 or negatives < 10:
        _fail()
    return ModelEvaluationSet(
        document["version"], document["capability"], document["source"],
        thresholds, cases,
    )


def load_evaluation_set(path):
    try:
        path = Path(path)
        if path.stat().st_size > _MAX_FILE_BYTES:
            _fail()
        document = json.loads(path.read_text(encoding="utf-8"))
    except ModelEvaluationSetError:
        raise
    except Exception:
        _fail()
    return validate_evaluation_document(document)


def build_evaluation_readiness(evaluation, *, approved_sha256=None):
    if type(evaluation) is not ModelEvaluationSet:
        _fail()
    approved = (
        type(approved_sha256) is str
        and approved_sha256 == evaluation.sha256
    )
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "version": evaluation.version,
        "capability": evaluation.capability,
        "source": evaluation.source,
        "caseCount": len(evaluation.cases),
        "evaluationSha256": evaluation.sha256,
        "humanApproved": approved,
        "readyForOfflineEvaluation": approved,
        "productionTrafficAllowed": False,
    }


def build_tuning_readiness(baseline, tuning):
    if (
        type(baseline) is not ModelEvaluationSet
        or type(tuning) is not ModelEvaluationSet
        or baseline.capability != tuning.capability
        or baseline.source != tuning.source
        or baseline.thresholds != tuning.thresholds
    ):
        _fail()
    baseline_case_ids = {case.case_id for case in baseline.cases}
    tuning_case_ids = {case.case_id for case in tuning.cases}
    baseline_work_names = {
        work.name.casefold()
        for case in baseline.cases
        for work in case.works
    }
    tuning_work_names = {
        work.name.casefold()
        for case in tuning.cases
        for work in case.works
    }
    if (
        baseline_case_ids & tuning_case_ids
        or baseline_work_names & tuning_work_names
    ):
        _fail()
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "capability": tuning.capability,
        "baselineCaseCount": len(baseline.cases),
        "tuningCaseCount": len(tuning.cases),
        "baselineSha256": baseline.sha256,
        "tuningSha256": tuning.sha256,
        "caseIdsDisjoint": True,
        "workNamesDisjoint": True,
        "readyForPromptTuning": True,
        "freshHoldoutRequired": True,
        "readyForOfflineEvaluation": False,
        "productionTrafficAllowed": False,
    }
