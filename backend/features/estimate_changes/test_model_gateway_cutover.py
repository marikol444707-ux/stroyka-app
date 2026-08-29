import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.estimate_changes import price_model, routes


PRICE_MODEL_PATH = Path(price_model.__file__)
ROUTES_PATH = Path(routes.__file__)
BACKEND_ROOT = PRICE_MODEL_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text='{"pricePerUnit":1250,"justification":"Рынок"}', error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class EstimateChangePriceGatewayCutoverTest(unittest.TestCase):
    def test_legacy_rollback_preserves_model_order_and_sdk_requests(self):
        captured = {"client": None, "requests": []}

        class FakeResponses:
            def create(self, **values):
                captured["requests"].append(values)
                return SimpleNamespace(
                    output_text=(
                        ""
                        if len(captured["requests"]) == 1
                        else '{"pricePerUnit":1250,"justification":"Рынок"}'
                    )
                )

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            answer, error = price_model.generate_estimate_change_price_legacy(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(
            answer,
            '{"pricePerUnit":1250,"justification":"Рынок"}',
        )
        self.assertIsNone(error)
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
                    "temperature": 0.2,
                    "instructions": "Инструкции",
                    "input": "Полный промпт",
                    "max_output_tokens": 800,
                },
                {
                    "model": "gpt://folder-1/yandexgpt-5.1/latest",
                    "temperature": 0.2,
                    "instructions": "Инструкции",
                    "input": "Полный промпт",
                    "max_output_tokens": 800,
                },
            ],
        )

    def test_gateway_path_builds_the_equivalent_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(price_model, "build_yandex_model_adapter", adapter_factory):
            answer, error = price_model.generate_estimate_change_price_gateway(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(
            answer,
            '{"pricePerUnit":1250,"justification":"Рынок"}',
        )
        self.assertIsNone(error)
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "estimate_change_price")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.2)
        self.assertEqual(request.max_output_tokens, 800)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_returns_a_fixed_non_leaking_code(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            price_model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            answer, error = price_model.generate_estimate_change_price_gateway(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "")
        self.assertEqual(error, "model_gateway_provider_failed")

    def test_gateway_preserves_a_specific_fixed_failure_code(self):
        from backend.features.model_gateway.contract import (
            MODEL_GATEWAY_DEADLINE_EXCEEDED,
            ModelGatewayError,
        )

        gateway = FakeGateway(
            error=ModelGatewayError(MODEL_GATEWAY_DEADLINE_EXCEEDED),
        )
        with patch.object(
            price_model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            answer, error = price_model.generate_estimate_change_price_gateway(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "")
        self.assertEqual(error, MODEL_GATEWAY_DEADLINE_EXCEEDED)

    def test_cutover_defaults_to_legacy_and_enables_only_this_gateway(self):
        calls = []
        with (
            patch.object(
                price_model,
                "generate_estimate_change_price_legacy",
                lambda *_args: calls.append("legacy") or ("old", None),
            ),
            patch.object(
                price_model,
                "generate_estimate_change_price_gateway",
                lambda *_args: calls.append("gateway") or ("new", None),
            ),
        ):
            old = price_model.generate_estimate_change_price(
                "prompt",
                "instructions",
                "key",
                "folder",
            )
            new = price_model.generate_estimate_change_price(
                "prompt",
                "instructions",
                "key",
                "folder",
                model_gateway_enabled=True,
            )

        self.assertEqual(old, ("old", None))
        self.assertEqual(new, ("new", None))
        self.assertEqual(calls, ["legacy", "gateway"])

    def test_direct_provider_access_is_confined_to_the_rollback_function(self):
        tree = ast.parse(
            PRICE_MODEL_PATH.read_text(encoding="utf-8"),
            filename=str(PRICE_MODEL_PATH),
        )
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "generate_estimate_change_price",
                "generate_estimate_change_price_gateway",
                "generate_estimate_change_price_legacy",
            }
        }

        self.assertEqual(
            set(functions),
            {
                "generate_estimate_change_price",
                "generate_estimate_change_price_gateway",
                "generate_estimate_change_price_legacy",
            },
        )
        self.assertIn(
            "OpenAI",
            ast.unparse(functions["generate_estimate_change_price_legacy"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_estimate_change_price_gateway"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_estimate_change_price"]),
        )

    def test_route_delegates_transport_with_its_caller_local_cutover(self):
        tree = ast.parse(
            ROUTES_PATH.read_text(encoding="utf-8"),
            filename=str(ROUTES_PATH),
        )
        registrations = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "register_estimate_changes_module"
        ]
        self.assertEqual(len(registrations), 1)
        source = ast.unparse(registrations[0])
        self.assertIn("generate_estimate_change_price", source)
        self.assertIn("model_gateway_enabled=model_gateway_enabled", source)
        self.assertNotIn("OpenAI", source)

    def test_composition_root_keeps_the_cutover_disabled_by_default(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_estimate_changes_module"
        ]
        self.assertEqual(len(registrations), 1)
        dependency_map = registrations[0].args[1]
        self.assertIsInstance(dependency_map, ast.Dict)
        values = {
            key.value: ast.unparse(value)
            for key, value in zip(dependency_map.keys, dependency_map.values)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        flag_expression = values["model_gateway_enabled"]
        self.assertIn("ESTIMATE_CHANGE_PRICE_MODEL_GATEWAY_ENABLED", flag_expression)
        self.assertIn("'false'", flag_expression)
        self.assertEqual(
            sum(
                line == "ESTIMATE_CHANGE_PRICE_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
