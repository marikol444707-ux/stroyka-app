import copy
from pathlib import Path
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import CookieSessionAuthenticationError
from backend.features.accounting_exception_checks.link_repair_runtime import (
    AccountingLinkRepairRuntimeError,
)
from backend.features.accounting_exception_checks.link_repair_routes import (
    register_accounting_link_repair_routes,
)


PATH = "/accounting-exception-link-repairs"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
PREVIEW = {
    "version": "accounting-exception-link-repair-v3",
    "companyId": 4,
    "state": "ready",
    "repairCount": 1,
    "unresolvedCount": 30,
    "proofCounts": {
        "reciprocal": 0, "delivery": 1, "request": 0, "identity": 0,
        "dangling": 0,
    },
    "planSha256": "b" * 64,
    "blockers": [],
}
APPLIED = {
    "ok": True,
    "appliedCount": 1,
    "unresolvedCount": 30,
    "planSha256": "b" * 64,
}


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path, **_kwargs):
        return self._decorator("GET", path)

    def post(self, path, **_kwargs):
        return self._decorator("POST", path)

    def _decorator(self, method, path):
        def decorate(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorate


class Harness:
    def __init__(
        self,
        *,
        auth_error=None,
        preview=None,
        applied=None,
        runtime_error=None,
    ):
        self.auth_error = auth_error
        self.preview = copy.deepcopy(PREVIEW if preview is None else preview)
        self.applied = copy.deepcopy(APPLIED if applied is None else applied)
        self.runtime_error = runtime_error
        self.auth_calls = []
        self.preview_calls = []
        self.apply_calls = []
        self.get_db = object()
        app = FastAPI()
        register_accounting_link_repair_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "finance_roles": ("директор", "зам_директора", "бухгалтер"),
            "get_db": self.get_db,
            "build_cookie_session_authentication": self.authenticate,
            "preview_accounting_link_repairs": self.run_preview,
            "apply_accounting_link_repairs": self.run_apply,
        })
        self.client = TestClient(app)

    def authenticate(
        self, request, authorization=None, csrf_token=None, *, require_csrf=True,
    ):
        self.auth_calls.append((
            request.method, authorization, csrf_token, require_csrf,
        ))
        if self.auth_error:
            raise self.auth_error
        return dict(AUTHENTICATION)

    def run_preview(self, get_db, authentication, company_id, finance_roles):
        self.preview_calls.append((
            get_db, authentication, company_id, finance_roles,
        ))
        if self.runtime_error:
            raise self.runtime_error
        return copy.deepcopy(self.preview)

    def run_apply(
        self,
        get_db,
        authentication,
        company_id,
        finance_roles,
        *,
        expected_repair_count,
        expected_plan_sha256,
    ):
        self.apply_calls.append((
            get_db, authentication, company_id, finance_roles,
            expected_repair_count, expected_plan_sha256,
        ))
        if self.runtime_error:
            raise self.runtime_error
        return copy.deepcopy(self.applied)

    @staticmethod
    def headers(*, csrf=False, **overrides):
        headers = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }
        if csrf:
            headers["X-CSRF-Token"] = "csrf"
        headers.update(overrides)
        return headers


