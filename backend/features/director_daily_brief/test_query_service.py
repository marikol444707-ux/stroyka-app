import unittest
from datetime import datetime

from backend.features.director_daily_brief.query_service import (
    DirectorDailyBriefQueryError,
    get_latest_director_daily_brief,
)


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row


def valid_result():
    return {
        "schemaVersion": 1,
        "briefDate": "2026-08-05",
        "mode": "deterministic_read_only",
        "summary": {"total": 2, "critical": 1, "warning": 1, "info": 0},
        "sections": [
            {
                "key": "overdue",
                "title": "Просрочки",
                "status": "attention",
                "count": 1,
                "truncated": False,
                "items": [{
                    "code": "project.deadline_overdue",
                    "severity": "critical",
                    "subject": "Школа",
                    "project": "Школа",
                    "metricValue": 3,
                    "metricUnit": "days",
                }],
            },
            {
                "key": "shortages",
                "title": "Дефициты",
                "status": "attention",
                "count": 1,
                "truncated": False,
                "items": [{
                    "code": "warehouse.below_minimum",
                    "severity": "warning",
                    "subject": "Кабель",
                    "metricValue": 20,
                    "metricUnit": "м",
                }],
            },
            {"key": "documents", "title": "Неподтверждённые документы", "status": "clear", "count": 0, "truncated": False, "items": []},
            {"key": "estimateDeviations", "title": "Отклонения смет", "status": "clear", "count": 0, "truncated": False, "items": []},
            {"key": "payments", "title": "Платежи", "status": "clear", "count": 0, "truncated": False, "items": []},
            {"key": "tasks", "title": "Задачи", "status": "clear", "count": 0, "truncated": False, "items": []},
        ],
        "sourceCounts": {
            "projects": 4,
            "warehouse": 10,
            "supply": 3,
            "estimates": 8,
            "finances": 4,
            "staff": 7,
            "ai_tasks": 2,
        },
    }


class DirectorDailyBriefQueryTests(unittest.TestCase):
    def test_returns_latest_company_scoped_public_projection(self):
        row = {
            "id": 17,
            "company_id": 4,
            "completed_at": datetime(2026, 8, 5, 11, 30, 0),
            "result_json": valid_result(),
            "payload_json": {"must": "stay hidden"},
            "locked_by": "worker-secret",
        }
        cur = FakeCursor(row)

        result = get_latest_director_daily_brief(cur, company_id=4)

        self.assertTrue(result["available"])
        self.assertEqual(result["jobId"], 17)
        self.assertEqual(result["completedAt"], "2026-08-05T11:30:00")
        self.assertEqual(result["brief"]["briefDate"], "2026-08-05")
        self.assertEqual(result["brief"]["sections"][0]["items"][0]["subject"], "Школа")
        self.assertEqual(result["attentionQueue"]["count"], 2)
        self.assertEqual(
            result["attentionQueue"]["items"][0]["reason"],
            "Просрочен срок объекта",
        )
        self.assertEqual(result["attentionQueue"]["items"][1]["project"], "Вся компания")
        self.assertTrue(result["attentionQueue"]["readOnly"])
        self.assertNotIn("payload_json", result)
        self.assertNotIn("result_json", result)
        self.assertNotIn("locked_by", result)
        sql, params = cur.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertIn("project_id IS NULL", sql)
        self.assertIn("job_type=%s", sql)
        self.assertIn("status='succeeded'", sql)
        self.assertEqual(params, (4, "director.daily_brief"))

    def test_returns_explicit_empty_result(self):
        cur = FakeCursor(None)

        self.assertEqual(
            get_latest_director_daily_brief(cur, company_id=4),
            {"available": False},
        )

    def test_rejects_malformed_stored_result(self):
        malformed = valid_result()
        malformed["sections"] = malformed["sections"][:-1]
        cur = FakeCursor({
            "id": 17,
            "completed_at": datetime(2026, 8, 5, 11, 30, 0),
            "result_json": malformed,
        })

        with self.assertRaises(DirectorDailyBriefQueryError):
            get_latest_director_daily_brief(cur, company_id=4)

    def test_rejects_invalid_company_before_sql(self):
        cur = FakeCursor(None)

        with self.assertRaises(DirectorDailyBriefQueryError):
            get_latest_director_daily_brief(cur, company_id=0)

        self.assertEqual(cur.calls, [])


if __name__ == "__main__":
    unittest.main()
