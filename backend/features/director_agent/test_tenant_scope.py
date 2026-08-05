import ast
import unittest
from pathlib import Path

from backend.features.director_agent.read_tools import (
    build_director_agent_tools,
    execute_director_agent_read_query,
)


MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.sessions = []
        self.cursor_value = FakeCursor()
        self.closed = False

    def set_session(self, **kwargs):
        self.sessions.append(kwargs)

    def cursor(self, **kwargs):
        return self.cursor_value

    def close(self):
        self.closed = True


class DirectorAgentTenantScopeTests(unittest.TestCase):
    def test_http_query_connection_is_forced_read_only(self):
        connection = FakeConnection()

        rows = execute_director_agent_read_query(
            "SELECT id FROM projects WHERE company_id=%s",
            (7,),
            connection_factory=lambda: connection,
        )

        self.assertEqual(rows, [])
        self.assertEqual(connection.sessions, [{"readonly": True, "autocommit": True}])
        self.assertEqual(connection.cursor_value.params, (7,))
        self.assertTrue(connection.closed)

    def test_every_tool_constrains_queries_by_company(self):
        calls = []
        tools = build_director_agent_tools(
            lambda sql, params=(): calls.append((" ".join(sql.split()), params)) or []
        )

        for name, metadata in tools.items():
            with self.subTest(tool=name):
                before = len(calls)
                metadata["fn"]({}, [9, "4", 9, None, -1])
                tool_calls = calls[before:]
                self.assertTrue(tool_calls)
                for sql, params in tool_calls:
                    self.assertTrue(sql.upper().startswith("SELECT"))
                    self.assertIn("company_id", sql.lower())
                    self.assertTrue(any(value == [4, 9] for value in params))

    def test_route_passes_company_scope_to_shared_tools(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        route = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "director_agent_ask"
        )
        scoped_calls = [
            node
            for node in ast.walk(route)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Subscript)
            and isinstance(node.func.value, ast.Subscript)
            and any(
                isinstance(arg, ast.Name) and arg.id == "request_company_ids"
                for arg in node.args
            )
        ]

        self.assertEqual(len(scoped_calls), 1)


if __name__ == "__main__":
    unittest.main()
