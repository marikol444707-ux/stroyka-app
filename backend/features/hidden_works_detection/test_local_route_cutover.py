import ast
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MAIN_PATH = BACKEND_ROOT / "main.py"
ENV_EXAMPLE_PATH = BACKEND_ROOT / ".env.example"


class HiddenWorksLocalRouteCutoverTest(unittest.TestCase):
    def test_route_uses_stored_company_and_preserves_all_existing_fallbacks(self):
        tree = ast.parse(
            MAIN_PATH.read_text(encoding="utf-8"),
            filename=str(MAIN_PATH),
        )
        route = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "ai_detect_hidden_works"
        )
        source = ast.unparse(route)

        self.assertIn("SELECT sections_json, company_id FROM estimates", source)
        self.assertIn("try_local_hidden_works_canary", source)
        self.assertIn("generate_local_hidden_works", source)
        self.assertIn("local_result is not None", source)
        self.assertIn("local_result.hidden_names", source)
        self.assertIn("local_result.method", source)
        self.assertIn("generate_hidden_works_detection", source)
        self.assertIn("_detect_hidden_by_keywords", source)
        self.assertLess(
            source.index("try_local_hidden_works_canary"),
            source.index("generate_hidden_works_detection"),
        )
        self.assertNotIn("X-Company", source)
        self.assertNotIn("str(e)", source)

    def test_local_empty_result_is_complete_and_does_not_trigger_keywords(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MAIN_PATH))
        route = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "ai_detect_hidden_works"
        )
        route_source = ast.unparse(route)

        self.assertIn("detection_completed = True", route_source)
        self.assertIn("if not detection_completed", route_source)

    def test_all_local_settings_are_explicit_and_off_by_default(self):
        lines = ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        expected = (
            "HIDDEN_WORKS_LOCAL_MODEL_ENABLED=false",
            "HIDDEN_WORKS_LOCAL_MODEL_COMPANY_IDS=",
            "HIDDEN_WORKS_LOCAL_MODEL_PORT=",
            "HIDDEN_WORKS_LOCAL_MODEL_API_KEY=",
        )
        for setting in expected:
            with self.subTest(setting=setting):
                self.assertEqual(lines.count(setting), 1)


if __name__ == "__main__":
    unittest.main()
