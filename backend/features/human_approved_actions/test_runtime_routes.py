import ast
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import auth
from backend.auth import CookieSessionAuthenticationError


PROPOSAL_PATH = "/human-approved-actions/proposals"
DECISION_PATH = "/human-approved-actions/decisions"
HISTORY_PATH = "/human-approved-actions/history"
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
PROPOSAL_BODY = {
    "projectId": 9,
    "jobId": 123,
    "selected": {
        "subjectKind": "warehouseInvoice",
        "subjectId": 456,
        "anomalyCode": "warehouse_invoice_project_mismatch",
    },
}
DECISION_BODY = {
    "proposalId": 71,
    "proposalSha256": "b" * 64,
    "decision": "approve",
}
PROPOSAL_RECEIPT = {
    "humanActionReceiptVersion": 1,
    "state": "proposed",
    "actionKind": "warehouse_anomaly_review_acknowledged",
    "proposalId": 71,
    "proposalSha256": "b" * 64,
    "companyId": 4,
    "projectId": 9,
    "sourceJobId": 123,
    "subjectKind": "warehouseInvoice",
    "subjectId": 456,
    "actorUserId": 11,
    "actorMembershipId": 12,
    "expiresAt": "2026-08-23T12:15:00.000000Z",
    "writesAttempted": 2,
    "committed": True,
    "idempotent": False,
}
DECISION_RECEIPT = {
    "humanActionReceiptVersion": 1,
    "state": "applied",
    "actionKind": "warehouse_anomaly_review_acknowledged",
    "proposalId": 71,
    "proposalSha256": "b" * 64,
    "companyId": 4,
    "projectId": 9,
    "sourceJobId": 123,
    "subjectKind": "warehouseInvoice",
    "subjectId": 456,
    "actorUserId": 11,
    "actorMembershipId": 12,
    "eventId": 73,
    "auditEventId": 74,
    "writesAttempted": 3,
    "committed": True,
    "idempotent": False,
}
HISTORY_RESULT = {
    "humanActionHistoryVersion": 1,
    "companyId": 4,
    "projectId": 9,
    "items": [{
        "eventId": 73,
        "eventKind": "applied",
        "proposalId": 71,
        "proposalSha256": "b" * 64,
        "actionKind": "warehouse_anomaly_review_acknowledged",
        "sourceJobId": 123,
        "subjectKind": "warehouseInvoice",
        "subjectId": 456,
        "actorUserId": 11,
        "actorMembershipId": 12,
        "occurredAt": "2026-08-23T12:05:00.000000Z",
        "eventSha256": "c" * 64,
    }],
    "nextBeforeId": None,
}


class _FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path, **kwargs):
        def decorate(function):
            self.routes[("POST", path)] = (function, kwargs)
            return function
        return decorate

    def get(self, path, **kwargs):
        def decorate(function):
            self.routes[("GET", path)] = (function, kwargs)
            return function
        return decorate


class _DependencyMap(dict):
    def __init__(self, values):
        super().__init__(values)
        self.read_keys = []

    def __getitem__(self, key):
        self.read_keys.append(key)
        return super().__getitem__(key)


