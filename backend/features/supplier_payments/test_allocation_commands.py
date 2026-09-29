import unittest
from uuid import uuid4

from fastapi import HTTPException

from .allocation_commands import normalize_allocation_command
from .commands import command_fingerprint


class AllocationCommandTests(unittest.TestCase):
    def body(self, **updates):
        return dict(requestId=str(uuid4()), groupId=3, expectedVersion=0,
                    reason='  Уточнение назначения  ', rows=[dict(paymentId=7, receiptId=8, amount='10')],
                    **updates)

    def test_canonical_money_reason_and_order(self):
        body = self.body()
        body['rows'] = [dict(paymentId=9, receiptId=8, amount='1.00'), body['rows'][0]]
        result = normalize_allocation_command(body)
        self.assertEqual(result['reason'], 'Уточнение назначения')
        self.assertEqual(result['rows'][0], dict(paymentId=7, receiptId=8, amount='10.00'))
        self.assertEqual(body['rows'][0]['paymentId'], 9)

    def test_reordered_equivalent_rows_have_same_fingerprint(self):
        body = self.body()
        body['rows'].append(dict(paymentId=9, receiptId=8, amount='1'))
        left = normalize_allocation_command(body)
        right = normalize_allocation_command({**body, 'rows': list(reversed(body['rows']))})
        self.assertEqual(command_fingerprint(2, 4, left), command_fingerprint(2, 4, right))

    def test_empty_full_map_is_explicit_unallocation(self):
        body = self.body()
        self.assertEqual(normalize_allocation_command({**body, 'rows': []})['rows'], [])

    def test_missing_unknown_and_server_owned_fields_rejected(self):
        body = self.body()
        for name in body:
            altered = {key: value for key, value in body.items() if key != name}
            with self.subTest(missing=name), self.assertRaises(HTTPException):
                normalize_allocation_command(altered)
        for name in ('actorId', 'companyId', 'paidAmount', 'reversed', 'createdAt'):
            with self.subTest(extra=name), self.assertRaises(HTTPException):
                normalize_allocation_command({**body, name: 1})

    def test_bad_identity_or_version_rejected(self):
        for field, values in [('groupId', [True, 1.0, '1', 0, -1]),
                              ('expectedVersion', [True, 1.0, '0', -1, 2147483647]),
                              ('requestId', [None, 'not-a-uuid', 1]),
                              ('reason', ['', ' ', None, 'x' * 1001])]:
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(HTTPException) as caught:
                    normalize_allocation_command({**self.body(), field: value})
                self.assertEqual(caught.exception.status_code, 422)

    def test_duplicate_and_unbounded_maps_rejected(self):
        row = self.body()['rows'][0]
        for rows in ([row, row], [row] * 2001, {}, None):
            with self.assertRaises(HTTPException):
                normalize_allocation_command({**self.body(), 'rows': rows})

    def test_invalid_rows_rejected_without_rounding(self):
        base = self.body()['rows'][0]
        invalid = [None, {}, {**base, 'payerCompanyId': 99}, {**base, 'paymentId': True},
                   {**base, 'receiptId': 0}]
        invalid += [{**base, 'amount': amount} for amount in
                    ('0', '-1', '0.001', 'NaN', 'Infinity', True, None, 0.1)]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(HTTPException):
                normalize_allocation_command({**self.body(), 'rows': [row]})
