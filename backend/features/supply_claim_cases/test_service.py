import unittest

from fastapi import HTTPException

from . import service


class ClaimPolicyTests(unittest.TestCase):
    def test_only_directors_resolve_and_reopen(self):
        self.assertTrue(service.capabilities('директор', 'Открыта')['canResolve'])
        self.assertFalse(service.capabilities('снабженец', 'Открыта')['canResolve'])
        self.assertTrue(service.capabilities('зам_директора', 'Решена')['canReopen'])
        self.assertFalse(service.capabilities('прораб', 'Решена')['canReopen'])

    def test_supplier_reply_requires_open_case(self):
        self.assertTrue(service.capabilities('поставщик', 'В работе')['canReply'])
        self.assertFalse(any(service.capabilities('поставщик', 'Решена').values()))
        self.assertFalse(any(service.capabilities('директор', 'Неизвестно').values()))

    def test_exact_input_envelope_and_text(self):
        body = dict(action='comment', text=' ответ ', expectedVersion=1, expectedActorId=2,
                    expectedCompanyId=3, requestId='unused-in-policy-validation')
        self.assertEqual(service.validate(body), ('comment', 'ответ'))
        for change in ({'status': 'Решена'}, {'text': ''}, {'text': 'a'*4001},
                       {'text': '\x00'}, {'action': 'delete'}, {'expectedVersion': True},
                       {'expectedActorId': '2'}, {'expectedCompanyId': None}):
            with self.subTest(change=change), self.assertRaises(HTTPException):
                service.validate({**body, **change})
