"""Static source audit for the exact Jev QA GET read-only blockers (#345).

This is intentionally a conservative audit, NOT proof of zero database writes.
It runs offline in backend CI, never opens a DB or makes HTTP requests.
"""
import ast
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
