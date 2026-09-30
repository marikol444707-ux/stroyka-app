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
    def test_invoice_scan_and_its_retries_use_gateway_only(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        functions = {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "_repair_invoice_scan_json",
                "_retry_invoice_scan_compact_json",
                "scan_invoice",
            }
        }

        self.assertEqual(len(functions), 3)
        self.assertIn("generate_yandex_text", functions["_repair_invoice_scan_json"])
        self.assertIn("generate_yandex_parts", functions["_retry_invoice_scan_compact_json"])
        self.assertIn("generate_yandex_parts", functions["scan_invoice"])
        for source in functions.values():
            self.assertIn("capability='invoice_scan'", source)
            self.assertNotIn("OpenAI", source)
            self.assertNotIn("responses.create", source)
            self.assertNotIn("gpt://", source)

    def test_invoice_pdf_and_images_are_carried_as_provider_neutral_parts(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        source = ast.unparse(next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_invoice_scan_ai_content"
        ))

        self.assertIn("kind='file_data_url'", source)
        self.assertIn("kind='image_data_url'", source)
        self.assertNotIn("files.create", source)
        self.assertNotIn("files.delete", source)

    def test_director_agent_serializes_its_read_only_conversation_for_gateway(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        source = ast.unparse(next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_director_agent_call_yandex"
        ))

        self.assertIn("generate_yandex_text", source)
        self.assertIn("capability='director_agent'", source)
        self.assertIn("max_output_tokens=max_tokens", source)
        self.assertIn("role", source)
        self.assertNotIn("urlopen", source)
        self.assertNotIn("Api-Key", source)
        self.assertNotIn("gpt://", source)

    def test_ai_chat_uses_explicit_gateway_routes_for_text_and_json(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        source = ast.unparse(next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "ai_chat"
        ))

        self.assertIn("generate_yandex_text", source)
        self.assertIn("'ai_chat_json' if json_only else 'ai_chat'", source)
        self.assertIn("max_output_tokens=primary_tokens", source)
        self.assertNotIn("OpenAI", source)
        self.assertNotIn("responses.create", source)
        self.assertNotIn("gpt://", source)

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
