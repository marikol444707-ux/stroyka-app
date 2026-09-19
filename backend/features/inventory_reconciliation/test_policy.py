from unittest import TestCase

from fastapi import HTTPException

from . import policy


class InventoryCountPolicyTests(TestCase):
    rows = [{'key': 'material:1', 'kind': 'material', 'expected': '5.25'},
            {'key': 'tool:3', 'kind': 'tool'}]

    def test_zero_is_a_count_and_difference_is_server_derived(self):
        counts = policy.validate_counts(self.rows, [
            {'key': 'material:1', 'actual': '0', 'reason': 'Пересчитано'},
            {'key': 'tool:3', 'condition': 'as_recorded', 'reason': ''}])
        self.assertEqual(counts['material:1']['actual'], '0')
        self.assertEqual(policy.difference(self.rows[0], counts['material:1']), '-5.25')
        policy.require_complete(self.rows, counts)

    def test_blank_is_not_zero_and_cannot_be_submitted(self):
        counts = policy.validate_counts(self.rows, [{'key': 'material:1', 'actual': '', 'reason': ''}])
        self.assertIsNone(counts['material:1']['actual'])
        with self.assertRaises(HTTPException):
            policy.require_complete(self.rows, counts)

    def test_untrusted_expected_and_difference_are_rejected(self):
        for field in ('expected', 'difference', 'unit', 'materialName', 'price', 'createdBy'):
            with self.subTest(field=field), self.assertRaises(HTTPException):
                policy.validate_counts(self.rows, [{'key': 'material:1', 'actual': '5.25', field: 99}])

    def test_invalid_quantity_duplicates_and_foreign_keys_are_rejected(self):
        for value in (-1, True, 'NaN', 'Infinity', '0.0000001'):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                policy.validate_counts(self.rows, [{'key': 'material:1', 'actual': value}])
        for values in ([{'key': 'material:99', 'actual': '1'}],
                       [{'key': 'material:1', 'actual': '1'}] * 2):
            with self.assertRaises(HTTPException):
                policy.validate_counts(self.rows, values)

    def test_discrepancy_needs_reason_before_submission(self):
        for key, value in [('material:1', {'actual': '4'}), ('tool:3', {'condition': 'missing'})]:
            counts = {'material:1': {'actual': '5.25', 'reason': ''},
                      'tool:3': {'condition': 'as_recorded', 'reason': ''}}
            counts[key] = {**value, 'reason': ''}
            with self.assertRaises(HTTPException):
                policy.require_complete(self.rows, counts)
