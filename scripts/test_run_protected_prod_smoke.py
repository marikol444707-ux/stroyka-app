import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("run_protected_prod_smoke.py")
SPEC = importlib.util.spec_from_file_location(
    "run_protected_prod_smoke", SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProtectedProductionSmokeRunnerTests(unittest.TestCase):
    def write_config(self, directory, content, mode=0o600):
        path = Path(directory) / "prod-smoke.env"
        path.write_text(content, encoding="utf-8")
        path.chmod(mode)
        return path

    def valid_config(self):
        return (
            "SMOKE_EMAIL=smoke@example.test\n"
            "SMOKE_PASSWORD=a long test password = with symbols !\n"
            "SMOKE_TOTP_SECRET=JBSWY3DPEHPK3PXP\n"
            "SMOKE_COMPANY_ID=1\n"
        )

    def valid_manual_code_config(self):
        return self.valid_config().replace(
            "SMOKE_TOTP_SECRET=JBSWY3DPEHPK3PXP\n", "",
        )

    def test_load_config_accepts_exact_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, self.valid_config())

            config = MODULE.load_config(path)

        self.assertEqual(
            config,
            {
                "SMOKE_EMAIL": "smoke@example.test",
                "SMOKE_PASSWORD": "a long test password = with symbols !",
                "SMOKE_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
                "SMOKE_COMPANY_ID": "1",
            },
        )

    def test_load_config_accepts_file_without_totp_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory, self.valid_manual_code_config(),
            )

            config = MODULE.load_config(path)

        self.assertEqual(
            config,
            {
                "SMOKE_EMAIL": "smoke@example.test",
                "SMOKE_PASSWORD": "a long test password = with symbols !",
                "SMOKE_COMPANY_ID": "1",
            },
        )

    def test_load_config_rejects_unsupported_permission_modes(self):
        for mode in (0o640, 0o700):
            with self.subTest(mode=oct(mode)):
                with tempfile.TemporaryDirectory() as directory:
                    path = self.write_config(
                        directory, self.valid_config(), mode=mode,
                    )

                    with self.assertRaisesRegex(
                        MODULE.ConfigurationError,
                        "permissions must be 0600 or stricter",
                    ):
                        MODULE.load_config(path)

    def test_load_config_rejects_symbolic_link(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.write_config(directory, self.valid_config())
            link = Path(directory) / "linked.env"
            link.symlink_to(target)

            with self.assertRaisesRegex(
                MODULE.ConfigurationError, "regular non-symlink file",
            ):
                MODULE.load_config(link)

    def test_load_config_rejects_unknown_duplicate_or_stale_code_fields(self):
        invalid_configs = (
            self.valid_config() + "BASE_URL=https://attacker.example\n",
            self.valid_config() + "SMOKE_COMPANY_ID=2\n",
            self.valid_config() + "SMOKE_2FA_CODE=123456\n",
        )
        for content in invalid_configs:
            with self.subTest(content=content.rsplit("\n", 2)[-2]):
                with tempfile.TemporaryDirectory() as directory:
                    path = self.write_config(directory, content)
                    with self.assertRaises(MODULE.ConfigurationError):
                        MODULE.load_config(path)

    def test_load_config_rejects_noncanonical_values(self):
        replacements = (
            ("smoke@example.test", "not-an-email"),
            (
                "smoke@example.test",
                "a" * 254 + "@" + "b" * 61 + ".test",
            ),
            ("smoke@example.test", "smoke\x00@example.test"),
            (
                "a long test password = with symbols !",
                "bad\x00password",
            ),
            ("JBSWY3DPEHPK3PXP", "lowercase-secret"),
            ("SMOKE_COMPANY_ID=1", "SMOKE_COMPANY_ID=01"),
        )
        for original, replacement in replacements:
            with self.subTest(replacement=replacement):
                with tempfile.TemporaryDirectory() as directory:
                    path = self.write_config(
                        directory,
                        self.valid_config().replace(original, replacement),
                    )
                    with self.assertRaises(MODULE.ConfigurationError):
                        MODULE.load_config(path)

    def test_build_environment_forces_production_and_removes_stale_auth(self):
        config = {
            "SMOKE_EMAIL": "smoke@example.test",
            "SMOKE_PASSWORD": "secret",
            "SMOKE_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
            "SMOKE_COMPANY_ID": "1",
        }
        inherited = {
            "PATH": "/usr/bin",
            "BASE_URL": "https://attacker.example",
            "SMOKE_2FA_CODE": "000000",
            "SMOKE_PASSWORD": "stale",
        }

        environment = MODULE.build_environment(config, inherited)

        self.assertEqual(environment["BASE_URL"], "https://stroyka26.pro")
        self.assertEqual(environment["SMOKE_PROTECTED_ONLY"], "1")
        self.assertEqual(environment["SMOKE_BUSINESS_READ_ONLY"], "1")
        self.assertEqual(environment["SMOKE_PASSWORD"], "secret")
        self.assertNotIn("SMOKE_2FA_CODE", environment)
        self.assertEqual(environment["PATH"], "/usr/bin")

    def test_check_mode_does_not_start_npm_or_print_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, self.valid_config())
            with patch.object(MODULE.os, "execvpe") as execute:
                with patch("builtins.print") as output:
                    result = MODULE.main(["--check", "--env-file", str(path)])

        self.assertEqual(result, 0)
        execute.assert_not_called()
        rendered = " ".join(
            " ".join(str(part) for part in call.args)
            for call in output.call_args_list
        )
        self.assertIn("PROTECTED_SMOKE_CONFIG_OK", rendered)
        self.assertNotIn("smoke@example.test", rendered)
        self.assertNotIn("a long test password", rendered)
        self.assertNotIn("JBSWY3DPEHPK3PXP", rendered)

    def test_check_mode_does_not_prompt_for_manual_two_factor_code(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory, self.valid_manual_code_config(),
            )
            with patch("getpass.getpass") as prompt:
                with patch.object(MODULE.os, "execvpe") as execute:
                    with patch("builtins.print"):
                        result = MODULE.main([
                            "--check", "--env-file", str(path),
                        ])

        self.assertEqual(result, 0)
        prompt.assert_not_called()
        execute.assert_not_called()

    def test_run_prompts_for_current_code_when_totp_secret_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory, self.valid_manual_code_config(),
            )
            with patch("getpass.getpass", return_value="123456") as prompt:
                with patch.object(MODULE.os, "execvpe") as execute:
                    result = MODULE.main(["--env-file", str(path)])

        self.assertEqual(result, 0)
        prompt.assert_called_once()
        environment = execute.call_args.args[2]
        self.assertEqual(environment["SMOKE_2FA_CODE"], "123456")
        self.assertNotIn("SMOKE_TOTP_SECRET", environment)

    def test_run_rejects_invalid_manual_two_factor_codes(self):
        for code in ("", "12345", "1234567", "12345a", " 123456"):
            with self.subTest(code=code):
                with tempfile.TemporaryDirectory() as directory:
                    path = self.write_config(
                        directory, self.valid_manual_code_config(),
                    )
                    with patch("getpass.getpass", return_value=code):
                        with patch.object(MODULE.os, "execvpe") as execute:
                            with self.assertRaisesRegex(
                                MODULE.ConfigurationError,
                                "six digits",
                            ):
                                MODULE.main(["--env-file", str(path)])

                execute.assert_not_called()

    def test_run_executes_only_the_existing_production_smoke(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, self.valid_config())
            with patch.object(MODULE.os, "execvpe") as execute:
                result = MODULE.main(["--env-file", str(path)])

        self.assertEqual(result, 0)
        execute.assert_called_once()
        executable, arguments, environment = execute.call_args.args
        self.assertEqual(executable, "npm")
        self.assertEqual(arguments, ["npm", "run", "smoke:prod"])
        self.assertEqual(environment["SMOKE_PROTECTED_ONLY"], "1")
        self.assertEqual(environment["SMOKE_BUSINESS_READ_ONLY"], "1")

    def test_production_smoke_guards_business_write_probes(self):
        smoke = SCRIPT_PATH.with_name("prod-smoke-check.sh").read_text(
            encoding="utf-8",
        )

        self.assertIn("protected_business_write_probes_enabled()", smoke)
        self.assertIn('${SMOKE_BUSINESS_READ_ONLY:-0}', smoke)
        self.assertGreaterEqual(
            smoke.count("if protected_business_write_probes_enabled; then"),
            2,
        )
        self.assertIn(
            "SKIP protected business write probes: read-only mode",
            smoke,
        )

    def test_package_exposes_one_protected_smoke_command(self):
        package = json.loads(
            SCRIPT_PATH.parent.parent.joinpath("package.json").read_text(
                encoding="utf-8",
            )
        )

        self.assertEqual(
            package["scripts"]["smoke:prod:protected"],
            "python3 scripts/run_protected_prod_smoke.py",
        )


if __name__ == "__main__":
    unittest.main()
