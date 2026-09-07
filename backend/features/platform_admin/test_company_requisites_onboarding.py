import unittest
from unittest.mock import patch

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

    def delete(self, path, **_kwargs):
        return self._decorator("DELETE", path)


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = None
        self.closed = False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if "INSERT INTO platform_accounts" in normalized:
            self.row = {"id": 7}
        elif "INSERT INTO companies" in normalized:
            self.row = {"id": 42}
        elif "INSERT INTO company_requisites" in normalized:
            self.row = {"id": 91, "company_id": 42}

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.autocommit = True
        self.cursor_instance = FakeCursor()
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


def build_handler(connection):
    app = FakeApp()
    routes.register_platform_admin_routes(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *_roles: (lambda: {}),
    })
    return app.handlers[("POST", "/system/companies")]


class CompanyRequisitesOnboardingTest(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "platformAccountName": "Клиент",
            "name": "ООО Клиент",
            "shortName": "Клиент",
            "inn": "1234567890",
            "ogrn": "1234567890123",
            "legalAddress": "Москва",
            "directorName": "Иван Петров",
            "contactName": "Иван Петров",
            "contactEmail": "director@example.test",
            "bik": "044525225",
            "plan": "demo",
        }
        self.preview = {
            "canCreate": True,
            "plan": "demo",
            "account": None,
            "duplicates": [],
            "accountUsage": {},
        }

    def test_creation_initializes_requisites_in_the_same_transaction(self):
        connection = FakeConnection()
        handler = build_handler(connection)

        with patch.object(routes, "_system_company_create_preview", return_value=self.preview), \
             patch.object(routes, "_system_write_audit"):
            result = handler(self.payload, {"id": 1, "name": "Владелец"})

        self.assertTrue(result["requisitesInitialized"])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)
        requisites_calls = [
            call for call in connection.cursor_instance.calls
            if "INSERT INTO company_requisites" in call[0]
        ]
        self.assertEqual(len(requisites_calls), 1)
        self.assertEqual(requisites_calls[0][1][0], 42)
        self.assertEqual(requisites_calls[0][1][1], "ООО Клиент")
        self.assertEqual(requisites_calls[0][1][5], "1234567890123")
        self.assertEqual(requisites_calls[0][1][14], "044525225")

    def test_requisites_failure_rolls_back_the_company_and_invite(self):
        connection = FakeConnection()
        handler = build_handler(connection)

        with patch.object(routes, "_system_company_create_preview", return_value=self.preview), \
             patch.object(routes, "_system_write_audit"), \
             patch.object(routes, "upsert_company_requisites", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                handler(self.payload, {"id": 1, "name": "Владелец"})

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_billing_profile_prefers_canonical_requisites(self):
        profile = routes._billing_company_profile({
            "requisite_id": 17,
            "company_name": "Сокращённая карточка",
            "company_inn": "0000000000",
            "company_contact_email": "summary@example.test",
            "requisite_full_name": "ООО Канонический клиент",
            "requisite_inn": "1234567890",
            "requisite_kpp": "123456789",
            "requisite_ogrn": "1234567890123",
            "requisite_legal_address": "г. Москва",
            "requisite_email": "legal@example.test",
            "requisite_director_name": "Иванов Иван Иванович",
            "requisite_director_position": "Генеральный директор",
            "requisite_basis": "Устава",
            "requisite_bank_name": "Банк",
            "requisite_bik": "044525225",
            "requisite_rs": "40702810000000000001",
            "requisite_ks": "30101810000000000225",
        })

        self.assertEqual(profile["name"], "ООО Канонический клиент")
        self.assertEqual(profile["inn"], "1234567890")
        self.assertEqual(profile["email"], "legal@example.test")
        self.assertEqual(profile["director_name"], "Иванов Иван Иванович")
        self.assertEqual(profile["rs"], "40702810000000000001")

    def test_billing_profile_does_not_restore_cleared_canonical_fields(self):
        profile = routes._billing_company_profile({
            "requisite_id": 17,
            "company_name": "Старая карточка",
            "company_contact_email": "old@example.test",
            "requisite_full_name": "ООО Актуальная карточка",
            "requisite_email": "",
        })

        self.assertEqual(profile["name"], "ООО Актуальная карточка")
        self.assertEqual(profile["email"], "")

    def test_billing_profile_uses_summary_only_before_requisites_exist(self):
        profile = routes._billing_company_profile({
            "requisite_id": None,
            "company_name": "ООО Старая карточка",
            "company_inn": "1234567890",
            "company_contact_email": "summary@example.test",
        })

        self.assertEqual(profile["name"], "ООО Старая карточка")
        self.assertEqual(profile["inn"], "1234567890")
        self.assertEqual(profile["email"], "summary@example.test")


if __name__ == "__main__":
    unittest.main()
