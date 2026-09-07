import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.features.client_account.subscription_access import (
    SUBSCRIPTION_READ_ONLY_CODE,
    register_subscription_read_only_middleware,
)


class FakeCursor:
    def __init__(self, company, queried_company_ids=None):
        self.company = dict(company)
        self.description = None
        self.queried_company_ids = queried_company_ids

    def execute(self, query, params=()):
        if "FROM companies" not in query:
            raise AssertionError("Unexpected query: " + " ".join(str(query).split()))
        if self.queried_company_ids is not None:
            self.queried_company_ids.append(params[0])

    def fetchone(self):
        return dict(self.company)

    def close(self):
        return None


class FakeConnection:
    def __init__(self, company):
        self.company = company
        self.rolled_back = False
        self.closed = False
        self.queried_company_ids = []

    def cursor(self, **_kwargs):
        return FakeCursor(self.company, self.queried_company_ids)

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


class ResourceSubscriptionContextTests(unittest.TestCase):
    def build(self, *, expired=False, resource_error=None, resource_context=None):
        connection = FakeConnection({
            "plan": "business",
            "plan_expires_at": dt.date(2026, 9, 1 if expired else 30),
            "payment_status": "active",
            "suspended_at": None,
        })
        resolve_resource = Mock(
            side_effect=resource_error,
            return_value=resource_context if resource_context is not None else {"companyId": 7},
        )
        resolve_work = Mock(side_effect=HTTPException(403, "Компания пользователя не назначена"))
        app = FastAPI()
        register_subscription_read_only_middleware(app, {
            "get_db": lambda: connection,
            "request_user_snapshot": lambda *_args: {"id": 42, "role": "поставщик", "companyId": None},
            "resolve_work_company_context": resolve_work,
            "resolve_resource_subscription_context": resolve_resource,
            "today": lambda: dt.date(2026, 9, 2),
        })

        @app.put("/supplier-offers/{offer_id}")
        def respond(offer_id: int):
            return {"saved": offer_id}

        return TestClient(app), connection, resolve_work, resolve_resource

    def test_addressed_supplier_without_work_company_uses_authorized_resource_owner(self):
        client, connection, resolve_work, _resolve_resource = self.build()
        response = client.put("/supplier-offers/9", headers={"X-Company-Id": "999"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"saved": 9})
        self.assertEqual(connection.queried_company_ids, [7])
        resolve_work.assert_not_called()
        self.assertTrue(connection.closed)

    def test_resource_company_subscription_still_blocks_supplier_write(self):
        client, connection, resolve_work, _resolve_resource = self.build(expired=True)
        response = client.put("/supplier-offers/9", headers={"X-Company-Id": "999"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], SUBSCRIPTION_READ_ONLY_CODE)
        self.assertEqual(connection.queried_company_ids, [7])
        resolve_work.assert_not_called()

    def test_resource_authorization_denial_is_not_replaced_by_work_company(self):
        client, _connection, resolve_work, _resolve_resource = self.build(
            resource_error=HTTPException(403, "Нет доступа к КП"),
        )
        response = client.put("/supplier-offers/9")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Нет доступа к КП")
        resolve_work.assert_not_called()

    def test_resource_lookup_failure_is_fail_closed(self):
        client, _connection, resolve_work, _resolve_resource = self.build(
            resource_error=RuntimeError("DB failure"),
        )
        response = client.put("/supplier-offers/9")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "subscription_check_unavailable")
        resolve_work.assert_not_called()

    def test_unhandled_resource_keeps_original_company_resolution(self):
        client, _connection, resolve_work, resolve_resource = self.build()
        resolve_resource.return_value = None
        response = client.put("/supplier-offers/9")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "company_context_invalid")
        resolve_work.assert_called_once()

    def test_handled_resource_without_owner_cannot_skip_subscription_check(self):
        client, _connection, _resolve_work, _resolve_resource = self.build(resource_context={})
        response = client.put("/supplier-offers/9")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
