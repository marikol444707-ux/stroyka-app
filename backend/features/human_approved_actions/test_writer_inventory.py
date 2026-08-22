import tempfile
import unittest
from pathlib import Path

from backend.features.human_approved_actions.writer_inventory import (
    ACTION_SOURCE_SURFACES,
    INVENTORY_VERSION,
    PROTECTED_WRITER_MODULES,
    PROTECTED_WRITER_SURFACES,
    audit_human_approved_action_inventory,
)


ROOT = Path(__file__).resolve().parents[3]


class HumanApprovedActionWriterInventoryTests(unittest.TestCase):
    def test_a12_release_package_and_real_postgres_proof_are_explicit(self):
        release_files = {
            "migration": ROOT / "docs/human-approved-actions-migration-runbook.md",
            "canary": ROOT / "docs/human-approved-actions-canary.md",
            "nginx": ROOT / "ops-nginx-human-approved-actions.conf",
        }
        for label, path in release_files.items():
            with self.subTest(artifact=label):
                self.assertTrue(path.is_file(), str(path))

        migration = release_files["migration"].read_text(encoding="utf-8")
        for marker in (
            "6d570c93eb504ade2a97f88ed1d12c0ea807d218049bf0db8dcf986cc2d34951",
            "expected_change_count=12",
            "HUMAN_ACTION_SCHEMA_CONFIRMATION",
            "separate explicit approval",
            "human_action_proposals",
            "human_action_events",
        ):
            self.assertIn(marker, migration)

        canary = release_files["canary"].read_text(encoding="utf-8")
        for marker in (
            "HUMAN_APPROVED_ACTIONS_HTTP_ENABLED=true",
            "REACT_APP_HUMAN_APPROVED_ACTIONS_ENABLED=true",
            "one canonical positive integer",
            "Do not manufacture",
            "disable the backend flag first",
            "no business correction",
        ):
            self.assertIn(marker, canary)

        nginx = release_files["nginx"].read_text(encoding="utf-8")
        self.assertEqual(
            nginx.count("location = /human-approved-actions/proposals"), 1,
        )
        self.assertEqual(
            nginx.count("location = /human-approved-actions/decisions"), 1,
        )
        self.assertEqual(
            nginx.count("location = /human-approved-actions/history"), 1,
        )
        self.assertIn("proxy_pass http://127.0.0.1:8001;", nginx)
        self.assertNotIn("proxy_pass http://0.0.0.0", nginx)
        self.assertEqual(
            nginx.count("error_page 429 = @human_action_429;"), 3,
        )
        self.assertEqual(nginx.count("client_max_body_size 4k;"), 2)
        self.assertEqual(nginx.count("location @human_action_429"), 1)
        self.assertIn(
            'add_header Cache-Control "no-store, max-age=0" always;',
            nginx,
        )
        self.assertIn(
            "{\"detail\":\"human_action_review_busy\"}",
            nginx,
        )

        postgres_proof = (
            ROOT
            / "backend/features/estimate_revision_impact/"
            "test_resource_limits_postgres.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "_prove_human_action_kernel_lifecycle",
            "human_action_kernel_source_stale",
            "concurrent_decisions",
            "protected_before",
            "protected_after",
        ):
            self.assertIn(marker, postgres_proof)

    def test_current_a12_registry_and_default_off_routes_are_exact(self):
        result = audit_human_approved_action_inventory(ROOT)

        self.assertEqual(result, {
            "inventoryVersion": INVENTORY_VERSION,
            "ok": True,
            "actionKinds": ["warehouse_anomaly_review_acknowledged"],
            "effectKinds": ["audit_only"],
            "productionFiles": [
                "backend/features/human_approved_actions/__init__.py",
                "backend/features/human_approved_actions/action_kernel.py",
                "backend/features/human_approved_actions/contract.py",
                "backend/features/human_approved_actions/runtime_routes.py",
                "backend/features/human_approved_actions/schema_contract.py",
                "backend/features/human_approved_actions/writer_inventory.py",
            ],
            "migrationFiles": [
                "backend/features/human_approved_actions/schema_contract.py",
            ],
            "kernelFiles": [
                "backend/features/human_approved_actions/action_kernel.py",
            ],
            "kernelWriteTargets": [
                "audit_log",
                "human_action_events",
                "human_action_proposals",
            ],
            "actionSourceSurfaces": [
                {
                    "module": module,
                    "callable": callable_name,
                }
                for module, callable_name in ACTION_SOURCE_SURFACES
            ],
            "protectedWriterSurfaces": [
                {
                    "module": module,
                    "callable": callable_name,
                }
                for module, callable_name in PROTECTED_WRITER_SURFACES
            ],
            "protectedWriterModules": list(PROTECTED_WRITER_MODULES),
            "runtimeRegistrations": [
                {
                    "module": (
                        "backend/features/human_approved_actions/"
                        "runtime_routes.py"
                    ),
                    "kind": "registration_function",
                    "callable": "register_human_approved_action_routes",
                },
                {
                    "module": (
                        "backend/features/human_approved_actions/"
                        "runtime_routes.py"
                    ),
                    "kind": "route",
                    "method": "GET",
                    "path": "/human-approved-actions/history",
                },
                {
                    "module": (
                        "backend/features/human_approved_actions/"
                        "runtime_routes.py"
                    ),
                    "kind": "route",
                    "method": "POST",
                    "path": "/human-approved-actions/decisions",
                },
                {
                    "module": (
                        "backend/features/human_approved_actions/"
                        "runtime_routes.py"
                    ),
                    "kind": "route",
                    "method": "POST",
                    "path": "/human-approved-actions/proposals",
                },
            ],
            "forbiddenImports": [],
            "databaseCalls": [],
            "violations": [],
        })

    def test_inventory_covers_the_preview_and_existing_write_precedents(self):
        self.assertEqual(ACTION_SOURCE_SURFACES, (
            (
                "backend/features/warehouse_recommendation_preview/"
                "content_preview.py",
                "run_warehouse_anomaly_content_preview",
            ),
        ))
        self.assertEqual(PROTECTED_WRITER_SURFACES, (
            (
                "backend/features/accounting_exception_checks/"
                "ownership_remediation_runner.py",
                "run_accounting_ownership_remediation",
            ),
            (
                "backend/features/project_budget_adjustments/approval.py",
                "apply_budget_adjustment",
            ),
            (
                "backend/features/supply_recommendation_preview/"
                "material_capability_writer.py",
                "run_material_capability_confirmation_write",
            ),
            (
                "backend/features/supply_recommendation_preview/"
                "material_capability_writer.py",
                "run_material_capability_revocation_write",
            ),
        ))
        self.assertEqual(PROTECTED_WRITER_MODULES, (
            "backend/features/accountable_payments/routes.py",
            "backend/features/contracts/routes.py",
            "backend/features/estimate_changes/routes.py",
            "backend/features/estimate_reconciliations/routes.py",
            "backend/features/estimate_row_transfer/routes.py",
            "backend/features/estimate_versions/routes.py",
            "backend/features/expense_reports/routes.py",
            "backend/features/expenses/routes.py",
            "backend/features/interim_acts/routes.py",
            "backend/features/material_aliases/routes.py",
            "backend/features/material_packaging/routes.py",
            "backend/features/material_traceability/receipt_lots.py",
            "backend/features/materials/routes.py",
            "backend/features/own_expenses/routes.py",
            "backend/features/project_budget_adjustments/approval.py",
            "backend/features/salary_payments/routes.py",
            "backend/features/supply_history/routes.py",
            "backend/features/supply_recommendation_preview/"
            "material_capability_writer.py",
            "backend/features/supervisor_acts/routes.py",
        ))

    def test_static_audit_fails_closed_for_import_call_route_and_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (
                *[module for module, _name in ACTION_SOURCE_SURFACES],
                *[module for module, _name in PROTECTED_WRITER_SURFACES],
                *PROTECTED_WRITER_MODULES,
                "backend/features/human_approved_actions/__init__.py",
                "backend/features/human_approved_actions/action_kernel.py",
                "backend/features/human_approved_actions/contract.py",
                "backend/features/human_approved_actions/schema_contract.py",
                "backend/features/human_approved_actions/writer_inventory.py",
                "backend/features/human_approved_actions/runtime_routes.py",
                "backend/main.py",
            ):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n", encoding="utf-8")

            for module, callable_name in (
                *ACTION_SOURCE_SURFACES,
                *PROTECTED_WRITER_SURFACES,
            ):
                target = root / module
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(f"def {callable_name}():\n    pass\n")

            (root / "backend/features/human_approved_actions/contract.py").write_text(
                "import psycopg2\n"
                "def apply_anything(cur):\n"
                "    cur.execute('DELETE FROM public.materials')\n",
                encoding="utf-8",
            )
            (root / "backend/features/human_approved_actions/action_kernel.py").write_text(
                "import psycopg2\n"
                "def write(cur):\n"
                "    cur.execute('UPDATE public.materials SET name=name')\n",
                encoding="utf-8",
            )
            (root / "backend/features/human_approved_actions/runtime_routes.py").write_text(
                "import backend.db\n"
                "def register_human_approved_action_routes(app):\n"
                "    @app.post('/human-actions')\n"
                "    def create(cur):\n"
                "        cur.execute('SELECT 1')\n"
                "        return None\n",
                encoding="utf-8",
            )
            (root / "backend/main.py").write_text(
                "from backend.features import human_approved_actions\n",
                encoding="utf-8",
            )

            result = audit_human_approved_action_inventory(root)

        self.assertFalse(result["ok"])
        self.assertIn("psycopg2", result["forbiddenImports"])
        self.assertTrue(any(
            item["attribute"] == "execute"
            for item in result["databaseCalls"]
        ))
        self.assertTrue(result["runtimeRegistrations"])
        reasons = {item["reasonCode"] for item in result["violations"]}
        self.assertIn("forbidden_sql_text", reasons)
        self.assertIn("main_registration_missing", reasons)
        self.assertIn("runtime_registration_mismatch", reasons)
        self.assertIn("route_import_not_allowlisted", reasons)
        self.assertIn("route_sql_present", reasons)

    def test_missing_or_renamed_reviewed_surface_fails_the_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (
                "backend/features/human_approved_actions/__init__.py",
                "backend/features/human_approved_actions/contract.py",
                "backend/features/human_approved_actions/schema_contract.py",
                "backend/features/human_approved_actions/writer_inventory.py",
                "backend/main.py",
            ):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n", encoding="utf-8")

            result = audit_human_approved_action_inventory(root)

        self.assertFalse(result["ok"])
        self.assertTrue(result["violations"])
        self.assertTrue(all(
            set(item) <= {"reasonCode", "module", "callable", "detail"}
            for item in result["violations"]
        ))
        self.assertNotIn(str(root), repr(result))


if __name__ == "__main__":
    unittest.main()
