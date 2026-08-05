import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from backend.features.director_daily_brief.producer import (
    DirectorDailyBriefProducerError,
    main,
    prepare_director_daily_brief_job,
    run_director_daily_brief_producer,
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


class FakeCursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.autocommit = True
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.session_calls = []

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)
        self.autocommit = kwargs.get("autocommit", self.autocommit)

    def cursor(self, **_kwargs):
        return FakeCursorContext(self.cursor_value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class DirectorDailyBriefProducerTests(unittest.TestCase):
    def test_dry_run_plans_one_company_day_without_enqueue(self):
        cursor = FakeCursor([{"id": 4}, None])
        enqueue_calls = []

        result = prepare_director_daily_brief_job(
            cursor,
            company_id=4,
            brief_date="2026-08-05",
            apply=False,
            enqueue_job=lambda *_args, **kwargs: enqueue_calls.append(kwargs),
        )

        self.assertEqual(result["state"], "would_enqueue")
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(result["companyId"], 4)
        self.assertEqual(result["briefDate"], "2026-08-05")
        self.assertEqual(enqueue_calls, [])
        self.assertIn("company.active IS TRUE", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (4,))
        self.assertEqual(
            cursor.calls[1][1],
            (4, "director.daily_brief", "daily:2026-08-05"),
        )

    def test_apply_enqueues_exact_system_owned_payload(self):
        cursor = FakeCursor([{"id": 4}, None])
        enqueue_calls = []

        def enqueue_job(_cursor, **kwargs):
            enqueue_calls.append(kwargs)
            return {"created": True, "job": {"id": 81, "status": "queued"}}

        result = prepare_director_daily_brief_job(
            cursor,
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            enqueue_job=enqueue_job,
        )

        self.assertEqual(result["state"], "enqueued")
        self.assertFalse(result["dryRun"])
        self.assertEqual(result["writesAttempted"], 1)
        self.assertEqual(result["jobId"], 81)
        self.assertEqual(result["status"], "queued")
        self.assertEqual(enqueue_calls, [{
            "company_id": 4,
            "job_type": "director.daily_brief",
            "idempotency_key": "daily:2026-08-05",
            "requested_by_role": "system",
            "payload": {"briefDate": "2026-08-05"},
            "correlation_id": "daily-brief:4:2026-08-05",
            "priority": 5,
            "max_attempts": 3,
        }])

    def test_existing_company_day_is_returned_without_enqueue(self):
        cursor = FakeCursor([{"id": 4}, {"id": 80, "status": "succeeded"}])
        enqueue_calls = []

        result = prepare_director_daily_brief_job(
            cursor,
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            enqueue_job=lambda *_args, **kwargs: enqueue_calls.append(kwargs),
        )

        self.assertEqual(result["state"], "existing")
        self.assertEqual(result["jobId"], 80)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(enqueue_calls, [])

    def test_rejects_invalid_owner_and_date_before_sql(self):
        for company_id, brief_date in ((0, "2026-08-05"), (4, "05.08.2026")):
            with self.subTest(company_id=company_id, brief_date=brief_date):
                cursor = FakeCursor()
                with self.assertRaises(DirectorDailyBriefProducerError):
                    prepare_director_daily_brief_job(
                        cursor,
                        company_id=company_id,
                        brief_date=brief_date,
                        apply=False,
                    )
                self.assertEqual(cursor.calls, [])

    def test_rejects_inactive_or_missing_company(self):
        cursor = FakeCursor([None])

        with self.assertRaises(DirectorDailyBriefProducerError):
            prepare_director_daily_brief_job(
                cursor,
                company_id=4,
                brief_date="2026-08-05",
                apply=False,
            )

        self.assertEqual(len(cursor.calls), 1)

    def test_runner_rolls_back_dry_run_and_commits_apply(self):
        dry_cursor = FakeCursor([{"id": 4}, None])
        dry_connection = FakeConnection(dry_cursor)
        dry_result = run_director_daily_brief_producer(
            company_id=4,
            brief_date="2026-08-05",
            apply=False,
            connection_factory=lambda: dry_connection,
        )

        self.assertEqual(dry_result["state"], "would_enqueue")
        self.assertEqual(dry_connection.commits, 0)
        self.assertEqual(dry_connection.rollbacks, 1)
        self.assertEqual(
            dry_connection.session_calls,
            [{"readonly": True, "autocommit": False}],
        )
        self.assertTrue(dry_connection.closed)

        apply_cursor = FakeCursor([{"id": 4}, {"id": 80, "status": "queued"}])
        apply_connection = FakeConnection(apply_cursor)
        apply_result = run_director_daily_brief_producer(
            company_id=4,
            brief_date="2026-08-05",
            apply=True,
            connection_factory=lambda: apply_connection,
        )

        self.assertEqual(apply_result["state"], "existing")
        self.assertEqual(apply_connection.commits, 1)
        self.assertEqual(apply_connection.rollbacks, 0)
        self.assertEqual(
            apply_connection.session_calls,
            [{"readonly": False, "autocommit": False}],
        )
        self.assertTrue(apply_connection.closed)

    def test_module_help_succeeds_without_database_connection(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.features.director_daily_brief.producer",
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

    def test_unexpected_cli_error_does_not_print_exception_message(self):
        stderr = io.StringIO()
        with patch(
            "backend.features.director_daily_brief.producer."
            "run_director_daily_brief_producer",
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
