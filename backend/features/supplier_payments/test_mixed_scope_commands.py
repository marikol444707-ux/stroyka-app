import unittest
from uuid import uuid4
from unittest.mock import Mock
from fastapi import HTTPException
from .mixed_scope_evidence import normalize, save_review


class MixedScopeCommandTests(unittest.TestCase):
    def body(self):
        return dict(requestId=str(uuid4()),invoiceId=4,evidenceHash='a'*64,reason=' Проверено ')

    def test_canonical_reason_and_identity(self):
        body=self.body();result=normalize(body)
        self.assertEqual(result,{**body,'reason':'Проверено'})

    def test_malformed_or_client_authority_rejected_before_database(self):
        body=self.body()
        invalid=[None,[],{},dict(body,companyId=2),dict(body,actorId=1),dict(body,invoiceId=True),
                 dict(body,requestId='bad'),dict(body,evidenceHash='a'*63),dict(body,reason=' ')]
        for command in invalid:
            with self.subTest(command=command):
                db=Mock(side_effect=AssertionError('Database must not be reached'))
                with self.assertRaises(HTTPException) as error:
                    save_review(db,Mock(),1,2,command)
                self.assertEqual(error.exception.status_code,422)
                db.assert_not_called()
