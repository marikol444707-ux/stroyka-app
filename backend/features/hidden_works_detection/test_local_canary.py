import json
import unittest
from unittest.mock import patch

from backend.features.hidden_works_detection.local_canary import (
    COMPANY_ALLOWLIST,
    FEATURE_FLAG,
    local_hidden_works_canary_enabled,
    try_local_hidden_works_canary,
)


class HiddenWorksLocalCanaryTest(unittest.TestCase):
    def test_canary_is_disabled_by_default_and_fails_closed(self):
        cases = (
            ({}, 1),
            ({FEATURE_FLAG: "false", COMPANY_ALLOWLIST: "1"}, 1),
            ({FEATURE_FLAG: "true", COMPANY_ALLOWLIST: ""}, 1),
            ({FEATURE_FLAG: "true", COMPANY_ALLOWLIST: "01"}, 1),
            ({FEATURE_FLAG: "true", COMPANY_ALLOWLIST: "1,1"}, 1),
            ({FEATURE_FLAG: "true", COMPANY_ALLOWLIST: "1,abc"}, 1),
            ({FEATURE_FLAG: "true", COMPANY_ALLOWLIST: "1, 2"}, 1),
            ({FEATURE_FLAG: "TRUE", COMPANY_ALLOWLIST: "1"}, 1),
            ({FEATURE_FLAG: "true", COMPANY_ALLOWLIST: "1"}, 2),
        )
        for environment, company_id in cases:
            with self.subTest(environment=environment, company_id=company_id):
                with patch.dict("os.environ", environment, clear=True):
                    self.assertFalse(
                        local_hidden_works_canary_enabled(company_id),
                    )

        with patch.dict(
            "os.environ",
            {FEATURE_FLAG: "true", COMPANY_ALLOWLIST: "1,2"},
            clear=True,
        ):
            self.assertTrue(local_hidden_works_canary_enabled(1))
            self.assertTrue(local_hidden_works_canary_enabled(2))
            self.assertFalse(local_hidden_works_canary_enabled(True))

    def test_valid_response_returns_only_exact_allowlisted_names(self):
        names = (
            "Армирование основания",
            "Окраска открытой поверхности",
        )
        result = try_local_hidden_works_canary(
            names=names,
            company_id=1,
            enabled=True,
            generate=lambda: '{"hidden":["Армирование основания"]}',
            correlation_id_factory=(
                lambda: "0123456789abcdef0123456789abcdef"
            ),
            log_fn=lambda _line: None,
        )

        self.assertEqual(result.hidden_names, ("Армирование основания",))
        self.assertEqual(result.method, "local_ai_canary")
        self.assertFalse(result.production_traffic_allowed)

        visible_only = try_local_hidden_works_canary(
            names=names,
            company_id=1,
            enabled=True,
            generate=lambda: '{"hidden":[]}',
            log_fn=lambda _line: None,
        )
        self.assertEqual(visible_only.hidden_names, ())

    def test_invalid_or_failed_model_output_returns_control_to_legacy(self):
        names = ("Скрытая прокладка", "Открытая окраска")
        failures = (
            lambda: "not-json",
            lambda: '{"hidden":["Неизвестная работа"]}',
            lambda: '{"hidden":["Скрытая прокладка","Скрытая прокладка"]}',
            lambda: '{"hidden":[],"extra":true}',
            lambda: '{"hidden":[],"hidden":[]}',
            lambda: (_ for _ in ()).throw(RuntimeError("PRIVATE api-key")),
        )
        for generate in failures:
            with self.subTest(generate=generate):
                self.assertIsNone(try_local_hidden_works_canary(
                    names=names,
                    company_id=1,
                    enabled=True,
                    generate=generate,
                    log_fn=lambda _line: None,
                ))

        called = False

        def should_not_run():
            nonlocal called
            called = True
            return '{"hidden":[]}'

        self.assertIsNone(try_local_hidden_works_canary(
            names=names,
            company_id=1,
            enabled=False,
            generate=should_not_run,
            log_fn=lambda _line: None,
        ))
        self.assertFalse(called)

    def test_log_is_structured_bounded_and_contains_no_business_payload(self):
        lines = []
        private_name = "PRIVATE WORK NAME"
        private_error = "PRIVATE provider output and api-key"

        result = try_local_hidden_works_canary(
            names=(private_name, "Visible work"),
            company_id=1,
            enabled=True,
            generate=lambda: (_ for _ in ()).throw(
                RuntimeError(private_error),
            ),
            correlation_id_factory=(
                lambda: "fedcba9876543210fedcba9876543210"
            ),
            log_fn=lines.append,
        )

        self.assertIsNone(result)
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event, {
            "event": "hidden_works_local_canary",
            "correlationId": "fedcba9876543210fedcba9876543210",
            "outcome": "fallback",
            "reason": "provider_error",
            "candidateCount": 2,
        })
        rendered = json.dumps(event)
        self.assertNotIn(private_name, rendered)
        self.assertNotIn(private_error, rendered)
        self.assertNotIn("company", rendered.lower())

    def test_broken_logging_cannot_break_a_successful_result(self):
        result = try_local_hidden_works_canary(
            names=("Работа один", "Работа два"),
            company_id=1,
            enabled=True,
            generate=lambda: '{"hidden":["Работа один"]}',
            log_fn=lambda _line: (_ for _ in ()).throw(
                RuntimeError("log unavailable"),
            ),
        )

        self.assertEqual(result.hidden_names, ("Работа один",))


if __name__ == "__main__":
    unittest.main()
