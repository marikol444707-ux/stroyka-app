import ast
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.document_recognition import routes


ROUTES_PATH = Path(routes.__file__)
BACKEND_ROOT = ROUTES_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text='{"docType":"Договор"}', error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


def _arguments():
    return {
        "text": "Договор № 7 от 29.08.2026",
        "context": "project_document",
        "entity_type": "contract",
        "project_name": "Кисловодск Лицей 4",
        "current_fields": {"number": ""},
        "api_key": "private-key",
        "folder_id": "folder-1",
    }


class DocumentRecognitionGatewayCutoverTest(unittest.TestCase):
    def test_legacy_rollback_preserves_the_existing_sdk_request(self):
        captured = {"client": None, "request": None}

        class FakeResponses:
            def create(self, **values):
                captured["request"] = values
                return SimpleNamespace(output_text='{"docType":"Договор"}')

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            fields, warning = routes._ai_extract_legacy(**_arguments())

        self.assertEqual(fields["docType"], "Договор")
        self.assertEqual(warning, "")
        self.assertEqual(
            captured["client"],
            {
                "api_key": "private-key",
                "base_url": "https://ai.api.cloud.yandex.net/v1",
                "project": "folder-1",
            },
        )
        self.assertEqual(
            {key: value for key, value in captured["request"].items() if key != "input"},
            {
                "model": "gpt://folder-1/yandexgpt-5.1/latest",
                "temperature": 0.1,
                "instructions": routes._DOCUMENT_RECOGNITION_INSTRUCTIONS,
                "max_output_tokens": 2500,
            },
        )
        self.assertEqual(
            json.loads(captured["request"]["input"]),
            routes._document_recognition_prompt(**{
                key: value
                for key, value in _arguments().items()
                if key not in {"api_key", "folder_id"}
            }),
        )

    def test_gateway_path_builds_the_equivalent_provider_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(routes, "build_yandex_model_adapter", adapter_factory):
            fields, warning = routes._ai_extract_gateway(**_arguments())

        self.assertEqual(fields["docType"], "Договор")
        self.assertEqual(warning, "")
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "document_recognition")
        self.assertEqual(request.instructions, routes._DOCUMENT_RECOGNITION_INSTRUCTIONS)
        self.assertEqual(
            json.loads(request.input_text),
            routes._document_recognition_prompt(**{
                key: value
                for key, value in _arguments().items()
                if key not in {"api_key", "folder_id"}
            }),
        )
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 2500)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_path_returns_a_fixed_warning_without_provider_details(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))

        with patch.object(
            routes,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            fields, warning = routes._ai_extract_gateway(**_arguments())

        self.assertEqual(fields, {})
        self.assertEqual(
            warning,
            "AI-распознавание недоступно: model_gateway_provider_failed",
        )
        self.assertNotIn("private-key", warning)

    def test_gateway_path_preserves_a_fixed_gateway_failure_code(self):
        from backend.features.model_gateway.contract import (
            MODEL_GATEWAY_DEADLINE_EXCEEDED,
            ModelGatewayError,
        )

        gateway = FakeGateway(
            error=ModelGatewayError(MODEL_GATEWAY_DEADLINE_EXCEEDED),
        )
        with patch.object(
            routes,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            fields, warning = routes._ai_extract_gateway(**_arguments())

        self.assertEqual(fields, {})
        self.assertEqual(
            warning,
            "AI-распознавание недоступно: model_gateway_deadline_exceeded",
        )

    def test_cutover_defaults_to_legacy_and_enables_only_this_gateway(self):
        calls = []
        with (
            patch.object(
                routes,
                "_ai_extract_legacy",
                lambda **_values: calls.append("legacy") or ({"source": "old"}, ""),
            ),
            patch.object(
                routes,
                "_ai_extract_gateway",
                lambda **_values: calls.append("gateway") or ({"source": "new"}, ""),
            ),
        ):
            old = routes._ai_extract(**_arguments())
            new = routes._ai_extract(
                **_arguments(),
                model_gateway_enabled=True,
            )

        self.assertEqual(old, ({"source": "old"}, ""))
        self.assertEqual(new, ({"source": "new"}, ""))
        self.assertEqual(calls, ["legacy", "gateway"])

    def test_direct_provider_access_is_confined_to_the_rollback_function(self):
        tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"), filename=str(ROUTES_PATH))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "_ai_extract",
                "_ai_extract_gateway",
                "_ai_extract_legacy",
            }
        }

        self.assertEqual(
            set(functions),
            {"_ai_extract", "_ai_extract_gateway", "_ai_extract_legacy"},
        )
        self.assertIn("OpenAI", ast.unparse(functions["_ai_extract_legacy"]))
        self.assertNotIn("OpenAI", ast.unparse(functions["_ai_extract_gateway"]))
        self.assertNotIn("OpenAI", ast.unparse(functions["_ai_extract"]))

    def test_composition_root_keeps_the_cutover_disabled_by_default(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_document_recognition_module"
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
        self.assertIn("DOCUMENT_RECOGNITION_MODEL_GATEWAY_ENABLED", flag_expression)
        self.assertIn("'false'", flag_expression)
        self.assertEqual(
            sum(
                line == "DOCUMENT_RECOGNITION_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
