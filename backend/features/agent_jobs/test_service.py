import json
import unittest

from backend.features.agent_jobs.service import AgentJobValidationError, enqueue_agent_job


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


class AgentJobServiceTests(unittest.TestCase):
    def test_enqueue_stores_one_company_actor_and_trace_context(self):
        row = {
            "id": 41,
            "company_id": 7,
            "project_id": 12,
            "job_type": "director.daily_brief",
            "status": "queued",
        }
        cur = FakeCursor([{"id": 12}, {"role": "директор"}, row])

        result = enqueue_agent_job(
            cur,
            company_id=7,
            project_id=12,
            job_type="director.daily_brief",
            idempotency_key="daily:2026-08-05",
            requested_by_user_id=3,
            requested_by_role="директор",
            payload={"date": "2026-08-05"},
            correlation_id="request-123",
        )

        self.assertTrue(result["created"])
        self.assertEqual(result["job"], row)
        self.assertEqual(len(cur.calls), 3)
        ownership_sql, ownership_params = cur.calls[0]
        self.assertIn("FROM projects", ownership_sql)
        self.assertEqual(ownership_params, (12, 7))
        membership_sql, membership_params = cur.calls[1]
        self.assertIn("FROM user_company_roles", membership_sql)
        self.assertEqual(membership_params, (3, 7, "директор"))
        sql, params = cur.calls[2]
        self.assertIn("INSERT INTO agent_jobs", sql)
        self.assertIn("ON CONFLICT ON CONSTRAINT uq_agent_jobs_idempotency DO NOTHING", sql)
        self.assertIn("RETURNING *", sql)
        self.assertEqual(params[0:6], (7, 12, 3, "директор", "director.daily_brief", "daily:2026-08-05"))
        self.assertEqual(json.loads(params[7]), {"date": "2026-08-05"})

    def test_duplicate_returns_existing_job_without_resetting_it(self):
        existing = {
            "id": 41,
            "company_id": 7,
            "job_type": "director.daily_brief",
            "status": "running",
            "attempts": 1,
        }
        cur = FakeCursor([None, existing])

        result = enqueue_agent_job(
            cur,
            company_id=7,
            job_type="director.daily_brief",
            idempotency_key="daily:2026-08-05",
            payload={},
        )

        self.assertFalse(result["created"])
        self.assertEqual(result["job"], existing)
        self.assertEqual(len(cur.calls), 2)
        self.assertTrue(cur.calls[1][0].startswith("SELECT * FROM agent_jobs"))
        self.assertNotIn("UPDATE agent_jobs", " ".join(sql for sql, _ in cur.calls))

    def test_missing_company_fails_closed_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=None,
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
            )

        self.assertEqual(cur.calls, [])

    def test_invalid_payload_fails_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=7,
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
                payload={"bad": object()},
            )

        self.assertEqual(cur.calls, [])

    def test_project_from_another_company_fails_before_insert(self):
        cur = FakeCursor([None])

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=7,
                project_id=12,
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
            )

        self.assertEqual(len(cur.calls), 1)
        self.assertNotIn("INSERT INTO agent_jobs", cur.calls[0][0])

    def test_user_from_another_company_fails_before_insert(self):
        cur = FakeCursor([None])

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=7,
                requested_by_user_id=3,
                requested_by_role="директор",
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
            )

        self.assertEqual(len(cur.calls), 1)
        self.assertIn("FROM user_company_roles", cur.calls[0][0])
        self.assertNotIn("INSERT INTO agent_jobs", cur.calls[0][0])

    def test_human_role_without_user_id_fails_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=7,
                requested_by_role="директор",
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
            )

        self.assertEqual(cur.calls, [])

    def test_project_id_is_part_of_idempotency_scope(self):
        existing = {
            "id": 42,
            "company_id": 7,
            "project_id": 13,
            "job_type": "director.daily_brief",
            "status": "queued",
        }
        cur = FakeCursor([{"id": 13}, None, existing])

        result = enqueue_agent_job(
            cur,
            company_id=7,
            project_id=13,
            job_type="director.daily_brief",
            idempotency_key="daily:2026-08-05",
        )

        self.assertFalse(result["created"])
        self.assertIn("project_scope_id=%s", cur.calls[2][0])
        self.assertEqual(cur.calls[2][1], (7, 13, "director.daily_brief", "daily:2026-08-05"))

    def test_oversized_payload_fails_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=7,
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
                payload={"text": "x" * 70000},
            )

        self.assertEqual(cur.calls, [])

    def test_sensitive_payload_key_fails_before_sql(self):
        cur = FakeCursor()

        with self.assertRaises(AgentJobValidationError):
            enqueue_agent_job(
                cur,
                company_id=7,
                job_type="director.daily_brief",
                idempotency_key="daily:2026-08-05",
                payload={"request": {"authToken": "must-not-be-stored"}},
            )

        self.assertEqual(cur.calls, [])


if __name__ == "__main__":
    unittest.main()
