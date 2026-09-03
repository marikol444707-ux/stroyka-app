import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.platform_admin import routes


class FakeApp:
    def __init__(self):
        self.handlers = {}

    def _decorator(self, method, path):
        def register(function):
            self.handlers[(method, path)] = function
            return function

        return register

    def get(self, path, **_kwargs):
        return self._decorator("GET", path)

    def post(self, path, **_kwargs):
        return self._decorator("POST", path)

    def put(self, path, **_kwargs):
        return self._decorator("PUT", path)


class FakeCursor:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.results.pop(0) if self.results else None

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current.pop(0) if self.current else None
        value = self.current
        self.current = None
        return value

    def fetchall(self):
        if self.current is None:
            return []
        value = self.current if isinstance(self.current, list) else [self.current]
        self.current = None
        return value

    def close(self):
        pass


class FakeConnection:
    def __init__(self, results=None):
        self.cursor_instance = FakeCursor(results)
        self.autocommit = True
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def register_handlers(connection):
    app = FakeApp()

    def require_roles(*_roles):
        return lambda: {}

    routes.register_platform_admin_routes(app, {
        "get_db": lambda: connection,
        "require_roles": require_roles,
    })
    return app.handlers


def company_row(**overrides):
    row = {
        "id": 42,
        "name": "ООО Клиент",
        "platform_account_id": 3,
    }
    row.update(overrides)
    return row


def contract_row(**overrides):
    row = {
        "id": 101,
        "platform_account_id": 3,
        "company_id": 42,
        "number": "STK-2026-0101",
        "status": "active",
    }
    row.update(overrides)
    return row


def payment_row(**overrides):
    row = {
        "id": 701,
        "company_id": 42,
        "client_contract_id": None,
        "amount": 49900,
        "payment_date": "2026-09-03",
        "method": "transfer",
        "invoice_number": "INV-81",
        "status": "paid",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "notes": "Оплачено",
        "created_by": "Владелец",
        "company_name": "ООО Клиент",
        "platform_account_id": 3,
        "client_contract_number": None,
        "client_contract_status": None,
    }
    row.update(overrides)
    return row


class PaymentContractTests(unittest.TestCase):
    def test_list_includes_contract_metadata_with_exact_company_scope(self):
        connection = FakeConnection([[
            payment_row(
                client_contract_id=101,
                client_contract_number="STK-2026-0101",
                client_contract_status="active",
            ),
        ]])
        handlers = register_handlers(connection)

        result = handlers[("GET", "/system/payments")]({})

        self.assertEqual(result[0]["client_contract_id"], 101)
        self.assertEqual(result[0]["client_contract_number"], "STK-2026-0101")
        sql = connection.cursor_instance.calls[0][0]
        self.assertIn("LEFT JOIN platform_client_contracts", sql)
        self.assertIn("pc.company_id=p.company_id", sql)
        self.assertIn("pc.platform_account_id=c.platform_account_id", sql)

    def test_create_links_same_company_contract_and_commits(self):
        connection = FakeConnection([
            company_row(),
            contract_row(),
            {"id": 701},
        ])
        handlers = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("POST", "/system/payments")](
                {
                    "companyId": 42,
                    "clientContractId": 101,
                    "amount": 49900,
                    "paymentDate": "2026-09-03",
                    "method": "transfer",
                    "invoiceNumber": "INV-81",
                    "status": "paid",
                    "periodStart": "2026-09-01",
                },
                {"id": 1, "name": "Владелец"},
            )

        self.assertTrue(result["ok"])
        calls = connection.cursor_instance.calls
        self.assertIn("company_id=%s AND platform_account_id=%s", calls[1][0])
        self.assertIn("status <> 'cancelled'", calls[1][0])
        self.assertIn("client_contract_id", calls[2][0])
        self.assertIn(101, calls[2][1])
        self.assertEqual(connection.commits, 1)
        audit.assert_called_once()
        self.assertEqual(audit.call_args.kwargs["details"]["clientContractId"], 101)

    def test_create_rejects_foreign_or_cancelled_contract_without_insert(self):
        connection = FakeConnection([company_row(), None])
        handlers = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("POST", "/system/payments")](
                {
                    "companyId": 42,
                    "clientContractId": 202,
                    "amount": 49900,
                },
                {"id": 1, "name": "Владелец"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any(
            "INSERT INTO company_payments" in sql
            for sql, _params in connection.cursor_instance.calls
        ))
        self.assertEqual(connection.commits, 0)

    def test_existing_payment_can_be_linked_and_unlinked(self):
        linked = payment_row(
            client_contract_id=101,
            client_contract_number="STK-2026-0101",
            client_contract_status="active",
        )
        connection = FakeConnection([
            payment_row(),
            contract_row(),
            linked,
        ])
        handlers = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("PUT", "/system/payments/{id}/client-contract")](
                id=701,
                data={"clientContractId": 101},
                current_user={"id": 1, "name": "Владелец"},
            )

        self.assertTrue(result["changed"])
        self.assertEqual(result["payment"]["client_contract_id"], 101)
        self.assertEqual(result["payment"]["client_contract_number"], "STK-2026-0101")
        self.assertEqual(connection.commits, 1)
        self.assertEqual(
            audit.call_args.args[2],
            "company_payment_contract_linked",
        )

        second_connection = FakeConnection([
            linked,
            payment_row(),
        ])
        second_handlers = register_handlers(second_connection)
        with patch.object(routes, "_system_write_audit") as second_audit:
            second_result = second_handlers[(
                "PUT",
                "/system/payments/{id}/client-contract",
            )](
                id=701,
                data={"clientContractId": None},
                current_user={"id": 1, "name": "Владелец"},
            )

        self.assertIsNone(second_result["payment"]["client_contract_id"])
        self.assertEqual(second_connection.commits, 1)
        self.assertEqual(
            second_audit.call_args.args[2],
            "company_payment_contract_unlinked",
        )

    def test_provider_confirmation_copies_document_contract_to_payment(self):
        event = {
            "id": 901,
            "event_id": "provider-901",
            "provider": "yukassa",
            "provider_status": "succeeded",
            "trusted": True,
            "action_status": "received",
            "payment_id": None,
            "billing_document_id": 81,
            "billing_document_number": "INV-81",
            "billing_document_status": "issued",
            "billing_document_amount": 49900,
            "billing_document_currency": "RUB",
            "billing_payment_provider": "yukassa",
            "billing_period_start": None,
            "billing_period_end": None,
            "billing_client_contract_id": 101,
            "document_platform_account_id": 3,
            "document_company_id": 42,
            "company_id": 42,
            "platform_account_id": 3,
            "amount": 49900,
            "currency": "RUB",
            "company_name": "ООО Клиент",
        }
        closed_document = {
            "id": 81,
            "document_type": "invoice",
            "status": "closed",
        }
        connection = FakeConnection([
            event,
            {"id": 701},
            closed_document,
            {**event, "payment_id": 701, "action_status": "payment_recorded"},
        ])
        handlers = register_handlers(connection)

        with patch.object(routes, "_system_write_audit"):
            result = handlers[("POST", "/system/payment-events/{id}/confirm")](
                id=901,
                data={},
                current_user={"id": 1, "name": "Владелец"},
            )

        self.assertEqual(result["paymentId"], 701)
        select_sql = connection.cursor_instance.calls[0][0]
        self.assertIn("d.client_contract_id AS billing_client_contract_id", select_sql)
        insert_sql, insert_params = connection.cursor_instance.calls[1]
        self.assertIn("client_contract_id", insert_sql)
        self.assertIn(101, insert_params)


if __name__ == "__main__":
    unittest.main()
