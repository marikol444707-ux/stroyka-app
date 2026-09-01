import unittest
from datetime import datetime

from backend.features.platform_admin import routes


class InitialCompanyInviteTest(unittest.TestCase):
    def test_builds_a_client_director_invite_for_the_contact(self):
        invite = routes._build_initial_company_invite(
            {
                "name": "ООО Новая компания",
                "contactName": "Иван Петров",
                "contactEmail": "director@example.test",
            },
            current_user={"name": "Владелец платформы"},
            company_id=42,
            platform_account_id=17,
            code="DIRECT01",
            expires_at=datetime(2026, 10, 1, 12, 30, 0),
        )

        self.assertEqual(invite["role"], "директор")
        self.assertEqual(invite["roleLabel"], "Директор компании")
        self.assertEqual(invite["presetCategory"], "client_user")
        self.assertEqual(invite["presetName"], "Иван Петров")
        self.assertEqual(invite["recipientEmail"], "director@example.test")
        self.assertEqual(invite["createdBy"], "Владелец платформы")
        self.assertEqual(invite["companyId"], 42)
        self.assertEqual(invite["platformAccountId"], 17)
        self.assertEqual(invite["expiresAt"], "2026-10-01 12:30:00")

    def test_falls_back_to_email_without_accepting_client_created_by(self):
        invite = routes._build_initial_company_invite(
            {
                "name": "ООО Новая компания",
                "contactEmail": "director@example.test",
                "createdBy": "Подмена автора",
            },
            current_user={"email": "owner@example.test"},
            company_id=42,
            platform_account_id=17,
            code="DIRECT02",
            expires_at=datetime(2026, 10, 2, 8, 0, 0),
        )

        self.assertEqual(invite["presetName"], "director@example.test")
        self.assertEqual(invite["createdBy"], "owner@example.test")


if __name__ == "__main__":
    unittest.main()
