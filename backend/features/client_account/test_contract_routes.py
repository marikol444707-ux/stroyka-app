import unittest

from fastapi import HTTPException

from backend.features.client_account import routes


class FakeApp:
    def __init__(self):
        self.handlers = {}

    def get(self, path, **_kwargs):
        def register(function):
            self.handlers[("GET", path)] = function
            return function
        return register


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
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
    def __init__(self, results):
        self.cursor_instance = FakeCursor(results)
        self.commits = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def account_row():
    return {
        "id": 3, "name": "Клиентская группа", "owner_name": "Директор",
        "contact_email": "director@example.test", "plan": "pro",
        "status": "active", "active": True,
        "created_at": "2026-09-01T00:00:00",
    }


def contract_row(**overrides):
    row = {
        "id": 101, "company_id": 42, "company_name": "ООО Клиент",
        "contract_type": "platform_license", "number": "STK-2026-0101",
        "contract_date": "2026-09-02", "starts_on": "2026-09-02",
        "ends_on": "2027-09-01", "plan": "pro",
        "monthly_fee": "49900.00", "currency": "RUB",
        "max_projects": 10, "max_users": 40, "status": "active",
        "generated_file_url": "https://storage.example/generated.pdf",
        "signed_file_url": "/tenant-files/502/content",
        "issued_at": "2026-09-02T11:00:00",
        "activated_at": "2026-09-03T12:00:00", "terminated_at": None,
    }
    row.update(overrides)
    return row


def history_row(**overrides):
    row = {
        "entity_id": 101,
        "details_json": {
            "fromStatus": "issued", "toStatus": "active",
            "reason": "Подписан", "internal": "do-not-expose",
        },
        "created_at": "2026-09-03T12:00:00",
    }
    row.update(overrides)
    return row


def register_handlers(connection):
    app = FakeApp()
    role_requests = []

    def require_roles(*roles_requested):
        role_requests.append(roles_requested)
        return lambda: {}

    routes.register_client_account_routes(app, {
        "get_db": lambda: connection,
        "require_roles": require_roles,
    })
    return app.handlers, role_requests


class ClientContractReadRoutesTests(unittest.TestCase):
    def test_account_owner_reads_safe_contract_and_preserved_history(self):
        connection = FakeConnection([account_row(), [contract_row()], [history_row()]])
        handlers, role_requests = register_handlers(connection)

        result = handlers[("GET", "/account/client-contracts")](
            current_user={"id": 8, "role": "account_owner", "platformAccountId": 3},
        )

        self.assertTrue(result["readOnly"])
        self.assertEqual(result["items"][0]["statusLabel"], "Действует")
        self.assertIsNone(result["items"][0]["generatedFileUrl"])
        self.assertEqual(result["items"][0]["signedFileUrl"], "/tenant-files/502/content")
        self.assertEqual(result["items"][0]["statusHistory"], [{
            "fromStatus": "issued", "toStatus": "active",
            "reason": "Подписан", "changedAt": "2026-09-03T12:00:00",
        }])
        self.assertIn(routes.CLIENT_CONTRACT_READ_ROLES, role_requests)
        sql = " ".join(call[0] for call in connection.cursor_instance.calls)
        self.assertIn("cc.status<>'draft'", sql)
        self.assertNotIn("INSERT ", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("DELETE ", sql)
        self.assertEqual(connection.commits, 0)

    def test_director_is_scoped_to_own_company_and_account(self):
        connection = FakeConnection([
            account_row(), {"id": 42}, [contract_row()], [history_row()],
        ])
        handlers, _role_requests = register_handlers(connection)

        result = handlers[("GET", "/account/client-contracts")](
            current_user={
                "id": 9, "role": "директор", "companyId": 42,
                "platformAccountId": 3,
            },
        )

        self.assertEqual(len(result["items"]), 1)
        calls = connection.cursor_instance.calls
        self.assertIn("cc.platform_account_id=%s", calls[2][0])
        self.assertIn("cc.company_id=%s", calls[2][0])
        self.assertEqual(calls[2][1], (3, 42))
        self.assertIn("company_id=%s", calls[3][0])
        self.assertEqual(calls[3][1], (3, [101], 42))

    def test_director_cannot_read_a_company_outside_account(self):
        connection = FakeConnection([account_row(), None])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("GET", "/account/client-contracts")](
                current_user={
                    "id": 9, "role": "директор", "companyId": 42,
                    "platformAccountId": 3,
                },
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(connection.commits, 0)


if __name__ == "__main__":
    unittest.main()
