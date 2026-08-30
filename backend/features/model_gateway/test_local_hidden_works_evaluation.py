import unittest
from unittest.mock import patch

from backend.features.model_gateway.evaluation_set import (
    HiddenWorksEvaluationCase,
    EvaluationWork,
)
from backend.features.model_gateway.local_hidden_works_evaluation import (
    LOCAL_EVALUATION_RESPONSE_INVALID,
    LocalHiddenWorksEvaluationError,
    build_hidden_works_evaluation_prompt,
    parse_hidden_works_evaluation_output,
    run_local_hidden_works_evaluation_case,
)


CASE = HiddenWorksEvaluationCase(
    case_id="hw-001",
    works=(
        EvaluationWork("w1", "Армирование монолитного фундамента"),
        EvaluationWork("w2", "Окраска фасада"),
    ),
    expected_hidden_ids=("w1",),
)


class LocalHiddenWorksEvaluationTest(unittest.TestCase):
    def test_prompt_preserves_the_production_task_and_exact_work_names(self):
        prompt = build_hidden_works_evaluation_prompt(CASE)

        self.assertIn("СКРЫТЫМИ работами", prompt)
        self.assertIn("Армирование монолитного фундамента", prompt)
        self.assertIn("Окраска фасада", prompt)
        self.assertIn(
            '{"hidden": ["точное название работы из списка", ...]}',
            prompt,
        )

    def test_parser_maps_exact_known_names_to_stable_work_ids(self):
        predicted = parse_hidden_works_evaluation_output(
            CASE,
            '{"hidden":["Армирование монолитного фундамента"]}',
        )

        self.assertEqual(predicted, ("w1",))

    def test_parser_tolerates_model_reasoning_but_not_unknown_names(self):
        predicted = parse_hidden_works_evaluation_output(
            CASE,
            "Разбор завершён.\n"
            '{"hidden":["Окраска фасада","Неизвестная работа"]}',
        )

        self.assertEqual(predicted, ("w2",))

    def test_invalid_or_oversized_model_output_becomes_no_predictions(self):
        for output in (
            None,
            "not json",
            '{"hidden":"Армирование монолитного фундамента"}',
            "x" * (64 * 1024 + 1),
        ):
            with self.subTest(output_type=type(output).__name__):
                self.assertEqual(
                    parse_hidden_works_evaluation_output(CASE, output),
                    (),
                )

    def test_local_case_uses_only_loopback_and_returns_a_scoring_observation(self):
        calls = []

        def post_json(
            url,
            body,
            *,
            authorization,
            timeout_seconds,
            max_response_bytes,
        ):
            calls.append((
                url,
                body,
                authorization,
                timeout_seconds,
                max_response_bytes,
            ))
            return {
                "choices": [{
                    "message": {
                        "content": (
                            '{"hidden":["Армирование монолитного фундамента"]}'
                        ),
                    },
                }],
                "usage": {"prompt_tokens": 123, "completion_tokens": 17},
            }

        with patch(
            "backend.features.model_gateway.local_hidden_works_evaluation.time.monotonic_ns",
            side_effect=(1_000_000_000, 1_250_000_000),
        ):
            result = run_local_hidden_works_evaluation_case(
                CASE,
                port=18080,
                api_key="a" * 32,
                post_json=post_json,
            )

        self.assertEqual(len(calls), 1)
        url, body, authorization, timeout_seconds, max_response_bytes = calls[0]
        self.assertEqual(url, "http://127.0.0.1:18080/v1/chat/completions")
        self.assertEqual(authorization, "Bearer " + "a" * 32)
        self.assertEqual(body["model"], "qwen3-4b-q4-k-m")
        self.assertEqual(body["temperature"], 0.1)
        self.assertEqual(body["max_tokens"], 2000)
        self.assertEqual(body["chat_template_kwargs"], {
            "enable_thinking": False,
        })
        self.assertFalse(body["stream"])
        self.assertEqual(timeout_seconds, 120)
        self.assertEqual(max_response_bytes, 128 * 1024)
        self.assertEqual(result.observation.case_id, "hw-001")
        self.assertEqual(result.observation.predicted_hidden_ids, ("w1",))
        self.assertEqual(result.observation.duration_ms, 250)
        self.assertEqual(result.observation.input_tokens, 123)
        self.assertEqual(result.observation.output_tokens, 17)
        self.assertFalse(result.production_traffic_allowed)

    def test_local_case_rejects_bad_port_and_invalid_response_with_fixed_error(self):
        with self.assertRaises(LocalHiddenWorksEvaluationError) as bad_port:
            run_local_hidden_works_evaluation_case(
                CASE,
                port=80,
                api_key="a" * 32,
                post_json=lambda *args, **kwargs: {},
            )
        self.assertEqual(bad_port.exception.code, LOCAL_EVALUATION_RESPONSE_INVALID)

        for api_key in (None, "short", "a" * 31, "a" * 129, "a key" * 8):
            with self.subTest(api_key=api_key):
                with self.assertRaises(LocalHiddenWorksEvaluationError):
                    run_local_hidden_works_evaluation_case(
                        CASE,
                        port=18080,
                        api_key=api_key,
                        post_json=lambda *args, **kwargs: {},
                    )

        invalid_responses = (
            {},
            {"choices": [], "usage": {}},
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1},
            },
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": -1, "completion_tokens": 1},
            },
        )
        for response in invalid_responses:
            with self.subTest(response=response):
                with self.assertRaises(LocalHiddenWorksEvaluationError) as raised:
                    run_local_hidden_works_evaluation_case(
                        CASE,
                        port=18080,
                        api_key="a" * 32,
                        post_json=lambda *args, response=response, **kwargs: response,
                    )
                self.assertEqual(
                    raised.exception.code,
                    LOCAL_EVALUATION_RESPONSE_INVALID,
                )


if __name__ == "__main__":
    unittest.main()
