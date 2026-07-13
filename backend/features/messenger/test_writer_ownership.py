import unittest

from fastapi import HTTPException

from .writer_ownership import (
    resolve_channel_write_owner,
    resolve_marketing_outbox_owners,
    resolve_supply_outbox_owner,
)


class MessengerWriterOwnershipTests(unittest.TestCase):
    def test_marketing_publication_inherits_exact_project_inside_channel_company(self):
        owners = resolve_marketing_outbox_owners(
            [{"id": 10, "company_id": 4, "project_id": None}],
            {"id": 21, "company_id": 4},
        )

        self.assertEqual(
            owners,
            {10: {"scope": "company", "companyId": 4, "projectId": 21}},
        )

    def test_marketing_publication_rejects_channels_from_different_companies(self):
        with self.assertRaisesRegex(HTTPException, "разных компаний"):
            resolve_marketing_outbox_owners(
                [
                    {"id": 10, "company_id": 4, "project_id": None},
                    {"id": 11, "company_id": 8, "project_id": None},
                ],
                None,
            )

    def test_marketing_publication_rejects_foreign_project(self):
        with self.assertRaisesRegex(HTTPException, "другой компании"):
            resolve_marketing_outbox_owners(
                [{"id": 10, "company_id": 4, "project_id": None}],
                {"id": 21, "company_id": 8},
            )

    def test_marketing_publication_rejects_different_channel_project(self):
        with self.assertRaisesRegex(HTTPException, "другому объекту"):
            resolve_marketing_outbox_owners(
                [{"id": 10, "company_id": 4, "project_id": 19}],
                {"id": 21, "company_id": 4},
            )

    def test_supply_notification_uses_request_company_and_project(self):
        owner = resolve_supply_outbox_owner(
            {"companyId": 4, "projectId": 21},
            {"company_id": 4},
        )

        self.assertEqual(
            owner,
            {"scope": "company", "companyId": 4, "projectId": 21},
        )

    def test_supply_notification_rejects_recipient_from_other_company(self):
        with self.assertRaisesRegex(HTTPException, "другой компании"):
            resolve_supply_outbox_owner(
                {"companyId": 4, "projectId": 21},
                {"company_id": 8},
            )

    def test_supply_notification_requires_stored_request_company(self):
        with self.assertRaisesRegex(HTTPException, "не привязана к компании"):
            resolve_supply_outbox_owner(
                {"companyId": None, "projectId": None},
                {"company_id": 4},
            )

    def test_channel_write_uses_selected_company_and_exact_project(self):
        owner = resolve_channel_write_owner(
            {"companyId": 4},
            [{"role": "директор"}],
            [{"id": 21, "company_id": 4}],
            project_required=True,
            leadership_roles=("директор",),
        )

        self.assertEqual(owner, {"companyId": 4, "projectId": 21})

    def test_channel_write_rejects_ambiguous_project(self):
        with self.assertRaisesRegex(HTTPException, "неоднозначно"):
            resolve_channel_write_owner(
                {"companyId": 4},
                [{"role": "директор"}],
                [{"id": 21, "company_id": 4}, {"id": 22, "company_id": 4}],
                project_required=True,
                leadership_roles=("директор",),
            )

    def test_channel_write_rejects_foreign_project(self):
        with self.assertRaisesRegex(HTTPException, "другой компании"):
            resolve_channel_write_owner(
                {"companyId": 4},
                [{"role": "директор"}],
                [{"id": 21, "company_id": 8}],
                project_required=True,
                leadership_roles=("директор",),
            )


if __name__ == "__main__":
    unittest.main()
