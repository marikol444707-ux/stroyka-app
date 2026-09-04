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
        self.closed = False

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
        self.closed = True


class FakeConnection:
    def __init__(self, results=None):
        self.cursor_instance = FakeCursor(results)
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


def document_row(**overrides):
    row = {
        "id": 81,
        "platform_account_id": 3,
        "company_id": 42,
        "client_contract_id": None,
        "document_type": "invoice",
        "number": "INV-81",
        "status": "draft",
        "amount": 49900,
        "company_name": "ООО Клиент",
        "platform_account_name": "Группа клиента",
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


class BillingDocumentContractTests(unittest.TestCase):
    def test_list_includes_current_contract_summary(self):
        connection = FakeConnection([[
            document_row(
                client_contract_id=101,
                client_contract_number="STK-2026-0101",
                client_contract_status="active",
            ),
        ]])
        handlers = register_handlers(connection)

        result = handlers[("GET", "/system/billing-documents")]({})

        self.assertEqual(result[0]["client_contract_id"], 101)
        self.assertEqual(result[0]["client_contract_number"], "STK-2026-0101")
        sql = connection.cursor_instance.calls[0][0]
        self.assertIn("LEFT JOIN platform_client_contracts", sql)
        self.assertIn("client_contract_number", sql)

    def test_contract_options_exclude_cancelled_contracts(self):
        connection = FakeConnection([[contract_row(company_name="ООО Клиент")]])
        handlers = register_handlers(connection)

        result = handlers[("GET", "/system/billing-contract-options")]({})

        self.assertEqual(result[0]["id"], 101)
        sql = connection.cursor_instance.calls[0][0]
        self.assertIn("status <> 'cancelled'", sql)

    def test_create_links_same_company_contract_and_keeps_link_optional(self):
        company = {"id": 42, "name": "ООО Клиент", "platform_account_id": 3}
        created = document_row(client_contract_id=101)
        connection = FakeConnection([company, contract_row(), created])
        handlers = register_handlers(connection)

        result = handlers[("POST", "/system/billing-documents")](
            {
                "companyId": 42,
                "clientContractId": 101,
                "documentType": "invoice",
                "status": "draft",
                "amount": 49900,
            },
            {"id": 1, "name": "Владелец"},
        )

        self.assertEqual(result["document"]["client_contract_id"], 101)
        calls = connection.cursor_instance.calls
        self.assertIn("company_id=%s AND platform_account_id=%s", calls[1][0])
        self.assertIn("client_contract_id", calls[2][0])
        self.assertIn(101, calls[2][1])

        optional_connection = FakeConnection([company, document_row()])
        optional_handlers = register_handlers(optional_connection)
        optional_result = optional_handlers[("POST", "/system/billing-documents")](
            {"companyId": 42, "amount": 49900},
            {"id": 1, "name": "Владелец"},
        )
        self.assertIsNone(optional_result["document"]["client_contract_id"])
        self.assertIsNone(optional_connection.cursor_instance.calls[1][1][2])

    def test_create_rejects_foreign_contract_without_insert(self):
        company = {"id": 42, "name": "ООО Клиент", "platform_account_id": 3}
        connection = FakeConnection([company, None])
        handlers = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("POST", "/system/billing-documents")](
                {
                    "companyId": 42,
                    "clientContractId": 202,
                    "amount": 49900,
                },
                {"id": 1, "name": "Владелец"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any(
            "INSERT INTO platform_billing_documents" in sql
            for sql, _params in connection.cursor_instance.calls
        ))

    def test_create_rejects_cancelled_contract(self):
        company = {"id": 42, "name": "ООО Клиент", "platform_account_id": 3}
        connection = FakeConnection([company, None])
        handlers = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("POST", "/system/billing-documents")](
                {
                    "companyId": 42,
                    "clientContractId": 101,
                    "amount": 49900,
                },
                {"id": 1, "name": "Владелец"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        contract_sql = connection.cursor_instance.calls[1][0]
        self.assertIn("status <> 'cancelled'", contract_sql)
        self.assertTrue(connection.closed)

    def test_existing_document_can_be_linked_and_unlinked(self):
        linked = document_row(client_contract_id=101)
        connection = FakeConnection([
            document_row(),
            contract_row(),
            linked,
        ])
        handlers = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[(
                "PUT",
                "/system/billing-documents/{id}/client-contract",
            )](
                id=81,
                data={"clientContractId": 101},
                current_user={"id": 1, "name": "Владелец"},
            )

        self.assertTrue(result["changed"])
        self.assertEqual(result["document"]["client_contract_id"], 101)
        self.assertEqual(result["document"]["client_contract_number"], "STK-2026-0101")
        self.assertEqual(connection.commits, 1)
        audit.assert_called_once()
        self.assertEqual(
            audit.call_args.args[2],
            "platform_billing_document_contract_linked",
        )

        unlinked = document_row(client_contract_id=None)
        second_connection = FakeConnection([linked, unlinked])
        second_handlers = register_handlers(second_connection)
        with patch.object(routes, "_system_write_audit") as second_audit:
            second_result = second_handlers[(
                "PUT",
                "/system/billing-documents/{id}/client-contract",
            )](
                id=81,
                data={"clientContractId": None},
                current_user={"id": 1, "name": "Владелец"},
            )

        self.assertIsNone(second_result["document"]["client_contract_id"])
        self.assertEqual(second_connection.commits, 1)
        self.assertEqual(
            second_audit.call_args.args[2],
            "platform_billing_document_contract_unlinked",
        )

    def test_existing_document_rejects_foreign_contract_without_update(self):
        connection = FakeConnection([document_row(), None])
        handlers = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[(
                "PUT",
                "/system/billing-documents/{id}/client-contract",
            )](
                id=81,
                data={"clientContractId": 202},
                current_user={"id": 1},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(connection.commits, 0)
        self.assertFalse(any(
            "UPDATE platform_billing_documents" in sql
            for sql, _params in connection.cursor_instance.calls
        ))


if __name__ == "__main__":
    unittest.main()
