import unittest

from fastapi import HTTPException

from backend.features.ai_findings.service import (
    close_stale_findings,
    resolve_project_owner,
    upsert_finding,
    validate_linked_entity_owner,
)


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.current = []
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else []

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current


class AiFindingsServiceTests(unittest.TestCase):
    def test_resolve_project_uses_selected_company_and_trimmed_name(self):
        cur = FakeCursor([[{"id": 10, "company_id": 4, "name": "Объект A "}]])
        project = resolve_project_owner(cur, "Объект A", company_id=4)
        self.assertEqual(project, {"id": 10, "companyId": 4, "name": "Объект A "})
        self.assertEqual(cur.calls[0][1], (4, "Объект A"))
        self.assertIn("BTRIM(name)=BTRIM(%s)", cur.calls[0][0])

    def test_global_resolution_rejects_same_name_in_two_companies(self):
        cur = FakeCursor([[
            {"id": 10, "company_id": 4, "name": "Объект A"},
            {"id": 11, "company_id": 8, "name": "Объект A"},
        ]])
        with self.assertRaises(HTTPException) as caught:
            resolve_project_owner(cur, "Объект A")
        self.assertEqual(caught.exception.status_code, 409)

    def test_linked_entity_must_resolve_to_same_stored_owner(self):
        cur = FakeCursor([[
            {"entity_project_name": "Объект B", "project_id": 11, "company_id": 8},
        ]])
        with self.assertRaises(HTTPException) as caught:
            validate_linked_entity_owner(cur, {"id": 10, "companyId": 4, "name": "Объект A"}, "room", "30")
        self.assertEqual(caught.exception.status_code, 409)

    def test_unsupported_linked_entity_fails_closed(self):
        cur = FakeCursor([])
        with self.assertRaises(HTTPException) as caught:
            validate_linked_entity_owner(cur, {"id": 10, "companyId": 4, "name": "Объект A"}, "invoice", "30")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(cur.calls, [])

    def test_upsert_dedupe_is_scoped_by_stored_owner(self):
        cur = FakeCursor([[{"id": 20}]])
        ensured = []
        finding_id, created = upsert_finding(
            cur,
            {"projectName": "Объект A", "title": "Проверить", "dedupeKey": "same"},
            {"id": 7, "name": "Директор"},
            {"id": 10, "companyId": 4, "name": "Объект A"},
            normalize_assignment=lambda *_args: {"assignedRole": "прораб", "assignedTo": ""},
            ensure_task=lambda *_args: ensured.append(True),
        )
        self.assertEqual((finding_id, created), (20, False))
        self.assertEqual(cur.calls[0][1], (4, 10, "same"))
        self.assertIn("company_id=%s AND project_id=%s", cur.calls[1][0])
        self.assertEqual(ensured, [True])

    def test_insert_persists_company_and_project_owner(self):
        cur = FakeCursor([[{"id": 22}]])
        finding_id, created = upsert_finding(
            cur,
            {"projectName": "Объект A", "title": "Новая"},
            {"id": 7, "name": "Директор"},
            {"id": 10, "companyId": 4, "name": "Объект A"},
            normalize_assignment=lambda *_args: {"assignedRole": "", "assignedTo": ""},
            ensure_task=lambda *_args: None,
        )
        self.assertEqual((finding_id, created), (22, True))
        self.assertIn("company_id,project_id,project_name", cur.calls[0][0])
        self.assertEqual(cur.calls[0][1][:3], (4, 10, "Объект A"))

    def test_close_stale_findings_is_owner_scoped(self):
        cur = FakeCursor([[
            {"id": 20, "dedupe_key": "keep"},
            {"id": 21, "dedupe_key": "stale"},
        ]])
        count = close_stale_findings(
            cur, {"id": 10, "companyId": 4, "name": "Объект A"}, ["ЖПР"], {"keep"}
        )
        self.assertEqual(count, 1)
        self.assertEqual(cur.calls[0][1], (4, 10, ["ЖПР"]))
        self.assertEqual(cur.calls[1][1], (4, 10, [21]))


if __name__ == "__main__":
    unittest.main()
