"""Pure scoring for an approved synthetic model evaluation; no I/O."""

import math
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from backend.features.model_gateway.evaluation_set import ModelEvaluationSet


MODEL_EVALUATION_RESULT_INVALID = "model_evaluation_result_invalid"
MODEL_EVALUATION_NOT_APPROVED = "model_evaluation_not_approved"
_CASE_ID_RE = re.compile(r"^hw-[0-9]{3}$")
_WORK_ID_RE = re.compile(r"^w[0-9]{1,2}$")
_MAX_DURATION_MS = 120_000
_MAX_TOKEN_COUNT = 10_000_000


class OfflineEvaluationError(ValueError):
    def __init__(self, code=MODEL_EVALUATION_RESULT_INVALID):
        if code not in {
            MODEL_EVALUATION_RESULT_INVALID,
            MODEL_EVALUATION_NOT_APPROVED,
        }:
            code = MODEL_EVALUATION_RESULT_INVALID
        self.code = code
        super().__init__(code)


def _fail(code=MODEL_EVALUATION_RESULT_INVALID):
    raise OfflineEvaluationError(code) from None


@dataclass(frozen=True)
class OfflineEvaluationObservation:
    case_id: str
    predicted_hidden_ids: Tuple[str, ...]
    duration_ms: int
    input_tokens: Optional[int]
    output_tokens: Optional[int]


def build_offline_observation(
    *,
    case_id,
    predicted_hidden_ids,
    duration_ms,
    input_tokens,
    output_tokens,
):
    if type(case_id) is not str or _CASE_ID_RE.fullmatch(case_id) is None:
        _fail()
    if (
        type(predicted_hidden_ids) is not tuple
        or len(predicted_hidden_ids) > 12
        or any(
            type(work_id) is not str
            or _WORK_ID_RE.fullmatch(work_id) is None
            for work_id in predicted_hidden_ids
        )
        or len(predicted_hidden_ids) != len(set(predicted_hidden_ids))
    ):
        _fail()
    if (
        type(duration_ms) is not int
        or not 0 <= duration_ms <= _MAX_DURATION_MS
    ):
        _fail()
    if (input_tokens is None) != (output_tokens is None):
        _fail()
    if input_tokens is not None:
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or not 0 <= input_tokens <= _MAX_TOKEN_COUNT
            or not 0 <= output_tokens <= _MAX_TOKEN_COUNT
        ):
            _fail()
    return OfflineEvaluationObservation(
        case_id=case_id,
        predicted_hidden_ids=predicted_hidden_ids,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _rate(numerator, denominator):
    if denominator <= 0:
        _fail()
    return numerator / denominator


def _nearest_rank_p95(values):
    ordered = sorted(values)
    rank = math.ceil(len(ordered) * 0.95)
    return ordered[rank - 1]


def _threshold_document(thresholds):
    return {
        "minimumExactMatchRate": thresholds.minimum_exact_match_rate,
        "maximumFalseNegativeRate": thresholds.maximum_false_negative_rate,
        "maximumFalsePositiveRate": thresholds.maximum_false_positive_rate,
        "maximumP95LatencyMs": thresholds.maximum_p95_latency_ms,
        "maximumAverageOutputTokens": thresholds.maximum_average_output_tokens,
        "minimumTokenCoverageRate": thresholds.minimum_token_coverage_rate,
    }


def score_hidden_works_evaluation(
    evaluation,
    observations,
    *,
    approved_sha256,
):
    if type(evaluation) is not ModelEvaluationSet:
        _fail()
    if (
        type(approved_sha256) is not str
        or approved_sha256 != evaluation.sha256
    ):
        _fail(MODEL_EVALUATION_NOT_APPROVED)
    if (
        type(observations) is not tuple
        or len(observations) != len(evaluation.cases)
        or any(
            type(observation) is not OfflineEvaluationObservation
            for observation in observations
        )
    ):
        _fail()

    observations = tuple(
        build_offline_observation(
            case_id=observation.case_id,
            predicted_hidden_ids=observation.predicted_hidden_ids,
            duration_ms=observation.duration_ms,
            input_tokens=observation.input_tokens,
            output_tokens=observation.output_tokens,
        )
        for observation in observations
    )

    observations_by_id = {
        observation.case_id: observation for observation in observations
    }
    expected_case_ids = {case.case_id for case in evaluation.cases}
    if (
        len(observations_by_id) != len(observations)
        or set(observations_by_id) != expected_case_ids
    ):
        _fail()

    exact_matches = 0
    false_negatives = 0
    false_positives = 0
    positive_labels = 0
    negative_labels = 0
    durations = []
    measured_output_tokens = []

    for case in evaluation.cases:
        observation = observations_by_id[case.case_id]
        known_ids = {work.work_id for work in case.works}
        predicted_ids = set(observation.predicted_hidden_ids)
        expected_ids = set(case.expected_hidden_ids)
        if not predicted_ids.issubset(known_ids):
            _fail()
        exact_matches += predicted_ids == expected_ids
        false_negatives += len(expected_ids - predicted_ids)
        false_positives += len(predicted_ids - expected_ids)
        positive_labels += len(expected_ids)
        negative_labels += len(known_ids - expected_ids)
        durations.append(observation.duration_ms)
        if observation.output_tokens is not None:
            measured_output_tokens.append(observation.output_tokens)

    token_coverage = _rate(
        len(measured_output_tokens),
        len(observations),
    )
    average_output_tokens = (
        sum(measured_output_tokens) / len(measured_output_tokens)
        if measured_output_tokens
        else None
    )
    metrics = {
        "exactMatchRate": _rate(exact_matches, len(observations)),
        "falseNegativeRate": _rate(false_negatives, positive_labels),
        "falsePositiveRate": _rate(false_positives, negative_labels),
        "p95LatencyMs": _nearest_rank_p95(durations),
        "averageOutputTokens": average_output_tokens,
        "tokenCoverageRate": token_coverage,
    }
    thresholds = evaluation.thresholds
    gates = (
        (
            "minimumExactMatchRate",
            metrics["exactMatchRate"] >= thresholds.minimum_exact_match_rate,
        ),
        (
            "maximumFalseNegativeRate",
            metrics["falseNegativeRate"] <= thresholds.maximum_false_negative_rate,
        ),
        (
            "maximumFalsePositiveRate",
            metrics["falsePositiveRate"] <= thresholds.maximum_false_positive_rate,
        ),
        (
            "maximumP95LatencyMs",
            metrics["p95LatencyMs"] <= thresholds.maximum_p95_latency_ms,
        ),
        (
            "maximumAverageOutputTokens",
            average_output_tokens is not None
            and average_output_tokens <= thresholds.maximum_average_output_tokens,
        ),
        (
            "minimumTokenCoverageRate",
            token_coverage >= thresholds.minimum_token_coverage_rate,
        ),
    )
    failed_gates = [name for name, passed in gates if not passed]
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "capability": evaluation.capability,
        "evaluationSha256": evaluation.sha256,
        "humanApproved": True,
        "caseCount": len(evaluation.cases),
        "metrics": metrics,
        "thresholds": _threshold_document(thresholds),
        "failedGates": failed_gates,
        "accepted": not failed_gates,
        "productionTrafficAllowed": False,
    }
