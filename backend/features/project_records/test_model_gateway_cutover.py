import ast
import io
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
    def test_room_draft_text_path_builds_the_neutral_request(self):
        gateway = FakeGateway()
        adapter_arguments = []

        def adapter_factory(**values):
            adapter_arguments.append(values)
            return gateway

        with patch.object(routes, "build_yandex_model_adapter", adapter_factory):
            rooms, source = routes._draft_rooms_with_ai(
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
            rooms, source = routes._draft_rooms_with_ai(
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
            rooms, source = routes._draft_rooms_with_ai(
                _measurement(),
                "private-key",
                "folder-1",
            )

        self.assertEqual(source, "fallback")
        self.assertTrue(rooms[0]["name"].startswith("Кабинет"))
        printed = " ".join(str(value) for call in print_mock.call_args_list for value in call.args)
        self.assertIn("model_gateway_provider_failed", printed)
        self.assertNotIn("private-key", printed)

    def test_room_draft_has_no_direct_provider_or_cutover_flag(self):
        tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"), filename=str(ROUTES_PATH))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("_draft_rooms_with_ai")
        }

        self.assertEqual(
            set(functions),
            {"_draft_rooms_with_ai"},
        )
        function_source = ast.unparse(functions["_draft_rooms_with_ai"])
        self.assertNotIn("OpenAI", function_source)
        self.assertNotIn("model_gateway_enabled", function_source)

    def test_composition_root_no_longer_has_a_cutover_flag(self):
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
        self.assertNotIn("model_gateway_enabled", values)
        self.assertEqual(
            sum(
                line == "PROJECT_ROOM_DRAFT_MODEL_GATEWAY_ENABLED=false"
                for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
