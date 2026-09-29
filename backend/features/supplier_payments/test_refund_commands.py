"""Public command shape for a future atomic allocated refund endpoint."""
import unittest
from copy import deepcopy
from fastapi import HTTPException
from .commands import command_fingerprint
from .refund_commands import normalize_refund_command


class RefundCommandTests(unittest.TestCase):
    def setUp(self):
        self.body = dict(requestId='12345678-1234-4234-8234-123456789abc',
                         groupId=1, expectedVersion=2, paymentId=3,
                         amount='25', unallocatedAmount='5', paidAt='2026-09-28',
                         reason=' Возврат ', releases=[dict(receiptId=4, amount='20')])

    def reject(self, body):
        with self.assertRaises(HTTPException) as caught:
            normalize_refund_command(body)
        self.assertEqual(caught.exception.status_code, 422)

    def test_normalizes_without_mutation(self):
        old = deepcopy(self.body)
        result = normalize_refund_command(self.body)
        self.assertEqual(result['amount'], '25.00')
        self.assertEqual(result['reason'], 'Возврат')
        self.assertEqual(self.body, old)

    def test_reordered_releases_have_same_fingerprint(self):
        self.body.update(releases=[dict(receiptId=7, amount='10'), dict(receiptId=4, amount='10')])
        first = normalize_refund_command(self.body)
        self.body['releases'].reverse()
        self.assertEqual(command_fingerprint(1, 2, first),
                         command_fingerprint(1, 2, normalize_refund_command(self.body)))
        self.assertNotEqual(command_fingerprint(1, 2, first), command_fingerprint(2, 2, first))

    def test_unknown_and_missing_fields_rejected(self):
        for field in self.body:
            self.reject({k:v for k,v in self.body.items() if k != field})
        for field in ('actorId', 'companyId', 'invoiceId', 'kind', 'refundId'):
            self.reject(dict(self.body, **{field:1}))

    def test_invalid_money(self):
        for field in ('amount', 'unallocatedAmount'):
            for value in (True, 1.5, None, 'NaN', 'Infinity', '-1', '0.001'):
                with self.subTest(field=field, value=value):
                    self.reject(dict(self.body, **{field:value}))
        self.reject(dict(self.body, amount='0'))

    def test_exact_sum_required(self):
        self.reject(dict(self.body, unallocatedAmount='4.99'))
        self.reject(dict(self.body, unallocatedAmount='5.01'))
        result = normalize_refund_command(dict(self.body, amount='0.03', unallocatedAmount='0.01',
            releases=[dict(receiptId=4, amount='0.02')]))
        self.assertEqual(result['amount'], '0.03')

    def test_free_only_refund(self):
        self.assertEqual(normalize_refund_command(dict(self.body, releases=[], unallocatedAmount='25'))['releases'], [])

    def test_release_validation(self):
        for rows in (None, {}, [dict(receiptId=4, amount='0')],
                     [dict(receiptId=4, amount='20', extra=True)],
                     [dict(receiptId=4, amount='10')]*2,
                     [dict(receiptId=True, amount='20')],
                     [dict(receiptId=4, amount=20.0)],
                     [dict(receiptId=i+1, amount='0.01') for i in range(2001)]):
            self.reject(dict(self.body, releases=rows))

    def test_identity_version_date_reason(self):
        for field in ('groupId', 'paymentId'):
            for value in (True, 0, -1, '1', 2**63):
                self.reject(dict(self.body, **{field:value}))
        for value in (True, -1, '0', 2147483647):
            self.reject(dict(self.body, expectedVersion=value))
        for value in ('2026-02-30', '2026-09-28T10:00:00', None):
            self.reject(dict(self.body, paidAt=value))
        for value in ('', ' ', 'a'*1001, None):
            self.reject(dict(self.body, reason=value))
        self.reject(dict(self.body, requestId='not-a-uuid'))
