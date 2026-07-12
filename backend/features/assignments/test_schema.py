import unittest

from backend.features.assignments.schema import ensure_assignments_schema


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql):
        self.calls.append(" ".join(sql.split()))

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class AssignmentSchemaTests(unittest.TestCase):
    def test_fresh_child_tables_include_complete_owner_shape(self):
        connection = FakeConnection()

        ensure_assignments_schema(lambda: connection)

        schema_sql = "\n".join(connection.cursor_value.calls)
        self.assertIn("CREATE TABLE IF NOT EXISTS ai_task_reports", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS ai_task_attachments", schema_sql)
        self.assertEqual(schema_sql.count("owner_scope TEXT"), 2)
        self.assertEqual(schema_sql.count("company_id INT"), 2)
        self.assertEqual(schema_sql.count("project_id INT"), 2)
        self.assertEqual(
            schema_sql.count("owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL"),
            2,
        )
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
