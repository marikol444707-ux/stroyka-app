import ast
import json
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import CookieSessionAuthenticationError
from backend.features.assignment_daily_drafts.assignment_projection import (
    AssignmentDraft,
    AssignmentDraftItem,
    AssignmentDraftScope,
    AssignmentDraftSummary,
)
from backend.features.assignment_daily_drafts.projection import (
    AssignmentDailyDraftScope,
    DailyWorkDraft,
    DailyWorkDraftItem,
    DailyWorkDraftSummary,
)
from backend.features.assignment_daily_drafts.runtime_preview import (
    AssignmentDailyPreviewError,
    run_authorized_assignment_daily_snapshot,
)
from backend.features.assignment_daily_drafts.runtime_routes import (
    register_assignment_daily_draft_preview_routes,
)
from backend.features.assignment_daily_drafts.snapshot import (
    AssignmentDailySnapshot,
    AssignmentDailySnapshotRequest,
)
from backend.features.assignment_daily_drafts.test_snapshot import (
    _assignment_row,
    _context_row,
    _daily_row,
)


PATH = "/assignment-daily-draft-previews"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
NGINX_PATH = PROJECT_ROOT / "ops-nginx-assignment-daily-draft-preview.conf"
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
BODY = {
    "projectId": 10,
    "date": "2026-08-21",
    "estimateId": 80,
    "estimateVersionId": 4,
    "workPackage": "Слаботочка",
}


def _snapshot():
    request = AssignmentDailySnapshotRequest(
        1, 10, "2026-08-21", 80, 4, "Слаботочка",
    )
    assignment = AssignmentDraft(
        AssignmentDraftScope(1, 10, 80, 4, "Слаботочка"),
        "ready",
        (AssignmentDraftItem(
            80, 4, 0, 0, "work-1", "Раздел", "Монтаж", "м",
            "10", "4", "6", "Слаботочка", None,
        ),),
        AssignmentDraftSummary(1, 1, 0),
        (),
    )
    daily = DailyWorkDraft(
        AssignmentDailyDraftScope(1, 10, "2026-08-21"),
        "ready",
        (DailyWorkDraftItem(
            7, "Монтаж", "м", "2.5", 31, "Иван Петров",
            "Слаботочка", "Подтверждено",
        ),),
        DailyWorkDraftSummary(1, 1, 1),
        (),
    )
    return AssignmentDailySnapshot(request, "ready", assignment, daily, ())


class _FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path, **kwargs):
        def decorate(func):
            self.routes[("POST", path)] = (func, kwargs)
            return func
        return decorate


class _Deps(dict):
    def __init__(self, values):
        super().__init__(values)
        self.read_keys = []

    def __getitem__(self, key):
        self.read_keys.append(key)
        return super().__getitem__(key)


