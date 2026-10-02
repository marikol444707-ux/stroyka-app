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

    def test_temporary_director_gets_explicit_company_membership(self):
        calls = []

        class Cursor:
            def execute(self, sql, params):
                calls.append((" ".join(sql.split()), params))

            def fetchone(self):
                return (501, "Smoke Deputy", "smoke@example.test", "зам_директора")

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
            MODULE.create_temp_director_token(company_id=7, platform_account_id=3)

        membership = next(call for call in calls if "INSERT INTO user_company_roles" in call[0])
        self.assertEqual(membership[1], (501, 3, 7, "зам_директора"))

    def test_membership_helper_preserves_worker_role(self):
        calls = []

        class Cursor:
            def execute(self, sql, params):
                calls.append((" ".join(sql.split()), params))

        MODULE.provision_company_membership(
            Cursor(),
            user_id=601,
            platform_account_id=4,
            company_id=8,
            role="мастер",
        )

        self.assertEqual(calls[0][1], (601, 4, 8, "мастер"))

    def test_production_smoke_does_not_create_immutable_work_ledger_rows(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertNotIn('api_json("PUT", f"/estimates/', source)


if __name__ == "__main__":
    unittest.main()
