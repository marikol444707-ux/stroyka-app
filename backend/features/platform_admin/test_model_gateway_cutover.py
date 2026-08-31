import ast
import base64
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.platform_admin import routes


ROUTES_PATH = Path(routes.__file__)
BACKEND_ROOT = ROUTES_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text=None, error=None):
        self.output_text = output_text or '{"companyName":"ООО Тест"}'
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


def _arguments(**overrides):
    values = {
        "file_content": b"",
        "file_name": "client-card.txt",
        "content_type": "text/plain",
        "source_text": "ООО Тест ИНН 1234567890",
        "api_key": "private-key",
        "folder_id": "folder-1",
    }
    values.update(overrides)
    return values


class PlatformClientCardGatewayCutoverTest(unittest.TestCase):
    def test_legacy_rollback_preserves_the_existing_sdk_request(self):
        captured = {"client": None, "request": None}

        class FakeResponses:
            def create(self, **values):
                captured["request"] = values
                return SimpleNamespace(output_text='{"companyName":"ООО Тест"}')

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            fields, warnings = routes._recognize_client_card_with_ai_legacy(
                **_arguments(),
            )

        self.assertEqual(fields["companyName"], "ООО Тест")
        self.assertEqual(warnings, [])
        self.assertEqual(captured["client"], {
            "api_key": "private-key",
            "base_url": "https://ai.api.cloud.yandex.net/v1",
            "project": "folder-1",
        })
        self.assertEqual(
            {key: value for key, value in captured["request"].items() if key != "input"},
            {
                "model": "gpt://folder-1/qwen3.6-35b-a3b/latest",
                "temperature": 0.1,
                "instructions": routes._CLIENT_CARD_INSTRUCTIONS,
                "max_output_tokens": 2500,
            },
        )
        self.assertEqual(
            captured["request"]["input"],
            [{"role": "user", "content": routes._client_card_ai_content(**{
                key: value
                for key, value in _arguments().items()
                if key not in {"api_key", "folder_id"}
            })[0]}],
        )

    def test_gateway_preserves_text_image_and_pdf_part_shapes(self):
        cases = (
            (_arguments(), [("text", "Извлеченный текст карты клиента:\nООО Тест ИНН 1234567890", ""), ("text", routes._CLIENT_CARD_PROMPT, "")]),
            (
                _arguments(
                    file_content=b"jpeg",
                    file_name="card.jpg",
                    content_type="image/jpeg",
                ),
                [
                    ("text", "Файл карты клиента: card.jpg", ""),
                    ("image_data_url", "data:image/jpeg;base64," + base64.b64encode(b"jpeg").decode(), ""),
                    ("text", "Извлеченный текст карты клиента:\nООО Тест ИНН 1234567890", ""),
                    ("text", routes._CLIENT_CARD_PROMPT, ""),
                ],
            ),
            (
                _arguments(
                    file_content=b"pdf",
                    file_name="карта.pdf",
                    content_type="application/pdf",
                ),
                [
                    ("text", "Файл карты клиента: карта.pdf", ""),
                    ("file_data_url", "data:application/pdf;base64," + base64.b64encode(b"pdf").decode(), "карта.pdf"),
                    ("text", "Извлеченный текст карты клиента:\nООО Тест ИНН 1234567890", ""),
                    ("text", routes._CLIENT_CARD_PROMPT, ""),
                ],
            ),
        )

        for arguments, expected_parts in cases:
            with self.subTest(file_name=arguments["file_name"]):
                gateway = FakeGateway()
                with patch.object(
                    routes,
                    "build_yandex_model_adapter",
                    lambda **_values: gateway,
                ):
                    fields, warnings = routes._recognize_client_card_with_ai_gateway(
                        **arguments,
                    )

                self.assertEqual(fields["companyName"], "ООО Тест")
                self.assertEqual(warnings, [])
                request = gateway.requests[0]
                self.assertEqual(request.capability, "platform_client_card")
                self.assertEqual(request.instructions, routes._CLIENT_CARD_INSTRUCTIONS)
                self.assertEqual(request.input_text, "")
                self.assertEqual(
                    [(part.kind, part.value, part.filename) for part in request.input_parts],
                    expected_parts,
                )
                self.assertEqual(request.temperature, 0.1)
                self.assertEqual(request.max_output_tokens, 2500)
                self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_failure_is_fixed_and_does_not_leak_credentials(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with patch.object(
            routes,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            fields, warnings = routes._recognize_client_card_with_ai_gateway(
                **_arguments(),
            )

        self.assertEqual(fields, {})
        self.assertEqual(
            warnings,
            ["AI/OCR не смог распознать карту клиента: model_gateway_provider_failed"],
        )
        self.assertNotIn("private-key", repr(warnings))

    def test_cutover_defaults_to_legacy_and_switches_only_this_call(self):
        calls = []
        with (
            patch.object(
                routes,
                "_recognize_client_card_with_ai_legacy",
                lambda **_values: calls.append("legacy") or ({"source": "old"}, []),
            ),
            patch.object(
                routes,
                "_recognize_client_card_with_ai_gateway",
                lambda **_values: calls.append("gateway") or ({"source": "new"}, []),
            ),
        ):
            old = routes._recognize_client_card_with_ai(**_arguments())
            new = routes._recognize_client_card_with_ai(
                **_arguments(),
                model_gateway_enabled=True,
            )

        self.assertEqual(old, ({"source": "old"}, []))
        self.assertEqual(new, ({"source": "new"}, []))
        self.assertEqual(calls, ["legacy", "gateway"])

    def test_direct_provider_access_is_confined_to_the_rollback_function(self):
        tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"), filename=str(ROUTES_PATH))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "_recognize_client_card_with_ai",
                "_recognize_client_card_with_ai_gateway",
                "_recognize_client_card_with_ai_legacy",
            }
        }

        self.assertEqual(set(functions), {
            "_recognize_client_card_with_ai",
            "_recognize_client_card_with_ai_gateway",
            "_recognize_client_card_with_ai_legacy",
        })
        self.assertIn("OpenAI", ast.unparse(functions["_recognize_client_card_with_ai_legacy"]))
        self.assertNotIn("OpenAI", ast.unparse(functions["_recognize_client_card_with_ai_gateway"]))
        self.assertNotIn("OpenAI", ast.unparse(functions["_recognize_client_card_with_ai"]))

    def test_composition_root_keeps_the_cutover_disabled_by_default(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_platform_admin_routes"
        ]
        self.assertEqual(len(registrations), 1)
        dependency_map = registrations[0].args[1]
        values = {
            key.value: ast.unparse(value)
            for key, value in zip(dependency_map.keys, dependency_map.values)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        flag_expression = values["model_gateway_enabled"]
        self.assertIn("PLATFORM_CLIENT_CARD_MODEL_GATEWAY_ENABLED", flag_expression)
        self.assertIn("'false'", flag_expression)
        self.assertEqual(
            sum(
                line == "PLATFORM_CLIENT_CARD_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
