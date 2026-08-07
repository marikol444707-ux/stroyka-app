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


class BudgetWriterInventoryTests(unittest.TestCase):
    def test_exact_existing_manual_writer_surface_is_ready(self):
        report = audit_writer_inventory(
            source_files={
                "backend/features/projects/routes.py": PROJECT_ROUTES,
                "backend/features/crm/routes.py": CRM_ROUTES,
                "backend/features/project_budget_adjustments/audit.py": (
                    "def audit(cur):\n    cur.execute('SELECT budget FROM projects')\n"
                ),
            },
            enforce_complete_inventory=True,
        )

        self.assertTrue(report["writerInventoryReady"])
        self.assertEqual(report["projectBudgetWriters"], 3)
        self.assertEqual(report["expectedProjectBudgetWriters"], 3)
        self.assertEqual(report["e6DmlStatements"], 0)
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

    def test_any_e6_dml_is_rejected_during_baseline_phase(self):
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
            "e6_baseline_dml_present",
            {item["reasonCode"] for item in report["violations"]},
        )

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
        self.assertEqual(report["projectBudgetWriters"], 3)
        self.assertEqual(report["e6DmlStatements"], 0)


if __name__ == "__main__":
    unittest.main()