class _RouteHarness:
    def __init__(
        self,
        *,
        auth_error=None,
        runtime_error=None,
        result=None,
        reject_authorization=False,
    ):
        self.auth_error = auth_error
        self.runtime_error = runtime_error
        self.result = result
        self.reject_authorization = reject_authorization
        self.auth_calls = []
        self.runtime_calls = []
        self.app = FastAPI()
        register_assignment_daily_draft_preview_routes(self.app, {
            "enabled": True,
            "allowed_company_ids": frozenset({1}),
            "get_db": object(),
            "build_cookie_session_authentication": self.authenticate,
            "run_authorized_assignment_daily_snapshot": self.run,
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
        self.auth_calls.append((authorization, csrf_token, require_csrf))
        if self.auth_error is not None:
            raise self.auth_error
        if self.reject_authorization and authorization is not None:
            raise CookieSessionAuthenticationError(
                "cookie_session_authentication_required"
            )
        return dict(AUTHENTICATION)

    def run(self, get_db, authentication, request):
        self.runtime_calls.append((get_db, authentication, request))
        if self.runtime_error is not None:
            raise self.runtime_error
        return _snapshot() if self.result is None else self.result

    @staticmethod
    def headers(**overrides):
        value = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-CSRF-Token": "csrf",
            "X-Company-Id": "1",
            "X-Company-Mode": "company",
        }
        value.update(overrides)
        return value


class AssignmentDailyDraftRouteTests(unittest.TestCase):
    def test_registration_is_default_off_and_fail_closed(self):
        for values in (
            {"enabled": False},
            {"enabled": True, "allowed_company_ids": frozenset()},
            {"enabled": True, "allowed_company_ids": frozenset({True})},
        ):
            with self.subTest(values=values):
                app = _FakeApp()
                deps = _Deps(values)
                self.assertIsNone(
                    register_assignment_daily_draft_preview_routes(app, deps)
                )
                self.assertEqual(app.routes, {})
                self.assertEqual(deps.read_keys, [])

    def test_cookie_csrf_company_and_exact_body_reach_runtime(self):
        harness = _RouteHarness()

        response = harness.client.post(
            PATH,
            headers=harness.headers(),
            json=BODY,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(harness.auth_calls, [(None, "csrf", True)])
        self.assertEqual(len(harness.runtime_calls), 1)
        _get_db, authentication, request = harness.runtime_calls[0]
        self.assertEqual(authentication, AUTHENTICATION)
        self.assertEqual(
            request,
            AssignmentDailySnapshotRequest(
                1, 10, "2026-08-21", 80, 4, "Слаботочка",
            ),
        )
        value = response.json()
        self.assertEqual(set(value), {
            "version", "state", "companyId", "projectId", "date",
            "assignmentDraft", "dailyWorkDraft", "review", "previewOnly",
            "applyAllowed", "writesAttempted", "readOnlyTransaction",
            "rolledBack",
        })
        self.assertEqual(value["assignmentDraft"]["items"][0]["assignee"], None)
        self.assertEqual(value["dailyWorkDraft"]["items"][0]["quantity"], "2.5")
        self.assertIs(value["previewOnly"], True)
        self.assertIs(value["applyAllowed"], False)
        self.assertEqual(value["writesAttempted"], 0)
        self.assertNotIn("price", json.dumps(value).lower())

    def test_cookie_and_csrf_fail_before_runtime(self):
        for code, expected_status in (
            ("cookie_session_authentication_required", 401),
            ("cookie_session_csrf_invalid", 403),
        ):
            with self.subTest(code=code):
                harness = _RouteHarness(
                    auth_error=CookieSessionAuthenticationError(code)
                )
                response = harness.client.post(
                    PATH,
                    headers=harness.headers(),
                    json=BODY,
                )
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(harness.runtime_calls, [])

        bearer = _RouteHarness(reject_authorization=True)
        response = bearer.client.post(
            PATH,
            headers=bearer.headers(**{"Authorization": "Bearer PRIVATE"}),
            json=BODY,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(bearer.runtime_calls, [])
        self.assertNotIn("PRIVATE", response.text)

    def test_allowlist_and_malformed_body_fail_before_runtime(self):
        harness = _RouteHarness()
        foreign = harness.client.post(
            PATH,
            headers=harness.headers(**{"X-Company-Id": "2"}),
            json=BODY,
        )
        duplicate = harness.client.post(
            PATH,
            headers=harness.headers(**{"Content-Type": "application/json"}),
            content=(
                '{"projectId":10,"projectId":11,"date":"2026-08-21",'
                '"estimateId":80,"estimateVersionId":4,'
                '"workPackage":"Слаботочка"}'
            ),
        )
        oversized = harness.client.post(
            PATH,
            headers=harness.headers(**{"Content-Type": "application/json"}),
            content=b"{" + b" " * 4096 + b"}",
        )

        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(duplicate.status_code, 422)
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(harness.runtime_calls, [])

    def test_fixed_runtime_errors_do_not_leak(self):
        cases = (
            ("assignment_daily_preview_not_found", 404),
            ("assignment_daily_snapshot_input_invalid", 422),
            ("assignment_daily_snapshot_read_failed", 503),
        )
        for code, status in cases:
            with self.subTest(code=code):
                harness = _RouteHarness(
                    runtime_error=AssignmentDailyPreviewError(code)
                )
                response = harness.client.post(
                    PATH,
                    headers=harness.headers(),
                    json=BODY,
                )
                self.assertEqual(response.status_code, status)
                self.assertNotIn("private", response.text.lower())

    def test_nested_foreign_scope_or_unknown_review_never_reaches_response(self):
        original = _snapshot()
        foreign_daily = DailyWorkDraft(
            AssignmentDailyDraftScope(2, 10, "2026-08-21"),
            original.daily_work_draft.state,
            original.daily_work_draft.items,
            original.daily_work_draft.summary,
            original.daily_work_draft.review_codes,
        )
        unknown_review = AssignmentDailySnapshot(
            original.request,
            "review_required",
            original.assignment_draft,
            original.daily_work_draft,
            ("PRIVATE_DATABASE_DETAIL",),
        )
        foreign_scope = AssignmentDailySnapshot(
            original.request,
            original.state,
            original.assignment_draft,
            foreign_daily,
            original.review_codes,
        )
        for result in (foreign_scope, unknown_review):
            with self.subTest(result=result):
                harness = _RouteHarness(result=result)
                response = harness.client.post(
                    PATH,
                    headers=harness.headers(),
                    json=BODY,
                )
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("PRIVATE", response.text)


class _Cursor:
    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.current = []
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        self.current = self.result_sets.pop(0) if self.result_sets else []

    def fetchall(self):
        return [dict(row) for row in self.current]

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.session = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1
        raise AssertionError("preview must never commit")

    def close(self):
        self.closed = True


class AssignmentDailyAuthorizedRuntimeTests(unittest.TestCase):
    def test_authorized_leader_uses_same_read_only_snapshot_and_rolls_back(self):
        for role in ("директор", "зам_директора"):
            with self.subTest(role=role):
                cursor = _Cursor([
                    [],
                    [{"actor_count": 1, "project_exists": True, "role": role}],
                    [_context_row()],
                    [_assignment_row()],
                    [_daily_row()],
                ])
                connection = _Connection(cursor)
                request = AssignmentDailySnapshotRequest(
                    1, 10, "2026-08-21", 80, 4, "Слаботочка",
                )

                result = run_authorized_assignment_daily_snapshot(
                    lambda: connection,
                    AUTHENTICATION,
                    request,
                )

                self.assertEqual(result.state, "ready")
                self.assertEqual(connection.session, {
                    "readonly": True,
                    "autocommit": False,
                    "isolation_level": "REPEATABLE READ",
                })
                self.assertEqual(len(cursor.calls), 5)
                authorization_sql, authorization_params = cursor.calls[1]
                self.assertIn(
                    "membership.role IN ('директор','зам_директора')",
                    authorization_sql,
                )
                self.assertEqual(
                    authorization_params,
                    ("a" * 64, 1, 2, 10, 1),
                )
                self.assertEqual(connection.rollbacks, 1)
                self.assertEqual(connection.commits, 0)
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def test_unauthorized_or_ambiguous_actor_stops_before_business_reads(self):
        for actor_row in (
            {"actor_count": 0, "project_exists": False, "role": None},
            {"actor_count": 2, "project_exists": False, "role": None},
            {"actor_count": 1, "project_exists": False, "role": "директор"},
            {"actor_count": 1, "project_exists": True, "role": "прораб"},
        ):
            with self.subTest(actor_row=actor_row):
                cursor = _Cursor([[], [actor_row]])
                connection = _Connection(cursor)
                with self.assertRaises(AssignmentDailyPreviewError) as raised:
                    run_authorized_assignment_daily_snapshot(
                        lambda: connection,
                        AUTHENTICATION,
                        AssignmentDailySnapshotRequest(
                            1, 10, "2026-08-21", 80, 4, "Слаботочка",
                        ),
                    )
                self.assertEqual(
                    raised.exception.args,
                    ("assignment_daily_preview_not_found",),
                )
                self.assertEqual(len(cursor.calls), 2)
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(connection.closed)

    def test_invalid_authentication_never_opens_database(self):
        opened = []
        with self.assertRaises(AssignmentDailyPreviewError) as raised:
            run_authorized_assignment_daily_snapshot(
                lambda: opened.append(True),
                {"authenticationKind": "bearer", "sessionHash": "a" * 64},
                AssignmentDailySnapshotRequest(
                    1, 10, "2026-08-21", 80, 4, "Слаботочка",
                ),
            )
        self.assertEqual(
            raised.exception.args,
            ("assignment_daily_snapshot_input_invalid",),
        )
        self.assertEqual(opened, [])

    def test_main_registration_is_exactly_default_off(self):
        main = Path(__file__).resolve().parents[3] / "backend" / "main.py"
        source = main.read_text(encoding="utf-8")
        self.assertIn(
            'os.getenv("ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED") == "true"',
            source,
        )
        self.assertIn("ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS", source)
        self.assertIn("register_assignment_daily_draft_preview_routes(app", source)

    def test_global_api_error_writer_skips_only_the_exact_preview_path(self):
        main = Path(__file__).resolve().parents[3] / "backend" / "main.py"
        tree = ast.parse(main.read_text(encoding="utf-8"))
        helper = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_api_error_logging_enabled_for_path"
        )
        module = ast.Module(body=[helper], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {}
        exec(compile(module, str(main), "exec"), namespace)
        enabled = namespace["_api_error_logging_enabled_for_path"]

        self.assertIs(enabled(PATH), False)
        self.assertIs(enabled(PATH + "/"), True)
        self.assertIs(enabled("/assignments"), True)

    def test_local_nginx_contract_has_exact_capacity_and_json_errors(self):
        source = NGINX_PATH.read_text(encoding="utf-8")
        exact_fragments = (
            "limit_req_zone $binary_remote_addr "
            "zone=assignment_daily_draft_preview_limit:10m rate=6r/m;",
            "limit_conn_zone $server_name "
            "zone=assignment_daily_draft_preview_conn:10m;",
            "location = /assignment-daily-draft-previews {",
            "limit_req zone=assignment_daily_draft_preview_limit "
            "burst=1 nodelay;",
            "limit_conn assignment_daily_draft_preview_conn 1;",
            "limit_req_status 429;",
            "limit_conn_status 429;",
            "client_max_body_size 4k;",
            "proxy_connect_timeout 6s;",
            "proxy_send_timeout 10s;",
            "proxy_read_timeout 45s;",
            "error_page 413 = @assignment_daily_draft_preview_413;",
            "error_page 429 = @assignment_daily_draft_preview_429;",
            "location @assignment_daily_draft_preview_413 {",
            "location @assignment_daily_draft_preview_429 {",
            "return 413 "
            "'{\"detail\":\"assignment_daily_preview_request_too_large\"}';",
            "return 429 "
            "'{\"detail\":\"assignment_daily_preview_busy\"}';",
            "add_header Retry-After 10 always;",
            'add_header Cache-Control "no-store, max-age=0" always;',
            'add_header Pragma "no-cache" always;',
            'add_header Vary "Cookie, X-Company-Id, X-Company-Mode" always;',
        )
        for fragment in exact_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        self.assertEqual(
            source.count("location = /assignment-daily-draft-previews {"), 1,
        )
        self.assertEqual(
            source.count("zone=assignment_daily_draft_preview_limit:10m"), 1,
        )
        self.assertEqual(
            source.count("zone=assignment_daily_draft_preview_conn:10m"), 1,
        )
        self.assertEqual(source.count(
            'add_header Cache-Control "no-store, max-age=0" always;'
        ), 2)
        self.assertEqual(source.count(
            'add_header Pragma "no-cache" always;'
        ), 2)
        self.assertEqual(source.count(
            'add_header Vary "Cookie, X-Company-Id, X-Company-Mode" always;'
        ), 2)
        self.assertEqual(source.count("add_header Retry-After 10 always;"), 1)
        for private in (
            "$cookie_", "$http_x_csrf", "$http_x_company",
            "projectId", "estimateId", "estimateVersionId", "workPackage",
        ):
            self.assertNotIn(private, source)


if __name__ == "__main__":
    unittest.main()
