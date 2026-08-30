import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.hidden_works_detection import model
from backend.features.hidden_works_detection.prompt import (
    HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
    build_hidden_works_detection_prompt,
)
from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    MODEL_GATEWAY_PROVIDER_FAILED,
    ModelGatewayError,
)


MODEL_PATH = Path(model.__file__)
BACKEND_ROOT = MODEL_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text='{"hidden":["Армирование"]}', error=None):
        self.output_text = output_text
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class HiddenWorksDetectionGatewayCutoverTest(unittest.TestCase):
    def test_prompt_contract_is_canonical_and_preserves_exact_work_names(self):
        prompt = build_hidden_works_detection_prompt([
            "Армирование монолитного фундамента",
            "Окраска фасада",
        ])

        self.assertEqual(
            HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
            "Ты отвечаешь СТРОГО валидным JSON без markdown и пояснений. Только JSON.",
        )
        self.assertIn("СКРЫТЫМИ работами", prompt)
        self.assertIn(
            "недоступен для контроля без вскрытия",
            prompt,
        )
        self.assertIn(
            "розетки, выключатели, светильники, вентиляционные решётки",
            prompt,
        )
        self.assertIn(
            "не являются скрытыми, даже если подключаются к скрытой сети",
            prompt,
        )
        self.assertIn(
            "воздуховод за потолком — скрытая работа, вентиляционная решётка — видимая",
            prompt,
        )
        self.assertIn(
            "проводка под штукатуркой — скрытая работа, розетка — видимая",
            prompt,
        )
        self.assertIn(
            '["Армирование монолитного фундамента", "Окраска фасада"]',
            prompt,
        )
        self.assertTrue(prompt.endswith(
            '{"hidden": ["точное название работы из списка", ...]}',
        ))

    def test_legacy_rollback_preserves_the_existing_sdk_request(self):
        captured = {"client": None, "request": None}

        class FakeResponses:
            def create(self, **values):
                captured["request"] = values
                return SimpleNamespace(output_text='{"hidden":["Армирование"]}')

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            answer = model.generate_hidden_works_detection_legacy(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, '{"hidden":["Армирование"]}')
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
                "max_output_tokens": 2000,
            },
        )

    def test_gateway_builds_the_equivalent_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(model, "build_yandex_model_adapter", adapter_factory):
            answer = model.generate_hidden_works_detection_gateway(
                "Полный промпт",
                "Инструкции",
                "private-key",
                "folder-1",
            )

        self.assertEqual(answer, '{"hidden":["Армирование"]}')
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "hidden_works_detection")
        self.assertEqual(request.instructions, "Инструкции")
        self.assertEqual(request.input_text, "Полный промпт")
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 2000)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_raises_a_fixed_non_leaking_error(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            model,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with self.assertRaises(ModelGatewayError) as caught:
                model.generate_hidden_works_detection_gateway(
                    "prompt",
                    "instructions",
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
                model.generate_hidden_works_detection_gateway(
                    "prompt",
                    "instructions",
                    "key",
                    "folder",
                )

        self.assertEqual(caught.exception.code, MODEL_GATEWAY_DEADLINE_EXCEEDED)

    def test_cutover_defaults_to_legacy_and_enables_only_this_gateway(self):
        calls = []
        with (
            patch.object(
                model,
                "generate_hidden_works_detection_legacy",
                lambda *_args: calls.append("legacy") or "old",
            ),
            patch.object(
                model,
                "generate_hidden_works_detection_gateway",
                lambda *_args: calls.append("gateway") or "new",
            ),
        ):
            old = model.generate_hidden_works_detection(
                "prompt",
                "instructions",
                "key",
                "folder",
            )
            new = model.generate_hidden_works_detection(
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
                "generate_hidden_works_detection",
                "generate_hidden_works_detection_gateway",
                "generate_hidden_works_detection_legacy",
            }
        }

        self.assertEqual(
            set(functions),
            {
                "generate_hidden_works_detection",
                "generate_hidden_works_detection_gateway",
                "generate_hidden_works_detection_legacy",
            },
        )
        self.assertIn(
            "OpenAI",
            ast.unparse(functions["generate_hidden_works_detection_legacy"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_hidden_works_detection_gateway"]),
        )
        self.assertNotIn(
            "OpenAI",
            ast.unparse(functions["generate_hidden_works_detection"]),
        )

    def test_route_keeps_validation_keyword_fallback_and_database_write_local(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        routes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "ai_detect_hidden_works"
        ]
        self.assertEqual(len(routes), 1)
        route_source = ast.unparse(routes[0])
        self.assertIn("generate_hidden_works_detection", route_source)
        self.assertIn("build_hidden_works_detection_prompt", route_source)
        self.assertIn("HIDDEN_WORKS_DETECTION_INSTRUCTIONS", route_source)
        self.assertIn("HIDDEN_WORKS_DETECTION_MODEL_GATEWAY_ENABLED", route_source)
        self.assertIn("'false'", route_source)
        self.assertIn("require_estimate_access", route_source)
        self.assertIn("_estimate_item_type_backend", route_source)
        self.assertIn("_detect_hidden_by_keywords", route_source)
        self.assertIn("j.loads", route_source)
        self.assertIn("UPDATE estimates SET sections_json", route_source)
        self.assertNotIn("OpenAI", route_source)
        self.assertEqual(
            sum(
                line == "HIDDEN_WORKS_DETECTION_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
