import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend/main.py"


class SupplierInvoiceLinkRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(
            MAIN_PATH.read_text(encoding="utf-8"),
            filename=str(MAIN_PATH),
        )
        cls.function = next(
            node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_supplier_invoice"
        )
        cls.route_source = ast.unparse(cls.function)
        cls.worker = next(node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_update_supplier_invoice_in_transaction")
        cls.source = ast.unparse(cls.worker)

    def test_route_passes_exact_context_and_uses_worker_result(self):
        self.assertIn("_update_supplier_invoice_in_transaction(cur, id, data, x_company_id, x_company_mode, _current_user)", self.route_source)
        self.assertIn("result = _update_supplier_invoice_in_transaction", self.route_source)
        self.assertIn("actor=_current_user", self.source)
        self.assertIn("companyId=supplier_company_id", self.source)
        self.assertIn("linkChanged=link_changed", self.source)
        self.assertIn("result.get('linkChanged')", self.route_source)

    def test_link_mutation_resolves_the_selected_company_actor(self):
        argument_names = {
            argument.arg for argument in self.function.args.args
        }
        self.assertIn("x_company_id", argument_names)
        self.assertIn("x_company_mode", argument_names)
        self.assertIn("resolve_resource_company_actor", self.source)
        self.assertIn("allowed_roles=FINANCE_ROLES", self.source)

    def test_link_mutation_rejects_cross_company_document_pairs(self):
        self.assertIn(
            "Складская накладная относится к другой компании",
            self.source,
        )

    def test_automatic_repair_revalidates_the_exact_document_pair(self):
        self.assertIn("accountingExceptionRepair", self.source)
        self.assertIn(
            "Документы не прошли безопасную автоматическую сверку",
            self.source,
        )
        self.assertIn(
            "Текущая связь существует и требует ручной проверки",
            self.source,
        )

    def test_changed_link_is_written_to_the_audit_log(self):
        self.assertIn(
            "accounting_supplier_warehouse_link_repaired",
            self.route_source,
        )
        self.assertIn("company_id=result['companyId']", self.route_source)


if __name__ == "__main__":
    unittest.main()
