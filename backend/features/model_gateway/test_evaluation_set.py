import copy
import unittest
from pathlib import Path

from backend.features.model_gateway.evaluation_set import (
    MODEL_EVALUATION_SET_INVALID,
    ModelEvaluationSetError,
    build_evaluation_readiness,
    load_evaluation_set,
    validate_evaluation_document,
)


EVALUATION_PATH = (
    Path(__file__).with_name("evaluation_sets")
    / "hidden_works_detection.v1.json"
)
EVALUATION_SHA256 = (
    "444cb34e19858e801b85f441de924f661af4978605a0b852bc0aeac4ccd63840"
)


class ModelEvaluationSetTest(unittest.TestCase):
    def test_synthetic_hidden_works_set_is_bounded_and_waits_for_approval(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)
        readiness = build_evaluation_readiness(evaluation)

        self.assertEqual(evaluation.version, "model-evaluation-v1")
        self.assertEqual(evaluation.capability, "hidden_works_detection")
        self.assertEqual(evaluation.source, "synthetic")
        self.assertEqual(len(evaluation.cases), 12)
        self.assertGreaterEqual(
            sum(len(case.expected_hidden_ids) for case in evaluation.cases),
            10,
        )
        self.assertGreaterEqual(
            sum(
                len(case.works) - len(case.expected_hidden_ids)
                for case in evaluation.cases
            ),
            10,
        )
        self.assertEqual(readiness, {
            "ok": True,
            "dryRun": True,
            "writesAttempted": 0,
            "version": "model-evaluation-v1",
            "capability": "hidden_works_detection",
            "source": "synthetic",
            "caseCount": 12,
            "evaluationSha256": evaluation.sha256,
            "humanApproved": False,
            "readyForOfflineEvaluation": False,
            "productionTrafficAllowed": False,
        })
        self.assertEqual(evaluation.sha256, EVALUATION_SHA256)

        approved = build_evaluation_readiness(
            evaluation,
            approved_sha256=evaluation.sha256,
        )
        self.assertTrue(approved["humanApproved"])
        self.assertTrue(approved["readyForOfflineEvaluation"])
        self.assertFalse(approved["productionTrafficAllowed"])

    def test_thresholds_make_hidden_work_false_negatives_blocking(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)

        self.assertEqual(evaluation.thresholds.minimum_exact_match_rate, 0.92)
        self.assertEqual(evaluation.thresholds.maximum_false_negative_rate, 0.0)
        self.assertEqual(evaluation.thresholds.maximum_false_positive_rate, 0.1)
        self.assertEqual(evaluation.thresholds.maximum_p95_latency_ms, 15_000)
        self.assertEqual(evaluation.thresholds.maximum_average_output_tokens, 500)
        self.assertEqual(evaluation.thresholds.minimum_token_coverage_rate, 0.95)

    def test_contract_rejects_extra_fields_pii_and_unbalanced_cases(self):
        valid = load_evaluation_set(EVALUATION_PATH).canonical_document
        cases = []

        extra = copy.deepcopy(valid)
        extra["productionModel"] = "arbitrary/model"
        cases.append(extra)

        pii = copy.deepcopy(valid)
        pii["cases"][0]["works"][0]["name"] = (
            "Работы для info@example.test ИНН 1234567890"
        )
        cases.append(pii)

        spaced_phone = copy.deepcopy(valid)
        spaced_phone["cases"][0]["works"][0]["name"] = (
            "Работы для +7 (999) 123-45-67"
        )
        cases.append(spaced_phone)

        unbalanced = copy.deepcopy(valid)
        for case in unbalanced["cases"]:
            case["expectedHiddenIds"] = [
                work["id"] for work in case["works"]
            ]
        cases.append(unbalanced)

        for document in cases:
            with self.subTest(document=document):
                with self.assertRaises(ModelEvaluationSetError) as raised:
                    validate_evaluation_document(document)
                self.assertEqual(
                    raised.exception.code,
                    MODEL_EVALUATION_SET_INVALID,
                )
                self.assertNotIn("example.test", str(raised.exception))
                self.assertNotIn("1234567890", str(raised.exception))
                self.assertNotIn("123-45-67", str(raised.exception))

    def test_wrong_or_malformed_approval_digest_never_unlocks_evaluation(self):
        evaluation = load_evaluation_set(EVALUATION_PATH)

        for digest in (
            None,
            "",
            "0" * 64,
            evaluation.sha256.upper(),
            "PRIVATE APPROVAL",
        ):
            with self.subTest(digest=digest):
                readiness = build_evaluation_readiness(
                    evaluation,
                    approved_sha256=digest,
                )
                self.assertFalse(readiness["humanApproved"])
                self.assertFalse(readiness["readyForOfflineEvaluation"])
                self.assertFalse(readiness["productionTrafficAllowed"])


if __name__ == "__main__":
    unittest.main()
