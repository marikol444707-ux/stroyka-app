"""Source and isolated middleware tests for Jev QA GET read-only blockers.

The source audit is conservative, NOT proof of zero database writes. Middleware
regressions execute extracted functions without importing main or its startup.
All checks run offline, never open a DB, and never make HTTP requests.
"""
import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[3]
ROUTES = (
    ROOT / "backend/features/company_context/routes.py",
    ROOT / "backend/features/supply_history/routes.py",
)


def get_route_risks(source):
    tree = ast.parse(source)
    findings = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        paths = []
        for dec in fn.decorator_list:
            if (isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "get"
                    and dec.args and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)):
                paths.append(dec.args[0].value)
        if not paths:
            continue
        risks = set()
        defaults = list(fn.args.defaults) + [
            x for x in fn.args.kw_defaults if x is not None
        ]
        for default in defaults:
            for node in ast.walk(default):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "Depends"
                        and node.args
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "get_current_user"):
                    risks.add("LEGACY_AUTH_GET_DEPENDENCY")
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "commit":
                    risks.add("EXPLICIT_COMMIT_ON_GET")
                if node.func.attr == "execute" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value.strip().split(" ", 1)[0].upper() in {
                            "INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP",
                        }:
                            risks.add("DIRECT_SQL_WRITE_ON_GET")
            if (isinstance(node.func, ast.Name)
                    and node.func.id.startswith("ensure_")):
                risks.add("GET_INITIALIZER_CALL")
        for route in paths:
            findings[route] = risks
    return findings


class JevGetSourceAuditTest(unittest.TestCase):
    def test_company_context_get_still_requires_auth_write_review(self):
        found = get_route_risks(ROUTES[0].read_text(encoding="utf-8"))
        for path in ("/company-context", "/users/company-context"):
            with self.subTest(path=path):
                self.assertIn("LEGACY_AUTH_GET_DEPENDENCY", found[path])

    def test_supply_history_get_has_no_direct_schema_mutation(self):
        found = get_route_risks(ROUTES[1].read_text(encoding="utf-8"))
        risks = found["/supply-history"]
        self.assertIn("LEGACY_AUTH_GET_DEPENDENCY", risks)
        self.assertNotIn("EXPLICIT_COMMIT_ON_GET", risks)
        self.assertNotIn("GET_INITIALIZER_CALL", risks)
        self.assertNotIn("DIRECT_SQL_WRITE_ON_GET", risks)

    def test_source_audit_catches_mutating_get_and_skips_post(self):
        sample = '''
@app.get("/broken")
def unsafe(user=Depends(get_current_user)):
    ensure_columns()
    cur.execute("UPDATE warehouse SET qty=0")
    conn.commit()
@app.post("/write")
def accepted():
    conn.commit()
'''
        risks = get_route_risks(sample)
        self.assertEqual(set(risks), {"/broken"})
        self.assertEqual(risks["/broken"], {
            "LEGACY_AUTH_GET_DEPENDENCY", "GET_INITIALIZER_CALL",
            "DIRECT_SQL_WRITE_ON_GET", "EXPLICIT_COMMIT_ON_GET",
        })

    def test_audit_does_not_claim_safe_without_dependency_trace(self):
        sample = '''
@app.get("/indirect")
def indirect():
    return call_helper_that_may_write()
'''
        self.assertEqual(get_route_risks(sample), {"/indirect": set()})


