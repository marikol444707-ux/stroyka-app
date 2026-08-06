import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.features.brigade_lineage.writer_audit import audit_brigade_contract_item_writers


class BrigadeContractItemWriterAuditTests(unittest.TestCase):
    def test_repository_has_only_explicit_source_inserts_and_safe_updates(self):
        repo_root = Path(__file__).resolve().parents[3]

        report = audit_brigade_contract_item_writers(repo_root)

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["insertStatements"], 3)
        self.assertEqual(report["updateStatements"], 3)
        self.assertEqual(report["violations"], [])

    def test_audit_detects_legacy_quantity_sync_and_missing_source_type(self):
        files = {
            "backend/main.py": """
                cur.execute(\"UPDATE brigade_contract_items SET quantity=%s WHERE id=%s\")
                cur.execute(\"INSERT INTO brigade_contract_items (contract_id) VALUES (%s)\")
            """,
        }

        report = audit_brigade_contract_item_writers(source_files=files)

        self.assertFalse(report["ok"])
        self.assertEqual(
            {item["code"] for item in report["violations"]},
            {"insert_writer_not_allowlisted", "insert_source_type_missing", "unsafe_update_column"},
        )

    def test_audit_detects_descriptive_contract_item_lookup(self):
        report = audit_brigade_contract_item_writers(source_files={
            "backend/main.py": """
                sql = \"FROM brigade_contract_items bci WHERE LOWER(TRIM(COALESCE(bci.description,'')))=%s\"
            """,
        })

        self.assertFalse(report["ok"])
        self.assertEqual(report["violations"][0]["code"], "fuzzy_contract_item_lookup")

    def test_repository_inventory_fails_closed_when_expected_writers_are_missing(self):
        with TemporaryDirectory() as temp_dir:
            backend = Path(temp_dir) / "backend"
            backend.mkdir()
            (backend / "main.py").write_text("value = 1\n", encoding="utf-8")

            report = audit_brigade_contract_item_writers(temp_dir)

        self.assertFalse(report["ok"])
        self.assertEqual(
            {item["code"] for item in report["violations"]},
            {"insert_writer_count_mismatch", "update_writer_count_mismatch"},
        )


if __name__ == "__main__":
    unittest.main()
