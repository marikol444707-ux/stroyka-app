import importlib.util
import json
import unittest
from pathlib import Path


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
