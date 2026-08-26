import ast
import copy
from decimal import Decimal
import json
from pathlib import Path
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import CookieSessionAuthenticationError
from backend.features.accounting_exception_checks.projection import (
    ACCOUNTING_EXCEPTION_SOURCES,
    build_accounting_exception_projection,
)
from backend.features.accounting_exception_checks.runtime_access import (
    AccountingExceptionAccessError,
)
from backend.features.accounting_exception_checks import runtime_routes
from backend.features.accounting_exception_checks.runtime_routes import (
    register_accounting_exception_check_routes,
)


PATH = "/accounting-exception-checks"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend/main.py"
OPS_PATH = PROJECT_ROOT / "ops-nginx-accounting-exception-checks.conf"
MIGRATION_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs/accounting-exception-checks-migration-runbook.md"
)
CANARY_PLAN_PATH = (
    PROJECT_ROOT / "docs/accounting-exception-checks-canary.md"
)
FEATURE_ENV = "ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED"
ALLOWLIST_ENV = "ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS"
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}


def _report(company_id=4):
    return build_accounting_exception_projection(
        company_id,
        {source: [] for source in ACCOUNTING_EXCEPTION_SOURCES},
    )


def _review_report(company_id=4):
    rows = {source: [] for source in ACCOUNTING_EXCEPTION_SOURCES}
    rows["supplier_invoices"] = [{
        "id": 9,
        "company_id": company_id,
        "owner_status": "verified",
        "project_id": None,
        "warehouse_invoice_id": None,
        "amount": Decimal("10"),
        "paid_amount": Decimal("11"),
    }]
    return build_accounting_exception_projection(company_id, rows)


class _App:
    def __init__(self):
        self.routes = {}

    def get(self, path, **kwargs):
        def decorate(handler):
            self.routes[("GET", path)] = (handler, dict(kwargs))
            return handler

        return decorate

    def post(self, path, **kwargs):
        def decorate(handler):
            self.routes[("POST", path)] = (handler, dict(kwargs))
            return handler

        return decorate


class _Deps(dict):
    def __init__(self, values):
        super().__init__(values)
        self.read_keys = []

    def __getitem__(self, key):
        self.read_keys.append(key)
        return super().__getitem__(key)


class _Harness:
    def __init__(
        self,
        *,
        auth_error=None,
        auth_result=None,
        runtime_error=None,
        result=None,
        allowed_company_ids=frozenset({4}),
    ):
        self.auth_error = auth_error
        self.auth_result = (
            dict(AUTHENTICATION) if auth_result is None else auth_result
        )
        self.runtime_error = runtime_error
        self.result = _report() if result is None else result
        self.auth_calls = []
        self.runtime_calls = []
        self.get_db = object()
        self.app = FastAPI()
        register_accounting_exception_check_routes(self.app, {
            "enabled": True,
            "allowed_company_ids": allowed_company_ids,
            "get_db": self.get_db,
            "finance_roles": ("директор", "зам_директора", "бухгалтер"),
            "build_cookie_session_authentication": self.authenticate,
            "run_authorized_accounting_exception_snapshot": self.run,
        })
        self.client = TestClient(self.app)

    def authenticate(
        self,
        request,
        authorization=None,
        csrf_token=None,
        *,
        require_csrf=True,
    ):
        self.auth_calls.append((
            authorization, csrf_token, require_csrf, request.url.path,
        ))
        if self.auth_error is not None:
            raise self.auth_error
        return self.auth_result

    def run(self, get_db, authentication, company_id, finance_roles):
        self.runtime_calls.append((
            get_db, authentication, company_id, finance_roles,
        ))
        if self.runtime_error is not None:
            raise self.runtime_error
        return copy.deepcopy(self.result)

    @staticmethod
    def headers(**overrides):
        headers = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }
        headers.update(overrides)
        return headers


