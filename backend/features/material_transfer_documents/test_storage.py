import unittest

from fastapi import HTTPException

from backend.features.material_transfer_documents.storage import (
    freeze_material_transfer_issue,
    freeze_material_transfer_receipt,
    snapshot_digest,
)


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


ROW = {
    "id": 41, "company_id": 3, "project_id": 17, "project_name": "Лицей",
    "from_location": "Лицей", "to_user_id": 8, "to_person": "Мастер",
    "to_person_role": "мастер", "work_package": "Отделка", "material_name": "Краска",
    "quantity": 5, "unit": "кг", "transfer_date": "2026-10-01", "notes": "",
    "created_by": "Прораб", "invoice_id": 11, "invoice_line_key": "line-1",
    "invoice_line_index": 0, "invoice_number": "77", "signed": False,
    "issue_party_snapshot_json": None, "issue_party_snapshot_hash": None,
    "receipt_party_snapshot_json": None, "receipt_party_snapshot_hash": None,
    "company_name": "Компания", "full_name": "ООО Компания", "short_name": "",
    "inn": "2611008712", "kpp": "261101001", "ogrn": "1234567890123",
    "legal_address": "Ставрополь", "actual_address": "", "phone": "+7",
    "email": "office@example.test",
}
ISSUER = {"id": 5, "name": "Прораб", "role": "прораб", "companyId": 3}
RECEIVER = {"id": 8, "name": "Мастер", "role": "мастер", "companyId": 3}


class MaterialTransferDocumentStorageTest(unittest.TestCase):
    def test_freezes_issue_from_exact_company_project_and_people(self):
        cursor = Cursor([ROW])
        result = freeze_material_transfer_issue(cursor, 41, ISSUER)
        self.assertEqual(result["company"]["fullName"], "ООО Компания")
        self.assertEqual(result["project"], {"id": 17, "name": "Лицей"})
        self.assertEqual(result["sender"]["userId"], 5)
        self.assertEqual(result["intendedReceiver"]["userId"], 8)
        self.assertEqual(result["source"]["invoiceId"], 11)
        self.assertTrue(any("issue_party_snapshot_json=%s::jsonb" in sql for sql, _ in cursor.calls))

    def test_receipt_reuses_valid_issue_and_freezes_actual_receiver(self):
        issue_cursor = Cursor([ROW])
        issue = freeze_material_transfer_issue(issue_cursor, 41, ISSUER)
        signed_row = dict(ROW, issue_party_snapshot_json=issue,
                          issue_party_snapshot_hash=snapshot_digest(issue))
        cursor = Cursor([signed_row])
        result = freeze_material_transfer_receipt(cursor, 41, RECEIVER)
        self.assertEqual(result["receiver"]["userId"], 8)
        self.assertEqual(result["issueSnapshotHash"], snapshot_digest(issue))
        self.assertTrue(any("signed=TRUE" in sql for sql, _ in cursor.calls))

    def test_receipt_rejects_another_user(self):
        issue_cursor = Cursor([ROW])
        issue = freeze_material_transfer_issue(issue_cursor, 41, ISSUER)
        row = dict(ROW, issue_party_snapshot_json=issue,
                   issue_party_snapshot_hash=snapshot_digest(issue))
        cursor = Cursor([row])
        with self.assertRaises(HTTPException) as raised:
            freeze_material_transfer_receipt(cursor, 41, {**RECEIVER, "id": 9})
        self.assertEqual(raised.exception.status_code, 403)

    def test_receipt_rejects_digest_valid_foreign_issue_identity(self):
        issue_cursor = Cursor([ROW])
        issue = freeze_material_transfer_issue(issue_cursor, 41, ISSUER)
        foreign = {**issue, "project": {"id": 99, "name": "Чужой"}}
        row = dict(ROW, issue_party_snapshot_json=foreign,
                   issue_party_snapshot_hash=snapshot_digest(foreign))
        with self.assertRaises(HTTPException) as raised:
            freeze_material_transfer_receipt(Cursor([row]), 41, RECEIVER)
        self.assertEqual(raised.exception.status_code, 409)

    def test_receipt_rejects_digest_valid_issue_with_changed_material(self):
        issue_cursor = Cursor([ROW])
        issue = freeze_material_transfer_issue(issue_cursor, 41, ISSUER)
        foreign = {**issue, "material": {**issue["material"], "quantity": "500"}}
        row = dict(ROW, issue_party_snapshot_json=foreign,
                   issue_party_snapshot_hash=snapshot_digest(foreign))
        with self.assertRaises(HTTPException) as raised:
            freeze_material_transfer_receipt(Cursor([row]), 41, RECEIVER)
        self.assertEqual(raised.exception.status_code, 409)

    def test_legacy_signed_transfer_is_not_backfilled(self):
        row = dict(ROW, signed=True)
        with self.assertRaises(HTTPException) as raised:
            freeze_material_transfer_receipt(Cursor([row]), 41, RECEIVER)
        self.assertIn("Историческую", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
