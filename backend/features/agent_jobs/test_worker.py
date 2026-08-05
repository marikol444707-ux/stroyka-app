import json
import unittest
from pathlib import Path

from backend.features.agent_jobs.worker import (
    AgentJobWorkerError,
    claim_next_agent_job,
    complete_agent_job,
    fail_agent_job,
    heartbeat_agent_job,
    recover_expired_agent_jobs,
)

LEASE_TOKEN = "a" * 32
OLD_LEASE_TOKEN = "b" * 32


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

    def fetchall(self):
        return list(self.current or [])


class AgentJobWorkerTests(unittest.TestCase):
    def test_production_smoke_uses_the_canonical_companies_table(self):
        smoke_path = (
            Path(__file__).resolve().parents[3]
            / "scripts"
            / "smoke-agent-job-worker.py"
        )
        source = " ".join(smoke_path.read_text(encoding="utf-8").split())

        self.assertIn("FROM companies", source)
        self.assertNotIn("managed_companies", source)

    def test_claim_is_skip_locked_leased_and_handler_allowlisted(self):
        row = {
            "id": 41,
            "company_id": 7,
            "project_id": 12,
            "job_type": "director.daily_brief",
            "status": "running",
            "attempts": 1,
            "locked_by": "worker-1",
            "lease_token": LEASE_TOKEN,
        }
        cur = FakeCursor([row])

        claimed = claim_next_agent_job(
            cur,
            worker_id="worker-1",
            allowed_job_types=("director.daily_brief",),
            lease_seconds=120,
        )

        self.assertEqual(claimed, row)
        sql, params = cur.calls[0]
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
        self.assertIn("status='queued'", sql)
        self.assertIn("attempts < max_attempts", sql)
        self.assertIn("job_type = ANY(%s::text[])", sql)
        self.assertIn("lease_expires_at", sql)
        self.assertEqual(params[0], ["director.daily_brief"])
        self.assertEqual(params[1], "worker-1")
        self.assertRegex(params[2], r"^[a-f0-9]{32}$")
        self.assertEqual(params[3], 120)

    def test_claim_requires_at_least_one_known_job_type(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobWorkerError):
            claim_next_agent_job(
                cur,
                worker_id="worker-1",
                allowed_job_types=(),
            )

        self.assertEqual(cur.calls, [])

    def test_heartbeat_only_extends_the_current_workers_running_job(self):
        row = {"id": 41, "status": "running", "locked_by": "worker-1"}
        cur = FakeCursor([row])

        updated = heartbeat_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=LEASE_TOKEN,
            lease_seconds=120,
        )

        self.assertEqual(updated, row)
        sql, params = cur.calls[0]
        self.assertIn("status='running'", sql)
        self.assertIn("locked_by=%s", sql)
        self.assertIn("lease_token=%s", sql)
        self.assertIn("lease_expires_at>=NOW()", sql)
        self.assertIn("lease_expires_at", sql)
        self.assertEqual(params, (120, 41, "worker-1", LEASE_TOKEN))

    def test_complete_only_finishes_the_current_workers_job(self):
        row = {"id": 41, "status": "succeeded", "locked_by": None}
        cur = FakeCursor([row])

        completed = complete_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=LEASE_TOKEN,
            result={"briefId": 17},
        )

        self.assertEqual(completed, row)
        sql, params = cur.calls[0]
        self.assertIn("status='succeeded'", sql)
        self.assertIn("locked_by=NULL", sql)
        self.assertIn("WHERE id=%s AND status='running' AND locked_by=%s AND lease_token=%s", sql)
        self.assertIn("lease_expires_at>=NOW()", sql)
        self.assertEqual(json.loads(params[0]), {"briefId": 17})
        self.assertEqual(params[1:], (41, "worker-1", LEASE_TOKEN))

    def test_wrong_worker_cannot_complete_a_job(self):
        cur = FakeCursor([None])

        completed = complete_agent_job(
            cur,
            job_id=41,
            worker_id="worker-2",
            lease_token=OLD_LEASE_TOKEN,
            result={},
        )

        self.assertIsNone(completed)

    def test_stale_lease_from_same_worker_cannot_complete_reclaimed_job(self):
        cur = FakeCursor([None])

        completed = complete_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=OLD_LEASE_TOKEN,
            result={},
        )

        self.assertIsNone(completed)
        sql, params = cur.calls[0]
        self.assertIn("locked_by=%s AND lease_token=%s", sql)
        self.assertEqual(params[-2:], ("worker-1", OLD_LEASE_TOKEN))

    def test_complete_rejects_sensitive_result_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobWorkerError):
            complete_agent_job(
                cur,
                job_id=41,
                worker_id="worker-1",
                lease_token=LEASE_TOKEN,
                result={"provider": {"accessToken": "must-not-be-stored"}},
            )

        self.assertEqual(cur.calls, [])

    def test_failure_requeues_until_attempt_limit_then_stays_failed(self):
        row = {"id": 41, "status": "queued", "attempts": 1, "max_attempts": 3}
        cur = FakeCursor([row])

        failed = fail_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=LEASE_TOKEN,
            error="provider unavailable",
            retry_delay_seconds=60,
        )

        self.assertEqual(failed, row)
        sql, params = cur.calls[0]
        self.assertIn("CASE WHEN attempts < max_attempts THEN 'queued' ELSE 'failed' END", sql)
        self.assertIn("run_after", sql)
        self.assertIn("1 << GREATEST(attempts - 1, 0)", sql)
        self.assertIn("locked_by=NULL", sql)
        self.assertIn("lease_token=NULL", sql)
        self.assertIn("lease_expires_at>=NOW()", sql)
        self.assertEqual(params, (60, "provider unavailable", 41, "worker-1", LEASE_TOKEN))

    def test_failure_redacts_obvious_credentials_from_error_summary(self):
        cur = FakeCursor([{"id": 41, "status": "queued"}])

        fail_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=LEASE_TOKEN,
            error='Authorization: Bearer abc123 access_token="secret value" password=hunter2',
        )

        stored_error = cur.calls[0][1][1]
        self.assertNotIn("abc123", stored_error)
        self.assertNotIn("secret value", stored_error)
        self.assertNotIn("hunter2", stored_error)
        self.assertIn("[REDACTED]", stored_error)

    def test_failure_redacts_a_standalone_bearer_token(self):
        cur = FakeCursor([{"id": 41, "status": "queued"}])

        fail_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=LEASE_TOKEN,
            error="provider rejected Bearer standalone-secret-value",
        )

        stored_error = cur.calls[0][1][1]
        self.assertNotIn("standalone-secret-value", stored_error)

    def test_failure_redacts_provider_keys_without_equals_separator(self):
        cur = FakeCursor([{"id": 41, "status": "queued"}])

        fail_agent_job(
            cur,
            job_id=41,
            worker_id="worker-1",
            lease_token=LEASE_TOKEN,
            error="OPENAI_API_KEY sk-provider-secret private_key=private-secret",
        )

        stored_error = cur.calls[0][1][1]
        self.assertNotIn("sk-provider-secret", stored_error)
        self.assertNotIn("private-secret", stored_error)

    def test_recovery_requeues_only_expired_running_leases(self):
        rows = [
            {"id": 41, "company_id": 7, "status": "queued"},
            {"id": 42, "company_id": 8, "status": "failed"},
        ]
        cur = FakeCursor([rows])

        recovered = recover_expired_agent_jobs(
            cur,
            allowed_job_types=("director.daily_brief",),
            retry_delay_seconds=30,
            recovery_limit=25,
        )

        self.assertEqual(recovered, rows)
        sql, params = cur.calls[0]
        self.assertIn("status='running'", sql)
        self.assertIn("lease_expires_at < NOW()", sql)
        self.assertIn("job_type = ANY(%s::text[])", sql)
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertIn("lease_token=NULL", sql)
        self.assertIn("1 << GREATEST(job.attempts - 1, 0)", sql)
        self.assertIn(
            "CASE WHEN job.attempts < job.max_attempts THEN 'queued' ELSE 'failed' END",
            sql,
        )
        self.assertEqual(params, (["director.daily_brief"], 25, 30))

    def test_recovery_rejects_an_unbounded_batch_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobWorkerError):
            recover_expired_agent_jobs(
                cur,
                allowed_job_types=("director.daily_brief",),
                recovery_limit=10000,
            )

        self.assertEqual(cur.calls, [])


if __name__ == "__main__":
    unittest.main()
