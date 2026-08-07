import ast
import unittest
from pathlib import Path


class MaterialControlSupplyTransactionContractTests(unittest.TestCase):
    def test_lineage_lock_and_insert_run_with_autocommit_disabled(self):
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_supply_request"
        )
        assignments = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "conn"
                and target.attr == "autocommit"
                for target in node.targets
            )
        ]
        self.assertTrue(
            any(
                isinstance(node.value, ast.Constant)
                and node.value.value is False
                for node in assignments
            ),
            "material-control lineage locks require conn.autocommit=False",
        )
        sql_literals = " ".join(
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
        self.assertIn("pg_advisory_xact_lock", sql_literals)
        self.assertIn("INSERT INTO supply_requests", sql_literals)


if __name__ == "__main__":
    unittest.main()
