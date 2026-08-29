import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    MODEL_GATEWAY_PROVIDER_FAILED,
    ModelGatewayError,
)
from backend.features.supply_delivery import model


MODEL_PATH = Path(model.__file__)
BACKEND_ROOT = MODEL_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text="Материал и количество совпадают.", error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class SupplyDeliveryGatewayCutoverTest(unittest.TestCase):
    def test_legacy_rollback_preserves_the_existing_sdk_request(self):
        captured = {"client": None, "request": None}

        class FakeResponses:
            def create(self, **values):
                captured["request"] = values
                return SimpleNamespace(output_text="  Материал совпадает.  ")

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            answer = model.generate_supply_delivery_check_legacy(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "Материал совпадает.")
        self.assertEqual(
            captured["client"],
            {
                "api_key": "private-key",
                "base_url": "https://ai.api.cloud.yandex.net/v1",
                "project": "folder-1",
            },
        )
        self.assertEqual(
            captured["request"],
            {
                "model": "gpt://folder-1/yandexgpt-5.1/latest",
                "temperature": 0.1,
                "instructions": "Инструкции",
                "input": "Полный промпт",
                "max_output_tokens": 500,
            },
        )

    def test_gateway_builds_the_equivalent_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(model, "build_yandex_model_adapter", adapter_factory):
            answer = model.generate_supply_delivery_check_gateway(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "Материал и количество совпадают.")
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "supply_delivery_check")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 500)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_raises_a_fixed_non_leaking_error(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with self.assertRaises(ModelGatewayError) as caught:
                model.generate_supply_delivery_check_gateway(
                    "Полный промпт",
                    "Инструкции",
                    "private-key",
                    "folder-1",
                )

        self.assertEqual(caught.exception.code, MODEL_GATEWAY_PROVIDER_FAILED)
        self.assertNotIn("private-key", str(caught.exception))

    def test_gateway_preserves_a_specific_fixed_failure_code(self):
        gateway = FakeGateway(
            error=ModelGatewayError(MODEL_GATEWAY_DEADLINE_EXCEEDED),
        )
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with self.assertRaises(ModelGatewayError) as caught:
                model.generate_supply_delivery_check_gateway(
                    "Полный промпт",
                    "Инструкции",
                    "private-key",
                    "folder-1",
                )

        self.assertEqual(caught.exception.code, MODEL_GATEWAY_DEADLINE_EXCEEDED)

    def test_cutover_defaults_to_legacy_and_enables_only_this_gateway(self):
        calls = []
        with (
            patch.object(
                model,
                "generate_supply_delivery_check_legacy",
                lambda *_args: calls.append("legacy") or "old",
            ),
            patch.object(
                model,
                "generate_supply_delivery_check_gateway",
                lambda *_args: calls.append("gateway") or "new",
            ),
        ):
            old = model.generate_supply_delivery_check(
                "prompt",
                "instructions",
                "key",
                "folder",
            )
            new = model.generate_supply_delivery_check(
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
                "generate_supply_delivery_check",
                "generate_supply_delivery_check_gateway",
                "generate_supply_delivery_check_legacy",
            }
        }

        self.assertEqual(
            set(functions),
            {
                "generate_supply_delivery_check",
                "generate_supply_delivery_check_gateway",
                "generate_supply_delivery_check_legacy",
            },
        )
        self.assertIn(
            "OpenAI",
            ast.unparse(functions["generate_supply_delivery_check_legacy"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_supply_delivery_check_gateway"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_supply_delivery_check"]),
        )

    def test_route_delegates_only_the_text_transport_with_a_safe_cutover(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        routes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "ai_check_supply_delivery"
        ]
        self.assertEqual(len(routes), 1)
        route_source = ast.unparse(routes[0])
        self.assertIn("if parsed_items", route_source)
        self.assertIn("generate_supply_delivery_check", route_source)
        self.assertIn("SUPPLY_DELIVERY_CHECK_MODEL_GATEWAY_ENABLED", route_source)
        self.assertIn("'false'", route_source)
        self.assertIn("doc_text[:4000]", route_source)
        self.assertNotIn("OpenAI", route_source)
        self.assertEqual(
            sum(
                line == "SUPPLY_DELIVERY_CHECK_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
