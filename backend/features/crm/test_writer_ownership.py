import unittest

from fastapi import HTTPException

from .writer_ownership import (
    resolve_authenticated_lead_owner,
    resolve_lead_child_owner,
    resolve_marketing_lead_owner,
    resolve_public_lead_owner,
    restrict_crm_read_context,
)


class CrmWriterOwnershipTests(unittest.TestCase):
    def test_authenticated_write_uses_exact_selected_company_and_effective_actor(self):
        owner = resolve_authenticated_lead_owner(
            {"mode": "company", "companyId": 4},
            [{"id": 9, "role": "директор", "companyId": 4}],
            allowed_roles=("директор", "менеджер_crm"),
        )

        self.assertEqual(owner["companyId"], 4)
        self.assertEqual(owner["actor"]["id"], 9)

    def test_authenticated_write_rejects_aggregate_context(self):
        with self.assertRaisesRegex(HTTPException, "одну конкретную компанию"):
            resolve_authenticated_lead_owner(
                {"mode": "all_companies", "companyId": None},
                [
                    {"role": "директор", "companyId": 4},
                    {"role": "директор", "companyId": 8},
                ],
                allowed_roles=("директор",),
            )

    def test_authenticated_write_uses_effective_company_role(self):
        with self.assertRaisesRegex(HTTPException, "не позволяет менять CRM"):
            resolve_authenticated_lead_owner(
                {"mode": "company", "companyId": 4},
                [{"role": "мастер", "companyId": 4}],
                allowed_roles=("директор", "менеджер_crm"),
            )

    def test_authenticated_write_rejects_actor_from_other_company(self):
        with self.assertRaisesRegex(HTTPException, "не совпадает"):
            resolve_authenticated_lead_owner(
                {"mode": "company", "companyId": 4},
                [{"role": "директор", "companyId": 8}],
                allowed_roles=("директор",),
            )

    def test_read_context_keeps_only_companies_with_effective_crm_role(self):
        context = restrict_crm_read_context(
            {"mode": "all_companies", "companyIds": [4, 8]},
            [
                {"role": "директор", "companyId": 4},
                {"role": "мастер", "companyId": 8},
            ],
            allowed_roles=("директор", "менеджер_crm"),
        )

        self.assertEqual(context["companyIds"], [4])

    def test_selected_company_requires_effective_crm_role(self):
        with self.assertRaisesRegex(HTTPException, "не позволяет просматривать CRM"):
            restrict_crm_read_context(
                {"mode": "company", "companyId": 4, "companyIds": [4]},
                [{"role": "мастер", "companyId": 4}],
                allowed_roles=("директор", "менеджер_crm"),
            )

    def test_public_site_requires_explicit_company(self):
        self.assertEqual(resolve_public_lead_owner(4), {"companyId": 4})
        with self.assertRaisesRegex(HTTPException, "не настроена"):
            resolve_public_lead_owner(None)

    def test_marketing_lead_inherits_stored_channel_company(self):
        self.assertEqual(resolve_marketing_lead_owner({"company_id": 4}), {"companyId": 4})
        with self.assertRaisesRegex(HTTPException, "не привязан"):
            resolve_marketing_lead_owner({"channel_type": "marketing"})

    def test_child_inherits_exact_lead_owner(self):
        self.assertEqual(
            resolve_lead_child_owner({"company_id": 4, "project_id": 21}),
            {"companyId": 4, "projectId": 21},
        )

    def test_child_rejects_legacy_unowned_lead(self):
        with self.assertRaisesRegex(HTTPException, "безопасный перенос"):
            resolve_lead_child_owner({"id": 10})


if __name__ == "__main__":
    unittest.main()
