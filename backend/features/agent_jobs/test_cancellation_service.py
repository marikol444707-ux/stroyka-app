import unittest
from pathlib import Path

from backend.features.agent_jobs.cancellation_service import (
    AgentJobCancellationError,
    cancel_queued_agent_job,
)


class FakeCursor:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchone(self):
        return self.current


def job(status="cancelled"):
    return {
        "id": 41,
        "company_id": 7,
        "project_id": 12,
        "job_type": "director.daily_brief",
        "status": status,
        "payload_json": {"private": "payload"},
        "result_json": {"private": "result"},
        "locked_by": None,
        "lease_token": None,
    }


class AgentJobCancellationServiceTests(unittest.TestCase):
    def test_production_smoke_is_rollback_only_and_verifies_audit_cleanup(self):
        smoke_path = (
            Path(__file__).resolve().parents[3]
            / "scripts"
            / "smoke-agent-job-cancellation.py"
        )
        source = " ".join(smoke_path.read_text(encoding="utf-8").split())

        self.assertIn("cancel_queued_agent_job", source)
        self.assertIn("insert_audit_event", source)
        self.assertIn("conn.rollback()", source)
        self.assertIn("persistedAgentJobs", source)
        self.assertIn("persistedAuditRows", source)
        self.assertIn("status == \"running\"", source)

    def test_cancels_only_a_queued_job_in_the_selected_company(self):
        cur = FakeCursor([job()])

        result = cancel_queued_agent_job(
            cur,
            company_id=7,
            job_id=41,
            reason_code="duplicate",
        )

        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["reasonCode"], "duplicate")
        self.assertEqual(result["job"]["status"], "cancelled")
        sql, params = cur.calls[0]
        self.assertIn("SET status='cancelled'", sql)
        self.assertIn("completed_at=NOW()", sql)
        self.assertIn("locked_by=NULL", sql)
        self.assertIn("lease_token=NULL", sql)
        self.assertNotIn("last_error=", sql)
        self.assertIn("WHERE id=%s AND company_id=%s AND status='queued'", sql)
        self.assertEqual(params, (41, 7))

    def test_running_job_is_not_cancelled(self):
        cur = FakeCursor([None, {"status": "running"}])

        result = cancel_queued_agent_job(cur, company_id=7, job_id=41)

        self.assertEqual(result, {
            "state": "conflict",
            "currentStatus": "running",
            "reasonCode": "user_request",
        })
        self.assertEqual(len(cur.calls), 2)
        self.assertIn("status='queued'", cur.calls[0][0])
        self.assertEqual(cur.calls[1][1], (41, 7))

    def test_job_from_another_company_is_not_found(self):
        cur = FakeCursor([None, None])

        result = cancel_queued_agent_job(cur, company_id=7, job_id=41)

        self.assertEqual(result, {
            "state": "not_found",
            "reasonCode": "user_request",
        })

    def test_rejects_unknown_reason_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobCancellationError):
            cancel_queued_agent_job(
                cur,
                company_id=7,
                job_id=41,
                reason_code="free-form secret text",
            )

        self.assertEqual(cur.calls, [])


if __name__ == "__main__":
    unittest.main()
