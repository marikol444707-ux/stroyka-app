import ast
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
    def test_price_estimation_builds_the_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(price_model, "build_yandex_model_adapter", adapter_factory):
            answer, error = price_model.generate_estimate_change_price(
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
            answer, error = price_model.generate_estimate_change_price(
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
            answer, error = price_model.generate_estimate_change_price(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "")
        self.assertEqual(error, MODEL_GATEWAY_DEADLINE_EXCEEDED)

    def test_price_estimation_has_no_direct_provider_or_cutover_flag(self):
        tree = ast.parse(
            PRICE_MODEL_PATH.read_text(encoding="utf-8"),
            filename=str(PRICE_MODEL_PATH),
        )
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("generate_estimate_change_price")
        }

        self.assertEqual(
            set(functions),
            {"generate_estimate_change_price"},
        )
        function_source = ast.unparse(functions["generate_estimate_change_price"])
        self.assertNotIn("OpenAI", function_source)
        self.assertNotIn("model_gateway_enabled", function_source)

    def test_route_delegates_transport_without_direct_provider_access(self):
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
        self.assertNotIn("model_gateway_enabled", source)
        self.assertNotIn("OpenAI", source)

    def test_composition_root_no_longer_has_a_cutover_flag(self):
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
        self.assertNotIn("model_gateway_enabled", values)
        self.assertEqual(
            sum(
                line == "ESTIMATE_CHANGE_PRICE_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
