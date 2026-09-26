import ast
import unittest

from fastapi import HTTPException

from backend.features.supplier_access.test_rfq_delivery_runtime import (
    MAIN_PATH,
    RuntimeHarness,
)


class SupplyRequestCompanyContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        cls.nodes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_allowed_membership_context_creates_request(self):
        harness = RuntimeHarness(self.nodes, role="директор")
        harness.company_context.return_value = {"mode": "company", "companyId": 7}

        result = harness.create()

        self.assertIn(result["id"], harness.connection.committed["supply_requests"])

    def test_foreign_company_rejection_from_resolver_is_preserved(self):
        harness = RuntimeHarness(self.nodes, role="директор")
        harness.company_context.side_effect = HTTPException(
            status_code=403,
            detail="Нет доступа к выбранной компании",
        )

        with self.assertRaises(HTTPException) as error:
            harness.create()

        self.assertEqual(403, error.exception.status_code)
        self.assertEqual({}, harness.connection.committed["supply_requests"])

    def test_all_companies_context_cannot_be_used_for_create(self):
        harness = RuntimeHarness(self.nodes, role="директор")
        harness.company_context.return_value = {
            "mode": "all_companies",
            "companyId": None,
            "companies": [{"companyId": 7}],
        }

        with self.assertRaises(HTTPException) as error:
            harness.create()

        self.assertEqual(403, error.exception.status_code)
        self.assertEqual({}, harness.connection.committed["supply_requests"])

    def test_missing_resolved_company_does_not_fallback_to_request_company_id(self):
        harness = RuntimeHarness(self.nodes, role="директор")
        harness.company_context.return_value = {"mode": "company", "companyId": None}

        with self.assertRaises(HTTPException) as error:
            harness.create()

        self.assertEqual(403, error.exception.status_code)
        self.assertEqual({}, harness.connection.committed["supply_requests"])


if __name__ == "__main__":
    unittest.main()
