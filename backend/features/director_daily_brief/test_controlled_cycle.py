import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from backend.features.agent_jobs.runner import AgentJobRunOutcome
from backend.features.director_daily_brief.controlled_cycle import (
    DirectorDailyBriefCycleError,
    build_director_daily_brief_handler_registry,
    main,
    run_director_daily_brief_cycle,
    run_exact_director_daily_brief_job,
)


def producer_report(*, state, status=None, job_id=None, dry_run=False):
    report = {
        "ok": True,
        "dryRun": dry_run,
        "writesAttempted": 0 if state != "enqueued" else 1,
        "companyId": 4,
        "briefDate": "2026-08-05",
        "jobType": "director.daily_brief",
        "state": state,
    }
    if status is not None:
        report["status"] = status
    if job_id is not None:
        report["jobId"] = job_id
    return report


class DirectorDailyBriefControlledCycleTests(unittest.TestCase):
    def test_dry_run_plans_without_calling_runner(self):
        producer_calls = []
        runner_calls = []

        result = run_director_daily_brief_cycle(
            company_id=4,
            brief_date="2026-08-05",
            apply=False,
            producer=lambda **kwargs: (
                producer_calls.append(kwargs)
                or producer_report(state="would_enqueue", dry_run=True)
            ),
            run_exact_job=lambda job_id: runner_calls.append(job_id),
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["state"], "planned")
        self.assertEqual(result["producerState"], "would_enqueue")
        self.assertEqual(result["businessWritesAttempted"], 0)
        self.assertFalse(result["runner"]["attempted"])
        self.assertEqual(producer_calls, [{
            "company_id": 4,
            "brief_date": "2026-08-05",
            "apply": False,
        }])
        self.assertEqual(runner_calls, [])

    def test_apply_runs_only_the_exact_enqueued_job(self):
        runner_calls = []

        result = run_director_daily_brief_cycle(
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            producer=lambda **_kwargs: producer_report(
                state="enqueued",
                status="queued",
                job_id=81,
            ),
            run_exact_job=lambda job_id: (
                runner_calls.append(job_id)
                or AgentJobRunOutcome(True, "succeeded", job_id)
            ),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["jobId"], 81)
        self.assertEqual(result["jobStatus"], "succeeded")
        self.assertEqual(result["businessWritesAttempted"], 0)
        self.assertEqual(result["runner"], {
            "attempted": True,
            "processed": True,
            "status": "succeeded",
        })
        self.assertEqual(runner_calls, [81])

    def test_existing_succeeded_job_is_not_run_again(self):
        runner_calls = []

        result = run_director_daily_brief_cycle(
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            producer=lambda **_kwargs: producer_report(
                state="existing",
                status="succeeded",
                job_id=80,
            ),
            run_exact_job=lambda job_id: runner_calls.append(job_id),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "already_succeeded")
        self.assertFalse(result["runner"]["attempted"])
        self.assertEqual(runner_calls, [])

    def test_default_exact_runner_uses_job_id_without_recovery(self):
        expected = AgentJobRunOutcome(True, "succeeded", 81)
        fake_runner = Mock()
        fake_runner.run_once.return_value = expected
        registry = object()
        config = object()

        with patch(
            "backend.features.director_daily_brief.controlled_cycle."
            "build_director_daily_brief_handler_registry",
            return_value=registry,
        ), patch(
            "backend.features.director_daily_brief.controlled_cycle."
            "build_runner_config_from_environment",
            return_value=config,
        ), patch(
            "backend.features.director_daily_brief.controlled_cycle.AgentJobRunner",
            return_value=fake_runner,
        ) as runner_class:
            result = run_exact_director_daily_brief_job(81)

        self.assertEqual(result, expected)
        runner_class.assert_called_once()
        self.assertEqual(runner_class.call_args.kwargs["registry"], registry)
        self.assertEqual(runner_class.call_args.kwargs["config"], config)
        fake_runner.run_once.assert_called_once_with(job_id=81)

    def test_controlled_cycle_registry_allows_only_daily_brief(self):
        registry = build_director_daily_brief_handler_registry()

        self.assertEqual(registry.job_types, ("director.daily_brief",))
        self.assertIsNotNone(registry.get("director.daily_brief"))
        self.assertIsNone(registry.get("system.worker_probe"))

    def test_unclaimable_exact_job_fails_closed_without_fallback(self):
        result = run_director_daily_brief_cycle(
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            producer=lambda **_kwargs: producer_report(
                state="existing",
                status="queued",
                job_id=80,
            ),
            run_exact_job=lambda job_id: AgentJobRunOutcome(False, "idle"),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "not_claimed")
        self.assertEqual(result["jobId"], 80)
        self.assertEqual(result["jobStatus"], "queued")
        self.assertEqual(result["runner"]["status"], "not_claimed")

    def test_processed_runner_result_must_confirm_the_exact_job_id(self):
        with self.assertRaises(DirectorDailyBriefCycleError):
            run_director_daily_brief_cycle(
                company_id=4,
                brief_date="2026-08-05",
                apply=True,
                producer=lambda **_kwargs: producer_report(
                    state="existing",
                    status="queued",
                    job_id=80,
                ),
                run_exact_job=lambda job_id: AgentJobRunOutcome(
                    True,
                    "succeeded",
                    None,
                ),
            )

    def test_nonqueued_existing_job_is_not_mutated_or_run(self):
        runner_calls = []

        result = run_director_daily_brief_cycle(
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            producer=lambda **_kwargs: producer_report(
                state="existing",
                status="running",
                job_id=80,
            ),
            run_exact_job=lambda job_id: runner_calls.append(job_id),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "not_runnable")
        self.assertEqual(result["jobStatus"], "running")
        self.assertEqual(runner_calls, [])

    def test_mismatched_producer_owner_is_rejected_before_runner(self):
        report = producer_report(
            state="enqueued",
            status="queued",
            job_id=81,
        )
        report["companyId"] = 9
        runner_calls = []

        with self.assertRaises(DirectorDailyBriefCycleError):
            run_director_daily_brief_cycle(
                company_id=4,
                brief_date="2026-08-05",
                apply=True,
                producer=lambda **_kwargs: report,
                run_exact_job=lambda job_id: runner_calls.append(job_id),
            )

        self.assertEqual(runner_calls, [])

    def test_invalid_producer_write_count_is_rejected_before_runner(self):
        report = producer_report(state="would_enqueue", dry_run=True)
        report["writesAttempted"] = "invalid"
        runner_calls = []

        with self.assertRaises(DirectorDailyBriefCycleError):
            run_director_daily_brief_cycle(
                company_id=4,
                brief_date="2026-08-05",
                apply=False,
                producer=lambda **_kwargs: report,
                run_exact_job=lambda job_id: runner_calls.append(job_id),
            )

        self.assertEqual(runner_calls, [])

    def test_module_help_succeeds_without_database_connection(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.features.director_daily_brief.controlled_cycle",
                "--help",
            ],
            cwd=Path(__file__).resolve().parents[3],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--company-id", completed.stdout)
        self.assertIn("--brief-date", completed.stdout)
        self.assertIn("--apply", completed.stdout)

    def test_cli_returns_nonzero_for_unclaimable_job(self):
        output = io.StringIO()
        report = {
            "ok": False,
            "dryRun": False,
            "state": "not_claimed",
            "jobId": 80,
        }
        with patch(
            "backend.features.director_daily_brief.controlled_cycle."
            "run_director_daily_brief_cycle",
            return_value=report,
        ), redirect_stdout(output):
            exit_code = main([
                "--company-id", "4",
                "--brief-date", "2026-08-05",
                "--apply",
            ])

        self.assertEqual(exit_code, 3)
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_unexpected_cli_error_does_not_print_exception_message(self):
        stderr = io.StringIO()
        with patch(
            "backend.features.director_daily_brief.controlled_cycle."
            "run_director_daily_brief_cycle",
            side_effect=RuntimeError("password=must-not-leak"),
        ), redirect_stderr(stderr):
            exit_code = main([
                "--company-id", "4",
                "--brief-date", "2026-08-05",
            ])

        self.assertEqual(exit_code, 1)
        self.assertIn('"errorType": "RuntimeError"', stderr.getvalue())
        self.assertNotIn("must-not-leak", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
