import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("smoke-tenant-files.py")
SPEC = importlib.util.spec_from_file_location("smoke_tenant_files", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TenantFileSmokeTests(unittest.TestCase):
    def test_private_s3_requires_anonymous_compatibility_url_to_be_blocked(self):
        with patch.object(MODULE, "env_value", side_effect={
            "STORAGE_BACKEND": "s3",
            "S3_ACL": "private",
            "PUBLIC_UPLOADS_MOUNT_ENABLED": "false",
        }.get):
            self.assertFalse(MODULE.compatibility_delivery_is_public())

    def test_public_s3_compatibility_mode_is_detected(self):
        with patch.object(MODULE, "env_value", side_effect={
            "STORAGE_BACKEND": "s3",
            "S3_ACL": "public-read",
            "PUBLIC_UPLOADS_MOUNT_ENABLED": "false",
        }.get):
            self.assertTrue(MODULE.compatibility_delivery_is_public())

    def test_s3_without_explicit_acl_uses_backend_public_default(self):
        with patch.object(MODULE, "env_value", side_effect={
            "STORAGE_BACKEND": "s3",
            "S3_ACL": "",
            "PUBLIC_UPLOADS_MOUNT_ENABLED": "false",
        }.get):
            self.assertTrue(MODULE.compatibility_delivery_is_public())

    def test_local_delivery_depends_on_public_mount_flag(self):
        with patch.object(MODULE, "env_value", side_effect={
            "STORAGE_BACKEND": "local",
            "S3_ACL": "",
            "PUBLIC_UPLOADS_MOUNT_ENABLED": "true",
        }.get):
            self.assertTrue(MODULE.compatibility_delivery_is_public())

        with patch.object(MODULE, "env_value", side_effect={
            "STORAGE_BACKEND": "local",
            "S3_ACL": "",
            "PUBLIC_UPLOADS_MOUNT_ENABLED": "false",
        }.get):
            self.assertFalse(MODULE.compatibility_delivery_is_public())

    def test_auth_token_uses_explicit_token_without_password_login(self):
        with patch.object(MODULE, "env_value", side_effect={
            "SMOKE_AUTH_TOKEN": "temporary-smoke-token",
        }.get), patch.object(MODULE, "login") as login:
            self.assertEqual(MODULE.auth_token(), "temporary-smoke-token")
            login.assert_not_called()

    def test_auth_token_falls_back_to_interactive_credentials(self):
        values = {
            "SMOKE_AUTH_TOKEN": "",
            "SMOKE_EMAIL": "smoke@example.test",
            "SMOKE_PASSWORD": "secret",
        }
        with patch.object(MODULE, "env_value", side_effect=values.get), patch.object(
            MODULE, "login", return_value="login-token"
        ) as login:
            self.assertEqual(MODULE.auth_token(), "login-token")
            login.assert_called_once_with("smoke@example.test", "secret")


if __name__ == "__main__":
    unittest.main()
