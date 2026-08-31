import os
import subprocess
import sys
import unittest

from backend import config


class AuthSecretConfigurationTest(unittest.TestCase):
    def test_explicit_generated_secret_is_ready_for_enforcement(self):
        status = config.build_auth_secret_readiness(
            {
                "AUTH_SECRET": "7VjZ2Xh0f9Nq4rLm8Bc3Ds6Wp1Ka5TyUe0Gi2Ho9",
                "DB_PASSWORD": "database-password",
                "AUTH_SECRET_REQUIRED": "true",
            }
        )

        self.assertTrue(status["readyForEnforcement"])
        self.assertTrue(status["explicit"])
        self.assertTrue(status["enforcementEnabled"])
        self.assertEqual(status["source"], "explicit")
        self.assertEqual(status["blockers"], [])
        self.assertNotIn("secret", " ".join(status.keys()).lower())
        self.assertNotIn("AUTH_SECRET", repr(status))
        self.assertNotIn(
            "7VjZ2Xh0f9Nq4rLm8Bc3Ds6Wp1Ka5TyUe0Gi2Ho9",
            repr(status),
        )

    def test_missing_secret_reports_legacy_database_fallback(self):
        status = config.build_auth_secret_readiness(
            {
                "DB_PASSWORD": "database-password",
                "AUTH_SECRET_REQUIRED": "false",
            }
        )

        self.assertFalse(status["readyForEnforcement"])
        self.assertFalse(status["explicit"])
        self.assertEqual(status["source"], "legacy_db_derived")
        self.assertEqual(status["blockers"], ["auth_secret_missing"])

    def test_predictable_and_database_derived_values_are_rejected(self):
        cases = (
            ("change-me", "database-password", "auth_secret_placeholder"),
            ("database-password", "database-password", "auth_secret_matches_database_password"),
            (
                "database-password|stroyka-auth",
                "database-password",
                "auth_secret_derived_from_database_password",
            ),
        )

        for secret, database_password, blocker in cases:
            with self.subTest(blocker=blocker):
                status = config.build_auth_secret_readiness(
                    {
                        "AUTH_SECRET": secret,
                        "DB_PASSWORD": database_password,
                        "AUTH_SECRET_REQUIRED": "true",
                    }
                )
                self.assertFalse(status["readyForEnforcement"])
                self.assertIn(blocker, status["blockers"])

    def test_short_or_whitespace_wrapped_secret_is_rejected(self):
        short = config.build_auth_secret_readiness({"AUTH_SECRET": "short-value"})
        padded = config.build_auth_secret_readiness(
            {"AUTH_SECRET": " 7VjZ2Xh0f9Nq4rLm8Bc3Ds6Wp1Ka5TyUe0Gi2Ho9 "}
        )

        self.assertIn("auth_secret_too_short", short["blockers"])
        self.assertIn("auth_secret_has_outer_whitespace", padded["blockers"])

    def test_low_diversity_secret_is_rejected(self):
        status = config.build_auth_secret_readiness(
            {"AUTH_SECRET": "a" * config.AUTH_SECRET_MIN_LENGTH}
        )

        self.assertIn("auth_secret_low_character_diversity", status["blockers"])

    def test_required_invalid_secret_fails_with_fixed_safe_error(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "AUTH_SECRET_REQUIRED_BUT_INVALID",
        ):
            config.require_ready_auth_secret(
                config.build_auth_secret_readiness(
                    {"AUTH_SECRET_REQUIRED": "true"}
                )
            )

    def test_required_invalid_secret_stops_config_import(self):
        environment = os.environ.copy()
        environment.update(
            {
                "AUTH_SECRET": "",
                "AUTH_SECRET_REQUIRED": "true",
                "DB_PASSWORD": "database-password",
            }
        )

        result = subprocess.run(
            [sys.executable, "-c", "import backend.config"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AUTH_SECRET_REQUIRED_BUT_INVALID", result.stderr)
        self.assertNotIn("database-password", result.stderr)


if __name__ == "__main__":
    unittest.main()
