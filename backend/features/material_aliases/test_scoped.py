import unittest
from unittest.mock import Mock

from fastapi import HTTPException
from backend.features.material_aliases.scoped import AliasAccess, normalize_alias, require_alias_actor, save_alias


class ScopedAliasPolicyTests(unittest.TestCase):
    def test_normalization_matches_business_key(self):
        self.assertEqual(normalize_alias(' Цемент (М500) / мешок '), 'цемент м500 мешок')

    def test_mutation_requires_an_explicit_transaction(self):
        cur = Mock()
        cur.connection.autocommit = True
        with self.assertRaises(RuntimeError):
            save_alias(cur, {'companyId': 2, 'id': 7}, alias_name='A', canonical_name='B')
        cur.execute.assert_not_called()

    def test_legacy_context_never_grants_alias_access(self):
        # No real membership ID even though the global profile has a company.
        from unittest.mock import patch
        with patch('backend.features.material_aliases.scoped.resolve_request_company_context',
                   return_value={'mode': 'company', 'source': 'legacy', 'companyId': 2, 'role': 'директор'}):
            with self.assertRaises(HTTPException) as error:
                require_alias_actor(Mock(), {'id': 7}, allowed_roles=('директор',))
        self.assertEqual(error.exception.status_code, 403)

    def test_expanding_unicode_key_is_rejected_before_deactivation(self):
        cur = Mock()
        cur.connection.autocommit = False
        cur.fetchone.return_value = {'transaction_isolation': 'read committed'}
        access = AliasAccess({'companyId': 2, 'id': 7}, True, ())
        with self.assertRaises(HTTPException) as error:
            save_alias(cur, access, alias_name='İ' * 500, canonical_name='B')
        self.assertEqual(error.exception.status_code, 400)
        self.assertFalse(any('UPDATE' in str(call) for call in cur.execute.call_args_list))

    def test_runtime_and_audit_normalization_stay_in_sync(self):
        from backend.features.material_aliases.readiness import _alias_key
        for value in (' Цемент (М500) ', 'A/B\\C', 'a, b; c: d', '«Brand»', 'a\tb\nC', None):
            self.assertEqual(normalize_alias(value), _alias_key(value))