class AccountingExceptionRouteRegistrationTests(unittest.TestCase):
    def test_registration_is_default_off(self):
        for values in (
            {"enabled": False},
            {"enabled": True, "allowed_company_ids": None},
            {"enabled": True, "allowed_company_ids": frozenset()},
            {"enabled": True, "allowed_company_ids": frozenset({True})},
            {"enabled": True, "allowed_company_ids": frozenset({0})},
            {"enabled": True, "allowed_company_ids": frozenset(range(1, 102))},
            {
                "enabled": True,
                "allowed_company_ids": frozenset({4}),
                "finance_roles": ["бухгалтер"],
            },
            {
                "enabled": True,
                "allowed_company_ids": frozenset({4}),
                "finance_roles": ("бухгалтер", "бухгалтер"),
            },
        ):
            with self.subTest(values=values):
                app = _App()
                deps = _Deps(values)
                self.assertIsNone(
                    register_accounting_exception_check_routes(app, deps)
                )
                self.assertEqual(app.routes, {})
                self.assertEqual(deps.read_keys, [])

    def test_valid_configuration_registers_one_exact_get_route(self):
        app = _App()
        no_call = lambda *_args, **_kwargs: None

        register_accounting_exception_check_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4, 17}),
            "get_db": object(),
            "finance_roles": ("директор", "зам_директора", "бухгалтер"),
            "build_cookie_session_authentication": no_call,
            "run_authorized_accounting_exception_snapshot": no_call,
        })

        self.assertEqual(set(app.routes), {("GET", PATH)})


