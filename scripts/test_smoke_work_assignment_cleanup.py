import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).with_name("smoke-work-assignment.py")
SPEC = importlib.util.spec_from_file_location("smoke_work_assignment", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class WorkAssignmentCleanupTests(unittest.TestCase):
    def test_cleanup_removes_ai_children_before_temporary_project(self):
        connection = FakeConnection()
        with mock.patch.object(MODULE, "db_conn", return_value=connection):
            MODULE.cleanup()

        statements = [sql for sql, _params in connection.fake_cursor.calls]
        attachment_index = next(i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM ai_task_attachments"))
        report_index = next(i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM ai_task_reports"))
        task_index = next(i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM ai_tasks"))
        finding_index = next(i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM ai_findings"))
        project_index = next(i for i, sql in enumerate(statements) if sql.startswith("DELETE FROM projects"))
        self.assertLess(attachment_index, report_index)
        self.assertLess(report_index, task_index)
        self.assertLess(task_index, finding_index)
        self.assertLess(finding_index, project_index)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
