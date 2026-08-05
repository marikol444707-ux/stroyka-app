import unittest
from datetime import datetime

from backend.features.agent_jobs.query_service import (
    AgentJobQueryError,
    get_agent_job,
    list_agent_jobs,
)


class FakeCursor:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        return self.current


def job(job_id, *, company_id=4, status="queued"):
    return {
        "id": job_id,
        "company_id": company_id,
        "project_id": 10,
        "requested_by_user_id": 7,
        "requested_by_role": "директор",
        "job_type": "director.daily_brief",
        "correlation_id": f"corr-{job_id}",
        "status": status,
        "priority": 5,
        "attempts": 1,
        "max_attempts": 3,
        "run_after": datetime(2026, 8, 5, 8, 0, 0),
        "heartbeat_at": None,
        "lease_expires_at": None,
        "started_at": None,
        "completed_at": None,
        "last_error": "",
        "created_at": datetime(2026, 8, 5, 7, 0, 0),
        "updated_at": datetime(2026, 8, 5, 7, 0, 0),
        "payload_json": {"must": "stay hidden"},
        "result_json": {"must": "stay hidden"},
        "locked_by": "internal-worker",
        "lease_token": "secret-token",
    }


class AgentJobQueryServiceTests(unittest.TestCase):
    def test_list_is_company_scoped_paginated_and_public_only(self):
        cur = FakeCursor([[job(30), job(29), job(28)]])

        result = list_agent_jobs(
            cur,
            company_id=4,
            status="queued",
            project_id=10,
            before_id=40,
            limit=2,
        )

        self.assertEqual([item["id"] for item in result["items"]], [30, 29])
        self.assertEqual(result["nextBeforeId"], 29)
        sql, params = cur.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertIn("project_id=%s", sql)
        self.assertIn("status=%s", sql)
        self.assertIn("id<%s", sql)
        self.assertEqual(params, (4, 10, "queued", 40, 3))
        exposed = result["items"][0]
        self.assertEqual(exposed["companyId"], 4)
        self.assertEqual(exposed["createdAt"], "2026-08-05T07:00:00")
        self.assertNotIn("payload_json", exposed)
        self.assertNotIn("result_json", exposed)
        self.assertNotIn("locked_by", exposed)
        self.assertNotIn("lease_token", exposed)

    def test_public_error_never_exposes_raw_provider_text(self):
        row = job(30, status="failed")
        row["last_error"] = "OPENAI_API_KEY sk-private-value request failed"
        cur = FakeCursor([row])

        result = get_agent_job(cur, company_id=4, job_id=30)

        self.assertEqual(
            result["lastError"],
            "Ошибка выполнения задачи; подробности доступны в серверном журнале",
        )
        self.assertNotIn("sk-private-value", result["lastError"])

    def test_list_rejects_unknown_status_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobQueryError):
            list_agent_jobs(cur, company_id=4, status="unknown")

        self.assertEqual(cur.calls, [])

    def test_detail_is_scoped_by_job_and_company(self):
        cur = FakeCursor([job(30)])

        result = get_agent_job(cur, company_id=4, job_id=30)

        self.assertEqual(result["id"], 30)
        sql, params = cur.calls[0]
        self.assertIn("id=%s AND company_id=%s", sql)
        self.assertEqual(params, (30, 4))

    def test_detail_from_another_company_is_hidden(self):
        cur = FakeCursor([None])

        result = get_agent_job(cur, company_id=4, job_id=30)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
