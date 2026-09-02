import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import CookieSessionAuthenticationError
from backend.features.supply_kp_comparison.runtime_access import (
    SupplyTechnicalComparisonAccessError,
)
from backend.features.supply_kp_comparison import runtime_routes
from backend.features.supply_kp_comparison.runtime_routes import (
    register_supply_technical_comparison_routes,
)
from backend.features.supply_kp_comparison.technical_matcher import (
    compare_required_to_offer,
)


PATH = (
    "/supply-requests/31/technical-comparisons/supplier_offer/81"
    "?projectId=7&fileId=44"
)
ROUTE = (
    "/supply-requests/{request_id}/technical-comparisons/"
    "{source_kind}/{source_id}"
)
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
ROLES = ("директор", "зам_директора", "снабженец")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend/main.py"
OPS_PATH = PROJECT_ROOT / "ops-nginx-supply-technical-comparison.conf"
DOC_PATH = PROJECT_ROOT / "docs/supply-technical-comparison-a8-5-3.md"
FEATURE_ENV = "SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED"
ALLOWLIST_ENV = "SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS"


def _sha(value):
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _report():
    required = {
        "name": "Труба PP-R PN20 20x3,4 мм",
        "unit": "м",
        "quantity": "100",
        "workPackage": "ВК",
        "category": "Трубы PP-R",
    }
    offered = {
        "name": "Труба Valfex PP-R PN20 20x3,4 мм",
        "unit": "м",
        "quantity": "100",
        "workPackage": "ВК",
        "category": "",
    }
    comparison = compare_required_to_offer(
        required["name"],
        offered["name"],
        required_unit=required["unit"],
        offered_unit=offered["unit"],
        category=required["category"],
    ).to_dict()
    result_hash = _sha({
        "contractVersion": 1,
        "companyId": 1,
        "projectId": 7,
        "requestId": 31,
        "sourceKind": "supplier_offer",
        "sourceId": 81,
        "fileId": 44,
        "comparisonHashes": [comparison["comparisonSha256"]],
    })
    return {
        "ok": True,
        "dryRun": True,
        "contractVersion": 1,
        "companyId": 1,
        "projectId": 7,
        "requestId": 31,
        "sourceKind": "supplier_offer",
        "sourceId": 81,
        "file": {
            "id": 44,
            "contentUrl": "/tenant-files/44/content",
            "context": "supplier-offer",
            "originalName": "offer.pdf",
            "contentType": "application/pdf",
        },
        "requestedLineCount": 1,
        "offeredLineCount": 1,
        "comparisonCount": 1,
        "comparisons": [{
            "lineNumber": 1,
            "required": required,
            "offered": offered,
            "result": comparison,
        }],
        "resultSha256": result_hash,
        "automaticApprovalAllowed": False,
        "writesAttempted": 0,
        "modelCalls": 0,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }


class _App:
    def __init__(self):
        self.routes = {}

    def get(self, path, **kwargs):
        def decorate(handler):
            self.routes[("GET", path)] = (handler, dict(kwargs))
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
        allowed_company_ids=frozenset({1}),
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
        register_supply_technical_comparison_routes(self.app, {
            "enabled": True,
            "allowed_company_ids": allowed_company_ids,
            "allowed_roles": ROLES,
            "get_db": self.get_db,
            "build_cookie_session_authentication": self.authenticate,
            "run_authorized_supply_technical_comparison": self.run,
        })
        self.client = TestClient(self.app)

    def authenticate(
        self, request, authorization=None, csrf_token=None, *, require_csrf=True,
    ):
        self.auth_calls.append((
            authorization, csrf_token, require_csrf, request.url.path,
        ))
        if self.auth_error is not None:
            raise self.auth_error
        return self.auth_result

    def run(self, get_db, authentication, allowed_roles, **selectors):
        self.runtime_calls.append((
            get_db, authentication, allowed_roles, dict(selectors),
        ))
        if self.runtime_error is not None:
            raise self.runtime_error
        return copy.deepcopy(self.result)

    @staticmethod
    def headers(**overrides):
        headers = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-Company-Id": "1",
            "X-Company-Mode": "company",
        }
        headers.update(overrides)
        return headers


