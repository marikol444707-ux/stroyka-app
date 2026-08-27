import unittest
from unittest.mock import patch

from backend.features.agent_jobs.operational_report import (
    MODEL_FREE_JOB_TYPES,
    build_operational_report,
    build_worker_report,
)


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row


class AgentJobOperationalReportTests(unittest.TestCase):
    def test_reports_queue_health_without_writes_or_sensitive_fields(self):
        cur = FakeCursor({
            "total": 15,
            "queued_due": 3,
            "queued_delayed": 2,
            "running": 1,
            "expired_running": 1,
            "failed": 2,
            "succeeded": 6,
            "cancelled": 1,
            "disallowed_due": 1,
            "oldest_due_age_seconds": 91.9,
            "recent_succeeded": 4,
            "recent_failed": 1,
            "recent_p95_duration_ms": 1250.7,
        })

        report = build_operational_report(
            cur,
            allowed_job_types=("system.worker_probe", "director.daily_brief"),
        )

        self.assertTrue(report["ok"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["workerMode"], "singleJob")
        self.assertEqual(report["queue"]["due"], 3)
        self.assertEqual(report["queue"]["expiredLeases"], 1)
        self.assertEqual(report["queue"]["oldestDueAgeSeconds"], 91)
        self.assertEqual(report["recent24h"]["p95DurationMs"], 1251)
        self.assertEqual(report["modelCost"]["state"], "notApplicable")
        self.assertEqual(report["modelCost"]["rubles"], 0)
        sql = cur.calls[0][0].upper()
        self.assertTrue(sql.startswith("SELECT"))
        self.assertNotIn("PAYLOAD_JSON", sql)
        self.assertNotIn("RESULT_JSON", sql)
        self.assertNotIn("LAST_ERROR", sql)
        self.assertNotIn("LEASE_TOKEN", sql)

    def test_unknown_handler_type_marks_model_cost_as_untracked(self):
        cur = FakeCursor({})

        report = build_operational_report(
            cur,
            allowed_job_types=("system.worker_probe", "future.model_job"),
        )

        self.assertEqual(report["modelCost"]["state"], "untracked")
        self.assertIsNone(report["modelCost"]["rubles"])
        self.assertEqual(report["modelCost"]["untrackedJobTypes"], ["future.model_job"])

    def test_model_free_contract_matches_current_registry(self):
        from backend.features.agent_jobs.handler_registry import (
            build_default_handler_registry,
        )

        self.assertEqual(
            set(build_default_handler_registry().job_types),
            set(MODEL_FREE_JOB_TYPES),
        )

    def test_worker_is_not_ready_when_schema_readiness_fails(self):
        cur = FakeCursor({})
        with patch(
            "backend.features.agent_jobs.operational_report.build_schema_report",
            return_value={"readyForWorker": False, "missingIndexes": ["claim"]},
        ):
            report = build_worker_report(
                cur,
                allowed_job_types=("system.worker_probe",),
            )

        self.assertFalse(report["readyForWorker"])
        self.assertFalse(report["schemaReady"])
        self.assertEqual(report["schema"]["missingIndexes"], ["claim"])


if __name__ == "__main__":
    unittest.main()
