import ast
import json
import unittest
from pathlib import Path


MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"
TOOL_NAMES = (
    "_director_agent_tool_projects",
    "_director_agent_tool_warehouse",
    "_director_agent_tool_supply",
    "_director_agent_tool_estimates",
    "_director_agent_tool_finances",
    "_director_agent_tool_staff",
    "_director_agent_tool_ai_tasks",
)
SUPPORT_NAMES = (
    "_director_agent_num",
    "_director_agent_json",
    "_director_agent_company_ids",
)


def load_director_agent_functions(query):
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
    wanted = set(TOOL_NAMES + SUPPORT_NAMES)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {
        "json": json,
        "_director_agent_query": query,
    }
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(MAIN_PATH), "exec"), namespace)
    return namespace


class DirectorAgentTenantScopeTests(unittest.TestCase):
    def test_every_tool_fails_closed_without_a_selected_company(self):
        queries = []

        def query(sql, params=()):
            queries.append((sql, params))
            return []

        functions = load_director_agent_functions(query)

        for name in TOOL_NAMES:
            with self.subTest(tool=name):
                result = functions[name]({}, [])
                self.assertIsNotNone(result)

        self.assertEqual(queries, [])

    def test_every_tool_constrains_its_queries_by_company(self):
        queries = []

        def query(sql, params=()):
            queries.append((" ".join(sql.split()), params))
            return []

        functions = load_director_agent_functions(query)

        for name in TOOL_NAMES:
            with self.subTest(tool=name):
                before = len(queries)
                functions[name]({}, [9, "4", 9, None, -1])
                tool_queries = queries[before:]
                self.assertTrue(tool_queries)
                for sql, params in tool_queries:
                    self.assertIn("company_id", sql.lower())
                    self.assertTrue(
                        any(value == [4, 9] for value in params),
                        msg=f"{name} did not pass the normalized company scope: {params}",
                    )

    def test_route_passes_company_scope_to_all_tools(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        route = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "director_agent_ask"
        )
        tool_calls = [
            node
            for node in ast.walk(route)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Subscript)
            and isinstance(node.func.value, ast.Subscript)
        ]
        scoped_calls = [
            call
            for call in tool_calls
            if any(isinstance(arg, ast.Name) and arg.id == "request_company_ids" for arg in call.args)
        ]

        self.assertEqual(len(scoped_calls), 1)
        self.assertFalse(any(
            isinstance(node, ast.If)
            and any(isinstance(value, ast.Constant) and value.value in ("finances", "ai_tasks")
                    for value in ast.walk(node.test))
            for node in ast.walk(route)
        ))


if __name__ == "__main__":
    unittest.main()
