import unittest

from fastapi import HTTPException

from .routes import resolve_internal_messenger_owner


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.responses.pop(0)

    def fetchone(self):
        rows = self.responses.pop(0)
        return rows[0] if rows else None


class InternalMessengerOwnerTests(unittest.TestCase):
    def test_channel_uses_exact_stored_owner(self):
        cursor = FakeCursor([[{"company_id": 1, "project_id": None}]])

        owner = resolve_internal_messenger_owner(
            cursor, {"source": "max_bot"}, entity_type="messenger_channel", entity_id=17
        )

        self.assertEqual(owner, {"scope": "company", "companyId": 1, "projectId": None})

    def test_employee_cannot_write_to_channel_from_another_company(self):
        cursor = FakeCursor([
            [{"company_id": 2, "project_id": None}],
            [{"company_id": 1}],
        ])

        with self.assertRaisesRegex(HTTPException, "другой компании"):
            resolve_internal_messenger_owner(
                cursor,
                {"source": "users", "id": 7},
                entity_type="messenger_channel",
                entity_id=17,
            )

    def test_user_project_resolves_inside_active_memberships(self):
        cursor = FakeCursor([
            [{"company_id": 1}],
            [{"id": 24, "company_id": 1, "name": "Лермонтова школа #1"}],
        ])

        owner = resolve_internal_messenger_owner(
            cursor,
            {"source": "users", "id": 7},
            project_name="Лермонтова школа #1",
        )

        self.assertEqual(owner, {"scope": "company", "companyId": 1, "projectId": 24})

    def test_duplicate_project_name_in_employee_companies_fails_closed(self):
        cursor = FakeCursor([
            [{"company_id": 1}, {"company_id": 2}],
            [
                {"id": 24, "company_id": 1, "name": "Общий объект"},
                {"id": 31, "company_id": 2, "name": "Общий объект"},
            ],
        ])

        with self.assertRaisesRegex(HTTPException, "одинаковым названием"):
            resolve_internal_messenger_owner(
                cursor, {"source": "users", "id": 7}, project_name="Общий объект"
            )

    def test_company_level_action_with_two_memberships_fails_closed(self):
        cursor = FakeCursor([[{"company_id": 1}, {"company_id": 2}]])

        with self.assertRaisesRegex(HTTPException, "компанию"):
            resolve_internal_messenger_owner(cursor, {"source": "users", "id": 7})

    def test_ownerless_channel_is_rejected(self):
        cursor = FakeCursor([[{"company_id": None, "project_id": None}]])

        with self.assertRaisesRegex(HTTPException, "владельца"):
            resolve_internal_messenger_owner(
                cursor, {"source": "max_bot"}, entity_type="messenger_channel", entity_id=17
            )

    def test_warehouse_document_from_another_company_is_rejected(self):
        cursor = FakeCursor([
            [{"company_id": 2, "project": "Объект B"}],
            [{"company_id": 1}],
        ])

        with self.assertRaisesRegex(HTTPException, "другой компании"):
            resolve_internal_messenger_owner(
                cursor,
                {"source": "users", "id": 7},
                entity_type="warehouse_invoice",
                entity_id=44,
            )


if __name__ == "__main__":
    unittest.main()
