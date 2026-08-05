import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.features.director_daily_brief.schedule import (
    DirectorDailyBriefScheduleError,
    main,
    resolve_moscow_brief_date,
    run_scheduled_director_daily_brief,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def cycle_report(*, apply, company_id=4, brief_date="2026-08-06"):
    return {
        "ok": True,
        "dryRun": not apply,
        "businessWritesAttempted": 0,
        "producerWritesAttempted": 1 if apply else 0,
        "companyId": company_id,
        "briefDate": brief_date,
        "jobType": "director.daily_brief",
        "producerState": "enqueued" if apply else "would_enqueue",
        "state": "succeeded" if apply else "planned",
        "jobId": 91 if apply else None,
        "jobStatus": "succeeded" if apply else None,
        "runner": {
            "attempted": apply,
            "processed": apply,
            "status": "succeeded" if apply else None,
        },
        "privatePayload": {"password": "must-not-leak"},
    }


class DirectorDailyBriefScheduleTests(unittest.TestCase):
    def test_moscow_date_is_used_across_utc_day_boundary(self):
        result = resolve_moscow_brief_date(
            now_provider=lambda: datetime(
                2026,
                8,
                5,
                21,
                30,
                tzinfo=timezone.utc,
            )
        )

        self.assertEqual(result, "2026-08-06")

    def test_naive_clock_value_is_rejected(self):
        with self.assertRaises(DirectorDailyBriefScheduleError):
            resolve_moscow_brief_date(
                now_provider=lambda: datetime(2026, 8, 5, 21, 30)
            )

    def test_dry_run_uses_resolved_date_and_does_not_apply(self):
        calls = []

        result = run_scheduled_director_daily_brief(
            company_id=4,
            apply=False,
            now_provider=lambda: datetime(
                2026,
                8,
                5,
                21,
                30,
                tzinfo=timezone.utc,
            ),
            run_cycle=lambda **kwargs: (
                calls.append(kwargs)
                or cycle_report(apply=False)
            ),
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["briefDate"], "2026-08-06")
        self.assertEqual(result["businessWritesAttempted"], 0)
        self.assertEqual(calls, [{
            "company_id": 4,
            "brief_date": "2026-08-06",
            "apply": False,
        }])

    def test_apply_runs_one_controlled_cycle_and_allowlists_output(self):
        calls = []

        result = run_scheduled_director_daily_brief(
            company_id=4,
            apply=True,
            now_provider=lambda: datetime(
                2026,
                8,
                6,
                4,
                10,
                tzinfo=timezone.utc,
            ),
            run_cycle=lambda **kwargs: (
                calls.append(kwargs)
                or cycle_report(apply=True)
            ),
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["dryRun"])
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["companyId"], 4)
        self.assertEqual(result["jobId"], 91)
        self.assertEqual(result["runner"], {
            "attempted": True,
            "processed": True,
            "status": "succeeded",
        })
        self.assertNotIn("privatePayload", result)
        self.assertNotIn("password", json.dumps(result))
        self.assertEqual(calls, [{
            "company_id": 4,
            "brief_date": "2026-08-06",
            "apply": True,
        }])

    def test_mismatched_cycle_identity_is_rejected(self):
        for field, value in (
            ("companyId", 9),
            ("briefDate", "2026-08-05"),
            ("jobType", "system.worker_probe"),
        ):
            with self.subTest(field=field):
                report = cycle_report(apply=False)
                report[field] = value
                with self.assertRaises(DirectorDailyBriefScheduleError):
                    run_scheduled_director_daily_brief(
                        company_id=4,
                        apply=False,
                        now_provider=lambda: datetime(
                            2026,
                            8,
                            6,
                            4,
                            10,
                            tzinfo=timezone.utc,
                        ),
                        run_cycle=lambda **_kwargs: report,
                    )

    def test_business_write_claim_is_rejected(self):
        report = cycle_report(apply=False)
        report["businessWritesAttempted"] = 1

        with self.assertRaises(DirectorDailyBriefScheduleError):
            run_scheduled_director_daily_brief(
                company_id=4,
                apply=False,
                now_provider=lambda: datetime(
                    2026,
                    8,
                    6,
                    4,
                    10,
                    tzinfo=timezone.utc,
                ),
                run_cycle=lambda **_kwargs: report,
            )

    def test_non_integer_write_counters_are_rejected(self):
        for field, value in (
            ("businessWritesAttempted", False),
            ("producerWritesAttempted", 0.5),
        ):
            with self.subTest(field=field):
                report = cycle_report(apply=False)
                report[field] = value
                with self.assertRaises(DirectorDailyBriefScheduleError):
                    run_scheduled_director_daily_brief(
                        company_id=4,
                        apply=False,
                        now_provider=lambda: datetime(
                            2026,
                            8,
                            6,
                            4,
                            10,
                            tzinfo=timezone.utc,
                        ),
                        run_cycle=lambda **_kwargs: report,
                    )

    def test_cli_help_succeeds_without_database_connection(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.features.director_daily_brief.schedule",
                "--help",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--company-id", completed.stdout)
        self.assertIn("--apply", completed.stdout)
        self.assertNotIn("--brief-date", completed.stdout)

    def test_unexpected_cli_error_does_not_print_exception_message(self):
        stderr = io.StringIO()
        with patch(
            "backend.features.director_daily_brief.schedule."
            "run_scheduled_director_daily_brief",
            side_effect=RuntimeError("password=must-not-leak"),
        ), redirect_stderr(stderr):
            exit_code = main(["--company-id", "4"])

        self.assertEqual(exit_code, 1)
        self.assertIn('"errorType": "RuntimeError"', stderr.getvalue())
        self.assertNotIn("must-not-leak", stderr.getvalue())

    def test_cli_returns_nonzero_when_controlled_cycle_does_not_succeed(self):
        stdout = io.StringIO()
        report = {
            "ok": False,
            "dryRun": False,
            "businessWritesAttempted": 0,
            "companyId": 4,
            "briefDate": "2026-08-06",
            "jobType": "director.daily_brief",
            "state": "not_claimed",
        }
        with patch(
            "backend.features.director_daily_brief.schedule."
            "run_scheduled_director_daily_brief",
            return_value=report,
        ), redirect_stdout(stdout):
            exit_code = main(["--company-id", "4", "--apply"])

        self.assertEqual(exit_code, 3)
        self.assertEqual(json.loads(stdout.getvalue()), report)


class DirectorDailyBriefSystemdContractTests(unittest.TestCase):
    def test_service_is_hardened_oneshot_for_exact_company(self):
        service = (
            REPO_ROOT / "ops/systemd/stroyka-director-daily-brief.service"
        ).read_text()

        self.assertIn("Type=oneshot", service)
        self.assertIn("WorkingDirectory=/var/www/stroyka-app", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertIn("PrivateTmp=true", service)
        self.assertIn("ProtectSystem=full", service)
        self.assertIn("Environment=HOME=/tmp", service)
        self.assertIn("Environment=NPM_CONFIG_CACHE=/tmp/npm-cache", service)
        self.assertIn("TimeoutStartSec=10min", service)
        self.assertIn(
            "ExecStart=/usr/bin/npm run schedule:director-daily-brief -- "
            "--company-id 1 --apply",
            service,
        )
        self.assertNotIn("worker:agent-jobs", service)
        self.assertNotIn("--brief-date", service)
        self.assertNotIn("all-companies", service)

    def test_timer_runs_once_each_moscow_morning_and_catches_up(self):
        timer = (
            REPO_ROOT / "ops/systemd/stroyka-director-daily-brief.timer"
        ).read_text()

        self.assertIn("OnCalendar=*-*-* 07:10:00 Europe/Moscow", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("RandomizedDelaySec=2min", timer)
        self.assertIn(
            "Unit=stroyka-director-daily-brief.service",
            timer,
        )
        self.assertIn("WantedBy=timers.target", timer)

    def test_normal_deploy_does_not_install_or_enable_schedule(self):
        deploy = (REPO_ROOT / "deploy.sh").read_text()

        self.assertNotIn("stroyka-director-daily-brief", deploy)
        self.assertNotIn("systemctl enable", deploy)


if __name__ == "__main__":
    unittest.main()
