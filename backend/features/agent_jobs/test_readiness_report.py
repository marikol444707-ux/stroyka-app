import unittest

from backend.features.agent_jobs.readiness_report import build_report


REQUIRED_COLUMNS = (
    "id",
    "owner_scope",
    "company_id",
    "project_id",
    "project_scope_id",
    "requested_by_user_id",
    "requested_by_role",
    "job_type",
    "idempotency_key",
    "correlation_id",
    "payload_json",
    "result_json",
    "status",
    "priority",
    "attempts",
    "max_attempts",
    "run_after",
    "locked_at",
    "locked_by",
    "heartbeat_at",
    "started_at",
    "completed_at",
    "last_error",
    "created_at",
    "updated_at",
)


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0)

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        return self.current


class AgentJobReadinessReportTests(unittest.TestCase):
    def test_ready_schema_and_empty_queue_are_reported_without_writes(self):
        cur = FakeCursor([
            [{"column_name": name} for name in REQUIRED_COLUMNS],
            [
                {"indexname": "idx_agent_jobs_claim"},
                {"indexname": "idx_agent_jobs_owner"},
                {"indexname": "idx_agent_jobs_correlation"},
            ],
            [{"constraint_name": "uq_agent_jobs_idempotency"}],
            {"total": 0, "invalid_owner": 0, "invalid_status": 0},
        ])

        report = build_report(cur)

        self.assertTrue(report["ok"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["readyForWorker"])
        self.assertEqual(report["summary"]["total"], 0)
        self.assertTrue(all(call[0].startswith("SELECT") for call in cur.calls))

    def test_missing_idempotency_constraint_is_not_ready(self):
        cur = FakeCursor([
            [{"column_name": name} for name in REQUIRED_COLUMNS],
            [
                {"indexname": "idx_agent_jobs_claim"},
                {"indexname": "idx_agent_jobs_owner"},
                {"indexname": "idx_agent_jobs_correlation"},
            ],
            [],
            {"total": 0, "invalid_owner": 0, "invalid_status": 0},
        ])

        report = build_report(cur)

        self.assertFalse(report["readyForWorker"])
        self.assertEqual(
            report["missingConstraints"],
            ["uq_agent_jobs_idempotency"],
        )

    def test_missing_table_returns_not_ready_without_querying_business_rows(self):
        cur = FakeCursor([[]])

        report = build_report(cur)

        self.assertFalse(report["readyForWorker"])
        self.assertEqual(report["missingColumns"], list(REQUIRED_COLUMNS))
        self.assertEqual(len(cur.calls), 1)


if __name__ == "__main__":
    unittest.main()
