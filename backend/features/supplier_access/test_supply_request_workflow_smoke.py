import ast
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "smoke-supply-request-workflow.py"
)
SPEC = importlib.util.spec_from_file_location(
    "supply_request_workflow_smoke",
    SCRIPT_PATH,
)
SMOKE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(SMOKE)


class SupplyRequestWorkflowSmokeHelperTests(unittest.TestCase):
    def test_exact_confirmation_is_required(self):
        SMOKE.validate_confirmation(
            SMOKE.CONFIRMATION_PHRASE
        )
        for value in ("", "YES", "run supply workflow smoke"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SMOKE.validate_confirmation(value)

    def test_totp_matches_rfc_sha1_vector(self):
        self.assertEqual(
            SMOKE.totp_code(
                "GEZDGNBVGY3TQOJQ"
                "GEZDGNBVGY3TQOJQ",
                timestamp=59,
            ),
            "287082",
        )

    def test_login_accepts_direct_auth_token(self):
        with mock.patch.object(
            SMOKE,
            "api_json",
            return_value=(
                200,
                {"authToken": "direct-token"},
            ),
        ) as api_json:
            token = SMOKE.login(
                "https://example.test",
                "worker@example.test",
                "password",
            )

        self.assertEqual(token, "direct-token")
        api_json.assert_called_once()

    def test_login_completes_initial_2fa_setup(self):
        with (
            mock.patch.object(
                SMOKE,
                "api_json",
                side_effect=[
                    (
                        200,
                        {
                            "twoFactorSetupRequired": True,
                            "setupToken": "setup-token",
                            "manualKey": "secret-key",
                        },
                    ),
                    (
                        200,
                        {"authToken": "2fa-token"},
                    ),
                ],
            ) as api_json,
            mock.patch.object(
                SMOKE,
                "totp_code",
                return_value="123456",
            ) as totp,
        ):
            token = SMOKE.login(
                "https://example.test",
                "director@example.test",
                "password",
            )

        self.assertEqual(token, "2fa-token")
        totp.assert_called_once_with("secret-key")

        self.assertEqual(
            api_json.call_args_list[1],
            mock.call(
                "POST",
                "/login/2fa/setup-confirm",
                base_url="https://example.test",
                data={
                    "setupToken": "setup-token",
                    "code": "123456",
                },
                expected=200,
            ),
        )

    def test_cleanup_revokes_sessions_and_clears_2fa(self):
        source = SCRIPT_PATH.read_text(
            encoding="utf-8"
        )

        for token in (
            "UPDATE user_sessions",
            "revoked_at=NOW()",
            "two_factor_secret=NULL",
            "two_factor_enabled=FALSE",
            "two_factor_confirmed_at=NULL",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_runtime_project_names_trim_legacy_whitespace(self):
        main_path = (
            Path(__file__).resolve().parents[2]
            / "main.py"
        )
        source = main_path.read_text(
            encoding="utf-8"
        )
        tree = ast.parse(
            source,
            filename=str(main_path),
        )

        matches = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "user_project_names"
        ]
        self.assertEqual(len(matches), 1)

        module = ast.fix_missing_locations(
            ast.Module(
                body=[matches[0]],
                type_ignores=[],
            )
        )
        namespace = {"json": json}

        exec(
            compile(
                module,
                str(main_path),
                "exec",
            ),
            namespace,
        )

        project_names = namespace[
            "user_project_names"
        ]

        self.assertEqual(
            project_names({
                "projectName":
                    "  Лермонтова школа #1 ",
                "project_name":
                    "Лермонтова школа #1",
                "assignedProjects": [
                    " Лермонтова школа #1 ",
                    "  Объект  ",
                    "",
                    None,
                ],
            }),
            [
                "Лермонтова школа #1",
                "Объект",
            ],
        )

        self.assertEqual(
            project_names({
                "assigned_projects": json.dumps(
                    [
                        "  Объект  ",
                        "Объект",
                    ],
                    ensure_ascii=False,
                ),
            }),
            ["Объект"],
        )

    def test_supplier_safe_view_accepts_public_fields(self):
        SMOKE.assert_supplier_request_safe({
            "id": 10,
            "project": "Объект",
            "status": "КП запрошены",
            "itemsJson": json.dumps([{
                "materialName": "Труба PN20",
                "quantity": 1,
                "unit": "м",
                "characteristics": {"pressureClass": "PN20"},
            }], ensure_ascii=False),
        })

    def test_supplier_safe_view_rejects_internal_fields(self):
        with self.assertRaises(AssertionError):
            SMOKE.assert_supplier_request_safe({
                "id": 10,
                "project": "Объект",
                "status": "КП запрошены",
                "selectedSuppliers": [1],
                "itemsJson": "[]",
            })
        with self.assertRaises(AssertionError):
            SMOKE.assert_supplier_request_safe({
                "id": 10,
                "project": "Объект",
                "status": "КП запрошены",
                "itemsJson": json.dumps([{
                    "materialName": "Труба",
                    "estimateControl": {"plannedSum": 1},
                }]),
            })

    def test_script_contains_both_complete_workflow_paths(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for token in (
            "def run_assigned_reviewer_path",
            "def run_director_fallback_path",
            'action="confirm_prorab"',
            'action="approve_director"',
            "/request-kp",
            "/supplier-offers",
            "assert_supplier_visibility",
            "Unaddressed supplier",
            "SUPPLY_WORKFLOW_E2E_OK",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_reviewer_detection_matches_runtime_sources(self):
        sql = " ".join(SMOKE.reviewer_assignment_sql("p").split())
        self.assertIn("user_company_roles membership", sql)
        self.assertIn("membership.assigned_projects", sql)
        self.assertIn("reviewer.assigned_projects", sql)
        self.assertIn("reviewer.project_id=p.id", sql)
        self.assertIn("COALESCE(reviewer.active,TRUE)=TRUE", sql)
        self.assertIn("COALESCE(membership.active,TRUE)=TRUE", sql)


if __name__ == "__main__":
    unittest.main()
