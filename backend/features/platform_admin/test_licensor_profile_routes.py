import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.platform_admin import licensor_profile_routes, routes


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

    def delete(self, path, **_kwargs):
        return self._decorator("DELETE", path)


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_instance = FakeCursor(rows)
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
    role_requests = []

    def require_roles(*roles):
        role_requests.append(roles)
        return lambda: {}

    licensor_profile_routes.register_licensor_profile_routes(app, {
        "get_db": lambda: connection,
        "require_roles": require_roles,
        "view_roles": routes.PLATFORM_VIEW_ROLES,
        "manage_roles": routes.PLATFORM_MANAGE_ROLES,
        "write_audit": lambda *args, **kwargs: routes._system_write_audit(
            *args, **kwargs
        ),
    })
    return app.handlers, role_requests


def profile_row(**overrides):
    row = {
        "id": 7,
        "platform_account_id": 3,
        "legal_form": "individual_entrepreneur",
        "legal_name": "ИП Буцькин Николай Сергеевич",
        "short_name": "ИП Буцькин",
        "inn": "261103507630",
        "kpp": None,
        "ogrn": None,
        "ogrnip": "309264413800022",
        "legal_address": "Ставропольский край",
        "phone": "+79097638505",
        "email": "owner@example.test",
        "settlement_account": "40802810000000000001",
        "bank_name": "Тестовый банк",
        "bank_bik": "040000001",
        "correspondent_account": "30101810000000000001",
        "signatory_name": "Буцькин Николай Сергеевич",
        "signatory_basis": "записи в ЕГРИП",
        "active": True,
        "created_at": "2026-09-01T00:00:00",
        "updated_at": "2026-09-01T00:00:00",
    }
    row.update(overrides)
    return row


class LicensorProfileRoutesTest(unittest.TestCase):
    def test_get_returns_active_profile_in_api_shape(self):
        connection = FakeConnection([profile_row()])
        handlers, role_requests = register_handlers(connection)

        result = handlers[("GET", "/system/licensor-profile")](
            platformAccountId=3,
            _current_user={"id": 1, "role": "platform_support"},
        )

        self.assertTrue(result["configured"])
        self.assertEqual(result["platformAccountId"], 3)
        self.assertEqual(result["profile"]["id"], 7)
        self.assertEqual(result["profile"]["legalName"], "ИП Буцькин Николай Сергеевич")
        self.assertEqual(result["profile"]["settlementAccount"], "40802810000000000001")
        self.assertIn(routes.PLATFORM_VIEW_ROLES, role_requests)
        sql, params = connection.cursor_instance.calls[0]
        self.assertIn("FROM platform_licensor_profiles", sql)
        self.assertIn("active IS TRUE", sql)
        self.assertEqual(params, (3,))
        self.assertTrue(connection.closed)

    def test_get_returns_empty_state_when_profile_is_not_configured(self):
        connection = FakeConnection()
        handlers, _role_requests = register_handlers(connection)

        result = handlers[("GET", "/system/licensor-profile")](
            platformAccountId=8,
            _current_user={"id": 1, "role": "system_owner"},
        )

        self.assertEqual(result, {
            "platformAccountId": 8,
            "configured": False,
            "profile": None,
        })

    def test_put_creates_profile_and_writes_audit_in_one_transaction(self):
        connection = FakeConnection([
            {"id": 3},
            None,
            profile_row(),
        ])
        handlers, role_requests = register_handlers(connection)
        payload = {
            "platformAccountId": 3,
            "legalForm": "individual_entrepreneur",
            "legalName": " ИП  Буцькин Николай Сергеевич ",
            "inn": "26 110 350 7630",
            "ogrnip": "30926-44138-00022",
            "legalAddress": "Ставропольский край",
            "phone": "8 (909) 763-85-05",
            "email": "OWNER@EXAMPLE.TEST",
            "settlementAccount": "40802810000000000001",
            "bankName": "Тестовый банк",
            "bankBik": "040000001",
            "correspondentAccount": "30101810000000000001",
            "signatoryName": "Буцькин Николай Сергеевич",
            "signatoryBasis": "записи в ЕГРИП",
        }

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("PUT", "/system/licensor-profile")](
                payload,
                {"id": 1, "name": "Владелец", "role": "system_owner"},
            )

        self.assertTrue(result["configured"])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)
        self.assertIn(routes.PLATFORM_MANAGE_ROLES, role_requests)
        insert_sql, insert_params = connection.cursor_instance.calls[2]
        self.assertIn("INSERT INTO platform_licensor_profiles", insert_sql)
        self.assertEqual(insert_params[0], 3)
        self.assertEqual(insert_params[2], "ИП Буцькин Николай Сергеевич")
        self.assertEqual(insert_params[4], "261103507630")
        self.assertEqual(insert_params[7], "309264413800022")
        self.assertEqual(insert_params[10], "owner@example.test")
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[2], "platform_licensor_profile_created")

    def test_put_updates_existing_active_profile(self):
        connection = FakeConnection([
            {"id": 3},
            {"id": 7},
            profile_row(legal_name="ИП Обновлённый"),
        ])
        handlers, _role_requests = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("PUT", "/system/licensor-profile")](
                {
                    "platformAccountId": 3,
                    "legalName": "ИП Обновлённый",
                    "inn": "261103507630",
                },
                {"id": 1, "name": "Владелец", "role": "platform_admin"},
            )

        update_sql, update_params = connection.cursor_instance.calls[2]
        self.assertIn("UPDATE platform_licensor_profiles", update_sql)
        self.assertEqual(update_params[-1], 7)
        self.assertEqual(result["profile"]["legalName"], "ИП Обновлённый")
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[2], "platform_licensor_profile_updated")

    def test_put_rejects_missing_platform_account_without_writing(self):
        connection = FakeConnection([None])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("PUT", "/system/licensor-profile")](
                {
                    "platformAccountId": 404,
                    "legalName": "ИП Буцькин Николай Сергеевич",
                },
                {"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_put_requires_legal_name(self):
        connection = FakeConnection([{"id": 3}])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("PUT", "/system/licensor-profile")](
                {"platformAccountId": 3, "inn": "261103507630"},
                {"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_put_rejects_unknown_legal_form(self):
        connection = FakeConnection([{"id": 3}])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("PUT", "/system/licensor-profile")](
                {
                    "platformAccountId": 3,
                    "legalForm": "untrusted-form",
                    "legalName": "Тестовый лицензиар",
                },
                {"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_put_rejects_values_larger_than_database_contract(self):
        connection = FakeConnection([{"id": 3}])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("PUT", "/system/licensor-profile")](
                {
                    "platformAccountId": 3,
                    "legalName": "И" * 501,
                },
                {"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
