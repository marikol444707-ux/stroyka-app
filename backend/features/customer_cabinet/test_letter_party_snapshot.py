import unittest

from fastapi import HTTPException

from .letter_party_snapshot import build_snapshot, snapshot_digest


class LetterPartySnapshotTest(unittest.TestCase):
    def setUp(self):
        self.project = {"id": 17, "company_id": 3, "name": "Лицей", "client_id": 8}
        self.company = {"company_id": 3, "full_name": "ООО Альянс", "short_name": "Альянс",
                        "inn": "2611008712", "email": "office@example.test"}
        self.customer = {"id": 8, "company_id": 3, "name": "Лицей №4", "inn": "2600000000"}
        self.actor = {"id": 9, "name": "Директор"}

    def test_builds_stable_exact_parties(self):
        snapshot = build_snapshot(self.project, self.company, self.customer, self.actor)
        self.assertEqual(snapshot["sender"]["companyId"], 3)
        self.assertEqual(snapshot["sender"]["inn"], "2611008712")
        self.assertEqual(snapshot["recipient"], {
            "clientId": 8, "fullName": "Лицей №4", "inn": "2600000000", "kpp": "",
            "ogrn": "", "legalAddress": "", "phone": "", "email": "",
        })
        self.assertEqual(snapshot["project"], {"id": 17, "name": "Лицей"})
        self.assertEqual(len(snapshot_digest(snapshot)), 64)

    def test_rejects_cross_company_or_wrong_recipient(self):
        for customer in ({**self.customer, "company_id": 4}, {**self.customer, "id": 9}):
            with self.assertRaises(HTTPException):
                build_snapshot(self.project, self.company, customer, self.actor)

    def test_requires_party_names_but_not_optional_requisites(self):
        snapshot = build_snapshot(self.project, {"company_id": 3, "full_name": "Стройка"},
                                  {"id": 8, "company_id": 3, "name": "Заказчик"}, self.actor)
        self.assertEqual(snapshot["sender"]["inn"], "")
        with self.assertRaises(HTTPException):
            build_snapshot(self.project, {"company_id": 3}, self.customer, self.actor)
