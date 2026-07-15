import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("smoke-max-marketing-lead.py")
SPEC = importlib.util.spec_from_file_location("smoke_max_marketing_lead", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MaxMarketingSmokeTests(unittest.TestCase):
    def test_temporary_user_password_is_stored_as_pbkdf2(self):
        self.assertRegex(
            MODULE.hash_password("temporary-secret"),
            r"^pbkdf2_sha256\$260000\$[0-9a-f]{32}\$[0-9a-f]{64}$",
        )

    def test_smoke_company_prefers_explicit_company_then_public_site_owner(self):
        with patch.object(
            MODULE,
            "env_value",
            side_effect=lambda name, default="": {
                "SMOKE_COMPANY_ID": "7",
                "PUBLIC_SITE_COMPANY_ID": "1",
            }.get(name, default),
        ):
            self.assertEqual(MODULE.smoke_company_id(), 7)

        with patch.object(
            MODULE,
            "env_value",
            side_effect=lambda name, default="": "1" if name == "PUBLIC_SITE_COMPANY_ID" else default,
        ):
            self.assertEqual(MODULE.smoke_company_id(), 1)

    def test_temporary_director_token_marks_2fa_as_passed(self):
        token = MODULE.auth_token_for({
            "id": 101,
            "email": "max-smoke@example.test",
            "role": "директор",
            "name": "MAX Smoke",
        })
        body, _signature = token.split(".", 1)
        payload = json.loads(MODULE.base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))

        self.assertIs(payload["twoFactorPassed"], True)

if __name__ == "__main__":
    unittest.main()
