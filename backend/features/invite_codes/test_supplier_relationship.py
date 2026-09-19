import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from backend.features.invite_codes.supplier_relationship import link_registered_supplier


class SupplierInviteRelationshipTests(unittest.TestCase):
    def test_legacy_invite_cannot_grant_company_relationship(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        self.assertIsNone(link_registered_supplier(cur, {'id': 8}, 40, {'id': 50}, {}))
        self.assertEqual(cur.execute.call_count, 1)

    def test_company_is_taken_from_verified_binding_not_registration_payload(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {'company_id': 2, 'platform_account_id': 3},
            {'id': 2, 'platform_account_id': 3, 'active': True},
            {'id': 60},
        ]
        link_registered_supplier(cur, {'id': 8, 'preset_category': 'Материалы'}, 40,
                                 {'id': 50, 'name': 'Supplier'},
                                 {'companyId': 999, 'email': 'supplier@example.invalid'})
        insert = next(c for c in cur.execute.call_args_list if 'INSERT INTO company_supplier_links' in c.args[0])
        self.assertEqual(insert.args[1][:3], (2, 40, 3))
        self.assertFalse(any('user_company_roles' in c.args[0] for c in cur.execute.call_args_list))

    def test_inactive_or_moved_company_rejects_registration(self):
        for company in (None, {'active': False, 'platform_account_id': 3},
                        {'active': True, 'platform_account_id': 4}):
            cur = MagicMock()
            cur.fetchone.side_effect = [{'company_id': 2, 'platform_account_id': 3}, company]
            with self.assertRaises(HTTPException) as raised:
                link_registered_supplier(cur, {'id': 8}, 40, {'id': 50}, {})
            self.assertEqual(raised.exception.status_code, 409)
            self.assertFalse(any('INSERT' in c.args[0] for c in cur.execute.call_args_list))
