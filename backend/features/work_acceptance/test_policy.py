from decimal import Decimal
import unittest

from fastapi import HTTPException

from .policy import review_quantities


class ReviewPolicyTests(unittest.TestCase):
    def test_partial_keeps_exact_total_and_requires_reason(self):
        self.assertEqual(review_quantities('100', '60', 'accept', 'Исправить оставшиеся участки'),
                         (Decimal('60'), Decimal('40')))
        with self.assertRaises(HTTPException):
            review_quantities('100', '60', 'accept', ' ')

    def test_full_acceptance_and_full_return_are_different_decisions(self):
        self.assertEqual(review_quantities('0.3', '0.3', 'accept', ''),
                         (Decimal('0.3'), Decimal('0')))
        self.assertEqual(review_quantities('0.3', None, 'return', 'Нужно исправить'),
                         (Decimal('0'), Decimal('0.3')))
        with self.assertRaises(HTTPException):
            review_quantities('0.3', '0', 'accept', 'Нужно исправить')

    def test_invalid_quantities_and_unknown_decisions_fail(self):
        for value in ('-1', '0', '2', 'NaN', 'Infinity', True, '0.0000001'):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                review_quantities('1', value, 'accept', 'Причина')
        with self.assertRaises(HTTPException):
            review_quantities('1', '1', 'other', '')
        with self.assertRaises(HTTPException):
            review_quantities('1', '0.5', 'return', 'Причина')
