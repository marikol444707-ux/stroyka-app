import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("smoke-work-assignment.py")
SPEC = importlib.util.spec_from_file_location("smoke_work_assignment", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkAssignmentSmokeTests(unittest.TestCase):
    def test_temporary_user_token_marks_2fa_as_passed(self):
        token = MODULE.auth_token_for({
            "id": 101,
            "email": "work-assignment-smoke@example.test",
            "role": "зам_директора",
            "name": "Work Assignment Smoke",
        })
        body, _signature = token.split(".", 1)
        payload = json.loads(MODULE.base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))

        self.assertIs(payload["twoFactorPassed"], True)

    def test_cleanup_deletes_estimate_versions_before_estimates(self):
        calls = []

        class Cursor:
            def execute(self, sql, params):
                calls.append(" ".join(sql.split()))

            def close(self):
                pass

        class Connection:
            def cursor(self):
                return Cursor()

            def commit(self):
                pass

            def close(self):
                pass

        with patch.object(MODULE, "db_conn", return_value=Connection()):
            MODULE.cleanup()

        version_delete = next(i for i, sql in enumerate(calls) if sql.startswith("DELETE FROM estimate_versions"))
        estimate_delete = next(i for i, sql in enumerate(calls) if sql.startswith("DELETE FROM estimates"))
        self.assertLess(version_delete, estimate_delete)


if __name__ == "__main__":
    unittest.main()
