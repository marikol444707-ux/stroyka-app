import unittest
import ast
from pathlib import Path

from backend.features.work_journal.hidden_work_photo import (
    HIDDEN_WORK_PHOTO_REQUIRED_DETAIL,
    hidden_work_photo_required,
)


class HiddenWorkPhotoRuleTests(unittest.TestCase):
    def test_confirmed_hidden_work_requires_a_photo(self):
        self.assertTrue(hidden_work_photo_required(
            hidden_work=True,
            status="Подтверждено",
            photo_url="",
        ))

    def test_pending_hidden_work_may_wait_for_a_photo(self):
        self.assertFalse(hidden_work_photo_required(
            hidden_work=True,
            status="На проверке",
            photo_url="",
        ))

    def test_confirmed_hidden_work_accepts_a_photo(self):
        self.assertFalse(hidden_work_photo_required(
            hidden_work=True,
            status="Подтверждено",
            photo_url=" /tenant-files/41/content ",
        ))

    def test_regular_work_does_not_require_a_photo(self):
        self.assertFalse(hidden_work_photo_required(
            hidden_work=False,
            status="Подтверждено",
            photo_url="",
        ))

    def test_error_message_explains_the_required_action(self):
        self.assertIn("Скрытую работу", HIDDEN_WORK_PHOTO_REQUIRED_DETAIL)
        self.assertIn("фото", HIDDEN_WORK_PHOTO_REQUIRED_DETAIL.lower())

    def test_main_routes_enforce_the_rule_and_trust_estimate_hidden_flag(self):
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
        functions = {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"create_work_journal", "update_work_journal", "update_estimate"}
        }

        self.assertEqual(set(functions), {
            "create_work_journal",
            "update_work_journal",
            "update_estimate",
        })
        self.assertIn('journal_hidden_work = bool(estimate_work_item.get(\'hiddenWork\'))', functions["create_work_journal"])
        self.assertIn("hidden_work_photo_required", functions["update_work_journal"])
        self.assertIn("hidden_work, photo_url", functions["update_work_journal"])
        self.assertIn("target_hidden_work if js_key == 'hiddenWork'", functions["update_work_journal"])
        self.assertIn("hidden_work_photo_required", functions["update_estimate"])


if __name__ == "__main__":
    unittest.main()
