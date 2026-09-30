import ast
import unittest
from pathlib import Path


MAIN_PATH = Path(__file__).parents[2] / "main.py"

EXPECTED = {
    "_enhance_norm_suggestions_with_ai": ("material_norm_suggestion", 3000),
    "ai_suggest_material_inspection": ("material_inspection_suggestion", 1500),
    "ai_suggest_cable_journal": ("cable_journal_suggestion", 1500),
    "ai_generate_tb_instruction": ("tb_instruction", 2000),
    "ai_generate_estimate": ("estimate_generation", 6000),
    "ai_generate_pricelist": ("pricelist_generation", 5000),
    "ai_prefill_hidden_works_act": ("hidden_works_act_prefill", 2000),
}


class MainRuntimeGatewayCutoverTest(unittest.TestCase):
    def test_business_callers_use_fixed_gateway_capabilities_and_limits(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        functions = {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in EXPECTED
        }
        self.assertEqual(set(functions), set(EXPECTED))
        for name, (capability, max_tokens) in EXPECTED.items():
            with self.subTest(name=name):
                source = functions[name]
                self.assertIn("generate_yandex_text", source)
                self.assertIn(f"capability='{capability}'", source)
                self.assertIn(f"max_output_tokens={max_tokens}", source)
                self.assertNotIn("OpenAI", source)
                self.assertNotIn("responses.create", source)
                self.assertNotIn("gpt://", source)


if __name__ == "__main__":
    unittest.main()