class JevIdentityMiddlewareTest(unittest.TestCase):
    """Run the actual middleware without importing main or its startup writes."""

    identity_path = "/users/qa-readonly-context/identity"

    def setUp(self):
        source = ROOT / "backend/main.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        selected = []
        for name in ("_api_error_logging_enabled_for_path", "api_error_logging_middleware"):
            node = next(node for node in tree.body if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and node.name == name)
            node.decorator_list = []
            selected.append(node)
        self.log_error = Mock()
        namespace = {
            "Request": object,
            "Response": lambda status_code: SimpleNamespace(status_code=status_code),
            "_log_api_error": self.log_error,
        }
        module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
        exec(compile(module, str(source), "exec"), namespace)
        self.middleware = namespace["api_error_logging_middleware"]

    def request(self, path):
        return SimpleNamespace(method="GET", url=SimpleNamespace(path=path))

    def test_identity_responses_preserve_status_without_database_error_logging(self):
        request = self.request(self.identity_path)
        for status in (200, 401, 403, 404, 500, 503, 599):
            with self.subTest(status=status):
                self.log_error.reset_mock()
                response = SimpleNamespace(status_code=status)
                call_next = AsyncMock(return_value=response)
                self.assertIs(asyncio.run(self.middleware(request, call_next)), response)
                call_next.assert_awaited_once_with(request)
                self.log_error.assert_not_called()

    def test_identity_setup_and_cleanup_exceptions_propagate_without_database_error_logging(self):
        request = self.request(self.identity_path)
        for stage in ("connect", "cursor", "set_read_only", "rollback", "close"):
            with self.subTest(stage=stage):
                self.log_error.reset_mock()
                error = RuntimeError(stage)
                call_next = AsyncMock(side_effect=error)
                with self.assertRaises(RuntimeError) as caught:
                    asyncio.run(self.middleware(request, call_next))
                self.assertIs(caught.exception, error)
                call_next.assert_awaited_once_with(request)
                self.log_error.assert_not_called()

    def test_only_exact_identity_path_is_exempt_from_database_error_logging(self):
        for path in (
            self.identity_path + "/",
            self.identity_path + "/extra",
            self.identity_path + "-other",
            "/users/qa-readonly-context",
            "/users/company-context",
            "/projects",
        ):
            for status in (500, 503):
                with self.subTest(path=path, status=status):
                    self.log_error.reset_mock()
                    request = self.request(path)
                    response = SimpleNamespace(status_code=status)
                    call_next = AsyncMock(return_value=response)
                    self.assertIs(asyncio.run(self.middleware(request, call_next)), response)
                    self.log_error.assert_called_once_with(request, None, status)
            with self.subTest(path=path, exception=True):
                self.log_error.reset_mock()
                request = self.request(path)
                error = RuntimeError("ordinary route failure")
                with self.assertRaises(RuntimeError) as caught:
                    asyncio.run(self.middleware(request, AsyncMock(side_effect=error)))
                self.assertIs(caught.exception, error)
                self.log_error.assert_called_once_with(request, error, 500)

    def test_ordinary_nonserver_error_responses_still_do_not_log(self):
        request = self.request("/projects")
        for status in (200, 401, 403, 404, 499):
            with self.subTest(status=status):
                response = SimpleNamespace(status_code=status)
                self.assertIs(asyncio.run(self.middleware(
                    request, AsyncMock(return_value=response),
                )), response)
                self.log_error.assert_not_called()

    def test_subscription_middleware_identity_get_opens_no_database_connection(self):
        source = ROOT / "backend/features/client_account/subscription_access.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        selected = [next(node for node in tree.body if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == "_READ_METHODS"
                                 for target in node.targets))]
        for name in ("should_check_subscription_access", "subscription_read_only_middleware"):
            node = next(node for node in ast.walk(tree) if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and node.name == name)
            node.decorator_list = []
            selected.append(node)
        get_db = Mock(side_effect=AssertionError("identity GET must not open a subscription connection"))
        namespace = {"get_db": get_db}
        module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
        exec(compile(module, str(source), "exec"), namespace)
        request = self.request(self.identity_path)
        response = SimpleNamespace(status_code=200)
        call_next = AsyncMock(return_value=response)
        self.assertIs(asyncio.run(namespace["subscription_read_only_middleware"](
            request, call_next,
        )), response)
        call_next.assert_awaited_once_with(request)
        get_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
