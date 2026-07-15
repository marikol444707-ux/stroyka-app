import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("smoke-platform-crm.py")
SPEC = importlib.util.spec_from_file_location("smoke_platform_crm", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlatformCrmCleanupTests(unittest.TestCase):
    def test_complete_2fa_setup_confirms_registration_challenge(self):
        with (
            patch.object(MODULE, "totp_code", return_value="123456"),
            patch.object(MODULE, "api_json", return_value=(200, {"authToken": "verified"})) as api_json,
        ):
            result = MODULE.complete_2fa_setup(
                {
                    "twoFactorSetupRequired": True,
                    "setupToken": "setup-token",
                    "manualKey": "JBSWY3DPEHPK3PXP",
                }
            )

        self.assertEqual(result, {"authToken": "verified"})
        self.assertEqual(
            api_json.call_args.kwargs["data"],
            {"setupToken": "setup-token", "code": "123456"},
        )

    def test_complete_2fa_setup_keeps_regular_registration(self):
        registration = {"authToken": "direct"}

        self.assertIs(MODULE.complete_2fa_setup(registration), registration)

    def test_smoke_token_marks_2fa_as_passed_for_temporary_user(self):
        token = MODULE.auth_token_for(
            {
                "id": 101,
                "email": "system-smoke@example.test",
                "role": "system_owner",
                "name": "System Smoke",
            }
        )
        body, _signature = token.split(".", 1)
        payload = json.loads(MODULE.base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))

        self.assertIs(payload["twoFactorPassed"], True)

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
