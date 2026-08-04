import ast
import unittest
from pathlib import Path


class EstimatePostCreateBackgroundTest(unittest.TestCase):
    def test_create_estimate_schedules_ai_after_response(self):
        source = Path(__file__).resolve().parents[2].joinpath("main.py").read_text()
        module = ast.parse(source)
        create_estimate = next(
            node for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "create_estimate"
        )
        direct_calls = [
            node for node in ast.walk(create_estimate)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "_run_project_ai_control_safely"
        ]
        scheduled_calls = [
            node for node in ast.walk(create_estimate)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_task"
        ]

        self.assertEqual(direct_calls, [])
        self.assertTrue(scheduled_calls)


if __name__ == "__main__":
    unittest.main()
