import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
)
from backend.features.estimate_revision_impact.producer import (
    EstimateRevisionImpactProducerError,
    main,
    prepare_estimate_revision_impact_job,
    run_estimate_revision_impact_producer,
)
from backend.features.estimate_revision_impact.test_baseline import source


def ready_baseline(value=None):
    value = value or source()
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "sourceReady": True,
        "readyForDomainScan": True,
        "source": {
            "companyId": value.company_id,
            "projectId": value.project_id,
            "estimateId": value.estimate_id,
            "sourceRevision": value.source_revision,
            "reconciliationId": 91,
            "baseEstimateId": 51,
            "reconciliationStatus": "Черновик",
        },
    }


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
        self.session_calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return FakeCursorContext(self.cursor_value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def job_row(job_id=81, status="queued"):
    plan = build_estimate_revision_impact_job_plan(source())
    return {
        "id": job_id,
        "status": status,
        "company_id": plan.company_id,
        "project_scope_id": plan.project_id,
        "job_type": plan.job_type,
        "idempotency_key": plan.idempotency_key,
    }


class EstimateRevisionImpactProducerTests(unittest.TestCase):
    def test_dry_run_revalidates_source_and_plans_without_enqueue(self):
        cursor = FakeCursor([None])
        baseline_calls = []
        enqueue_calls = []

        result = prepare_estimate_revision_impact_job(
            cursor,
            source(),
            apply=False,
            collect_baseline=lambda cur, value: (
                baseline_calls.append((cur, value)) or ready_baseline(value)
            ),
            enqueue_job=lambda *_args, **kwargs: enqueue_calls.append(kwargs),
        )

        plan = build_estimate_revision_impact_job_plan(source())
        self.assertEqual(result["state"], "would_enqueue")
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(result["companyId"], 4)
        self.assertEqual(result["projectId"], 17)
        self.assertEqual(result["estimateId"], 52)
        self.assertEqual(result["sourceRevision"], source().source_revision)
        self.assertEqual(result["idempotencyKey"], plan.idempotency_key)
        self.assertEqual(len(baseline_calls), 1)
        self.assertEqual(enqueue_calls, [])
        self.assertEqual(cursor.calls[0][1], (
            4, 17, plan.job_type, plan.idempotency_key,
        ))

    def test_apply_enqueues_exact_system_owned_project_scoped_job(self):
        cursor = FakeCursor([None])
        enqueue_calls = []

        def enqueue_job(_cursor, **kwargs):
            enqueue_calls.append(kwargs)
            return {"created": True, "job": job_row()}

        result = prepare_estimate_revision_impact_job(
            cursor,
            source(),
            apply=True,
            collect_baseline=lambda *_args: ready_baseline(),
            enqueue_job=enqueue_job,
        )

        plan = build_estimate_revision_impact_job_plan(source())
        self.assertEqual(result["state"], "enqueued")
        self.assertFalse(result["dryRun"])
        self.assertEqual(result["writesAttempted"], 1)
        self.assertEqual(result["jobId"], 81)
        self.assertEqual(enqueue_calls, [{
            "company_id": 4,
            "project_id": 17,
            "job_type": plan.job_type,
            "idempotency_key": plan.idempotency_key,
            "requested_by_role": "system",
            "payload": dict(plan.payload),
            "correlation_id": plan.correlation_id,
            "priority": plan.priority,
            "max_attempts": plan.max_attempts,
        }])

    def test_existing_exact_job_is_returned_without_enqueue(self):
        cursor = FakeCursor([job_row(80, "succeeded")])
        enqueue_calls = []

        result = prepare_estimate_revision_impact_job(
            cursor,
            source(),
            apply=True,
            collect_baseline=lambda *_args: ready_baseline(),
            enqueue_job=lambda *_args, **kwargs: enqueue_calls.append(kwargs),
        )

        self.assertEqual(result["state"], "existing")
        self.assertEqual(result["jobId"], 80)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(enqueue_calls, [])

    def test_rejects_stale_or_unready_source_before_queue_lookup(self):
        invalid_reports = (
            {**ready_baseline(), "readyForDomainScan": False},
            {
                **ready_baseline(),
                "source": {**ready_baseline()["source"], "projectId": 18},
            },
        )
        for invalid in invalid_reports:
            with self.subTest(invalid=invalid):
                cursor = FakeCursor()
                with self.assertRaises(EstimateRevisionImpactProducerError):
                    prepare_estimate_revision_impact_job(
                        cursor,
                        source(),
                        collect_baseline=lambda *_args, value=invalid: value,
                    )
                self.assertEqual(cursor.calls, [])

    def test_rejects_unvalidated_source_and_invalid_dependencies_before_sql(self):
        for value, apply, collector, enqueue in (
            ({"companyId": 4}, False, lambda *_args: ready_baseline(), lambda: None),
            (source(), "yes", lambda *_args: ready_baseline(), lambda: None),
            (source(), False, None, lambda: None),
            (source(), False, lambda *_args: ready_baseline(), None),
        ):
            with self.subTest(value=value, apply=apply):
                cursor = FakeCursor()
                with self.assertRaises(EstimateRevisionImpactProducerError):
                    prepare_estimate_revision_impact_job(
                        cursor,
                        value,
                        apply=apply,
                        collect_baseline=collector,
                        enqueue_job=enqueue,
                    )
                self.assertEqual(cursor.calls, [])

    def test_runner_uses_repeatable_read_for_dry_run_and_serializable_for_apply(self):
        dry_connection = FakeConnection(FakeCursor([None]))
        dry_result = run_estimate_revision_impact_producer(
            source(),
            apply=False,
            connection_factory=lambda: dry_connection,
            collect_baseline=lambda *_args: ready_baseline(),
        )
        self.assertEqual(dry_result["state"], "would_enqueue")
        self.assertEqual(dry_connection.session_calls, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(dry_connection.commits, 0)
        self.assertEqual(dry_connection.rollbacks, 1)
        self.assertTrue(dry_connection.closed)

        apply_connection = FakeConnection(FakeCursor([job_row()]))
        apply_result = run_estimate_revision_impact_producer(
            source(),
            apply=True,
            connection_factory=lambda: apply_connection,
            collect_baseline=lambda *_args: ready_baseline(),
        )
        self.assertEqual(apply_result["state"], "existing")
        self.assertEqual(apply_connection.session_calls, [{
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        }])
        self.assertEqual(apply_connection.commits, 1)
        self.assertEqual(apply_connection.rollbacks, 0)
        self.assertTrue(apply_connection.closed)

    def test_module_help_and_package_script_are_available(self):
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.features.estimate_revision_impact.producer",
                "--help",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for option in (
            "--company-id", "--project-id", "--estimate-id",
            "--source-revision", "--apply",
        ):
            self.assertIn(option, completed.stdout)
        scripts = json.loads((root / "package.json").read_text())["scripts"]
        self.assertEqual(
            scripts["enqueue:estimate-revision-impact"],
            "python3 -m backend.features.estimate_revision_impact.producer",
        )

    def test_unexpected_cli_error_does_not_print_exception_message(self):
        stderr = io.StringIO()
        with patch(
            "backend.features.estimate_revision_impact.producer."
            "run_estimate_revision_impact_producer",
            side_effect=RuntimeError("password=must-not-leak"),
        ), redirect_stderr(stderr):
            exit_code = main([
                "--company-id", "4",
                "--project-id", "17",
                "--estimate-id", "52",
                "--source-revision", source().source_revision,
            ])
        self.assertEqual(exit_code, 1)
        self.assertIn('"errorType": "RuntimeError"', stderr.getvalue())
        self.assertNotIn("must-not-leak", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