class _Harness:
    def __init__(
        self,
        routes,
        *,
        authentication_error=None,
        gate=None,
        proposal_result=None,
        history_result=None,
    ):
        self.authentication_error = authentication_error
        self.auth_calls = []
        self.proposal_calls = []
        self.decision_calls = []
        self.history_calls = []
        self.proposal_result = (
            dict(PROPOSAL_RECEIPT)
            if proposal_result is None
            else proposal_result
        )
        self.history_result = (
            HISTORY_RESULT if history_result is None else history_result
        )
        app = FastAPI()
        dependencies = {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "get_db": object(),
            "build_cookie_session_authentication": self.authenticate,
            "create_review_acknowledgement_proposal": self.create_proposal,
            "decide_review_acknowledgement": self.decide,
            "list_review_acknowledgement_history": self.history,
        }
        if gate is not None:
            dependencies["gate"] = gate
        routes.register_human_approved_action_routes(app, dependencies)
        self.client = TestClient(app)

    def authenticate(
        self, request, authorization=None, csrf_token=None, *, require_csrf=True,
    ):
        self.auth_calls.append((
            request.method,
            request.url.path,
            authorization,
            csrf_token,
            require_csrf,
        ))
        if self.authentication_error is not None:
            raise self.authentication_error
        return dict(AUTHENTICATION)

    def create_proposal(self, *args, **kwargs):
        self.proposal_calls.append((args, kwargs))
        return dict(self.proposal_result)

    def decide(self, *args, **kwargs):
        self.decision_calls.append((args, kwargs))
        return dict(DECISION_RECEIPT)

    def history(self, *args, **kwargs):
        self.history_calls.append((args, kwargs))
        return {
            **self.history_result,
            "items": [dict(item) for item in self.history_result["items"]],
        }

    @staticmethod
    def headers(**overrides):
        headers = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-CSRF-Token": "csrf",
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }
        headers.update(overrides)
        return headers


class HumanApprovedActionRuntimeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.human_approved_actions import runtime_routes
        cls.routes = runtime_routes

    def test_disabled_or_invalid_allowlist_registers_nothing(self):
        for values in (
            {"enabled": False},
            {"enabled": True, "allowed_company_ids": None},
            {"enabled": True, "allowed_company_ids": frozenset()},
            {"enabled": True, "allowed_company_ids": frozenset({True})},
            {"enabled": True, "allowed_company_ids": frozenset({0})},
            {"enabled": True, "allowed_company_ids": frozenset({4, 5})},
        ):
            with self.subTest(values=values):
                app = _FakeApp()
                deps = _DependencyMap(values)
                self.assertIsNone(
                    self.routes.register_human_approved_action_routes(app, deps)
                )
                self.assertEqual(app.routes, {})
                self.assertEqual(deps.read_keys, [])

    def test_valid_configuration_registers_three_exact_routes(self):
        app = _FakeApp()
        no_call = lambda *_args, **_kwargs: None
        self.routes.register_human_approved_action_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "get_db": object(),
            "build_cookie_session_authentication": no_call,
            "create_review_acknowledgement_proposal": no_call,
            "decide_review_acknowledgement": no_call,
            "list_review_acknowledgement_history": no_call,
        })
        self.assertEqual(set(app.routes), {
            ("POST", PROPOSAL_PATH),
            ("POST", DECISION_PATH),
            ("GET", HISTORY_PATH),
        })

    def test_proposal_decision_and_history_use_cookie_csrf_and_exact_scope(self):
        harness = _Harness(self.routes)

        proposal = harness.client.post(
            PROPOSAL_PATH,
            headers=harness.headers(),
            json=PROPOSAL_BODY,
        )
        decision = harness.client.post(
            DECISION_PATH,
            headers=harness.headers(),
            json=DECISION_BODY,
        )
        history = harness.client.get(
            HISTORY_PATH + "?projectId=9&limit=25&beforeId=80",
            headers=harness.headers(),
        )

        self.assertEqual(proposal.status_code, 200)
        self.assertEqual(proposal.json(), PROPOSAL_RECEIPT)
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json(), DECISION_RECEIPT)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json(), HISTORY_RESULT)
        self.assertEqual(harness.auth_calls, [
            ("POST", PROPOSAL_PATH, None, "csrf", True),
            ("POST", DECISION_PATH, None, "csrf", True),
            ("GET", HISTORY_PATH, None, "csrf", True),
        ])
        self.assertEqual(harness.proposal_calls[0][1], {
            "company_mode": "company",
            "company_id": "4",
            "body": PROPOSAL_BODY,
        })
        self.assertEqual(harness.decision_calls[0][1], {
            "company_mode": "company",
            "company_id": "4",
        })
        self.assertEqual(harness.decision_calls[0][0][2], DECISION_BODY)
        self.assertEqual(harness.history_calls[0][1], {
            "company_mode": "company",
            "company_id": "4",
            "project_id": 9,
            "before_event_id": 80,
            "limit": 25,
        })
        for response in (proposal, decision, history):
            self.assertEqual(
                response.headers.get("cache-control"),
                "no-store, max-age=0",
            )
            self.assertEqual(
                response.headers.get("vary"),
                "Cookie, X-Company-Id, X-Company-Mode",
            )

    def test_auth_scope_allowlist_and_body_fail_before_business_calls(self):
        cases = (
            ({"Authorization": "Bearer forbidden"}, 401),
            ({"X-CSRF-Token": ""}, 403),
            ({"X-Company-Mode": "all"}, 422),
            ({"X-Company-Id": "5"}, 404),
        )
        for overrides, status in cases:
            with self.subTest(overrides=overrides):
                authentication_error = None
                if "Authorization" in overrides:
                    authentication_error = CookieSessionAuthenticationError(
                        "cookie_session_authentication_required"
                    )
                elif overrides.get("X-CSRF-Token") == "":
                    authentication_error = CookieSessionAuthenticationError(
                        "cookie_session_csrf_invalid"
                    )
                harness = _Harness(
                    self.routes,
                    authentication_error=authentication_error,
                )
                response = harness.client.post(
                    PROPOSAL_PATH,
                    headers=harness.headers(**overrides),
                    json=PROPOSAL_BODY,
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(harness.proposal_calls, [])
                self.assertEqual(harness.decision_calls, [])
                self.assertEqual(harness.history_calls, [])

        harness = _Harness(self.routes)
        response = harness.client.post(
            PROPOSAL_PATH,
            headers={**harness.headers(), "Content-Type": "application/json"},
            content='{"projectId":9,"projectId":10}',
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(harness.proposal_calls, [])

    def test_payload_and_history_query_are_bounded_before_business_calls(self):
        harness = _Harness(self.routes)
        too_large = harness.client.post(
            PROPOSAL_PATH,
            headers=harness.headers(**{"Content-Type": "application/json"}),
            content=b'{' + b'"x":"' + b'a' * 5000 + b'"}',
        )
        invalid_history = harness.client.get(
            HISTORY_PATH + "?projectId=9&limit=101",
            headers=harness.headers(),
        )
        self.assertEqual(too_large.status_code, 413)
        self.assertEqual(invalid_history.status_code, 422)
        self.assertEqual(harness.proposal_calls, [])
        self.assertEqual(harness.history_calls, [])

    def test_history_rejects_unknown_or_duplicate_query_keys(self):
        for query in (
            "projectId=9&extra=1",
            "projectId=9&projectId=10",
            "projectId=9&limit=25&limit=26",
            "projectId=9&beforeId=80&beforeId=79",
        ):
            with self.subTest(query=query):
                harness = _Harness(self.routes)
                response = harness.client.get(
                    HISTORY_PATH + "?" + query,
                    headers=harness.headers(),
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(harness.history_calls, [])

    def test_public_results_must_match_request_and_page_cursor(self):
        mismatched = {
            **PROPOSAL_RECEIPT,
            "projectId": 10,
        }
        harness = _Harness(self.routes, proposal_result=mismatched)
        response = harness.client.post(
            PROPOSAL_PATH,
            headers=harness.headers(),
            json=PROPOSAL_BODY,
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("projectId", response.text)

        bad_history = {
            **HISTORY_RESULT,
            "nextBeforeId": 999,
        }
        harness = _Harness(self.routes, history_result=bad_history)
        response = harness.client.get(
            HISTORY_PATH + "?projectId=9&limit=25",
            headers=harness.headers(),
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("999", response.text)

    def test_one_concurrent_slot_and_bounded_rate_fail_before_kernel(self):
        clock_values = [100.0]
        gate = self.routes._HumanActionRouteGate(
            clock=lambda: clock_values[0],
        )
        held, reason, retry_after = gate.try_acquire(4, "proposal")
        self.assertIsNotNone(held)
        self.assertIsNone(reason)
        self.assertIsNone(retry_after)

        harness = _Harness(self.routes, gate=gate)
        busy = harness.client.post(
            PROPOSAL_PATH,
            headers=harness.headers(),
            json=PROPOSAL_BODY,
        )
        self.assertEqual(busy.status_code, 429)
        self.assertEqual(busy.json(), {"detail": "human_approved_action_busy"})
        self.assertEqual(busy.headers.get("retry-after"), "1")
        self.assertEqual(harness.proposal_calls, [])
        held.release()

        for _index in range(9):
            lease, reason, retry_after = gate.try_acquire(4, "decision")
            self.assertIsNotNone(lease)
            self.assertIsNone(reason)
            self.assertIsNone(retry_after)
            lease.release()
        lease, reason, retry_after = gate.try_acquire(4, "proposal")
        self.assertIsNone(lease)
        self.assertEqual(reason, "rate")
        self.assertEqual(retry_after, 60)

        clock_values[0] = 160.0
        lease, reason, retry_after = gate.try_acquire(4, "proposal")
        self.assertIsNotNone(lease)
        self.assertIsNone(reason)
        self.assertIsNone(retry_after)
        lease.release()

    def test_main_registration_is_strict_default_off_and_one_company_only(self):
        root = Path(__file__).resolve().parents[3]
        main_path = root / "backend" / "main.py"
        source = main_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(main_path))
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_parse_human_approved_action_company_ids"
        ]
        self.assertEqual(len(functions), 1)
        namespace = {}
        exec(compile(
            ast.Module(body=functions, type_ignores=[]),
            str(main_path),
            "exec",
        ), namespace)
        parse = namespace["_parse_human_approved_action_company_ids"]

        self.assertEqual(parse("4"), frozenset({4}))
        for raw in (
            None, "", "0", "04", "-1", " 4", "4 ", "4,5", "4,4",
            "9223372036854775808",
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(parse(raw))
        self.assertIn(
            'os.getenv("HUMAN_APPROVED_ACTIONS_HTTP_ENABLED") == "true"',
            source,
        )
        self.assertIn("HUMAN_APPROVED_ACTIONS_COMPANY_IDS", source)
        self.assertIn("register_human_approved_action_routes(app", source)

        package_source = Path(__file__).with_name("__init__.py").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("runtime_routes", package_source)
        self.assertEqual(self.routes.__all__, [])

    def test_real_cookie_csrf_rejects_missing_foreign_and_bearer_controls(self):
        calls = []

        def forbidden(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("authentication failure reached kernel")

        app = FastAPI()
        self.routes.register_human_approved_action_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "get_db": object(),
            "build_cookie_session_authentication": (
                auth.build_cookie_session_authentication
            ),
            "create_review_acknowledgement_proposal": forbidden,
            "decide_review_acknowledgement": forbidden,
            "list_review_acknowledgement_history": forbidden,
        })
        client = TestClient(app)
        session = "A" * 64
        foreign_session = "B" * 64
        with mock.patch.object(auth, "AUTH_SECRET", "a12-http-secret"):
            csrf = auth._create_csrf_token(session)
            foreign_csrf = auth._create_csrf_token(foreign_session)
            base = {
                "Cookie": auth.AUTH_SESSION_COOKIE_NAME + "=" + session,
                "X-CSRF-Token": csrf,
                "X-Company-Id": "4",
                "X-Company-Mode": "company",
            }
            cases = (
                ({"Cookie": ""}, 401),
                ({"X-CSRF-Token": ""}, 403),
                ({"X-CSRF-Token": foreign_csrf}, 403),
                ({"Authorization": "Bearer PRIVATE"}, 401),
            )
            for overrides, status in cases:
                with self.subTest(overrides=overrides):
                    response = client.post(
                        PROPOSAL_PATH,
                        headers={**base, **overrides},
                        json=PROPOSAL_BODY,
                    )
                    self.assertEqual(response.status_code, status)
                    self.assertNotIn("PRIVATE", response.text)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
