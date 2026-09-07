import unittest

from backend.features.company_requisites.service import (
    mirror_company_identity,
    normalize_company_requisites,
    upsert_company_requisites,
)


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = {"id": 91, "company_id": 42}

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row


class CompanyRequisitesServiceTest(unittest.TestCase):
    def test_normalizes_onboarding_fields_into_the_canonical_profile(self):
        result = normalize_company_requisites({
            "name": "  ИП Бучькин Николай Сергеевич  ",
            "shortName": " Бучькин Н.С. ",
            "inn": "26 110 350 7630",
            "kpp": "not-applicable",
            "ogrn": "309264413800022",
            "legalAddress": "  356031, Ставропольский край  ",
            "actualAddress": "  356031, Ставропольский край  ",
            "contactName": "  Бучькин Николай Сергеевич ",
            "contactPosition": " Индивидуальный предприниматель ",
            "contactPhone": " 8 909 763 85 05 ",
            "contactEmail": " OWNER@EXAMPLE.RU ",
            "bankName": " ПАО Банк ",
            "bik": "04 050 9000",
            "rs": "40 802 810 000 000 000 001",
            "ks": "30 101 810 000 000 000 001",
        })

        self.assertEqual(result, {
            "fullName": "ИП Бучькин Николай Сергеевич",
            "shortName": "Бучькин Н.С.",
            "inn": "261103507630",
            "kpp": "",
            "ogrn": "309264413800022",
            "legalAddress": "356031, Ставропольский край",
            "actualAddress": "356031, Ставропольский край",
            "phone": "8 909 763 85 05",
            "email": "owner@example.ru",
            "directorName": "Бучькин Николай Сергеевич",
            "directorPosition": "Индивидуальный предприниматель",
            "basis": "записи в ЕГРИП",
            "bankName": "ПАО Банк",
            "bik": "040509000",
            "rs": "40802810000000000001",
            "ks": "30101810000000000001",
        })

    def test_upsert_is_scoped_to_the_server_selected_company(self):
        cursor = FakeCursor()

        row = upsert_company_requisites(cursor, 42, {
            "companyId": 999,
            "name": "ООО Клиент",
            "inn": "1234567890",
            "contactName": "Иван Петров",
        })

        self.assertEqual(row, {"id": 91, "company_id": 42})
        sql, params = cursor.calls[0]
        self.assertIn("ON CONFLICT (company_id) DO UPDATE", sql)
        self.assertEqual(params[0], 42)
        self.assertNotIn(999, params)
        self.assertEqual(params[1], "ООО Клиент")
        self.assertEqual(params[3], "1234567890")
        self.assertEqual(params[10], "Иван Петров")

    def test_canonical_empty_value_does_not_restore_a_stale_alias(self):
        result = normalize_company_requisites({
            "fullName": "",
            "companyName": "Старое название",
            "email": "",
            "contactEmail": "stale@example.ru",
        })

        self.assertEqual(result["fullName"], "")
        self.assertEqual(result["email"], "")

    def test_summary_projection_clears_removed_optional_values(self):
        cursor = FakeCursor()

        mirror_company_identity(cursor, 42, {
            "fullName": "ООО Клиент",
            "shortName": "",
            "inn": "",
            "kpp": "",
            "directorName": "",
            "phone": "",
            "email": "",
        })

        sql, params = cursor.calls[0]
        self.assertIn("short_name=%s", sql)
        self.assertIn("contact_email=%s", sql)
        self.assertNotIn("short_name=COALESCE", sql)
        self.assertNotIn("contact_email=COALESCE", sql)
        self.assertEqual(params[1:7], ("", "", "", "", "", ""))


if __name__ == "__main__":
    unittest.main()