class AccountingExceptionRouteContractTests(unittest.TestCase):
    def assert_error(self, response, status, detail):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json(), {"detail": detail})
        self.assertEqual(
            response.headers.get("cache-control"), "no-store, max-age=0",
        )
        self.assertEqual(response.headers.get("pragma"), "no-cache")
        self.assertEqual(
            response.headers.get("vary"),
            "Cookie, X-Company-Id, X-Company-Mode",
        )

    def test_cookie_company_and_finance_runtime_return_closed_no_store_result(self):
        for expected in (_report(), _review_report()):
            with self.subTest(state=expected["state"]):
                harness = _Harness(result=expected)
                response = harness.client.get(
                    PATH, headers=harness.headers(),
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), expected)
                self.assertEqual(
                    response.headers["cache-control"], "no-store, max-age=0",
                )
                self.assertEqual(
                    harness.auth_calls, [(None, None, False, PATH)],
                )
                self.assertEqual(harness.runtime_calls, [(
                    harness.get_db,
                    AUTHENTICATION,
                    4,
                    ("директор", "зам_директора", "бухгалтер"),
                )])
                rendered = response.text.lower()
                for forbidden in (
                    "purpose", "note", "photo", "bank", "items_json",
                    "owner_status", "company_id", "raw",
                ):
                    self.assertNotIn(forbidden, rendered)

    def test_cookie_authentication_is_required_and_bearer_is_rejected(self):
        for code, status in (
            ("cookie_session_authentication_required", 401),
            ("cookie_session_csrf_invalid", 403),
        ):
            with self.subTest(code=code):
                harness = _Harness(
                    auth_error=CookieSessionAuthenticationError(code),
                )
                response = harness.client.get(
                    PATH, headers=harness.headers(),
                )
                self.assert_error(
                    response,
                    status,
                    (
                        "accounting_exception_review_authentication_required"
                        if status == 401
                        else "accounting_exception_review_request_forbidden"
                    ),
                )
                self.assertEqual(harness.runtime_calls, [])

        bearer = _Harness(
            auth_error=CookieSessionAuthenticationError(
                "cookie_session_authentication_required"
            )
        )
        response = bearer.client.get(
            PATH,
            headers=bearer.headers(Authorization="Bearer PRIVATE"),
        )
        self.assert_error(
            response,
            401,
            "accounting_exception_review_authentication_required",
        )
        self.assertNotIn("PRIVATE", response.text)
        self.assertEqual(bearer.runtime_calls, [])

        malformed = _Harness(auth_result={
            "authenticationKind": "cookie_session",
            "sessionHash": "a" * 64,
            "private": "PRIVATE_AUTH",
        })
        response = malformed.client.get(
            PATH, headers=malformed.headers(),
        )
        self.assert_error(
            response, 503, "accounting_exception_review_unavailable",
        )
        self.assertNotIn("PRIVATE", response.text)
        self.assertEqual(malformed.runtime_calls, [])

    def test_exact_company_mode_and_allowlist_fail_before_business_runtime(self):
        invalid_headers = (
            {"X-Company-Id": ""},
            {"X-Company-Id": "04"},
            {"X-Company-Id": "+4"},
            {"X-Company-Id": "4 ", "X-Company-Mode": "company"},
            {"X-Company-Mode": "all_companies"},
            {"X-Company-Mode": "COMPANY"},
        )
        for overrides in invalid_headers:
            with self.subTest(overrides=overrides):
                harness = _Harness()
                response = harness.client.get(
                    PATH, headers=harness.headers(**overrides),
                )
                self.assert_error(
                    response,
                    422,
                    "accounting_exception_review_request_invalid",
                )
                self.assertEqual(harness.auth_calls, [])
                self.assertEqual(harness.runtime_calls, [])

        foreign = _Harness()
        response = foreign.client.get(
            PATH, headers=foreign.headers(**{"X-Company-Id": "5"}),
        )
        self.assert_error(
            response, 404, "accounting_exception_review_not_found",
        )
        self.assertEqual(foreign.auth_calls, [(None, None, False, PATH)])
        self.assertEqual(foreign.runtime_calls, [])

    def test_runtime_access_errors_are_fixed_and_nonleaking(self):
        cases = (
            (
                "accounting_exception_review_input_invalid",
                422,
                "accounting_exception_review_request_invalid",
            ),
            (
                "accounting_exception_review_authentication_required",
                401,
                "accounting_exception_review_authentication_required",
            ),
            (
                "accounting_exception_review_request_forbidden",
                403,
                "accounting_exception_review_request_forbidden",
            ),
            (
                "accounting_exception_review_read_failed",
                503,
                "accounting_exception_review_unavailable",
            ),
        )
        for code, status, detail in cases:
            with self.subTest(code=code):
                error = AccountingExceptionAccessError(code)
                error.private = "PRIVATE_DB_TEXT"
                harness = _Harness(runtime_error=error)
                response = harness.client.get(
                    PATH, headers=harness.headers(),
                )
                self.assert_error(response, status, detail)
                self.assertNotIn("PRIVATE", response.text)
        unknown = _Harness(runtime_error=RuntimeError("PRIVATE_STACK"))
        response = unknown.client.get(PATH, headers=unknown.headers())
        self.assert_error(
            response, 503, "accounting_exception_review_unavailable",
        )
        self.assertNotIn("PRIVATE", response.text)
        self.assertEqual(response.headers.get("retry-after"), "30")

    def test_unknown_or_malformed_result_never_crosses_http_boundary(self):
        mutations = []
        extra = _report()
        extra["rawRows"] = [{"secret": "PRIVATE"}]
        mutations.append(extra)
        wrong_company = _report()
        wrong_company["companyId"] = 5
        mutations.append(wrong_company)
        unknown_reason = _review_report()
        unknown_reason["findings"][0]["reasonCode"] = "PRIVATE_REASON"
        mutations.append(unknown_reason)
        raw_finding = _review_report()
        raw_finding["findings"][0]["note"] = "PRIVATE_NOTE"
        mutations.append(raw_finding)
        bad_count = _report()
        bad_count["sourceCounts"]["staff"] = 1001
        mutations.append(bad_count)
        for result in mutations:
            with self.subTest(keys=tuple(result)):
                harness = _Harness(result=result)
                response = harness.client.get(
                    PATH, headers=harness.headers(),
                )
                self.assert_error(
                    response, 503, "accounting_exception_review_unavailable",
                )
                self.assertNotIn("PRIVATE", response.text)

    def test_route_is_get_only_and_contains_no_mutation_capability(self):
        harness = _Harness()
        for method in ("post", "put", "patch", "delete"):
            response = harness.client.request(
                method.upper(),
                PATH, headers=harness.headers(), json={},
            )
            self.assertEqual(response.status_code, 405)
        text = Path(runtime_routes.__file__).read_text(encoding="utf-8").upper()
        for forbidden in (
            "@APP.POST", "@APP.PUT", "@APP.PATCH", "@APP.DELETE",
            ".COMMIT(", "INSERT ", "UPDATE ", "DELETE ", "FOR UPDATE",
        ):
            self.assertNotIn(forbidden, text)
        self.assertEqual(runtime_routes.__all__, [])


