import unittest
from fastapi import HTTPException
from .commands import normalize_command, command_fingerprint


class CommandTests(unittest.TestCase):
    def body(self, **overrides):
        return dict(requestId='0e756440-01cd-440f-89bb-493e3b323be6', kind='payment',
                    documentKind='invoice', documentId=1, amount='0.10',
                    paidAt='2026-09-18', reason='Recorded bank payment', **overrides)

    def test_canonical_amount_and_reason(self):
        a = self.body(); b = {**a, 'amount': 0.1, 'reason': ' Recorded bank payment '}
        self.assertEqual(normalize_command(a), normalize_command(b))
        self.assertEqual(normalize_command(a)['amount'], '0.10')

    def test_invalid_amounts_and_unknown_fields(self):
        for value in (True, -1, 0, None, 'NaN', 'Infinity', '0.001', '1000000000000'):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                normalize_command({**self.body(), 'amount': value})
        with self.assertRaises(HTTPException):
            normalize_command({**self.body(), 'payerCompanyId': 3})

    def test_invalid_identity_and_date(self):
        for key, value in (('documentId', True), ('documentId', -1), ('documentKind', 'sql'),
                           ('requestId', 'bad'), ('paidAt', '2026-02-30'), ('reason', ' ')):
            with self.subTest(key=key), self.assertRaises(HTTPException):
                normalize_command({**self.body(), key: value})

    def test_reversal_has_no_caller_amount(self):
        body = {key: value for key, value in self.body().items() if key != 'amount'}
        body.update(kind='reversal', reversesId=9)
        self.assertEqual(normalize_command(body)['reversesId'], 9)
        with self.assertRaises(HTTPException):
            normalize_command({**body, 'amount': '1'})

    def test_fingerprint_scopes_actor_company_and_payload(self):
        command = normalize_command(self.body())
        first = command_fingerprint(2, 5, command)
        self.assertNotEqual(first, command_fingerprint(3, 5, command))
        self.assertNotEqual(first, command_fingerprint(2, 6, command))
        self.assertNotEqual(first, command_fingerprint(2, 5, {**command, 'amount': '0.20'}))
