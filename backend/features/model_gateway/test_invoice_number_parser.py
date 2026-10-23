import ast
import re
import unittest
from pathlib import Path


MAIN_PATH = Path(__file__).parents[2] / "main.py"


def load_invoice_number_parser():
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_invoice_number_value"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {"re": re}
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace[function.name]


class InvoiceNumberParserTest(unittest.TestCase):
    def test_parses_decimal_and_grouping_conventions(self):
        parse = load_invoice_number_parser()
        examples = {
            "263.50": 263.5,
            "263,50": 263.5,
            "1.263,50": 1263.5,
            "1,263.50": 1263.5,
            "1.234": 1.234,
            "1,234": 1.234,
            "3.600.000": 3600000.0,
            "1,234,567": 1234567.0,
            "1.234.567,89": 1234567.89,
            "12 345.67 ₽": 12345.67,
        }

        for value, expected in examples.items():
            with self.subTest(value=value):
                self.assertEqual(parse(value), expected)


if __name__ == "__main__":
    unittest.main()