class AccountingExceptionMainAndOpsContractTests(unittest.TestCase):
    @staticmethod
    def _tree():
        source = MAIN_PATH.read_text(encoding="utf-8")
        return source, ast.parse(source, filename=str(MAIN_PATH))

    @staticmethod
    def _function(tree, name):
        matches = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if len(matches) != 1:
            raise AssertionError("expected one " + name)
        return matches[0]

    def test_main_allowlist_parser_is_exact_and_duplicate_free(self):
        _source, tree = self._tree()
        parser = copy.deepcopy(self._function(
            tree, "_parse_accounting_exception_check_company_ids",
        ))
        module = ast.Module(body=[parser], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {}
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        parse = namespace[parser.name]

        self.assertEqual(parse("4"), frozenset({4}))
        self.assertEqual(parse("4,17"), frozenset({4, 17}))
        self.assertEqual(
            parse("9223372036854775807"),
            frozenset({9223372036854775807}),
        )
        for value in (
            None, "", "1,1", "01", " 1", "1 ", "1,,2", "+1", "１",
            "9223372036854775808",
            ",".join(str(item) for item in range(1, 102)),
        ):
            with self.subTest(value=repr(value)[:100]):
                self.assertIsNone(parse(value))

    def test_main_import_and_registration_are_inside_both_default_off_gates(self):
        _source, tree = self._tree()
        matching = [
            statement for statement in tree.body
            if isinstance(statement, ast.If)
            and ast.unparse(statement.test) == (
                "os.getenv('ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED') "
                "== 'true'"
            )
        ]
        self.assertEqual(len(matching), 1)
        outer = matching[0]
        nested = [node for node in outer.body if isinstance(node, ast.If)]
        self.assertEqual(len(nested), 1)
        self.assertEqual(
            ast.unparse(nested[0].test),
            "accounting_exception_check_company_ids is not None",
        )
        rendered = ast.unparse(nested[0])
        for required in (
            "accounting_exception_checks.runtime_access",
            "accounting_exception_checks.runtime_routes",
            "run_authorized_accounting_exception_snapshot",
            "register_accounting_exception_check_routes",
            "build_cookie_session_authentication",
            "FINANCE_ROLES",
            "get_db",
        ):
            self.assertIn(required, rendered)
        self.assertNotIn(ALLOWLIST_ENV, rendered)
        register_calls = [
            node for node in ast.walk(nested[0])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_accounting_exception_check_routes"
        ]
        self.assertEqual(len(register_calls), 1)
        dependency_dict = register_calls[0].args[1]
        self.assertIsInstance(dependency_dict, ast.Dict)
        keys = {key.value for key in dependency_dict.keys}
        self.assertEqual(keys, {
            "enabled", "allowed_company_ids", "get_db", "finance_roles",
            "build_cookie_session_authentication",
            "run_authorized_accounting_exception_snapshot",
        })

    def test_extracted_main_wiring_defaults_off_for_partial_or_invalid_env(self):
        _source, tree = self._tree()
        parser = copy.deepcopy(self._function(
            tree, "_parse_accounting_exception_check_company_ids",
        ))
        wiring = [
            copy.deepcopy(statement)
            for statement in tree.body
            if isinstance(statement, ast.If)
            and ast.unparse(statement.test) == (
                "os.getenv('ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED') "
                "== 'true'"
            )
        ]
        self.assertEqual(len(wiring), 1)
        module = ast.Module(body=[parser, wiring[0]], type_ignores=[])
        ast.fix_missing_locations(module)
        compiled = compile(module, str(MAIN_PATH), "exec")
        cases = (
            (None, None, False),
            ("1", "4", False),
            ("TRUE", "4", False),
            ("true ", "4", False),
            ("true", None, False),
            ("true", "", False),
            ("true", "4,4", False),
            ("true", "04", False),
            ("true", "4,17", True),
        )
        for enabled, allowlist, expected in cases:
            with self.subTest(enabled=enabled, allowlist=allowlist):
                app = _App()
                namespace = {
                    "os": __import__("os"),
                    "app": app,
                    "get_db": object(),
                    "FINANCE_ROLES": (
                        "директор", "зам_директора", "бухгалтер",
                    ),
                    "build_cookie_session_authentication": object(),
                }
                with mock.patch.dict(__import__("os").environ, {}, clear=False):
                    __import__("os").environ.pop(FEATURE_ENV, None)
                    __import__("os").environ.pop(ALLOWLIST_ENV, None)
                    if enabled is not None:
                        __import__("os").environ[FEATURE_ENV] = enabled
                    if allowlist is not None:
                        __import__("os").environ[ALLOWLIST_ENV] = allowlist
                    exec(compiled, namespace)
                self.assertEqual(
                    set(app.routes), {
                        ("GET", PATH),
                        ("GET", "/accounting-exception-link-repairs"),
                        ("POST", "/accounting-exception-link-repairs"),
                    } if expected else set(),
                )

    def test_global_api_error_writer_skips_only_the_exact_review_path(self):
        _source, tree = self._tree()
        helper = self._function(tree, "_api_error_logging_enabled_for_path")
        module = ast.Module(body=[copy.deepcopy(helper)], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {}
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        enabled = namespace["_api_error_logging_enabled_for_path"]

        self.assertIs(enabled(PATH), False)
        self.assertIs(enabled("/accounting-exception-link-repairs"), False)
        self.assertIs(enabled(PATH + "/"), True)
        self.assertIs(enabled("/accounting-exception-link-repairs/"), True)
        self.assertIs(enabled("/accountable-payments"), True)

    def test_ops_fragment_is_exact_get_only_bounded_and_no_store(self):
        source = OPS_PATH.read_text(encoding="utf-8")
        for fragment in (
            "limit_req_zone $binary_remote_addr "
            "zone=accounting_exception_check_limit:10m rate=12r/m;",
            "limit_conn_zone $server_name "
            "zone=accounting_exception_check_conn:10m;",
            "location = /accounting-exception-checks {",
            "limit_req zone=accounting_exception_check_limit burst=2 nodelay;",
            "limit_conn accounting_exception_check_conn 1;",
            "limit_req_status 429;",
            "limit_conn_status 429;",
            "proxy_connect_timeout 6s;",
            "proxy_send_timeout 10s;",
            "proxy_read_timeout 45s;",
            "error_page 429 = @accounting_exception_check_429;",
            "proxy_pass http://127.0.0.1:8001;",
            "add_header Cache-Control \"no-store, max-age=0\" always;",
            "add_header Pragma \"no-cache\" always;",
            "add_header Vary "
            "\"Cookie, X-Company-Id, X-Company-Mode\" always;",
            "add_header Retry-After 10 always;",
            "return 429 "
            "'{\"detail\":\"accounting_exception_review_busy\"}';",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        self.assertEqual(
            source.count("location = /accounting-exception-checks {"), 1,
        )
        for forbidden in (
            "POST", "PUT", "PATCH", "DELETE", "$cookie_", "$http_x_company",
        ):
            self.assertNotIn(forbidden, source)

    def test_separate_migration_and_canary_documents_keep_production_unapproved(self):
        migration = MIGRATION_RUNBOOK_PATH.read_text(encoding="utf-8")
        canary = CANARY_PLAN_PATH.read_text(encoding="utf-8")
        normalized_migration = " ".join(migration.lower().split())
        normalized_canary = " ".join(canary.lower().split())

        for fragment in (
            "production execution requires separate explicit approval",
            "preflight inventory",
            "database backup",
            "row counts",
            "quarantine counts",
            "transactional stop conditions",
            "rollback and recovery",
            "expected_change_count",
            "expected_plan_sha256",
            "expected_ready_count",
            "APPLY_EXACT_ACCOUNTING_OWNERSHIP_REMEDIATION",
        ):
            with self.subTest(document="migration", fragment=fragment):
                self.assertIn(fragment.lower(), normalized_migration)

        for fragment in (
            "production execution requires separate explicit approval",
            "one exact company",
            "ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED=true",
            "ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS=<CANARY_COMPANY_ID>",
            "REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_ENABLED=true",
            "REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS=<CANARY_COMPANY_ID>",
            "p95 latency",
            "stop thresholds",
            "rollback",
            "GET /accounting-exception-checks",
        ):
            with self.subTest(document="canary", fragment=fragment):
                self.assertIn(fragment.lower(), normalized_canary)


if __name__ == "__main__":
    unittest.main()
