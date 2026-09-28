import unittest
from unittest.mock import MagicMock, patch
from .review_context import build_contract_review_context


class ReviewProfileTests(unittest.TestCase):
    def context(self, profile, supplier=None):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {'buyer_company_id': 1, 'payer_company_id': 1, 'version': 2},
            supplier or {'name': 'Supplier', 'inn': '7701234567'}, {'version': 3}, None]
        cur.fetchall.side_effect = [[profile], [], []]
        conn = MagicMock()
        conn.cursor.return_value = cur
        actor = MagicMock()
        offer = {'id': 4, 'company_id': 1, 'supplier_id': 9, 'status': 'Утверждено'}
        with patch('backend.features.supplier_deal_parties.review_context.build_deal_access',
                   return_value=(actor, lambda *a: (offer, None))):
            result = build_contract_review_context({'get_db': lambda: conn})(4, {'role': 'директор'})
        self.assertEqual(actor.call_args.args[2], 1)
        self.assertFalse(conn.commit.called)
        return result

    def test_full_profile_populates_only_company_parties(self):
        result = self.context({'company_id': 1, 'full_name': 'Buyer', 'inn': '7707654321',
            'legal_address': 'Address', 'bank_name': 'Bank', 'rs': '4'*20,
            'director_name': 'Signer', 'basis': 'Power of attorney'})
        for side in ('buyer', 'payer'):
            self.assertEqual(result[side]['bankName'], 'Bank')
            self.assertEqual(result[side]['legalAddress'], 'Address')
            self.assertEqual(result[side]['directorName'], 'Signer')
            self.assertEqual(result[side]['basis'], 'Power of attorney')
        self.assertEqual(result['supplier']['bankName'], '')
        self.assertEqual(result['expectedVersion'], 3)

    def test_missing_signer_and_authority_are_not_invented(self):
        result = self.context({'company_id': 1, 'full_name': 'Buyer', 'inn': '7707654321'})
        self.assertEqual(result['buyer']['directorPosition'], '')
        self.assertEqual(result['buyer']['basis'], '')
        self.assertEqual(result['buyer']['rs'], '')

    def test_supplier_uses_own_bank_columns_without_inventing_authority(self):
        result = self.context({'company_id': 1, 'full_name': 'Buyer', 'inn': '7707654321'},
            {'name': 'Supplier', 'inn': '7701234567', 'bank': 'Supplier bank',
             'account': '4'*20, 'kor_account': '3'*20, 'director_name': 'Supplier signer'})
        self.assertEqual(result['supplier']['bankName'], 'Supplier bank')
        self.assertEqual(result['supplier']['rs'], '4'*20)
        self.assertEqual(result['supplier']['ks'], '3'*20)
        self.assertEqual(result['supplier']['directorName'], 'Supplier signer')
        self.assertEqual(result['supplier']['basis'], '')
        self.assertEqual(result['buyer']['bankName'], '')
