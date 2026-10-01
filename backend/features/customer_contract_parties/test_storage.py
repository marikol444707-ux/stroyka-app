import unittest

from fastapi import HTTPException

from backend.features.customer_contract_parties.storage import freeze_customer_contract_if_ready


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


DOCUMENT = {
    "id": 40, "company_id": 3, "project_id": 17, "side": "customer",
    "doc_type": "Договор", "number": "15", "doc_date": "2026-10-01",
    "scan_url": "/tenant-files/77/content", "sign_status": "Подписан",
    "contract_version": 1, "revises_document_id": None,
    "party_snapshot_json": None, "party_snapshot_hash": None,
    "project_name": "Лицей", "client_id": 8,
}
COMPANY = {
    "company_id": 3, "full_name": "ООО Исполнитель", "inn": "2611008712",
    "legal_address": "Ставрополь", "director_name": "Петров П.П.",
    "director_position": "Директор", "basis": "Устава",
}
CUSTOMER = {
    "id": 8, "company_id": 3, "name": "ООО Заказчик", "inn": "2632090186",
    "legal_address": "Пятигорск", "director_name": "Иванов И.И.",
    "director_position": "Директор", "basis": "Устава",
}
FILE = {"id": 77, "company_id": 3, "project_id": 17, "deletion_status": "active"}


class CustomerContractStorageTest(unittest.TestCase):
    def test_freezes_exact_profiles_on_signed_contract_with_original(self):
        cursor = Cursor([DOCUMENT, FILE, COMPANY, CUSTOMER])
        result = freeze_customer_contract_if_ready(cursor, 40, {"id": 5, "name": "Директор"})
        self.assertEqual(result["customer"]["clientId"], 8)
        update = cursor.calls[-1]
        self.assertIn("customer_client_id=%s", update[0])
        self.assertEqual(update[1][-3:], (8, 40, 3))
        self.assertEqual(result["source"]["fileId"], 77)

    def test_unsigned_document_is_not_frozen_or_profile_loaded(self):
        cursor = Cursor([dict(DOCUMENT, sign_status="На подписи")])
        self.assertIsNone(freeze_customer_contract_if_ready(cursor, 40, {}))
        self.assertEqual(len(cursor.calls), 1)

    def test_existing_snapshot_is_returned_without_current_profiles(self):
        saved = {"schemaVersion": 1, "customer": {"clientId": 8}}
        cursor = Cursor([dict(DOCUMENT, party_snapshot_json=saved, party_snapshot_hash="a" * 64)])
        self.assertEqual(freeze_customer_contract_if_ready(cursor, 40, {}), saved)
        self.assertEqual(len(cursor.calls), 1)

    def test_foreign_original_cannot_be_frozen(self):
        cursor = Cursor([DOCUMENT, dict(FILE, company_id=9)])
        with self.assertRaises(HTTPException) as raised:
            freeze_customer_contract_if_ready(cursor, 40, {})
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
