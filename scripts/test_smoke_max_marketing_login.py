import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("smoke-max-marketing-lead.py")
SPEC = importlib.util.spec_from_file_location("smoke_max_marketing_lead", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MaxMarketingLoginTests(unittest.TestCase):
    def test_login_returns_direct_token_without_2fa(self):
        with patch.object(MODULE, "api_json", return_value=(200, {"authToken": "direct-token"})):
            self.assertEqual(MODULE.login("director@example.test", "secret"), "direct-token")

    def test_login_verifies_2fa_challenge(self):
        responses = [
            (200, {"twoFactorRequired": True, "challengeToken": "challenge"}),
            (200, {"authToken": "verified-token"}),
        ]
        with (
            patch.object(MODULE, "api_json", side_effect=responses) as api_json,
            patch.object(MODULE, "env_value", side_effect=lambda name, default="": "123456" if name == "SMOKE_2FA_CODE" else default),
        ):
            token = MODULE.login("director@example.test", "secret")

        self.assertEqual(token, "verified-token")
        self.assertEqual(api_json.call_count, 2)
        self.assertEqual(
            api_json.call_args_list[1].kwargs["data"],
            {"challengeToken": "challenge", "code": "123456"},
        )

    def test_login_requires_2fa_input_for_challenge(self):
        with (
            patch.object(
                MODULE,
                "api_json",
                return_value=(200, {"twoFactorRequired": True, "challengeToken": "challenge"}),
            ),
            patch.object(MODULE, "env_value", return_value=""),
        ):
            with self.assertRaisesRegex(SystemExit, "SMOKE_2FA_CODE"):
                MODULE.login("director@example.test", "secret")


if __name__ == "__main__":
    unittest.main()
