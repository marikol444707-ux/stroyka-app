import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"


def _main_function(name, namespace):
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"backend.main must define exactly one {name}")
    module = ast.Module(body=matches, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace[name], matches[0]


class FakeGateway:
    def __init__(self, *, output_text="Ответ ИИ", error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class EstimateChatGatewayCutoverTest(unittest.TestCase):
    def test_estimate_chat_builds_the_provider_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        from backend.features.model_gateway.contract import build_model_request

        function, _node = _main_function(
            "_generate_estimate_chat_answer",
            {
                "YANDEX_API_KEY": "private-key",
                "YANDEX_FOLDER_ID": "folder-1",
                "build_model_request": build_model_request,
                "build_yandex_model_adapter": adapter_factory,
            },
        )

        answer = function("Полный промпт", "Инструкции")

        self.assertEqual(answer, "Ответ ИИ")
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "estimate_chat")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.temperature, 0.3)
        self.assertEqual(request.max_output_tokens, 1500)
        self.assertEqual(request.deadline_seconds, 120)

    def test_estimate_chat_preserves_error_prefix_without_leaking_details(self):
        function, _node = _main_function(
            "_generate_estimate_chat_answer",
            {
                "YANDEX_API_KEY": "private-key",
                "YANDEX_FOLDER_ID": "folder-1",
                "build_model_request": lambda **_values: object(),
                "build_yandex_model_adapter": lambda **_values: FakeGateway(
                    error=RuntimeError("provider leaked private-key"),
                ),
                "MODEL_GATEWAY_PROVIDER_FAILED": "model_gateway_provider_failed",
                "ModelGatewayError": type("FakeModelGatewayError", (ValueError,), {}),
            },
        )

        self.assertEqual(
            function("Полный промпт", "Инструкции"),
            "Ошибка ИИ: model_gateway_provider_failed",
        )

    def test_estimate_chat_keeps_the_fixed_gateway_failure_code(self):
        from backend.features.model_gateway.contract import (
            MODEL_GATEWAY_DEADLINE_EXCEEDED,
            MODEL_GATEWAY_PROVIDER_FAILED,
            ModelGatewayError,
        )

        function, _node = _main_function(
            "_generate_estimate_chat_answer",
            {
                "YANDEX_API_KEY": "private-key",
                "YANDEX_FOLDER_ID": "folder-1",
                "build_model_request": lambda **_values: object(),
                "build_yandex_model_adapter": lambda **_values: FakeGateway(
                    error=ModelGatewayError(MODEL_GATEWAY_DEADLINE_EXCEEDED),
                ),
                "MODEL_GATEWAY_PROVIDER_FAILED": MODEL_GATEWAY_PROVIDER_FAILED,
                "ModelGatewayError": ModelGatewayError,
            },
        )

        self.assertEqual(
            function("Полный промпт", "Инструкции"),
            "Ошибка ИИ: model_gateway_deadline_exceeded",
        )

    def test_estimate_chat_has_no_direct_provider_or_cutover_flag(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("_generate_estimate_chat_answer")
        }

        self.assertEqual(
            set(functions),
            {"_generate_estimate_chat_answer"},
        )
        function_source = ast.unparse(functions["_generate_estimate_chat_answer"])
        self.assertNotIn("OpenAI", function_source)
        self.assertNotIn("ESTIMATE_CHAT_MODEL_GATEWAY_ENABLED", function_source)


if __name__ == "__main__":
    unittest.main()
