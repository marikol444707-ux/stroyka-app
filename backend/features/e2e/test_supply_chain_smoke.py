import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SMOKE_PATH = ROOT / "scripts" / "smoke-supply-chain.py"


class SupplyChainSmokeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SMOKE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(SMOKE_PATH))
        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def function_source(self, name):
        node = self.functions[name]
        return ast.get_source_segment(self.source, node) or ""

    def test_main_wires_real_business_chain_in_order(self):
        main_source = self.function_source("main")
        steps = [
            "select_working_candidate(",
            "create_and_select_offer(",
            "create_supplier_invoice_for_offer(",
            "ship_and_receive(",
            "assert_supply_company_lineage(",
            "record_payment_for_received_invoice(",
        ]
        positions = [main_source.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))

    def test_payment_step_uses_selected_company_and_real_project_payment(self):
        payment_source = self.function_source("record_payment_for_received_invoice")
        self.assertIn('"X-Company-Mode": "company"', payment_source)
        self.assertIn('"X-Company-Id": str(expected_company_id)', payment_source)
        self.assertIn('"paymentAmount": payment_amount', payment_source)
        self.assertIn("FROM project_payments", payment_source)
        self.assertIn('payment.get("company_id")', payment_source)

    def test_smoke_cleans_up_created_payment(self):
        cleanup_source = self.function_source("cleanup")
        self.assertIn("DELETE FROM project_payments WHERE id=%s", cleanup_source)
        self.assertIn('ids["paymentId"]', cleanup_source)


if __name__ == "__main__":
    unittest.main()
