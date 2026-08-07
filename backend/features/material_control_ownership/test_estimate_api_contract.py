import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path


def _load_estimate_response_mapper():
    main_path = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_estimate_response_payload_from_row"
    )
    namespace = {"_safe_float": lambda value: float(value or 0)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(main_path), "exec"), namespace)
    return namespace[function.name]


def _main_function(name):
    main_path = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _called_names(function):
    return {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


class EstimateApiOwnershipContractTests(unittest.TestCase):
    def test_shared_estimate_response_includes_stored_company_id(self):
        row = (
            101,
            17,
            "Школа",
            "Смета",
            "1.0",
            "[]",
            "Заказчик",
            "Основная",
            False,
            "Активная",
            datetime(2026, 8, 7, tzinfo=timezone.utc),
            3,
            datetime(2026, 8, 7, tzinfo=timezone.utc),
            23,
        )

        payload = _load_estimate_response_mapper()(
            row,
            [],
            sections_loaded=False,
            total_override=0,
        )

        self.assertEqual(payload["companyId"], 23)
        self.assertEqual(payload["projectId"], 17)

    def test_list_summary_and_detail_share_the_owner_aware_mapper(self):
        list_route = _main_function("get_estimates")
        summary_route = _main_function("get_estimates_summary")
        detail_route = _main_function("get_estimate_detail")

        self.assertIn("_estimate_response_payload_from_row", _called_names(list_route))
        self.assertIn("get_estimates", _called_names(summary_route))
        self.assertIn("_estimate_response_payload_from_row", _called_names(detail_route))
        for route in (list_route, detail_route):
            sql_literals = " ".join(
                node.value
                for node in ast.walk(route)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            )
            self.assertIn("e.company_id", sql_literals)


if __name__ == "__main__":
    unittest.main()
