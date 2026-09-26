import unittest
from pydantic import ValidationError

from .contracts import ContractReview, build_snapshot


def payload():
    return {
        'partyVersion': 1, 'expectedVersion': 0, 'sourceFileId': 31,
        'number': 'ДП-1', 'date': '2026-09-15', 'reviewConfirmed': True,
        'buyer': {'fullName':'Компания А', 'inn':'7701234567'},
        'payer': {'fullName':'Компания Б', 'inn':'7707654321'},
        'supplier': {'fullName':'Поставщик', 'inn':'7709876543'},
        'paymentTerms': '30% аванс, 70% после приёмки', 'reason':'Проверено по договору',
    }


class ContractReviewTest(unittest.TestCase):
    def test_missing_signer_and_bank_are_not_invented(self):
        review = ContractReview(**payload())
        self.assertEqual(review.buyer.basis, '')
        self.assertEqual(review.buyer.directorPosition, '')
        self.assertEqual(review.buyer.rs, '')

    def test_requires_explicit_boolean_review(self):
        for value in (False, 'true', 1, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ContractReview(**{**payload(), 'reviewConfirmed': value})

    def test_rejects_bad_ids_extra_fields_and_blank_number(self):
        for change in ({'sourceFileId':True}, {'partyVersion':0}, {'signed':True}, {'number':' '}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ContractReview(**{**payload(), **change})

    def test_snapshot_is_detached_and_never_claims_signature(self):
        review = ContractReview(**payload())
        snapshot = build_snapshot(review, {'buyer_company_id':12,'payer_company_id':99,'supplier_id':5})
        review.buyer.fullName = 'Changed later'
        self.assertEqual(snapshot['buyer']['fullName'], 'Компания А')
        self.assertEqual(snapshot['buyer']['companyId'], 12)
        self.assertEqual(snapshot['supplier']['supplierId'], 5)
        self.assertEqual(snapshot['signatureStatus'], 'not_verified')
        self.assertFalse(snapshot['appliedToAccounting'])
