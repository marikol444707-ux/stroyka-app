import ast
import copy
import os
import sys
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from fastapi import HTTPException

from backend.auth import CookieSessionAuthenticationError
from backend.features.supply_recommendation_preview.runtime_routes import (
    register_material_capability_runtime_module,
)


MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"
FEATURE_ENV = "SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED"
REGISTER_NAME = "register_material_capability_runtime_module"
AUTH_IMPORT_NAMES = {
    "CookieSessionAuthenticationError",
    "build_cookie_session_authentication",
}
RUNTIME_DEPENDENCIES = {
    "enabled": None,
    "get_db": "get_db",
    "build_cookie_session_authentication": (
        "build_cookie_session_authentication"
    ),
    "run_material_capability_runtime_read": (
        "run_material_capability_runtime_read"
    ),
    "run_material_capability_confirmation_write": (
        "run_material_capability_confirmation_write"
    ),
    "run_material_capability_revocation_write": (
        "run_material_capability_revocation_write"
    ),
}


def _main_source_and_tree():
    source = MAIN_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(MAIN_PATH))


def _imported_names(statements, module):
    names = set()
    for statement in statements:
        if isinstance(statement, ast.ImportFrom) and statement.module == module:
            names.update(alias.name for alias in statement.names)
    return names


def _matching_import_try(tree, backend_module, fallback_module):
    matches = []
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        backend_names = _imported_names(node.body, backend_module)
        fallback_names = set()
        for handler in node.handlers:
            fallback_names.update(_imported_names(handler.body, fallback_module))
        if backend_names or fallback_names:
            matches.append((backend_names, fallback_names))
    return matches


def _runtime_registration_call(tree):
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == REGISTER_NAME
    ]
    if len(calls) != 1:
        raise AssertionError(
            "backend.main must contain exactly one material capability "
            "runtime registration"
        )
    return calls[0]


def _registration_dependencies(call):
    if (
        len(call.args) != 2
        or not isinstance(call.args[0], ast.Name)
        or call.args[0].id != "app"
        or not isinstance(call.args[1], ast.Dict)
        or call.keywords
    ):
        raise AssertionError("material capability registration shape is invalid")
    result = {}
    for key, value in zip(call.args[1].keys, call.args[1].values):
        if not isinstance(key, ast.Constant) or type(key.value) is not str:
            raise AssertionError("material capability dependency key is invalid")
        result[key.value] = value
    return result


def _is_exact_feature_gate(node):
    return bool(
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value == "true"
        and isinstance(node.left, ast.Call)
        and isinstance(node.left.func, ast.Attribute)
        and isinstance(node.left.func.value, ast.Name)
        and node.left.func.value.id == "os"
        and node.left.func.attr == "getenv"
        and len(node.left.args) == 1
        and isinstance(node.left.args[0], ast.Constant)
        and node.left.args[0].value == FEATURE_ENV
        and not node.left.keywords
    )


def _csrf_function(tree):
    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "csrf_token"
    ]
    if len(functions) != 1:
        raise AssertionError("backend.main must define exactly one csrf_token")
    return functions[0]


def _load_isolated_csrf_function(function_node, events):
    node = copy.deepcopy(function_node)
    node.decorator_list = []

    def header(**_kwargs):
        return None

    def depends(_dependency):
        return None

    def build_authentication(
        request,
        authorization=None,
        csrf_token=None,
        *,
        require_csrf=True,
    ):
        events.append((
            "build",
            authorization,
            csrf_token,
            require_csrf,
        ))
        if authorization is not None:
            raise CookieSessionAuthenticationError(
                "cookie_session_authentication_required"
            )
        return {
            "authenticationKind": "cookie_session",
            "sessionHash": "a" * 64,
        }

    def live_session(request):
        events.append(("live", request))
        return {"id": 7}

    def create_csrf(session_token):
        events.append(("create", session_token))
        return "signed-cookie-bound-csrf"

    namespace = {
        "AUTH_SESSION_COOKIE_NAME": "stroyka_session",
        "CSRF_TOKEN_TTL_SECONDS": 7200,
        "CookieSessionAuthenticationError": CookieSessionAuthenticationError,
        "Depends": depends,
        "Header": header,
        "HTTPException": HTTPException,
        "Optional": Optional,
        "Request": object,
        "_create_csrf_token": create_csrf,
        "_current_user_from_session_cookie": live_session,
        "build_cookie_session_authentication": build_authentication,
        "get_current_user": object(),
    }
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace["csrf_token"]


