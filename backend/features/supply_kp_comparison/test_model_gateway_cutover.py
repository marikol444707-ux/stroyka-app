import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    MODEL_GATEWAY_PROVIDER_FAILED,
    ModelGatewayError,
)
from backend.features.supply_kp_comparison import model


MODEL_PATH = Path(model.__file__)
BACKEND_ROOT = MODEL_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text="Выберите поставщика №1.", error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class SupplyKpComparisonGatewayCutoverTest(unittest.TestCase):
    def test_kp_comparison_builds_the_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(model, "build_yandex_model_adapter", adapter_factory):
            answer = model.generate_supply_kp_comparison(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "Выберите поставщика №1.")
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "supply_kp_comparison")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.2)
        self.assertEqual(request.max_output_tokens, 400)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_raises_a_fixed_non_leaking_error(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with self.assertRaises(ModelGatewayError) as caught:
                model.generate_supply_kp_comparison(
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
                model.generate_supply_kp_comparison(
                    "Полный промпт",
                    "Инструкции",
                    "private-key",
                    "folder-1",
                )

        self.assertEqual(caught.exception.code, MODEL_GATEWAY_DEADLINE_EXCEEDED)

    def test_kp_comparison_has_no_direct_provider_or_cutover_flag(self):
        tree = ast.parse(
            MODEL_PATH.read_text(encoding="utf-8"),
            filename=str(MODEL_PATH),
        )
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("generate_supply_kp_comparison")
        }

        self.assertEqual(set(functions), {"generate_supply_kp_comparison"})
        function_source = ast.unparse(functions["generate_supply_kp_comparison"])
        self.assertNotIn("OpenAI", function_source)
        self.assertNotIn("model_gateway_enabled", function_source)

    def test_route_delegates_without_a_cutover_flag(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        routes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "compare_kp_for_request"
        ]
        self.assertEqual(len(routes), 1)
        route_source = ast.unparse(routes[0])
        self.assertIn("generate_supply_kp_comparison", route_source)
        self.assertNotIn("SUPPLY_KP_COMPARISON_MODEL_GATEWAY_ENABLED", route_source)
        self.assertIn("offers_summary.sort", route_source)
        self.assertIn("bestOfferId", route_source)
        self.assertNotIn("OpenAI", route_source)
        self.assertEqual(
            sum(
                line == "SUPPLY_KP_COMPARISON_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
