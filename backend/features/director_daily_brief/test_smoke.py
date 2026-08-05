import unittest
from types import SimpleNamespace

from backend.features.director_daily_brief.smoke import run_controlled_smoke


def _brief_result():
    return {
        "schemaVersion": 1,
        "briefDate": "2026-08-05",
        "mode": "deterministic_read_only",
        "summary": {"total": 0, "critical": 0, "warning": 0, "info": 0},
        "sections": [
            {"key": key, "status": "clear", "count": 0, "truncated": False, "items": []}
            for key in (
                "overdue",
                "shortages",
                "documents",
                "estimateDeviations",
                "payments",
                "tasks",
            )
        ],
        "sourceCounts": {},
    }


class DirectorDailyBriefSmokeTests(unittest.TestCase):
    def test_runs_one_exact_job_and_cleans_it_up(self):
        calls = []

        report = run_controlled_smoke(
            email="director@example.test",
            brief_date="2026-08-05",
            create_job=lambda **kwargs: calls.append(("create", kwargs)) or {
                "id": 42,
                "companyId": 7,
            },
            run_job=lambda: calls.append(("run", None)) or SimpleNamespace(
                processed=True,
                status="succeeded",
                job_id=42,
            ),
            load_job=lambda correlation_id: calls.append(("load", correlation_id)) or {
                "id": 42,
                "status": "succeeded",
                "result": _brief_result(),
            },
            cleanup_job=lambda correlation_id: calls.append(("cleanup", correlation_id)) or 0,
            run_id="abc123",
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["businessWritesAttempted"], 0)
        self.assertEqual(report["persistedAgentJobs"], 0)
        self.assertEqual(report["companyId"], 7)
        self.assertEqual(report["jobId"], 42)
        self.assertEqual(report["sectionKeys"], [
            "overdue",
            "shortages",
            "documents",
            "estimateDeviations",
            "payments",
            "tasks",
        ])
        self.assertEqual([name for name, _ in calls], ["create", "run", "load", "cleanup"])
        self.assertNotIn("result", report)

    def test_cleanup_runs_when_the_job_fails(self):
        cleaned = []

        report = run_controlled_smoke(
            email="director@example.test",
            brief_date="2026-08-05",
            create_job=lambda **kwargs: {"id": 42, "companyId": 7},
            run_job=lambda: (_ for _ in ()).throw(RuntimeError("private row data")),
            load_job=lambda correlation_id: None,
            cleanup_job=lambda correlation_id: cleaned.append(correlation_id) or 0,
            run_id="failure123",
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["failureType"], "RuntimeError")
        self.assertNotIn("private row data", str(report))
        self.assertEqual(report["persistedAgentJobs"], 0)
        self.assertEqual(len(cleaned), 1)

    def test_rejects_a_result_with_wrong_section_contract(self):
        result = _brief_result()
        result["sections"] = result["sections"][:-1]

        report = run_controlled_smoke(
            email="director@example.test",
            brief_date="2026-08-05",
            create_job=lambda **kwargs: {"id": 42, "companyId": 7},
            run_job=lambda: SimpleNamespace(processed=True, status="succeeded", job_id=42),
            load_job=lambda correlation_id: {
                "id": 42,
                "status": "succeeded",
                "result": result,
            },
            cleanup_job=lambda correlation_id: 0,
            run_id="contract123",
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["failureType"], "ControlledDailyBriefSmokeError")


if __name__ == "__main__":
    unittest.main()
