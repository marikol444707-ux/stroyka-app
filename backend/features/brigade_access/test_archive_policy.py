import unittest

from fastapi import HTTPException

from backend.features.brigade_access.archive_policy import require_empty_signed_duplicate


CONTRACT = {
    "id": 20,
    "companyId": 7,
    "projectId": 24,
    "workPackage": "Основная",
    "contractorId": 5627,
    "brigadeName": "Исполнитель",
    "status": "Подписан",
    "partySnapshot": None,
    "contractScanUrl": "",
    "actScanUrl": "",
}


class Cursor:
    def __init__(self, results):
        self.results = list(results)
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.results.pop(0)


class ArchivePolicyTests(unittest.TestCase):
    def test_allows_only_empty_signed_duplicate_in_same_company_and_project(self):
        cursor = Cursor([None, None, None, None, (1,)])
        require_empty_signed_duplicate(cursor, CONTRACT)
        peer_sql, peer_params = cursor.queries[-1]
        self.assertIn("peer.company_id=%s AND peer.project_id=%s", peer_sql)
        self.assertIn("peer.contractor_id=%s", peer_sql)
        self.assertEqual(peer_params, (7, 24, "Основная", 20, 5627))

    def test_preserves_contract_with_items_payments_or_acts(self):
        for index in range(4):
            with self.subTest(index=index):
                cursor = Cursor([None] * index + [(1,)])
                with self.assertRaises(HTTPException) as caught:
                    require_empty_signed_duplicate(cursor, CONTRACT)
                self.assertEqual(caught.exception.status_code, 409)
                self.assertFalse(any("FROM brigade_contracts peer" in sql for sql, _ in cursor.queries))

    def test_preserves_signed_file_or_frozen_parties(self):
        for field, value in (("contractScanUrl", "/docs/20.pdf"), ("actScanUrl", "/docs/act.pdf"), ("partySnapshot", {})):
            with self.subTest(field=field):
                cursor = Cursor([])
                with self.assertRaises(HTTPException) as caught:
                    require_empty_signed_duplicate(cursor, {**CONTRACT, field: value})
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(cursor.queries, [])

    def test_preserves_contract_without_active_peer(self):
        cursor = Cursor([None, None, None, None, None])
        with self.assertRaises(HTTPException) as caught:
            require_empty_signed_duplicate(cursor, CONTRACT)
        self.assertEqual(caught.exception.status_code, 409)

    def test_unlinked_brigade_matches_name_only_without_contractor_id(self):
        cursor = Cursor([None, None, None, None, (1,)])
        require_empty_signed_duplicate(cursor, {**CONTRACT, "contractorId": None})
        peer_sql, peer_params = cursor.queries[-1]
        self.assertIn("peer.contractor_id IS NULL", peer_sql)
        self.assertEqual(peer_params[-1], "Исполнитель")

    def test_existing_draft_archiving_remains_available(self):
        cursor = Cursor([])
        require_empty_signed_duplicate(cursor, {**CONTRACT, "status": "Черновик"})
        self.assertEqual(cursor.queries, [])


if __name__ == "__main__":
    unittest.main()
