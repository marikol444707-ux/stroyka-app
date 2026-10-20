"""Canonical invitation resolution cannot cross buyer boundaries or guess identities."""
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException
from .supplier_relationship import canonical_invited_card, matching_invited_card, same_legal


def row(sid, inn='', ogrn='', target=None):
    return dict(id=sid, name='Supplier', inn=inn, ogrn=ogrn,
                profile={} if target is None else {'mergedIntoSupplierId': target})


class MergedSupplierInvitationTests(unittest.TestCase):
    def test_source_resolves_only_to_direct_target(self):
        rows = {1: row(1, target=2), 2: row(2)}
        self.assertEqual(canonical_invited_card(rows, 1), 2)
        self.assertEqual(canonical_invited_card(rows, 2), 2)

    def test_missing_target_foreign_target_cycle_chain_and_malformed_fail_closed(self):
        cases = [({}, 1), ({1: row(1, target=2)}, 1),
                 ({1: row(1, target=1)}, 1),
                 ({1: row(1, target=2), 2: row(2, target=1)}, 1),
                 ({1: row(1, target=2), 2: row(2, target=3), 3: row(3)}, 1),
                 ({1: row(1, target='2'), 2: row(2)}, 1),
                 ({1: row(1, target=True)}, 1),
                 ({1: row(1, target={'id': 2})}, 1),
                 ({1: row(1, target=[2])}, 1),
                 ({1: dict(row(1), profile=['invalid'])}, 1)]
        for rows, sid in cases:
            with self.subTest(rows=rows), self.assertRaises(HTTPException) as caught:
                canonical_invited_card(rows, sid)
            self.assertEqual(caught.exception.status_code, 409)

    def match(self, rows, **requisites):
        cur = MagicMock()
        cur.fetchone.return_value = dict(company_id=2, platform_account_id=4)
        cur.fetchall.return_value = rows
        result = matching_invited_card(cur, {'id': 8}, requisites, lambda s: s.lower().strip())
        catalog_sql, params = cur.execute.call_args.args
        self.assertIn('l.company_id=%s AND l.platform_account_id=%s', catalog_sql)
        self.assertEqual(params, (2, 4))
        return result

    def test_legal_key_on_archived_source_resolves_to_one_canonical_identity(self):
        self.assertEqual(self.match([row(1, inn='77 9911-2233', target=2), row(2)], inn='7799112233'), 2)
        self.assertEqual(self.match([row(1, ogrn='1234567890123', target=2), row(2)], ogrn='1234567890123'), 2)

    def test_matching_source_and_target_do_not_look_like_two_suppliers(self):
        self.assertEqual(self.match([row(1, inn='7799112233', target=2), row(2, inn='7799112233')], inn='7799112233'), 2)

    def test_two_canonical_identities_or_conflicting_keys_need_review(self):
        for rows, keys in [([row(1, inn='7799112233'), row(2, inn='7799112233')], dict(inn='7799112233')),
                           ([row(1, inn='7799112233'), row(2, ogrn='1234567890123')], dict(inn='7799112233', ogrn='1234567890123'))]:
            with self.assertRaises(HTTPException) as caught:
                self.match(rows, **keys)
            self.assertEqual(caught.exception.status_code, 409)

    def test_name_only_never_claims_archived_history(self):
        with self.assertRaises(HTTPException):
            self.match([row(1, target=2), row(2)], name='Supplier')

    def test_malformed_legal_values_never_match_by_stripping_letters(self):
        self.assertFalse(same_legal('7799112233x', '7799112233', 'inn'))
        self.assertFalse(same_legal('7799112233x', '7799112233x', 'inn'))
        self.assertTrue(same_legal('77 9911-2233', '7799112233', 'inn'))


class RegistrationIdentityLockTests(unittest.TestCase):
    def test_old_invitation_locks_canonical_and_child_legal_keys_before_rows(self):
        from .supplier_relationship import lock_invited_identity
        cur = MagicMock()
        cur.fetchone.return_value = dict(company_id=2, platform_account_id=4)
        cur.fetchall.side_effect = [
            [row(1, inn='77 9911-2233', target=2), row(2, ogrn='1234567890123'), row(3, target={'invalid': 2})],
            [dict(id=1, inn='77 9911-2233', ogrn=''), dict(id=2, inn='', ogrn='1234567890123')],
        ]
        lock_invited_identity(cur, dict(id=8, supplier_id=1), {'inn': '7799112233'})
        calls = [c.args for c in cur.execute.call_args_list]
        locks = [(index, args[1][0]) for index, args in enumerate(calls) if 'pg_advisory_xact_lock' in args[0]]
        self.assertEqual([key for _, key in locks], ['supplier-legal:1234567890123', 'supplier-legal:77 9911-2233', 'supplier-legal:7799112233'])
        row_lock = next(index for index, args in enumerate(calls) if 'FOR UPDATE' in args[0])
        self.assertTrue(all(index < row_lock for index, _ in locks))
        self.assertEqual(calls[row_lock][1], ([1, 2],))

    def test_identity_change_while_waiting_rejects_without_claim(self):
        from .supplier_relationship import lock_invited_identity
        cur = MagicMock()
        cur.fetchone.return_value = dict(company_id=2, platform_account_id=4)
        cur.fetchall.side_effect = [[row(1, inn='7799112233')], [dict(id=1, inn='7799112234', ogrn='')]]
        with self.assertRaises(HTTPException) as caught:
            lock_invited_identity(cur, dict(id=8, supplier_id=1), {'inn': '7799112233'})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(any('UPDATE suppliers' in c.args[0] for c in cur.execute.call_args_list))
