import ast
import unittest
from pathlib import Path

from backend.features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS
from backend.features.director_agent.read_tools import (
    build_director_agent_tools,
    read_director_agent_tool_results,
    validate_director_agent_read_sql,
)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.sessions = []
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.sessions.append(kwargs)

    def cursor(self, **kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class DirectorAgentReadToolsTests(unittest.TestCase):
    def test_http_director_agent_uses_the_shared_read_tool_registry(self):
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
        assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "DIRECTOR_AGENT_TOOLS"
                for target in node.targets
            )
        ]

        self.assertEqual(len(assignments), 1)
        self.assertIsInstance(assignments[0].value, ast.Name)
        self.assertEqual(assignments[0].value.id, "SHARED_DIRECTOR_AGENT_TOOLS")

    def test_registry_is_immutable_and_matches_the_execution_allowlist(self):
        tools = build_director_agent_tools(lambda sql, params=(): [])

        self.assertEqual(tuple(tools), DIRECTOR_AGENT_READ_TOOLS)
        with self.assertRaises(TypeError):
            tools["sql"] = {"fn": lambda *_: []}
        with self.assertRaises(TypeError):
            tools["projects"]["fn"] = lambda *_: []

    def test_every_tool_fails_closed_without_company_and_scopes_every_query(self):
        calls = []

        def query(sql, params=()):
            calls.append((" ".join(sql.split()), tuple(params)))
            return []

        tools = build_director_agent_tools(query)
        for tool_name in DIRECTOR_AGENT_READ_TOOLS:
            with self.subTest(tool_name=tool_name):
                before = len(calls)
                self.assertIsNotNone(tools[tool_name]["fn"]({}, []))
                self.assertEqual(len(calls), before)

                tools[tool_name]["fn"]({}, [9, "4", 9, None, -1])
                tool_calls = calls[before:]
                self.assertTrue(tool_calls)
                for sql, params in tool_calls:
                    self.assertTrue(sql.upper().startswith("SELECT"))
                    self.assertIn("company_id", sql.lower())
                    self.assertTrue(any(value == [4, 9] for value in params))

    def test_search_is_parameterized_and_cannot_add_a_second_statement(self):
        calls = []
        tools = build_director_agent_tools(
            lambda sql, params=(): calls.append((sql, params)) or []
        )

        tools["projects"]["fn"](
            {"search": "School%'; DELETE FROM projects; --"},
            [7],
        )

        sql, params = calls[0]
        self.assertNotIn("DELETE", sql)
        self.assertIn("DELETE", params[1])
        self.assertEqual(params[0], [7])

    def test_company_read_uses_one_read_only_transaction_and_rolls_it_back(self):
        connection = FakeConnection()

        result = read_director_agent_tool_results(
            company_id=7,
            connection_factory=lambda: connection,
        )

        self.assertEqual(tuple(result), DIRECTOR_AGENT_READ_TOOLS)
        self.assertEqual(connection.sessions, [{"readonly": True, "autocommit": False}])
        self.assertGreater(len(connection.cursor_value.calls), len(DIRECTOR_AGENT_READ_TOOLS))
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)
        for sql, params in connection.cursor_value.calls:
            self.assertTrue(sql.upper().startswith("SELECT"))
            self.assertNotIn(";", sql)
            self.assertTrue(any(value == [7] for value in params))

    def test_company_read_rejects_invalid_owner_before_opening_connection(self):
        calls = []
        for company_id in (None, 0, -1, "all_companies", [7]):
            with self.subTest(company_id=company_id):
                with self.assertRaises(ValueError):
                    read_director_agent_tool_results(
                        company_id=company_id,
                        connection_factory=lambda: calls.append(True),
                    )

        self.assertEqual(calls, [])

    def test_read_sql_validator_accepts_one_select_only(self):
        self.assertEqual(
            validate_director_agent_read_sql(" SELECT id FROM projects "),
            "SELECT id FROM projects",
        )
        for sql in (
            "DELETE FROM projects",
            "SELECT id FROM projects; DELETE FROM projects",
            "WITH changed AS (DELETE FROM projects RETURNING id) SELECT * FROM changed",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    validate_director_agent_read_sql(sql)


if __name__ == "__main__":
    unittest.main()
