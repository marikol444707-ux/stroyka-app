import unittest

from fastapi import HTTPException

from backend.features.customer_contract_parties.customer_act_storage import freeze_customer_act_if_ready
from backend.features.customer_contract_parties.snapshot import contract_snapshot_digest


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


PARTIES = {
    "schemaVersion": 1,
    "executor": {"companyId": 3, "fullName": "ООО Исполнитель"},
    "customer": {"clientId": 8, "fullName": "ООО Заказчик"},
    "project": {"id": 17, "name": "Лицей"},
    "contract": {"number": "15", "date": "2026-10-01", "version": 1},
    "source": {"fileId": 70, "fileUrl": "/tenant-files/70/content"},
}
DOCUMENT = {
    "id": 44, "company_id": 3, "project_id": 17, "side": "customer",
    "doc_type": "Акт КС-2", "number": "2", "doc_date": "2026-10-01",
    "counterparty": "ООО Заказчик", "amount": 1200, "scan_url": "/tenant-files/77/content",
    "sign_status": "Подписан", "basis_contract_document_id": 40,
    "party_snapshot_json": None, "party_snapshot_hash": None,
    "project_name": "Лицей", "client_id": 8,
}
FILE = {"id": 77, "company_id": 3, "project_id": 17, "deletion_status": "active"}
CONTRACT = {
    "id": 40, "company_id": 3, "project_id": 17, "side": "customer",
    "doc_type": "Договор", "number": "15", "doc_date": "2026-09-01",
    "contract_version": 1, "party_snapshot_json": PARTIES,
    "party_snapshot_hash": contract_snapshot_digest(PARTIES), "customer_client_id": 8,
    "sign_status": "Подписан", "scan_url": "/tenant-files/70/content",
}


class CustomerActStorageTest(unittest.TestCase):
    def test_freezes_act_from_exact_contract_and_protected_original(self):
        cursor = Cursor([DOCUMENT, FILE, CONTRACT])
        result = freeze_customer_act_if_ready(cursor, 44, {"id": 5, "name": "Директор"})
        self.assertEqual(result["executor"], PARTIES["executor"])
        self.assertEqual(result["customer"], PARTIES["customer"])
        self.assertEqual(result["contractBasis"]["documentId"], 40)
        self.assertEqual(result["source"]["fileId"], 77)
        self.assertTrue(any("party_snapshot_json=%s::jsonb" in sql for sql, _ in cursor.calls))

    def test_unsigned_act_does_not_load_contract(self):
        cursor = Cursor([dict(DOCUMENT, sign_status="На подписи")])
        self.assertIsNone(freeze_customer_act_if_ready(cursor, 44, {}))
        self.assertEqual(len(cursor.calls), 1)

    def test_signed_act_requires_a_protected_original(self):
        cursor = Cursor([dict(DOCUMENT, scan_url="")])
        with self.assertRaises(HTTPException) as raised:
            freeze_customer_act_if_ready(cursor, 44, {})
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("Загрузите", raised.exception.detail)

    def test_rejects_contract_from_another_project(self):
        cursor = Cursor([DOCUMENT, FILE, dict(CONTRACT, project_id=18)])
        with self.assertRaises(HTTPException) as raised:
            freeze_customer_act_if_ready(cursor, 44, {})
        self.assertEqual(raised.exception.status_code, 409)

    def test_rejects_damaged_contract_snapshot(self):
        cursor = Cursor([DOCUMENT, FILE, dict(CONTRACT, party_snapshot_hash="a" * 64)])
        with self.assertRaises(HTTPException) as raised:
            freeze_customer_act_if_ready(cursor, 44, {})
        self.assertIn("повреждён", raised.exception.detail)

    def test_rejects_digest_valid_snapshot_with_foreign_party_ids(self):
        foreign = {**PARTIES, "customer": {**PARTIES["customer"], "clientId": 99}}
        contract = dict(CONTRACT, party_snapshot_json=foreign,
                        party_snapshot_hash=contract_snapshot_digest(foreign))
        cursor = Cursor([DOCUMENT, FILE, contract])
        with self.assertRaises(HTTPException) as raised:
            freeze_customer_act_if_ready(cursor, 44, {})
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("не соответствуют", raised.exception.detail)

    def test_rejects_foreign_act_original(self):
        cursor = Cursor([DOCUMENT, dict(FILE, company_id=9)])
        with self.assertRaises(HTTPException) as raised:
            freeze_customer_act_if_ready(cursor, 44, {})
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