class AccountingLinkRepairRouteTests(unittest.TestCase):
    def assert_no_store(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(response.headers["pragma"], "no-cache")

    def test_registration_is_default_off_and_has_two_exact_routes_when_enabled(self):
        for deps in (
            {"enabled": False},
            {"enabled": True, "allowed_company_ids": frozenset()},
            {"enabled": True, "allowed_company_ids": frozenset({True})},
            {
                "enabled": True,
                "allowed_company_ids": frozenset({4}),
                "finance_roles": ["бухгалтер"],
            },
        ):
            app = FakeApp()
            register_accounting_link_repair_routes(app, deps)
            self.assertEqual(app.routes, {})

        app = FakeApp()
        no_call = lambda *_args, **_kwargs: None
        register_accounting_link_repair_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "finance_roles": ("бухгалтер",),
            "get_db": object(),
            "build_cookie_session_authentication": no_call,
            "preview_accounting_link_repairs": no_call,
            "apply_accounting_link_repairs": no_call,
        })
        self.assertEqual(set(app.routes), {("GET", PATH), ("POST", PATH)})

    def test_get_uses_cookie_without_csrf_and_returns_only_validated_preview(self):
        harness = Harness()

        response = harness.client.get(PATH, headers=harness.headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), PREVIEW)
        self.assertEqual(harness.auth_calls, [("GET", None, None, False)])
        self.assertEqual(len(harness.preview_calls), 1)
        self.assert_no_store(response)

    def test_post_requires_csrf_and_applies_only_the_exact_preview(self):
        harness = Harness()
        body = {
            "confirm": "APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS",
            "expectedRepairCount": 1,
            "expectedPlanSha256": "b" * 64,
        }

        response = harness.client.post(
            PATH, headers=harness.headers(csrf=True), json=body,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), APPLIED)
        self.assertEqual(harness.auth_calls, [("POST", None, "csrf", True)])
        self.assertEqual(harness.apply_calls[0][4:], (1, "b" * 64))
        self.assert_no_store(response)

    def test_malformed_extra_duplicate_and_oversized_bodies_fail_before_runtime(self):
        cases = (
            ({}, 422),
            ({
                "confirm": "WRONG",
                "expectedRepairCount": 1,
                "expectedPlanSha256": "b" * 64,
            }, 422),
            ({
                "confirm": "APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS",
                "expectedRepairCount": True,
                "expectedPlanSha256": "b" * 64,
            }, 422),
            ({
                "confirm": "APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS",
                "expectedRepairCount": 1,
                "expectedPlanSha256": "b" * 64,
                "extra": "forbidden",
            }, 422),
        )
        for body, status in cases:
            with self.subTest(body=body):
                harness = Harness()
                response = harness.client.post(
                    PATH, headers=harness.headers(csrf=True), json=body,
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(harness.apply_calls, [])

        harness = Harness()
        response = harness.client.post(
            PATH,
            headers={**harness.headers(csrf=True), "Content-Type": "application/json"},
            content=b'{' + b'"padding":"' + b'x' * 5000 + b'"}',
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(harness.apply_calls, [])

        harness = Harness()
        response = harness.client.post(
            PATH,
            headers={**harness.headers(csrf=True), "Content-Type": "application/json"},
            content=(
                b'{"confirm":"APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS",'
                b'"expectedRepairCount":1,"expectedRepairCount":1,'
                + b'"expectedPlanSha256":"' + b'b' * 64 + b'"}'
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(harness.apply_calls, [])

    def test_auth_company_and_runtime_errors_have_fixed_statuses(self):
        auth_cases = (
            (CookieSessionAuthenticationError("cookie_session_authentication_required"), 401),
            (CookieSessionAuthenticationError("cookie_session_csrf_invalid"), 403),
        )
        body = {
            "confirm": "APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS",
            "expectedRepairCount": 1,
            "expectedPlanSha256": "b" * 64,
        }
        for error, status in auth_cases:
            harness = Harness(auth_error=error)
            response = harness.client.post(
                PATH, headers=harness.headers(csrf=True), json=body,
            )
            self.assertEqual(response.status_code, status)
            self.assertEqual(harness.apply_calls, [])

        harness = Harness()
        response = harness.client.get(
            PATH, headers=harness.headers(**{"X-Company-Id": "5"}),
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(harness.preview_calls, [])

        runtime_cases = (
            ("accounting_link_repair_input_invalid", 422),
            ("accounting_link_repair_authentication_required", 401),
            ("accounting_link_repair_request_forbidden", 403),
            ("accounting_link_repair_plan_stale", 409),
            ("accounting_link_repair_plan_blocked", 409),
            ("accounting_link_repair_busy", 429),
            ("accounting_link_repair_write_failed", 503),
        )
        for code, status in runtime_cases:
            with self.subTest(code=code):
                harness = Harness(
                    runtime_error=AccountingLinkRepairRuntimeError(code),
                )
                response = harness.client.post(
                    PATH, headers=harness.headers(csrf=True), json=body,
                )
                self.assertEqual(response.status_code, status)
                self.assert_no_store(response)

    def test_aggregate_mode_bearer_only_and_unknown_methods_fail_closed(self):
        harness = Harness()
        response = harness.client.get(
            PATH,
            headers=harness.headers(**{"X-Company-Mode": "all_companies"}),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(harness.preview_calls, [])

        harness = Harness(auth_error=CookieSessionAuthenticationError(
            "cookie_session_authentication_required",
        ))
        response = harness.client.get(
            PATH,
            headers={
                "Authorization": "Bearer forbidden",
                "X-Company-Id": "4",
                "X-Company-Mode": "company",
            },
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(harness.preview_calls, [])

        harness = Harness()
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = harness.client.request(
                    method, PATH, headers=harness.headers(), json={},
                )
                self.assertEqual(response.status_code, 405)

    def test_private_or_malformed_runtime_results_are_not_exposed(self):
        harness = Harness(preview={**PREVIEW, "privateRows": ["SECRET"]})
        response = harness.client.get(PATH, headers=harness.headers())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SECRET", response.text)

    def test_main_frontend_and_nginx_register_only_the_exact_default_off_route(self):
        main = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        api = (PROJECT_ROOT / "src/api.js").read_text(encoding="utf-8")
        nginx = (
            PROJECT_ROOT / "ops-nginx-accounting-exception-checks.conf"
        ).read_text(encoding="utf-8")

        self.assertIn("register_accounting_link_repair_routes", main)
        self.assertIn("preview_accounting_link_repairs", main)
        self.assertIn("apply_accounting_link_repairs", main)
        self.assertEqual(
            main.count('ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED'), 1,
        )
        self.assertIn(r"/^\/accounting-exception-link-repairs$/", api)
        self.assertEqual(
            nginx.count("location = /accounting-exception-link-repairs {"), 1,
        )
        self.assertIn("client_max_body_size 1k;", nginx)
        self.assertIn(
            "error_page 429 = @accounting_link_repair_429;", nginx,
        )
        self.assertEqual(
            nginx.count("location @accounting_link_repair_429 {"), 1,
        )
        self.assertIn(
            "{\"detail\":\"accounting_link_repair_busy\"}", nginx,
        )
        self.assertIn(
            "limit_req zone=accounting_link_repair_limit burst=2 nodelay;",
            nginx,
        )
        self.assertIn("limit_conn accounting_link_repair_conn 1;", nginx)
        self.assertNotIn(
            "limit_req zone=accounting_exception_review_limit burst=2 nodelay;\n"
            "    limit_conn accounting_link_repair_conn 1;",
            nginx,
        )
        self.assertNotIn("location ^~ /accounting-exception-link-repairs", nginx)

    def test_production_smoke_checks_accounting_review_and_repair_routes(self):
        smoke = (
            PROJECT_ROOT / "scripts/prod-smoke-check.sh"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'check_not_spa_fallback "accounting exception checks route" '
            '"$BASE_URL/accounting-exception-checks" "401 403 404 422 429"',
            smoke,
        )

    def test_protected_smoke_uses_cookie_session_for_read_only_accounting_checks(self):
        smoke = (
            PROJECT_ROOT / "scripts/prod-smoke-check.sh"
        ).read_text(encoding="utf-8")
        helper_start = smoke.index("check_cookie_json_predicate() {")
        helper_end = smoke.index("\n}\n\ncheck_not_spa_fallback()", helper_start)
        helper = smoke[helper_start:helper_end]

        self.assertIn('smoke_cookie_jar="$(mktemp)"', smoke)
        self.assertGreaterEqual(smoke.count('-c "$smoke_cookie_jar"'), 2)
        self.assertIn('-b "$smoke_cookie_jar"', smoke)
        self.assertIn('-b "$cookie_jar"', helper)
        self.assertIn('-H "X-Company-Id: $company_id"', helper)
        self.assertIn("-H 'X-Company-Mode: company'", helper)
        self.assertNotIn("-X POST", helper)
        self.assertIn('rm -f "$body_file"', helper)
        self.assertIn("trap 'rm -f", smoke)
        self.assertIn('${SMOKE_COMPANY_ID:-}', smoke)
        self.assertIn(
            'check_cookie_json_predicate "protected accounting checks" '
            '"$BASE_URL/accounting-exception-checks"',
            smoke,
        )
        self.assertIn(
            'check_cookie_json_predicate "protected accounting link repairs" '
            '"$BASE_URL/accounting-exception-link-repairs"',
            smoke,
        )
        self.assertNotIn(
            'check_cookie_json_predicate "protected accounting link repairs post"',
            smoke,
        )
        self.assertIn(
            'check_not_spa_fallback "accounting link repairs route" '
            '"$BASE_URL/accounting-exception-link-repairs" '
            '"401 403 404 422 429"',
            smoke,
        )
        self.assertIn(
            'check_post_not_spa_fallback "accounting link repairs post route" '
            '"$BASE_URL/accounting-exception-link-repairs" '
            '"401 403 404 415 422 429"',
            smoke,
        )


if __name__ == "__main__":
    unittest.main()
