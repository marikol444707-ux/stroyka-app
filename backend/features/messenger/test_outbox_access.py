import unittest

from fastapi import HTTPException

from .outbox_access import resolve_outbox_read_company_ids
from .routes import _public_messenger_outbox_item


class MessengerOutboxAccessTests(unittest.TestCase):
    def test_selected_company_requires_leadership_membership(self):
        company_ids = resolve_outbox_read_company_ids(
            {"mode": "company", "companyId": 4},
            [{"companyId": 4, "role": "директор"}],
            leadership_roles=("директор", "зам_директора"),
        )

        self.assertEqual(company_ids, [4])

    def test_selected_company_rejects_non_leadership_membership(self):
        with self.assertRaisesRegex(HTTPException, "не позволяет читать"):
            resolve_outbox_read_company_ids(
                {"mode": "company", "companyId": 4},
                [{"companyId": 4, "role": "прораб"}],
                leadership_roles=("директор", "зам_директора"),
            )

    def test_all_companies_keeps_only_leadership_memberships(self):
        company_ids = resolve_outbox_read_company_ids(
            {"mode": "all_companies", "companyIds": [4, 8, 9]},
            [
                {"companyId": 4, "role": "директор"},
                {"companyId": 8, "role": "прораб"},
                {"companyId": 9, "role": "зам_директора"},
            ],
            leadership_roles=("директор", "зам_директора"),
        )

        self.assertEqual(company_ids, [4, 9])

    def test_selected_company_rejects_mismatched_actor(self):
        with self.assertRaisesRegex(HTTPException, "неоднозначно"):
            resolve_outbox_read_company_ids(
                {"mode": "company", "companyId": 4},
                [{"companyId": 8, "role": "директор"}],
                leadership_roles=("директор", "зам_директора"),
            )

    def test_all_companies_rejects_empty_leadership_scope(self):
        with self.assertRaisesRegex(HTTPException, "нет доступа"):
            resolve_outbox_read_company_ids(
                {"mode": "all_companies", "companyIds": [4]},
                [{"companyId": 4, "role": "прораб"}],
                leadership_roles=("директор", "зам_директора"),
            )

    def test_public_item_exposes_stored_owner_for_diagnostics(self):
        item = _public_messenger_outbox_item({
            "id": 17,
            "owner_scope": "company",
            "company_id": 4,
            "project_id": 21,
        })

        self.assertEqual(item["ownerScope"], "company")
        self.assertEqual(item["companyId"], 4)
        self.assertEqual(item["projectId"], 21)


if __name__ == "__main__":
    unittest.main()
