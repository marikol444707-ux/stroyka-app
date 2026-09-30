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
from backend.features.work_journal import model


MODEL_PATH = Path(model.__file__)
BACKEND_ROOT = MODEL_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text='{"qualityNote":"Соответствует"}', error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class WorkJournalModelGatewayCutoverTest(unittest.TestCase):
    def test_work_journal_prefill_builds_the_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(model, "build_yandex_model_adapter", adapter_factory):
            answer, error = model.generate_work_journal_prefill(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, '{"qualityNote":"Соответствует"}')
        self.assertIsNone(error)
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "work_journal_prefill")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 2000)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_returns_a_fixed_non_leaking_error(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            answer, error = model.generate_work_journal_prefill(
                "prompt",
                "instructions",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, "")
        self.assertEqual(error, MODEL_GATEWAY_PROVIDER_FAILED)
        self.assertNotIn("private-key", error)

    def test_gateway_preserves_a_specific_fixed_failure_code(self):
        gateway = FakeGateway(
            error=ModelGatewayError(MODEL_GATEWAY_DEADLINE_EXCEEDED),
        )
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            answer, error = model.generate_work_journal_prefill(
                "prompt",
                "instructions",
                "key",
                "folder",
            )

        self.assertEqual(answer, "")
        self.assertEqual(error, MODEL_GATEWAY_DEADLINE_EXCEEDED)

    def test_work_journal_prefill_has_no_direct_provider_or_cutover_flag(self):
        tree = ast.parse(
            MODEL_PATH.read_text(encoding="utf-8"),
            filename=str(MODEL_PATH),
        )
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("generate_work_journal_prefill")
        }

        self.assertEqual(set(functions), {"generate_work_journal_prefill"})
        function_source = ast.unparse(functions["generate_work_journal_prefill"])
        self.assertNotIn("OpenAI", function_source)
        self.assertNotIn("model_gateway_enabled", function_source)

    def test_route_delegates_without_a_cutover_flag(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        routes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "ai_prefill_work_journal"
        ]
        self.assertEqual(len(routes), 1)
        route_source = ast.unparse(routes[0])
        self.assertIn("generate_work_journal_prefill", route_source)
        self.assertNotIn("WORK_JOURNAL_PREFILL_MODEL_GATEWAY_ENABLED", route_source)
        self.assertIn("_resolve_work_journal_mutation", route_source)
        self.assertIn("UPDATE work_journal", route_source)
        self.assertNotIn("OpenAI", route_source)
        self.assertEqual(
            sum(
                line == "WORK_JOURNAL_PREFILL_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
