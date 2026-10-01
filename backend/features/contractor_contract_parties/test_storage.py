import datetime
import unittest

from fastapi import HTTPException

from .storage import freeze_contract


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.rows.pop(0)


CONTRACT = (71, 3, 17, "Лицей", "Иванов", "ИП", 41, "Черновик", None, None, None)
FILE = (77, 3, 17, "active")
COMPANY = (3, "ООО Альянс", "2611008712", "261101001", "1" * 13, "Ставрополь",
           "Петров П.П.", "Директор", "Устава", "Банк", "044525104", "4" * 20, "3" * 20)
CONTRACTOR = (41, "Иванов Иван", "07 01 123456", "263200000001", "ИП",
              "4" * 20, "Банк ИП", "+79990000000", "3" * 15)


class ContractorContractStorageTests(unittest.TestCase):
    def test_freezes_only_exact_owned_file_and_exact_user_profile(self):
        cur = Cursor([CONTRACT, FILE, COMPANY, CONTRACTOR, (datetime.date(2026, 10, 1),)])
        snapshot = freeze_contract(cur, 71, 3, "/tenant-files/77/content", {"id": 9, "name": "Директор"})
        self.assertEqual(snapshot["contractor"]["userId"], 41)
        self.assertEqual(snapshot["source"]["fileId"], 77)
        sql = "\n".join(call[0] for call in cur.calls)
        self.assertIn("WHERE mp.user_id=%s", sql)
        self.assertIn("UPDATE file_ownership SET retained_at", sql)
        self.assertIn("party_snapshot_json=%s::jsonb", sql)
        profile_call = next(call for call in cur.calls if "FROM master_profiles" in call[0])
        self.assertEqual(profile_call[1], (41, 3, 3))

    def test_rejects_file_from_other_company_before_reading_profiles(self):
        cur = Cursor([CONTRACT, (77, 4, 17, "active")])
        with self.assertRaises(HTTPException) as raised:
            freeze_contract(cur, 71, 3, "/tenant-files/77/content", {"id": 9})
        self.assertEqual(raised.exception.status_code, 403)
        self.assertFalse(any("FROM master_profiles" in sql for sql, _ in cur.calls))

    def test_never_resolves_contractor_by_name(self):
        cur = Cursor([CONTRACT, FILE, COMPANY, None])
        with self.assertRaises(HTTPException) as raised:
            freeze_contract(cur, 71, 3, "/tenant-files/77/content", {"id": 9})
        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any("full_name=%s" in sql or "name=%s" in sql for sql, _ in cur.calls))


if __name__ == "__main__":
    unittest.main()
