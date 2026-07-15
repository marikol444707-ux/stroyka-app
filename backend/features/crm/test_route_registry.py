import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CRM_ROUTE_SOURCES = (
    ROOT / "backend" / "main.py",
    ROOT / "backend" / "features" / "crm" / "routes.py",
)
HTTP_METHODS = {"delete", "get", "patch", "post", "put"}


def collect_crm_routes(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in HTTP_METHODS or not decorator.args:
                continue
            route_arg = decorator.args[0]
            if not isinstance(route_arg, ast.Constant) or not isinstance(route_arg.value, str):
                continue
            route = route_arg.value
            if not route.startswith("/crm"):
                continue
            normalized_route = re.sub(r"\{[^{}]+\}", "{}", route)
            routes.append({
                "key": (method.upper(), normalized_route),
                "path": route,
                "function": node.name,
                "source": path.relative_to(ROOT).as_posix(),
                "line": decorator.lineno,
            })
    return routes


class CrmRouteRegistryTests(unittest.TestCase):
    def test_crm_route_signatures_are_unique(self):
        by_signature = {}
        for source in CRM_ROUTE_SOURCES:
            for route in collect_crm_routes(source):
                by_signature.setdefault(route["key"], []).append(route)

        duplicates = {
            f"{method} {path}": definitions
            for (method, path), definitions in by_signature.items()
            if len(definitions) > 1
        }

        self.assertEqual(
            {},
            duplicates,
            "FastAPI uses the first matching route, so duplicate CRM signatures can bypass "
            "the tenant-safe module handler.",
        )


if __name__ == "__main__":
    unittest.main()
