import unittest

from fastapi import HTTPException

from .attachments import normalize_attachment
from .commands import command_fingerprint


class AttachmentCommandTests(unittest.TestCase):
    def body(self):
        return dict(requestId='0e756440-01cd-440f-89bb-493e3b323be6', invoiceId=1,
                    warehouseId=2, reason='Full receipt')

    def test_strict_fields_and_ids(self):
        for body in (None, {}, {**self.body(), 'amount': '1'},
                     {**self.body(), 'invoiceId': True}, {**self.body(), 'warehouseId': '2'},
                     {**self.body(), 'requestId': 'bad'}, {**self.body(), 'reason': ' '},
                     {**self.body(), 'reason': 'x' * 1001}):
            with self.subTest(body=body), self.assertRaises(HTTPException) as error:
                normalize_attachment(body)
            self.assertEqual(error.exception.status_code, 422)

    def test_reason_canonicalization_and_identity_fingerprint(self):
        first = normalize_attachment(self.body())
        self.assertEqual(first, normalize_attachment({**self.body(), 'reason': ' Full receipt '}))
        fingerprint = command_fingerprint(2, 5, first)
        for company, actor, command in ((3, 5, first), (2, 6, first),
                                        (2, 5, {**first, 'warehouseId': 3})):
            self.assertNotEqual(fingerprint, command_fingerprint(company, actor, command))
