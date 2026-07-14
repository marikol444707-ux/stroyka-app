import unittest

from fastapi import HTTPException

from .account_access import (
    account_identity_lock_keys,
    require_account_target_company,
    resolve_account_company_ids,
    resolve_existing_account,
)


class MessengerAccountAccessTests(unittest.TestCase):
    def test_selected_company_requires_leadership_actor(self):
        result = resolve_account_company_ids(
            {"mode": "company", "companyId": 4},
            [{"companyId": 4, "role": "директор"}],
            leadership_roles=("директор", "зам_директора"),
        )

        self.assertEqual(result, [4])

    def test_selected_company_rejects_lower_role(self):
        with self.assertRaisesRegex(HTTPException, "не позволяет управлять"):
            resolve_account_company_ids(
                {"mode": "company", "companyId": 4},
                [{"companyId": 4, "role": "прораб"}],
                leadership_roles=("директор", "зам_директора"),
            )

    def test_all_companies_read_keeps_only_leadership_companies(self):
        result = resolve_account_company_ids(
            {"mode": "all_companies", "companyIds": [4, 8, 9]},
            [
                {"companyId": 4, "role": "директор"},
                {"companyId": 8, "role": "прораб"},
                {"companyId": 9, "role": "зам_директора"},
            ],
            leadership_roles=("директор", "зам_директора"),
        )

        self.assertEqual(result, [4, 9])

    def test_all_companies_write_is_forbidden(self):
        with self.assertRaisesRegex(HTTPException, "выберите одну компанию"):
            resolve_account_company_ids(
                {"mode": "all_companies", "companyIds": [4]},
                [{"companyId": 4, "role": "директор"}],
                leadership_roles=("директор",),
                write=True,
            )

    def test_target_must_belong_to_selected_company(self):
        self.assertEqual(require_account_target_company([4, 8], 4), 4)

        with self.assertRaisesRegex(HTTPException, "не принадлежит"):
            require_account_target_company([8], 4)

    def test_existing_identity_may_be_updated_for_same_user(self):
        row = resolve_existing_account(
            [{"id": 7, "user_id": 11, "staff_id": None}],
            user_id=11,
        )

        self.assertEqual(row["id"], 7)

    def test_identity_lock_keys_cover_every_unique_dimension_in_stable_order(self):
        keys = account_identity_lock_keys(
            "MAX",
            external_user_id="max-11",
            chat_id="chat-11",
            user_id=11,
        )

        self.assertEqual(keys, [
            "messenger-account:max:chat:chat-11",
            "messenger-account:max:external:max-11",
            "messenger-account:max:user:11",
        ])

    def test_existing_identity_cannot_move_to_another_employee(self):
        with self.assertRaisesRegex(HTTPException, "другому сотруднику"):
            resolve_existing_account(
                [{"id": 7, "user_id": 11, "staff_id": None}],
                user_id=12,
            )

    def test_overlapping_matches_require_manual_review(self):
        with self.assertRaisesRegex(HTTPException, "несколько пересекающихся"):
            resolve_existing_account(
                [
                    {"id": 7, "user_id": 11},
                    {"id": 8, "user_id": 11},
                ],
                user_id=11,
            )


if __name__ == "__main__":
    unittest.main()
