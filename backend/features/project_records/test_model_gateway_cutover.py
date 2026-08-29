import ast
import io
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.project_records import routes


ROUTES_PATH = Path(routes.__file__)
BACKEND_ROOT = ROUTES_PATH.parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class FakeGateway:
    def __init__(self, *, output_text=None, error=None):
        self.output_text = output_text or '{"rooms":[{"name":"Кабинет"}]}'
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


def _measurement(**overrides):
    value = {
        "title": "Обмер первого этажа",
        "notes": "Кабинет 18 м2, высота 3 м",
        "source_type": "Обмер",
        "doc_type": "План",
        "file_url": "",
    }
    value.update(overrides)
    return value


class ProjectRoomDraftGatewayCutoverTest(unittest.TestCase):
    def test_legacy_rollback_preserves_the_existing_sdk_request(self):
        captured = {"client": None, "request": None}

        class FakeResponses:
            def create(self, **values):
                captured["request"] = values
                return SimpleNamespace(output_text='{"rooms":[{"name":"Кабинет"}]}')

        class FakeOpenAI:
            def __init__(self, **values):
                captured["client"] = values
                self.responses = FakeResponses()

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAI

        with patch.dict(sys.modules, {"openai": fake_openai}):
            rooms, source = routes._draft_rooms_with_ai_legacy(
                _measurement(),
                "private-key",
                "folder-1",
            )

        self.assertEqual(rooms, [{"name": "Кабинет"}])
        self.assertEqual(source, "ai")
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
                "model": "gpt://folder-1/qwen3.6-35b-a3b/latest",
                "temperature": 0.1,
                "instructions": routes._ROOM_DRAFT_INSTRUCTIONS,
                "input": routes._room_draft_prompt(_measurement()),
                "max_output_tokens": 2500,
            },
        )

    def test_gateway_text_path_builds_the_equivalent_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(routes, "build_yandex_model_adapter", adapter_factory):
            rooms, source = routes._draft_rooms_with_ai_gateway(
                _measurement(),
                "private-key",
                "folder-1",
            )

        self.assertEqual(rooms, [{"name": "Кабинет"}])
        self.assertEqual(source, "ai")
        self.assertEqual(
            adapter_arguments,
            [{"api_key": "private-key", "folder_id": "folder-1"}],
        )
        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request.capability, "project_room_draft")
        self.assertEqual(request.instructions, routes._ROOM_DRAFT_INSTRUCTIONS)
        self.assertEqual(request.input_text, routes._room_draft_prompt(_measurement()))
        self.assertEqual(request.input_parts, ())
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 2500)
        self.assertEqual(request.deadline_seconds, 120)

    def test_gateway_image_path_preserves_the_image_and_prompt_order(self):
        gateway = FakeGateway()
        with (
            patch.object(routes, "build_yandex_model_adapter", lambda **_values: gateway),
            patch.object(routes.os.path, "exists", return_value=True),
            patch("builtins.open", return_value=io.BytesIO(b"jpeg-bytes")),
        ):
            rooms, source = routes._draft_rooms_with_ai_gateway(
                _measurement(file_url="/uploads/room.jpg"),
                "private-key",
                "folder-1",
            )

        self.assertEqual(rooms, [{"name": "Кабинет"}])
        self.assertEqual(source, "ai")
        request = gateway.requests[0]
        self.assertEqual(request.input_text, "")
        self.assertEqual(
            [(part.kind, part.value) for part in request.input_parts],
            [
                ("image_data_url", "data:image/jpeg;base64,anBlZy1ieXRlcw=="),
                ("text", routes._room_draft_prompt(_measurement(file_url="/uploads/room.jpg"))),
            ],
        )

    def test_image_path_cannot_escape_the_upload_directory(self):
        with patch("builtins.open") as open_mock:
            value = routes._room_draft_image_data_url({
                "file_url": "/uploads/../../backend/.env.jpg",
            })

        self.assertEqual(value, "")
        open_mock.assert_not_called()

    def test_gateway_failure_uses_the_existing_fallback_without_secret_leakage(self):
        gateway = FakeGateway(error=RuntimeError("provider leaked private-key"))
        with (
            patch.object(routes, "build_yandex_model_adapter", lambda **_values: gateway),
            patch("builtins.print") as print_mock,
        ):
            rooms, source = routes._draft_rooms_with_ai_gateway(
                _measurement(),
                "private-key",
                "folder-1",
            )

        self.assertEqual(source, "fallback")
        self.assertTrue(rooms[0]["name"].startswith("Кабинет"))
        printed = " ".join(str(value) for call in print_mock.call_args_list for value in call.args)
        self.assertIn("model_gateway_provider_failed", printed)
        self.assertNotIn("private-key", printed)

    def test_cutover_defaults_to_legacy_and_enables_only_this_gateway(self):
        calls = []
        with (
            patch.object(
                routes,
                "_draft_rooms_with_ai_legacy",
                lambda *_args: calls.append("legacy") or ([{"name": "old"}], "ai"),
            ),
            patch.object(
                routes,
                "_draft_rooms_with_ai_gateway",
                lambda *_args: calls.append("gateway") or ([{"name": "new"}], "ai"),
            ),
        ):
            old = routes._draft_rooms_with_ai(_measurement(), "key", "folder")
            new = routes._draft_rooms_with_ai(
                _measurement(),
                "key",
                "folder",
                model_gateway_enabled=True,
            )

        self.assertEqual(old, ([{"name": "old"}], "ai"))
        self.assertEqual(new, ([{"name": "new"}], "ai"))
        self.assertEqual(calls, ["legacy", "gateway"])

    def test_direct_provider_access_is_confined_to_the_rollback_function(self):
        tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"), filename=str(ROUTES_PATH))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "_draft_rooms_with_ai",
                "_draft_rooms_with_ai_gateway",
                "_draft_rooms_with_ai_legacy",
            }
        }

        self.assertEqual(
            set(functions),
            {
                "_draft_rooms_with_ai",
                "_draft_rooms_with_ai_gateway",
                "_draft_rooms_with_ai_legacy",
            },
        )
        self.assertIn("OpenAI", ast.unparse(functions["_draft_rooms_with_ai_legacy"]))
        self.assertNotIn("OpenAI", ast.unparse(functions["_draft_rooms_with_ai_gateway"]))
        self.assertNotIn("OpenAI", ast.unparse(functions["_draft_rooms_with_ai"]))

    def test_composition_root_keeps_the_cutover_disabled_by_default(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_project_records_module"
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
        self.assertIn("PROJECT_ROOM_DRAFT_MODEL_GATEWAY_ENABLED", flag_expression)
        self.assertIn("'false'", flag_expression)
        self.assertEqual(
            sum(
                line == "PROJECT_ROOM_DRAFT_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
