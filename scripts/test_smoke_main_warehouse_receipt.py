import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("smoke-main-warehouse-receipt.py")
SPEC = importlib.util.spec_from_file_location("smoke_main_warehouse_receipt", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MainWarehouseReceiptLoginTests(unittest.TestCase):
    def test_initial_2fa_setup_returns_authenticated_token(self):
        calls = []

        def fake_api_json(method, path, **kwargs):
            calls.append((method, path, kwargs.get("data")))
            return {"authToken": "qa-token"}

        with patch.object(MODULE, "api_json", side_effect=fake_api_json), patch.object(
            MODULE, "totp_code", return_value="123456"
        ):
            token = MODULE.token_from_login_response(
                {
                    "twoFactorSetupRequired": True,
                    "setupToken": "setup-token",
                    "manualKey": "BASE32SECRET",
                },
                "qa@example.test",
            )

        self.assertEqual(token, "qa-token")
        self.assertEqual(calls, [
            (
                "POST",
                "/login/2fa/setup-confirm",
                {"setupToken": "setup-token", "code": "123456"},
            ),
        ])


if __name__ == "__main__":
    unittest.main()
