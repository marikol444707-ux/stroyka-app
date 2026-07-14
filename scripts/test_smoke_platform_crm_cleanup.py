import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("smoke-platform-crm.py")
SPEC = importlib.util.spec_from_file_location("smoke_platform_crm", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlatformCrmCleanupTests(unittest.TestCase):
    def test_audit_cleanup_is_limited_to_current_smoke_prefix(self):
        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params):
                self.calls.append((" ".join(sql.split()), params))

        cursor = Cursor()

        MODULE.cleanup_audit_log(cursor)

        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        self.assertIn("DELETE FROM audit_log", sql)
        self.assertIn("project_name LIKE", sql)
        self.assertIn("user_name LIKE", sql)
        self.assertIn("description LIKE", sql)
        self.assertEqual(
            params,
            (
                MODULE.PREFIX + "%",
                MODULE.PREFIX + "%",
                "%" + MODULE.PREFIX + "%",
            ),
        )


if __name__ == "__main__":
    unittest.main()
