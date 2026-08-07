import unittest

from backend.features.project_budget_adjustments.writer_inventory import (
    audit_writer_inventory,
)


PROJECT_ROUTES = """
def create_project(cur):
    cur.execute('INSERT INTO projects (company_id,name,budget) VALUES (%s,%s,%s)')

def update_project(cur, data):
    fields_map = [('name', 'name'), ('budget', 'budget')]
    sets = [db_col + '=%s' for js_key, db_col in fields_map if js_key in data]
    cur.execute('UPDATE projects SET ' + ','.join(sets) + ' WHERE id=%s')
"""

CRM_ROUTES = """
def crm_create_project_from_lead(cur):
    cur.execute('INSERT INTO projects (company_id,name,budget) VALUES (%s,%s,%s)')
"""

APPROVAL_STORAGE = """
def insert_budget_adjustment_receipt(cur):
    cur.execute('INSERT INTO project_budget_adjustments (project_id) VALUES (%s)')

def update_project_budget(cur):
    cur.execute('UPDATE projects SET budget=%s WHERE id=%s AND company_id=%s AND budget=%s')
"""


class BudgetWriterInventoryTests(unittest.TestCase):
    def test_exact_existing_manual_writer_surface_is_ready(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
                "backend/features/crm/routes.py": CRM_ROUTES,
                "backend/features/project_budget_adjustments/audit.py": (
                    "def audit(cur):\n    cur.execute('SELECT budget FROM projects')\n"
                ),
                "backend/features/project_budget_adjustments/approval_storage.py": (
                    APPROVAL_STORAGE
                ),
            },
            enforce_complete_inventory=True,
        )

        self.assertTrue(report["writerInventoryReady"])
        self.assertEqual(report["projectBudgetWriters"], 4)
        self.assertEqual(report["expectedProjectBudgetWriters"], 4)
        self.assertEqual(report["e6DmlStatements"], 2)
        self.assertEqual(report["expectedE6DmlStatements"], 2)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["writesAttempted"], 0)

    def test_unreviewed_direct_budget_update_is_rejected(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
                "backend/features/crm/routes.py": CRM_ROUTES,
                "backend/features/other/routes.py": """
def surprise(cur):
    cur.execute('UPDATE projects SET budget=%s WHERE id=%s')
""",
            },
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertIn(
            "project_budget_writer_not_allowlisted",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_split_static_budget_update_cannot_evade_inventory(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
                "backend/features/crm/routes.py": CRM_ROUTES,
                "backend/features/other/routes.py": """
def surprise(cur):
    sql = 'UPDATE projects SET ' + 'budget=%s WHERE id=%s'
    cur.execute(sql)
""",
            },
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertIn(
            "project_budget_writer_not_allowlisted",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_missing_existing_writer_fails_exact_inventory(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
            },
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertIn(
            "project_budget_writer_inventory_mismatch",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_any_unreviewed_e6_dml_is_rejected(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
                "backend/features/crm/routes.py": CRM_ROUTES,
                "backend/features/project_budget_adjustments/storage.py": """
def write(cur):
    cur.execute('INSERT INTO project_budget_adjustments (project_id) VALUES (%s)')
""",
            },
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertEqual(report["e6DmlStatements"], 1)
        self.assertIn(
            "e6_runtime_dml_not_allowlisted",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_schema_trigger_update_or_delete_clause_is_not_runtime_dml(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
                "backend/features/crm/routes.py": CRM_ROUTES,
                "backend/features/project_budget_adjustments/schema.py": """
TRIGGER_SQL = '''
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE
ON public.project_budget_adjustments FOR EACH ROW EXECUTE FUNCTION guard()
'''
""",
                "backend/features/project_budget_adjustments/approval_storage.py": (
                    APPROVAL_STORAGE
                ),
            },
            enforce_complete_inventory=True,
        )

        self.assertTrue(report["writerInventoryReady"], report["violations"])
        self.assertEqual(report["e6DmlStatements"], 2)

    def test_parse_failure_is_a_blocker(self):
        report = audit_writer_inventory(
            source_files={"backend/broken.py": "def broken(:\n"},
            enforce_complete_inventory=False,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertEqual(report["violations"], [{
            "reasonCode": "source_parse_error",
            "file": "backend/broken.py",
        }])

    def test_real_repository_has_only_the_reviewed_baseline_writers(self):
        report = audit_writer_inventory()

        self.assertTrue(report["writerInventoryReady"], report["violations"])
        self.assertEqual(report["projectBudgetWriters"], 4)
        self.assertEqual(report["e6DmlStatements"], 2)
        self.assertEqual(report["expectedE6DmlStatements"], 2)


if __name__ == "__main__":
    unittest.main()
