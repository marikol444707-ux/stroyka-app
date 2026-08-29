import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.estimate_distribution import model
from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    ModelGatewayError,
)


MODEL_PATH = Path(model.__file__)
BACKEND_ROOT = MODEL_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text='{"assignments":[]}', error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class EstimateDistributionGatewayCutoverTest(unittest.TestCase):
    def test_legacy_rollback_preserves_model_order_and_sdk_requests(self):
        captured = {"client": None, "requests": []}

        class FakeResponses:
            def create(self, **values):
                captured["requests"].append(values)
                output = "" if len(captured["requests"]) == 1 else '{"assignments":[]}'
                return SimpleNamespace(output_text=output)

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            answer = model.generate_estimate_distribution_legacy(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, '{"assignments":[]}')
        self.assertEqual(
            captured["client"],
            {
                "api_key": "private-key",
                "base_url": "https://ai.api.cloud.yandex.net/v1",
                "project": "folder-1",
            },
        )
        self.assertEqual(
            captured["requests"],
            [
                {
                    "model": "gpt://folder-1/qwen3.6-35b-a3b/latest",
                    "temperature": 0.1,
                    "instructions": "Инструкции",
                    "input": "Полный промпт",
                    "max_output_tokens": 4000,
                },
                {
                    "model": "gpt://folder-1/yandexgpt-5.1/latest",
                    "temperature": 0.1,
                    "instructions": "Инструкции",
                    "input": "Полный промпт",
                    "max_output_tokens": 4000,
                },
            ],
        )

    def test_gateway_builds_the_equivalent_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(model, "build_yandex_model_adapter", adapter_factory):
            answer = model.generate_estimate_distribution_gateway(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, '{"assignments":[]}')
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "estimate_distribution")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 4000)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_is_non_leaking_and_keeps_empty_result_fallback(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with patch("builtins.print") as print_mock:
                answer = model.generate_estimate_distribution_gateway(
                    "Полный промпт",
                    "Инструкции",
                    "private-key",
                    "folder-1",
                )

        self.assertEqual(answer, "")
        print_mock.assert_called_once_with(
            "AI-DISTRIBUTE ERROR:",
            "model_gateway_provider_failed",
        )

    def test_gateway_preserves_a_specific_fixed_failure_code(self):
        gateway = FakeGateway(
            error=ModelGatewayError(MODEL_GATEWAY_DEADLINE_EXCEEDED),
        )
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with patch("builtins.print") as print_mock:
                answer = model.generate_estimate_distribution_gateway(
                    "Полный промпт",
                    "Инструкции",
                    "private-key",
                    "folder-1",
                )

        self.assertEqual(answer, "")
        print_mock.assert_called_once_with(
            "AI-DISTRIBUTE ERROR:",
            MODEL_GATEWAY_DEADLINE_EXCEEDED,
        )

    def test_cutover_defaults_to_legacy_and_enables_only_this_gateway(self):
        calls = []
        with (
            patch.object(
                model,
                "generate_estimate_distribution_legacy",
                lambda *_args: calls.append("legacy") or "old",
            ),
            patch.object(
                model,
                "generate_estimate_distribution_gateway",
                lambda *_args: calls.append("gateway") or "new",
            ),
        ):
            old = model.generate_estimate_distribution(
                "prompt",
                "instructions",
                "key",
                "folder",
            )
            new = model.generate_estimate_distribution(
                "prompt",
                "instructions",
                "key",
                "folder",
                model_gateway_enabled=True,
            )

        self.assertEqual(old, "old")
        self.assertEqual(new, "new")
        self.assertEqual(calls, ["legacy", "gateway"])

    def test_direct_provider_access_is_confined_to_the_rollback_function(self):
        tree = ast.parse(
            MODEL_PATH.read_text(encoding="utf-8"),
            filename=str(MODEL_PATH),
        )
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "generate_estimate_distribution",
                "generate_estimate_distribution_gateway",
                "generate_estimate_distribution_legacy",
            }
        }

        self.assertEqual(
            set(functions),
            {
                "generate_estimate_distribution",
                "generate_estimate_distribution_gateway",
                "generate_estimate_distribution_legacy",
            },
        )
        self.assertIn(
            "OpenAI",
            ast.unparse(functions["generate_estimate_distribution_legacy"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_estimate_distribution_gateway"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_estimate_distribution"]),
        )

    def test_route_delegates_transport_with_a_disabled_by_default_cutover(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        routes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "ai_suggest_distribution"
        ]
        self.assertEqual(len(routes), 1)
        route_source = ast.unparse(routes[0])
        self.assertIn("generate_estimate_distribution", route_source)
        self.assertIn("ESTIMATE_DISTRIBUTION_MODEL_GATEWAY_ENABLED", route_source)
        self.assertIn("'false'", route_source)
        self.assertNotIn("OpenAI", route_source)
        self.assertEqual(
            sum(
                line == "ESTIMATE_DISTRIBUTION_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
