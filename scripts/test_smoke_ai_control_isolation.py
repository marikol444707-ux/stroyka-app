import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("smoke-ai-control-isolation.py")
SPEC = importlib.util.spec_from_file_location("smoke_ai_control_isolation", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AiControlIsolationSmokeTests(unittest.TestCase):
    def test_assert_success_accepts_only_exact_project(self):
        MODULE.assert_success({"ok": True, "projectName": "A"}, "A", "single")
        with self.assertRaises(RuntimeError):
            MODULE.assert_success({"ok": True, "projectName": "B"}, "A", "single")
        with self.assertRaises(RuntimeError):
            MODULE.assert_success({"ok": False, "projectName": "A"}, "A", "single")

    def test_batch_requires_exactly_one_fixture_project(self):
        MODULE.assert_batch_scope(
            {"ok": True, "projects": 1, "results": [{"ok": True, "projectName": "A"}]},
            "A",
        )
        with self.assertRaises(RuntimeError):
            MODULE.assert_batch_scope(
                {
                    "ok": True,
                    "projects": 2,
                    "results": [
                        {"ok": True, "projectName": "A"},
                        {"ok": True, "projectName": "B"},
                    ],
                },
                "A",
            )

    def test_fixture_names_are_unique_and_non_production(self):
        self.assertIn("CODEX AI smoke", MODULE.FIXTURE["company_a_name"])
        self.assertNotEqual(MODULE.FIXTURE["company_a_name"], MODULE.FIXTURE["company_b_name"])
        self.assertNotEqual(MODULE.FIXTURE["project_a_name"], MODULE.FIXTURE["project_b_name"])


if __name__ == "__main__":
    unittest.main()
