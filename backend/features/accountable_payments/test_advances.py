from decimal import Decimal
import unittest
from fastapi import HTTPException
from .advances import money, expected_revision


class AdvanceValidationTests(unittest.TestCase):
    def test_money_uses_exact_cents(self):
        self.assertEqual(money('100.01'), Decimal('100.01'))
        self.assertEqual(money(0), Decimal('0'))

    def test_invalid_money_cannot_enter_ledger(self):
        for value in [True, None, 'NaN', 'Infinity', '-1', '0.001', '1000000000000']:
            with self.subTest(value=value), self.assertRaises(HTTPException):
                money(value)

    def test_expected_revision_is_mandatory_integer(self):
        for value in [None, True, -1, '0', 0.1]:
            with self.subTest(value=value), self.assertRaises(HTTPException):
                expected_revision(value)
        self.assertEqual(expected_revision(0), 0)
