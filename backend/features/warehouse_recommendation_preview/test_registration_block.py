"""Pin the warehouse preview registration block, not all of backend/main.py.

Unrelated splits may edit main.py. This check fails when the flag gate or the
registration statements inside it change.
"""

import ast
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = ROOT / "backend" / "main.py"
FLAG_TEST = "os.getenv('WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED') == 'true'"
ALLOWLIST_TEST = "warehouse_anomaly_preview_company_ids is not None"
REGISTER_NAME = "register_warehouse_anomaly_preview_routes"
BLOCK_SHA256 = "8c43da5677aebf1d80eab054bd4194f468a8615559f4cebecd0e7c631666f650"


def warehouse_preview_registration_block(main_path=MAIN_PATH):
    source = Path(main_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(main_path))
    blocks = [
        node for node in tree.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == FLAG_TEST
    ]
    if len(blocks) != 1:
        raise AssertionError(
            f"expected one {FLAG_TEST} gate, found {len(blocks)}"
        )
    block = blocks[0]
    segment = ast.get_source_segment(source, block)
    if segment is None:
        raise AssertionError("warehouse preview registration block has no source")
    digest = hashlib.sha256(segment.encode("utf-8")).hexdigest()
    if digest != BLOCK_SHA256:
        raise AssertionError(
            "warehouse preview registration block changed: " + digest
        )
    nested = [node for node in block.body if isinstance(node, ast.If)]
    if len(nested) != 1 or ast.unparse(nested[0].test) != ALLOWLIST_TEST:
        raise AssertionError("preview routes must stay behind the company allowlist")
    parse_calls = [
        node for node in ast.walk(block)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_parse_warehouse_anomaly_preview_company_ids"
    ]
    register_calls = [
        node for node in ast.walk(block)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == REGISTER_NAME
    ]
    if len(parse_calls) != 1 or len(register_calls) != 1:
        raise AssertionError("preview gate must parse the allowlist and register once")
    if not (parse_calls[0].lineno < nested[0].lineno <= register_calls[0].lineno):
        raise AssertionError("allowlist parse must run before route registration")
    if register_calls[0].lineno < nested[0].lineno or register_calls[0].lineno > nested[0].end_lineno:
        raise AssertionError("route registration must stay inside the allowlist gate")
    return segment


class WarehousePreviewRegistrationBlockTests(unittest.TestCase):
    def test_registration_block_is_pinned(self):
        segment = warehouse_preview_registration_block()
        self.assertIn("register_warehouse_anomaly_preview_routes", segment)
        self.assertIn("WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED", segment)


if __name__ == "__main__":
    unittest.main()
