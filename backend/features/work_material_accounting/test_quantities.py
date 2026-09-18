from decimal import Decimal
import unittest

from fastapi import HTTPException

from .quantities import quantity, source_quantities, money


class MaterialQuantityTests(unittest.TestCase):
    def test_exact_source_split_is_preserved(self):
        self.assertEqual(source_quantities({
            'quantity': '0.3', 'personalQuantity': '0.1', 'warehouseQuantity': '0.2',
        }), (Decimal('0.3'), Decimal('0.1'), Decimal('0.2')))

    def test_a_visible_source_cannot_be_silently_changed(self):
        for item in ({'quantity': 4},
                     {'quantity': 4, 'personalQuantity': 4},
                     {'quantity': 4, 'personalQuantity': 3, 'warehouseQuantity': 2}):
            with self.subTest(item=item), self.assertRaises(HTTPException):
                source_quantities(item)

    def test_zero_source_allowed_but_positive_total_required(self):
        self.assertEqual(source_quantities({
            'quantity': 5, 'personalQuantity': 0, 'warehouseQuantity': 5,
        }), (Decimal(5), Decimal(0), Decimal(5)))
        with self.assertRaises(HTTPException):
            source_quantities({'quantity': 0, 'personalQuantity': 0, 'warehouseQuantity': 0})

    def test_invalid_quantities_are_not_rounded_or_ignored(self):
        for value in (True, False, None, '', 'NaN', 'Infinity', '-Infinity',
                      '-1', '0.0000001', '100000000', {}, []):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                quantity(value)

    def test_money_has_exact_kopecks(self):
        self.assertEqual(money('100.01'), Decimal('100.01'))
        for value in ('0.001', 'NaN', True, '-1'):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                money(value)


if __name__ == '__main__':
    unittest.main()
