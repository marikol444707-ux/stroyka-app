"""A9.4d end-to-end HTTP/auth closure proofs for the default-off route."""

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import auth
from backend.features.warehouse_recommendation_preview import runtime_budget
from backend.features.warehouse_recommendation_preview import runtime_contract
from backend.features.warehouse_recommendation_preview import runtime_preview
from backend.features.warehouse_recommendation_preview import runtime_routes
from backend.features.warehouse_recommendation_preview.test_runtime_preview import (
    _Clock,
    _Connection,
    _RawCursor,
)
from backend.features.warehouse_recommendation_preview.test_runtime_routes import (
    BODY,
    DB_CONFIG,
    PATH,
)


_AUTH_SECRET = "warehouse-anomaly-http-closure-secret"
_SESSION_COOKIE = "A" * 64
_OTHER_SESSION_COOKIE = "B" * 64


def _headers(csrf_token, **extra):
    headers = {
        "Content-Type": "application/json",
        "Cookie": (
            auth.AUTH_SESSION_COOKIE_NAME + "=" + _SESSION_COOKIE
        ),
        "X-CSRF-Token": csrf_token,
        "X-Company-Id": "4",
        "X-Company-Mode": "company",
    }
    headers.update(extra)
    return headers


def _register(app, run_preview):
    runtime_routes.register_warehouse_anomaly_preview_routes(app, {
        "enabled": True,
        "allowed_company_ids": frozenset({4}),
        "db_config": DB_CONFIG,
        "build_cookie_session_authentication": (
            auth.build_cookie_session_authentication
        ),
        "parse_warehouse_anomaly_runtime_claims": (
            runtime_contract._parse_warehouse_anomaly_runtime_claims
        ),
        "run_warehouse_anomaly_runtime_preview": run_preview,
    })


class WarehouseAnomalyRuntimeHttpClosureTests(unittest.TestCase):
    def assert_fixed_error(self, response, status, detail):
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
        self.assertNotIn("etag", response.headers)

    def test_real_cookie_csrf_boundary_rejects_spoofed_requests_before_runtime(self):
        runtime_calls = []

        def no_runtime(*args, **kwargs):
            runtime_calls.append((args, kwargs))
            raise AssertionError("rejected authentication reached runtime")

        app = FastAPI()
        _register(app, no_runtime)
        client = TestClient(app)
        with mock.patch.object(auth, "AUTH_SECRET", _AUTH_SECRET):
            valid_csrf = auth._create_csrf_token(_SESSION_COOKIE)
            foreign_csrf = auth._create_csrf_token(_OTHER_SESSION_COOKIE)
            cases = (
                ({"Cookie": "", "X-CSRF-Token": valid_csrf}, 401),
                ({"X-CSRF-Token": ""}, 403),
                ({"X-CSRF-Token": foreign_csrf}, 403),
                ({"Authorization": "Bearer PRIVATE"}, 401),
            )
            for overrides, status in cases:
                with self.subTest(overrides=tuple(overrides), status=status):
                    response = client.post(
                        PATH,
                        headers=_headers(valid_csrf, **overrides),
                        json=BODY,
                    )
                    expected = (
                        "warehouse_anomaly_preview_request_forbidden"
                        if status == 403
                        else "warehouse_anomaly_preview_authentication_required"
                    )
                    self.assert_fixed_error(response, status, expected)
        self.assertEqual(runtime_calls, [])

    def test_real_http_runner_keeps_live_actor_project_precedence_and_cleanup(self):
        cases = (
            (
                {"actor_count": 0, "project_exists": False},
                401,
                "warehouse_anomaly_preview_authentication_required",
            ),
            (
                {"actor_count": 0, "project_exists": True},
                401,
                "warehouse_anomaly_preview_authentication_required",
            ),
            (
                {"actor_count": 2, "project_exists": True},
                401,
                "warehouse_anomaly_preview_authentication_required",
            ),
            (
                {"actor_count": 1, "project_exists": False},
                404,
                "warehouse_anomaly_preview_not_found",
            ),
            (
                {"actor_count": True, "project_exists": True},
                503,
                "warehouse_anomaly_preview_unavailable",
            ),
        )
        for auth_row, status, detail in cases:
            with self.subTest(auth_row=auth_row):
                raw_cursor = _RawCursor([
                    [dict(runtime_budget._EXPECTED_SETTINGS_ROW)],
                    [dict(auth_row)],
                ])
                connection = _Connection(raw_cursor)
                connect_calls = []

                def connect(**kwargs):
                    connect_calls.append(dict(kwargs))
                    return connection

                def run_preview(*args, **kwargs):
                    return runtime_preview.run_warehouse_anomaly_runtime_preview(
                        *args,
                        **kwargs,
                        clock=_Clock(),
                        connect=connect,
                    )

                app = FastAPI()
                _register(app, run_preview)
                with mock.patch.object(auth, "AUTH_SECRET", _AUTH_SECRET):
                    csrf = auth._create_csrf_token(_SESSION_COOKIE)
                    response = TestClient(app).post(
                        PATH, headers=_headers(csrf), json=BODY,
                    )

                self.assert_fixed_error(response, status, detail)
                self.assertEqual(len(connect_calls), 1)
                self.assertEqual(connection.close_calls, 1)
                self.assertEqual(raw_cursor.close_calls, 1)
                self.assertEqual(raw_cursor.fetchall_calls, 2)
                self.assertEqual(len(raw_cursor.execute_calls), 4)
                self.assertEqual(
                    raw_cursor.execute_calls[-1],
                    (runtime_budget._ROLLBACK_SQL, ()),
                )
                self.assertEqual(raw_cursor.result_sets, [])

                auth_sql = raw_cursor.execute_calls[2][0].upper()
                for required in (
                    "SESSION.TWO_FACTOR_PASSED IS TRUE",
                    "ACTOR_USER.ACTIVE IS TRUE",
                    "ACTOR_USER.TWO_FACTOR_ENABLED IS TRUE",
                    "MEMBERSHIP.ROLE='ДИРЕКТОР'",
                    "MEMBERSHIP.COMPANY_ID=%S",
                    "PROJECT.COMPANY_ID=%S",
                ):
                    self.assertIn(required, auth_sql)
                for forbidden in (
                    "UPDATE ", "INSERT ", "DELETE ", "FOR UPDATE",
                    "LAST_SEEN_AT", "ALL_COMPANIES",
                ):
                    self.assertNotIn(forbidden, auth_sql)


if __name__ == "__main__":
    unittest.main()
