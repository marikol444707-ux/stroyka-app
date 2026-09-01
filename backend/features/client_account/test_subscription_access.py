import datetime as dt
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.features.client_account.subscription_access import (
    SUBSCRIPTION_READ_ONLY_CODE,
    register_subscription_read_only_middleware,
)


class FakeCursor:
    def __init__(self, company):
        self.company = dict(company)
        self.description = None

    def execute(self, query, params=()):
        if "FROM companies" not in query:
            raise AssertionError("Unexpected query: " + " ".join(str(query).split()))

    def fetchone(self):
        return dict(self.company)

    def close(self):
        return None


class FakeConnection:
    def __init__(self, company):
        self.company = company
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return FakeCursor(self.company)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build_client(
    company,
    *,
    role="директор",
    get_db_override=None,
    request_user_snapshot_override=None,
):
    connections = []

    def get_db():
        connection = FakeConnection(company)
        connections.append(connection)
        return connection

    app = FastAPI()
    register_subscription_read_only_middleware(app, {
        "get_db": get_db_override or get_db,
        "request_user_snapshot": request_user_snapshot_override
        or (lambda _request, _cur: {"id": 42, "role": role}),
        "resolve_work_company_context": lambda *_args, **_kwargs: {
            "mode": "company",
            "companyId": 7,
        },
        "platform_staff_roles": ("system_owner", "platform_admin"),
        "today": lambda: dt.date(2026, 9, 2),
    })

    @app.get("/records")
    def list_records():
        return {"ok": True}

    @app.post("/records")
    def create_record():
        return {"created": True}

    @app.put("/records")
    def replace_record():
        return {"updated": True}

    @app.patch("/records")
    def update_record():
        return {"updated": True}

    @app.delete("/records")
    def delete_record():
        return {"deleted": True}

    return TestClient(app), connections


class SubscriptionReadOnlyMiddlewareTests(unittest.TestCase):
    def test_expired_company_can_still_read(self):
        client, connections = build_client({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 1),
            "payment_status": "active",
            "suspended_at": None,
        })

        response = client.get("/records")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(connections, [])

    def test_expired_company_cannot_create_change_or_delete_data(self):
        client, connections = build_client({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 1),
            "payment_status": "active",
            "suspended_at": None,
        })

        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(client, method)("/records")

                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["code"], SUBSCRIPTION_READ_ONLY_CODE)
                self.assertIn("только просмотр", response.json()["detail"].lower())
                self.assertTrue(response.json()["billingState"]["readOnly"])

        self.assertEqual(len(connections), 4)
        self.assertTrue(all(connection.rolled_back for connection in connections))
        self.assertTrue(all(connection.closed for connection in connections))

    def test_blocked_mutation_emits_correlated_structured_event(self):
        client, _connections = build_client({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 1),
            "payment_status": "active",
            "suspended_at": None,
        })

        with patch(
            "backend.features.client_account.subscription_access._write_structured_log"
        ) as write_log:
            response = client.post("/records", headers={"X-Request-Id": "subscription-test-1"})

        self.assertEqual(response.headers["X-Request-Id"], "subscription-test-1")
        event = write_log.call_args.args[0]
        self.assertEqual(event["event"], "subscription_write_blocked")
        self.assertEqual(event["correlationId"], "subscription-test-1")
        self.assertEqual(event["companyId"], 7)
        self.assertEqual(event["method"], "POST")
        self.assertNotIn("user", json.dumps(event).lower())

    def test_seven_day_warning_does_not_block_work(self):
        client, _connections = build_client({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 9),
            "payment_status": "active",
            "suspended_at": None,
        })

        response = client.post("/records")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"created": True})

    def test_platform_staff_can_restore_expired_company(self):
        client, connections = build_client({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 1),
            "payment_status": "active",
            "suspended_at": None,
        }, role="system_owner")

        response = client.post("/records")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(connections[0].rolled_back)
        self.assertTrue(connections[0].closed)

    def test_client_account_role_cannot_bypass_expired_company(self):
        client, _connections = build_client({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 1),
            "payment_status": "active",
            "suspended_at": None,
        }, role="account_owner")

        response = client.post("/records")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], SUBSCRIPTION_READ_ONLY_CODE)

    def test_subscription_check_failure_blocks_the_mutation(self):
        def unavailable_db():
            raise RuntimeError("database unavailable")

        client, _connections = build_client({}, get_db_override=unavailable_db)

        with patch(
            "backend.features.client_account.subscription_access._write_structured_log"
        ) as write_log:
            response = client.post("/records", headers={"X-Request-Id": "subscription-test-2"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "subscription_check_unavailable")
        self.assertEqual(response.headers["X-Request-Id"], "subscription-test-2")
        event = write_log.call_args.args[0]
        self.assertEqual(event["event"], "subscription_access_check_failed")
        self.assertEqual(event["errorType"], "RuntimeError")
        self.assertNotIn("database unavailable", json.dumps(event).lower())

    def test_missing_company_record_cannot_bypass_the_subscription_check(self):
        client, _connections = build_client({})

        with patch(
            "backend.features.client_account.subscription_access._write_structured_log"
        ) as write_log:
            response = client.post("/records")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "subscription_check_unavailable")
        event = write_log.call_args.args[0]
        self.assertEqual(event["event"], "subscription_access_check_failed")
        self.assertEqual(event["errorType"], "LookupError")
        self.assertNotIn("not found", json.dumps(event).lower())

    def test_user_snapshot_failure_cannot_bypass_the_subscription_check(self):
        def unavailable_snapshot(_request, _cur):
            raise RuntimeError("identity lookup unavailable")

        client, _connections = build_client(
            {},
            request_user_snapshot_override=unavailable_snapshot,
        )

        with patch(
            "backend.features.client_account.subscription_access._write_structured_log"
        ) as write_log:
            response = client.post("/records")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "subscription_check_unavailable")
        event = write_log.call_args.args[0]
        self.assertEqual(event["event"], "subscription_access_check_failed")
        self.assertEqual(event["errorType"], "RuntimeError")
        self.assertNotIn("identity lookup unavailable", json.dumps(event).lower())


if __name__ == "__main__":
    unittest.main()
