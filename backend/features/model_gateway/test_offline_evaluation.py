import unittest
from pathlib import Path

from backend.features.model_gateway.evaluation_set import load_evaluation_set
from backend.features.model_gateway.offline_evaluation import (
    MODEL_EVALUATION_NOT_APPROVED,
    OfflineEvaluationError,
    OfflineEvaluationObservation,
    build_offline_observation,
    score_hidden_works_evaluation,
)


EVALUATION_PATH = (
    Path(__file__).with_name("evaluation_sets")
    / "hidden_works_detection.v1.json"
)
EVALUATION_SHA256 = (
    "444cb34e19858e801b85f441de924f661af4978605a0b852bc0aeac4ccd63840"
)


def _perfect_observations(evaluation):
    return tuple(
        build_offline_observation(
            case_id=case.case_id,
            predicted_hidden_ids=case.expected_hidden_ids,
            duration_ms=100 + index,
            input_tokens=80 + index,
            output_tokens=20 + index,
        )
        for index, case in enumerate(evaluation.cases)
    )


class OfflineEvaluationTest(unittest.TestCase):
    def test_perfect_approved_run_passes_without_enabling_production(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)

        report = score_hidden_works_evaluation(
            evaluation,
            _perfect_observations(evaluation),
            approved_sha256=EVALUATION_SHA256,
        )

        self.assertTrue(report["accepted"])
        self.assertEqual(report["evaluationSha256"], EVALUATION_SHA256)
        self.assertEqual(report["caseCount"], 12)
        self.assertEqual(report["metrics"], {
            "exactMatchRate": 1.0,
            "falseNegativeRate": 0.0,
            "falsePositiveRate": 0.0,
            "p95LatencyMs": 111,
            "averageOutputTokens": 25.5,
            "tokenCoverageRate": 1.0,
        })
        self.assertEqual(report["failedGates"], [])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertFalse(report["productionTrafficAllowed"])

    def test_false_negative_is_a_blocking_failure(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)
        observations = list(_perfect_observations(evaluation))
        first = observations[0]
        observations[0] = build_offline_observation(
            case_id=first.case_id,
            predicted_hidden_ids=(),
            duration_ms=first.duration_ms,
            input_tokens=first.input_tokens,
            output_tokens=first.output_tokens,
        )

        report = score_hidden_works_evaluation(
            evaluation,
            tuple(observations),
            approved_sha256=EVALUATION_SHA256,
        )

        self.assertFalse(report["accepted"])
        self.assertGreater(report["metrics"]["falseNegativeRate"], 0)
        self.assertIn("maximumFalseNegativeRate", report["failedGates"])
        self.assertIn("minimumExactMatchRate", report["failedGates"])

    def test_latency_false_positives_and_missing_tokens_fail_their_gates(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)
        observations = list(_perfect_observations(evaluation))
        first = observations[0]
        observations[0] = build_offline_observation(
            case_id=first.case_id,
            predicted_hidden_ids=("w1", "w2"),
            duration_ms=15_001,
            input_tokens=None,
            output_tokens=None,
        )
        second = observations[1]
        observations[1] = build_offline_observation(
            case_id=second.case_id,
            predicted_hidden_ids=("w1", "w2"),
            duration_ms=second.duration_ms,
            input_tokens=second.input_tokens,
            output_tokens=second.output_tokens,
        )

        report = score_hidden_works_evaluation(
            evaluation,
            tuple(observations),
            approved_sha256=EVALUATION_SHA256,
        )

        self.assertFalse(report["accepted"])
        self.assertEqual(set(report["failedGates"]), {
            "maximumFalsePositiveRate",
            "maximumP95LatencyMs",
            "minimumExactMatchRate",
            "minimumTokenCoverageRate",
        })

    def test_exact_digest_and_complete_unique_case_results_are_required(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)
        observations = _perfect_observations(evaluation)

        with self.assertRaises(OfflineEvaluationError) as unapproved:
            score_hidden_works_evaluation(
                evaluation,
                observations,
                approved_sha256="0" * 64,
            )
        self.assertEqual(unapproved.exception.code, MODEL_EVALUATION_NOT_APPROVED)

        for invalid in (
            observations[:-1],
            observations[:-1] + (observations[0],),
            observations[:-1] + (
                build_offline_observation(
                    case_id="hw-999",
                    predicted_hidden_ids=(),
                    duration_ms=1,
                    input_tokens=1,
                    output_tokens=1,
                ),
            ),
        ):
            with self.subTest(invalid=invalid[-1].case_id):
                with self.assertRaises(OfflineEvaluationError):
                    score_hidden_works_evaluation(
                        evaluation,
                        invalid,
                        approved_sha256=EVALUATION_SHA256,
                    )

    def test_observation_rejects_unknown_output_ids_and_partial_token_usage(self):
        for values in (
            {"predicted_hidden_ids": ("unknown",)},
            {"predicted_hidden_ids": ("w1", "w1")},
            {"input_tokens": 1, "output_tokens": None},
            {"duration_ms": 120_001},
        ):
            arguments = {
                "case_id": "hw-001",
                "predicted_hidden_ids": ("w1",),
                "duration_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
            }
            arguments.update(values)
            with self.subTest(values=values):
                with self.assertRaises(OfflineEvaluationError):
                    build_offline_observation(**arguments)

    def test_scorer_revalidates_directly_constructed_observations(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)
        observations = list(_perfect_observations(evaluation))
        first = observations[0]
        observations[0] = OfflineEvaluationObservation(
            case_id=first.case_id,
            predicted_hidden_ids=first.predicted_hidden_ids,
            duration_ms=first.duration_ms,
            input_tokens=1,
            output_tokens=None,
        )

        with self.assertRaises(OfflineEvaluationError):
            score_hidden_works_evaluation(
                evaluation,
                tuple(observations),
                approved_sha256=EVALUATION_SHA256,
            )


if __name__ == "__main__":
    unittest.main()