class SupplyTechnicalComparisonRouteTests(unittest.TestCase):
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

    def test_registration_is_default_off_and_fail_closed(self):
        no_call = lambda *_args, **_kwargs: None
        valid = {
            "enabled": True,
            "allowed_company_ids": frozenset({1}),
            "allowed_roles": ROLES,
            "get_db": object(),
            "build_cookie_session_authentication": no_call,
            "run_authorized_supply_technical_comparison": no_call,
        }
        invalid = (
            {"enabled": False},
            {**valid, "allowed_company_ids": frozenset()},
            {**valid, "allowed_company_ids": frozenset({True})},
            {**valid, "allowed_roles": ("снабженец", "снабженец")},
            {**valid, "allowed_roles": ["снабженец"]},
        )
        for values in invalid:
            with self.subTest(values=values):
                app = _App()
                deps = _Deps(values)
                self.assertIsNone(
                    register_supply_technical_comparison_routes(app, deps)
                )
                self.assertEqual(app.routes, {})
                if values.get("enabled") is not True:
                    self.assertEqual(deps.read_keys, [])

        app = _App()
        register_supply_technical_comparison_routes(app, valid)
        self.assertEqual(set(app.routes), {("GET", ROUTE)})

    def test_exact_cookie_company_and_selector_return_narrow_no_store_result(self):
        harness = _Harness()
        response = harness.client.get(PATH, headers=harness.headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), _report())
        self.assertEqual(
            response.headers["cache-control"], "no-store, max-age=0",
        )
        self.assertEqual(
            harness.auth_calls,
            [(None, None, False, PATH.split("?", 1)[0])],
        )
        self.assertEqual(harness.runtime_calls, [(
            harness.get_db,
            AUTHENTICATION,
            ROLES,
            {
                "company_id": 1,
                "project_id": 7,
                "request_id": 31,
                "source_kind": "supplier_offer",
                "source_id": 81,
                "file_id": 44,
            },
        )])
        rendered = response.text.lower()
        for forbidden in (
            "storage_key", "file_url", "sessionhash", "sql", "private",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_cookie_only_authentication_is_required_and_bearer_is_rejected(self):
        for code, expected_status, expected_detail in (
            (
                "cookie_session_authentication_required",
                401,
                "supply_technical_comparison_authentication_required",
            ),
            (
                "cookie_session_csrf_invalid",
                403,
                "supply_technical_comparison_request_forbidden",
            ),
        ):
            harness = _Harness(
                auth_error=CookieSessionAuthenticationError(code),
            )
            response = harness.client.get(PATH, headers=harness.headers())
            self.assert_error(
                response, expected_status, expected_detail,
            )
            self.assertEqual(harness.runtime_calls, [])

        harness = _Harness(auth_error=CookieSessionAuthenticationError(
            "cookie_session_authentication_required"
        ))
        response = harness.client.get(
            PATH,
            headers=harness.headers(Authorization="Bearer PRIVATE"),
        )
        self.assert_error(
            response,
            401,
            "supply_technical_comparison_authentication_required",
        )
        self.assertNotIn("PRIVATE", response.text)

    def test_selectors_company_mode_and_allowlist_fail_before_runtime(self):
        invalid_paths = (
            PATH.replace("/31/", "/031/"),
            PATH.replace("/81?", "/+81?"),
            PATH.replace("supplier_offer", "PRIVATE"),
            PATH.replace("projectId=7", "projectId=07"),
            PATH.replace("fileId=44", "fileId=true"),
        )
        for path in invalid_paths:
            harness = _Harness()
            response = harness.client.get(path, headers=harness.headers())
            self.assert_error(
                response, 422, "supply_technical_comparison_request_invalid",
            )
            self.assertEqual(harness.auth_calls, [])
            self.assertEqual(harness.runtime_calls, [])

        for path in (
            PATH + "&projectId=8",
            PATH + "&fileId=45",
        ):
            harness = _Harness()
            response = harness.client.get(path, headers=harness.headers())
            self.assert_error(
                response, 422, "supply_technical_comparison_request_invalid",
            )
            self.assertEqual(harness.auth_calls, [])
            self.assertEqual(harness.runtime_calls, [])

        for duplicate_headers in (
            [
                ("Cookie", "stroyka_session=" + "s" * 64),
                ("X-Company-Id", "1"),
                ("X-Company-Id", "2"),
                ("X-Company-Mode", "company"),
            ],
            [
                ("Cookie", "stroyka_session=" + "s" * 64),
                ("X-Company-Id", "1"),
                ("X-Company-Mode", "company"),
                ("X-Company-Mode", "all_companies"),
            ],
        ):
            harness = _Harness()
            response = harness.client.get(PATH, headers=duplicate_headers)
            self.assert_error(
                response, 422, "supply_technical_comparison_request_invalid",
            )
            self.assertEqual(harness.auth_calls, [])
            self.assertEqual(harness.runtime_calls, [])

        for overrides in (
            {"X-Company-Id": "01"},
            {"X-Company-Mode": "all_companies"},
            {"X-Company-Mode": "COMPANY"},
        ):
            harness = _Harness()
            response = harness.client.get(
                PATH, headers=harness.headers(**overrides),
            )
            self.assert_error(
                response, 422, "supply_technical_comparison_request_invalid",
            )
            self.assertEqual(harness.auth_calls, [])

        harness = _Harness()
        response = harness.client.get(
            PATH, headers=harness.headers(**{"X-Company-Id": "2"}),
        )
        self.assert_error(
            response, 404, "supply_technical_comparison_not_found",
        )
        self.assertEqual(harness.runtime_calls, [])

    def test_runtime_failures_are_fixed_nonleaking_and_retryable(self):
        cases = (
            (
                "supply_technical_comparison_access_not_found",
                404,
                "supply_technical_comparison_not_found",
            ),
            (
                "supply_technical_comparison_access_input_invalid",
                503,
                "supply_technical_comparison_unavailable",
            ),
            (
                "supply_technical_comparison_access_read_failed",
                503,
                "supply_technical_comparison_unavailable",
            ),
            (
                "supply_technical_comparison_access_rollback_failed",
                503,
                "supply_technical_comparison_unavailable",
            ),
        )
        for code, status, detail in cases:
            error = SupplyTechnicalComparisonAccessError(code)
            error.private = "PRIVATE_DB"
            harness = _Harness(runtime_error=error)
            response = harness.client.get(PATH, headers=harness.headers())
            self.assert_error(response, status, detail)
            self.assertNotIn("PRIVATE", response.text)
            if status == 503:
                self.assertEqual(response.headers.get("retry-after"), "30")

    def test_malformed_result_is_rejected_without_private_data_leak(self):
        mutations = []
        extra = _report()
        extra["privateRows"] = [{"secret": "PRIVATE"}]
        mutations.append(extra)
        nested = _report()
        nested["comparisons"][0]["result"]["private"] = "PRIVATE"
        mutations.append(nested)
        unsafe = _report()
        unsafe["automaticApprovalAllowed"] = True
        mutations.append(unsafe)
        wrong_hash = _report()
        wrong_hash["resultSha256"] = "f" * 64
        mutations.append(wrong_hash)
        wrong_file = _report()
        wrong_file["file"]["contentUrl"] = "https://s3.example/PRIVATE"
        mutations.append(wrong_file)
        for result in mutations:
            harness = _Harness(result=result)
            response = harness.client.get(PATH, headers=harness.headers())
            self.assert_error(
                response, 503, "supply_technical_comparison_unavailable",
            )
            self.assertNotIn("PRIVATE", response.text)

    def test_route_is_get_only_and_contains_no_mutation_capability(self):
        harness = _Harness()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = harness.client.request(
                method, PATH, headers=harness.headers(), json={},
            )
            self.assertEqual(response.status_code, 405)
        source = Path(runtime_routes.__file__).read_text(encoding="utf-8").upper()
        for forbidden in (
            "@APP.POST", "@APP.PUT", "@APP.PATCH", "@APP.DELETE",
            ".COMMIT(", "INSERT ", "UPDATE ", "DELETE ", "FOR UPDATE",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(runtime_routes.__all__, [])


class SupplyTechnicalComparisonWiringTests(unittest.TestCase):
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

    def test_main_has_exact_default_off_feature_and_allowlist_gates(self):
        _source, tree = self._tree()
        parser = self._function(
            tree, "_parse_supply_technical_comparison_company_ids",
        )
        namespace = {}
        module = ast.Module(body=[copy.deepcopy(parser)], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        parse = namespace[parser.name]
        self.assertEqual(parse("1,17"), frozenset({1, 17}))
        for value in (
            None, "", "1,1", "01", "+1", " 1", "1 ", "１",
            "9223372036854775808",
            ",".join(str(item) for item in range(1, 102)),
        ):
            self.assertIsNone(parse(value))

        matching = [
            statement for statement in tree.body
            if isinstance(statement, ast.If)
            and ast.unparse(statement.test) == (
                "os.getenv('SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED') "
                "== 'true'"
            )
        ]
        self.assertEqual(len(matching), 1)
        rendered = ast.unparse(matching[0])
        for required in (
            "SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS",
            "register_supply_technical_comparison_routes",
            "run_authorized_supply_technical_comparison",
            "build_cookie_session_authentication",
            "SUPPLY_TECHNICAL_COMPARISON_ROLES",
            "get_db",
        ):
            self.assertIn(required, rendered)

    def test_nginx_fragment_is_exact_rate_limited_and_documented(self):
        text = OPS_PATH.read_text(encoding="utf-8")
        self.assertIn("limit_req_zone", text)
        self.assertIn("limit_conn_zone", text)
        self.assertIn(
            "limit_conn_zone $binary_remote_addr "
            "zone=supply_technical_comparison_conn:10m;",
            text,
        )
        self.assertIn('location ~ "^/supply-requests/', text)
        self.assertIn("^/supply-requests/", text)
        self.assertIn("/technical-comparisons/", text)
        self.assertIn("limit_req_status 429", text)
        self.assertIn("proxy_pass http://127.0.0.1:8001", text)
        self.assertIn("supply_technical_comparison_busy", text)
        self.assertTrue(DOC_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