class CookieJar:
    def __init__(self, events, value="s" * 64):
        self.events = events
        self.value = value

    def get(self, key):
        self.events.append(("cookie", key))
        return self.value


class FakeRequest:
    def __init__(self, events):
        self.cookies = CookieJar(events)


class MaterialCapabilityMainIntegrationContractTests(unittest.TestCase):
    def test_main_wires_exact_runtime_imports_and_dependencies(self):
        _source, tree = _main_source_and_tree()
        runtime_imports = _matching_import_try(
            tree,
            "backend.features.supply_recommendation_preview.runtime_routes",
            "features.supply_recommendation_preview.runtime_routes",
        )
        self.assertEqual(len(runtime_imports), 1)
        self.assertIn(REGISTER_NAME, runtime_imports[0][0])
        self.assertIn(REGISTER_NAME, runtime_imports[0][1])

        dependencies = _registration_dependencies(
            _runtime_registration_call(tree)
        )
        self.assertEqual(set(dependencies), set(RUNTIME_DEPENDENCIES))
        for key, expected_name in RUNTIME_DEPENDENCIES.items():
            if key == "enabled":
                self.assertTrue(_is_exact_feature_gate(dependencies[key]))
            else:
                self.assertIsInstance(dependencies[key], ast.Name)
                self.assertEqual(dependencies[key].id, expected_name)

    def test_feature_gate_is_true_only_for_exact_lowercase_true(self):
        _source, tree = _main_source_and_tree()
        enabled = _registration_dependencies(
            _runtime_registration_call(tree)
        )["enabled"]
        expression = ast.Expression(body=copy.deepcopy(enabled))
        ast.fix_missing_locations(expression)
        compiled = compile(expression, str(MAIN_PATH), "eval")

        cases = (
            (None, False),
            ("", False),
            ("1", False),
            ("TRUE", False),
            ("true ", False),
            (" true", False),
            ("true", True),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(FEATURE_ENV, None)
                    if value is not None:
                        os.environ[FEATURE_ENV] = value
                    actual = eval(compiled, {"os": os})
                    self.assertIs(actual, expected)
                    if not expected:
                        app = type("OffApp", (), {"routes": {}})()
                        register_material_capability_runtime_module(
                            app, {"enabled": actual}
                        )
                        self.assertEqual(app.routes, {})

    def test_cookie_adapter_symbols_exist_in_both_main_auth_import_blocks(self):
        _source, tree = _main_source_and_tree()
        auth_imports = _matching_import_try(tree, "backend.auth", "auth")

        self.assertEqual(len(auth_imports), 1)
        backend_names, fallback_names = auth_imports[0]
        self.assertTrue(AUTH_IMPORT_NAMES.issubset(backend_names))
        self.assertTrue(AUTH_IMPORT_NAMES.issubset(fallback_names))

    def test_csrf_token_rejects_authorization_before_cookie_or_live_session(self):
        _source, tree = _main_source_and_tree()
        for authorization in (
            "Bearer compatibility-token",
            "Basic compatibility-token",
            "",
        ):
            with self.subTest(authorization=authorization):
                events = []
                csrf_token = _load_isolated_csrf_function(
                    _csrf_function(tree), events
                )
                request = FakeRequest(events)

                with self.assertRaises(HTTPException) as raised:
                    csrf_token(request, authorization=authorization)

                self.assertEqual(raised.exception.status_code, 401)
                self.assertEqual(
                    raised.exception.detail,
                    "cookie_session_authentication_required",
                )
                self.assertEqual(events, [
                    ("build", authorization, None, False),
                ])

    def test_csrf_token_keeps_live_cookie_bound_issuance(self):
        _source, tree = _main_source_and_tree()
        events = []
        csrf_token = _load_isolated_csrf_function(_csrf_function(tree), events)
        request = FakeRequest(events)

        result = csrf_token(request, authorization=None)

        self.assertEqual(result, {
            "csrfToken": "signed-cookie-bound-csrf",
            "expiresIn": 7200,
        })
        self.assertEqual(events[0], ("build", None, None, False))
        self.assertEqual(events[1], ("live", request))
        self.assertEqual(events[2], ("cookie", "stroyka_session"))
        self.assertEqual(events[3], ("create", "s" * 64))

    def test_contract_never_imports_backend_main(self):
        self.assertNotIn("backend.main", sys.modules)


if __name__ == "__main__":
    unittest.main()
