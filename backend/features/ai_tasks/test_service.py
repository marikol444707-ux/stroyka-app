import unittest

from fastapi import HTTPException

from backend.features.ai_tasks.service import resolve_task_owner, task_owner_filter


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        return list(self.current or [])


class AiTaskRuntimeServiceTests(unittest.TestCase):
    def test_task_inherits_stored_finding_owner(self):
        cur = FakeCursor([
            {"company_id": 4, "project_id": 10, "project_name": "Объект A"},
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
        ])
        owner = resolve_task_owner(cur, {"projectName": "Объект A", "findingId": 20})
        self.assertEqual(owner, {"scope": "company", "companyId": 4, "projectId": 10, "projectName": "Объект A"})

    def test_task_without_finding_uses_exact_project_owner(self):
        cur = FakeCursor([])
        owner = resolve_task_owner(
            cur,
            {"projectName": "Объект A"},
            project_owner={"id": 10, "companyId": 4, "name": "Объект A"},
        )
        self.assertEqual((owner["scope"], owner["companyId"], owner["projectId"]), ("company", 4, 10))
        self.assertEqual(cur.calls, [])

    def test_system_task_has_platform_scope_without_ids(self):
        cur = FakeCursor([])
        owner = resolve_task_owner(cur, {"projectName": "Система"})
        self.assertEqual(owner, {"scope": "platform", "companyId": None, "projectId": None, "projectName": "Система"})

    def test_system_task_with_finding_fails_closed(self):
        with self.assertRaises(HTTPException) as caught:
            resolve_task_owner(FakeCursor([]), {"projectName": "Система", "findingId": 20})
        self.assertEqual(caught.exception.status_code, 409)

    def test_company_filter_uses_all_stored_owner_fields(self):
        sql, params = task_owner_filter({"scope": "company", "companyId": 4, "projectId": 10}, alias="t")
        self.assertEqual(sql, "t.owner_scope='company' AND t.company_id=%s AND t.project_id=%s")
        self.assertEqual(params, [4, 10])


if __name__ == "__main__":
    unittest.main()
