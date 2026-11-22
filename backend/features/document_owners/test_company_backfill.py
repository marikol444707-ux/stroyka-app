import ast
import importlib.util
import unittest
from pathlib import Path

from backend.features.document_owners.company_backfill import (
    ADD_COLUMNS_SQL,
    plan_document_owners,
)

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations" / "versions" / "0124_document_record_owners.py"


def companies(*ids):
    return [{"id": company_id} for company_id in ids]


def project(project_id, company_id, name):
    return {"id": project_id, "company_id": company_id, "name": name}


def document(row_id, name, company_id=None, project_id=None):
    return {
        "id": row_id,
        "company_id": company_id,
        "project_id": project_id,
        "project_name": name,
    }


class DocumentOwnerPlanTests(unittest.TestCase):
    def test_blank_document_uses_the_only_project_of_the_original_company(self):
        plan = plan_document_owners(
            companies(7, 9),
            [project(4, 7, "Лицей")],
            {"project_documents": [document(1, None)], "project_letters": []},
            [],
        )
        self.assertEqual(plan["legacyCompanyId"], 7)
        self.assertEqual(plan["assignments"], [{
            "table": "project_documents",
            "id": 1,
            "company_id": 7,
            "project_id": 4,
            "state": "assign",
        }])

    def test_exact_project_name_assigns_that_project_company(self):
        plan = plan_document_owners(
            companies(7, 8),
            [project(4, 7, "Лицей"), project(5, 8, "Склад")],
            {"project_documents": [document(2, "Склад")], "project_letters": [document(3, "Лицей")]},
            [],
        )
        self.assertIsNone(plan["legacyCompanyId"])
        assigned = {(item["table"], item["id"]): (item["company_id"], item["project_id"])
                    for item in plan["assignments"]}
        self.assertEqual(assigned[("project_documents", 2)], (8, 5))
        self.assertEqual(assigned[("project_letters", 3)], (7, 4))

    def test_shared_name_and_unowned_namesake_stay_blank(self):
        shared = plan_document_owners(
            companies(7, 8),
            [project(4, 7, "Лицей"), project(5, 8, "Лицей")],
            {"project_documents": [document(1, "Лицей")], "project_letters": []},
            [],
        )
        self.assertEqual(shared["assignments"], [])
        self.assertEqual(shared["counts"]["project_documents"]["ambiguous"], 1)

        unowned = plan_document_owners(
            companies(7, 8),
            [project(4, 7, "Лицей"), project(5, None, "Лицей")],
            {"project_documents": [document(1, "Лицей")], "project_letters": []},
            [],
        )
        self.assertEqual(unowned["assignments"], [])
        self.assertEqual(unowned["counts"]["project_documents"]["ambiguous"], 1)

    def test_named_document_is_not_attached_to_a_different_only_project(self):
        plan = plan_document_owners(
            companies(7),
            [project(4, 7, "Лицей")],
            {"project_documents": [document(1, "Склад")], "project_letters": []},
            [],
        )
        self.assertEqual(plan["assignments"], [])
        self.assertEqual(plan["counts"]["project_documents"]["unknown"], 1)

    def test_existing_company_is_kept_and_versions_follow_the_act(self):
        plan = plan_document_owners(
            companies(7, 8),
            [project(4, 7, "Лицей"), project(5, 8, "Склад")],
            {"project_documents": [document(9, "Склад", company_id=7, project_id=4)], "project_letters": []},
            [
                {"id": 1, "company_id": None, "parent_company_id": 8},
                {"id": 2, "company_id": 7, "parent_company_id": 8},
                {"id": 3, "company_id": None, "parent_company_id": None},
            ],
        )
        self.assertEqual(plan["assignments"], [{
            "table": "document_versions",
            "id": 1,
            "company_id": 8,
            "state": "inherited",
        }])
        self.assertEqual(plan["counts"]["project_documents"]["alreadyOwned"], 1)
        self.assertEqual(plan["counts"]["document_versions"]["alreadyOwned"], 1)
        self.assertEqual(plan["counts"]["document_versions"]["unknown"], 1)

    def test_several_projects_in_the_original_company_do_not_pick_a_blank_name(self):
        plan = plan_document_owners(
            companies(7, 9),
            [project(4, 7, "Лицей"), project(5, 7, "Склад")],
            {"project_documents": [document(1, None)], "project_letters": []},
            [],
        )
        self.assertEqual(plan["legacyCompanyId"], 7)
        self.assertEqual(plan["assignments"], [])

    def test_migration_is_the_single_head_and_does_not_use_a_person_name(self):
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('revision = "0124_document_record_owners"', source)
        self.assertIn('down_revision = "0123_explicit_company_owner"', source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)
        self.assertNotIn("FROM users", source)
        self.assertNotIn("DEFAULT 1", ADD_COLUMNS_SQL)
        tree = ast.parse(source)
        downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        self.assertIsInstance(downgrade.body[0], ast.Raise)
        spec = importlib.util.spec_from_file_location("document_record_owners", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0124_document_record_owners")
        self.assertLessEqual(len(module.revision), 32)
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        graph = ScriptDirectory.from_config(config)
        self.assertEqual(graph.get_heads(), ["0124_document_record_owners"])


if __name__ == "__main__":
    unittest.main()
