import unittest

from fastapi import HTTPException

from backend.features.customer_contract_parties.snapshot import (
    build_customer_contract_snapshot,
    contract_snapshot_digest,
    is_customer_contract,
)


COMPANY = {
    "company_id": 3, "full_name": "ООО Исполнитель", "inn": "2611008712",
    "kpp": "261101001", "ogrn": "1234567890123", "legal_address": "Ставрополь",
    "director_name": "Петров П.П.", "director_position": "Директор", "basis": "Устава",
    "bank_name": "Банк", "bik": "044525104", "rs": "40702810309500007753",
    "ks": "30101810745374525104", "phone": "+7", "email": "office@example.test",
}
CUSTOMER = {
    "id": 8, "company_id": 3, "name": "ООО Заказчик", "inn": "2632090186",
    "kpp": "263201001", "ogrn": "1092632000001", "legal_address": "Пятигорск",
    "director_name": "Иванов И.И.", "director_position": "Директор", "basis": "Устава",
    "bank_name": "Банк 2", "bik": "044525411", "rs": "40702810415590000143",
    "ks": "30101810145250000411", "phone": "+7", "email": "client@example.test",
}
PROJECT = {"id": 17, "company_id": 3, "name": "Лицей", "client_id": 8}
DOCUMENT = {
    "id": 40, "company_id": 3, "project_id": 17, "side": "customer",
    "doc_type": "Договор", "number": "15", "doc_date": "2026-10-01",
    "scan_url": "/tenant-files/77/content", "sign_status": "Подписан",
    "contract_version": 2, "revises_document_id": 39,
    "source_file_id": 77,
}


class CustomerContractSnapshotTest(unittest.TestCase):
    def test_only_customer_contract_family_is_frozen(self):
        self.assertTrue(is_customer_contract("customer", "Договор подряда"))
        self.assertTrue(is_customer_contract("customer", "Доп.соглашение"))
        self.assertFalse(is_customer_contract("contractor", "Договор"))
        self.assertFalse(is_customer_contract("customer", "Счёт"))

    def test_snapshot_contains_exact_executor_customer_project_and_source(self):
        snapshot = build_customer_contract_snapshot(DOCUMENT, PROJECT, COMPANY, CUSTOMER, {"id": 5, "name": "Директор"})
        self.assertEqual(snapshot["executor"]["companyId"], 3)
        self.assertEqual(snapshot["executor"]["inn"], "2611008712")
        self.assertEqual(snapshot["customer"]["clientId"], 8)
        self.assertEqual(snapshot["customer"]["inn"], "2632090186")
        self.assertEqual(snapshot["project"], {"id": 17, "name": "Лицей"})
        self.assertEqual(snapshot["contract"]["number"], "15")
        self.assertEqual(snapshot["contract"]["version"], 2)
        self.assertEqual(snapshot["contract"]["revisesDocumentId"], 39)
        self.assertEqual(snapshot["source"]["fileUrl"], "/tenant-files/77/content")
        self.assertEqual(snapshot["source"]["fileId"], 77)
        self.assertEqual(len(contract_snapshot_digest(snapshot)), 64)

    def test_snapshot_refuses_cross_company_or_different_customer(self):
        with self.assertRaises(HTTPException):
            build_customer_contract_snapshot(DOCUMENT, PROJECT, COMPANY, dict(CUSTOMER, company_id=9), {})
        with self.assertRaises(HTTPException):
            build_customer_contract_snapshot(DOCUMENT, PROJECT, COMPANY, dict(CUSTOMER, id=9), {})

    def test_snapshot_does_not_invent_missing_legal_identity_or_signer(self):
        for side, broken in (("исполнителя", dict(COMPANY, director_name="")),
                             ("заказчика", dict(CUSTOMER, inn=""))):
            with self.subTest(side=side), self.assertRaises(HTTPException) as raised:
                build_customer_contract_snapshot(DOCUMENT, PROJECT,
                                                 broken if side == "исполнителя" else COMPANY,
                                                 broken if side == "заказчика" else CUSTOMER, {})
            self.assertEqual(raised.exception.status_code, 409)
            self.assertIn(side, str(raised.exception.detail).lower())


if __name__ == "__main__":
    unittest.main()
