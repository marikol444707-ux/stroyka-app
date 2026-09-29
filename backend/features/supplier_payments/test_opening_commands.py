import unittest
from uuid import uuid4
from fastapi import HTTPException
from .openings import normalize


class OpeningCommandTests(unittest.TestCase):
    def body(self):
        return dict(requestId=str(uuid4()),invoiceId=1,reviewedHash='a'*64,reason='Документы сверены')

    def test_no_amount_or_actor_can_be_supplied(self):
        for field in ('amount','openingPaid','actorId','companyId','sourceSnapshot'):
            with self.subTest(field=field),self.assertRaises(HTTPException):
                normalize({**self.body(),field:'1'})

    def test_required_identity_hash_reason(self):
        for field,value in [('requestId','bad'),('invoiceId',True),('invoiceId',0),
                            ('reviewedHash','a'*63),('reason',' '),('reason','a'*1001)]:
            with self.subTest(field=field),self.assertRaises(HTTPException):
                normalize({**self.body(),field:value})
        for field in self.body():
            body=self.body();del body[field]
            with self.assertRaises(HTTPException):
                normalize(body)

    def test_exact_review_command(self):
        body=self.body();result=normalize(body)
        self.assertEqual(result['documentId'],1)
        self.assertEqual(result['reviewedHash'],body['reviewedHash'])
        self.assertEqual(result['kind'],'opening')
