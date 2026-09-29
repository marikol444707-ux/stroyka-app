import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("smoke-supply-request-workflow.py")
SPEC = importlib.util.spec_from_file_location("smoke_supply_request_workflow", SCRIPT)
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((" ".join(str(query).split()), params))

    def fetchone(self):
        return self.rows.pop(0)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.cursor_value = FakeCursor(rows)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class SupplyWorkflowSmokeTest(unittest.TestCase):
    def test_target_selection_accepts_project_with_existing_reviewer(self):
        connection = FakeConnection([{
            "project_id": 1,
            "company_id": 2,
            "project_name": "Object",
            "platform_account_id": 3,
        }])
        with patch.object(WORKFLOW, "db_conn", return_value=connection):
            selected = WORKFLOW.select_target_project()

        self.assertEqual(selected["project_id"], 1)
        query = connection.cursor_value.queries[0][0]
        self.assertNotIn("user_company_roles", query)
        self.assertTrue(connection.closed)

    def test_cleanup_removes_company_link_before_supplier(self):
        connection = FakeConnection([(0,), (0,), (0,)])
        with patch.object(WORKFLOW, "db_conn", return_value=connection):
            WORKFLOW.cleanup({
                "request_ids": [10],
                "supplier_ids": [20],
                "user_ids": [30],
            })

        statements = [query for query, _params in connection.cursor_value.queries]
        link_delete = next(i for i, query in enumerate(statements)
                           if query.startswith("DELETE FROM company_supplier_links"))
        supplier_delete = next(i for i, query in enumerate(statements)
                               if query.startswith("DELETE FROM suppliers"))
        self.assertLess(link_delete, supplier_delete)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
