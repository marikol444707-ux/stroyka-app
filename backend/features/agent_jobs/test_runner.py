import io
import json
import os
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.agent_jobs.handler_registry import (
    AgentJobHandlerRegistry,
    build_default_handler_registry,
)
from backend.features.agent_jobs.runner import (
    AgentJobRunner,
    AgentJobRunnerConfig,
    LeaseHeartbeat,
    build_runner_config_from_environment,
    build_worker_id,
    emit_json_event,
    main,
)


LEASE_TOKEN = "a" * 32


class FakeCursor:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.response

    def fetchall(self):
        return list(self.response or [])


class FakeConnection:
    def __init__(self, response=None):
        self.autocommit = True
        self.cursor_value = FakeCursor(response)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class ConnectionSequence:
    def __init__(self, *connections):
        self.connections = list(connections)
        self.created = []

    def __call__(self):
        connection = self.connections.pop(0)
        self.created.append(connection)
        return connection


class FakeHeartbeat:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def claimed_row(**overrides):
    row = {
        "id": 41,
        "company_id": 7,
        "project_id": 12,
        "requested_by_user_id": 5,
        "requested_by_role": "director",
        "job_type": "director.daily_brief",
        "correlation_id": "corr-41",
        "payload_json": {"briefDate": "2026-08-05"},
        "status": "running",
        "attempts": 1,
        "max_attempts": 3,
        "locked_by": "agent-worker:test",
        "lease_token": LEASE_TOKEN,
    }
    row.update(overrides)
    return row


class AgentJobRunnerTests(unittest.TestCase):
    def config(self):
        return AgentJobRunnerConfig(
            worker_id="agent-worker:test",
            lease_seconds=60,
            heartbeat_interval_seconds=15,
            poll_interval_seconds=0.05,
            retry_delay_seconds=30,
            recovery_interval_seconds=60,
            recovery_limit=25,
        )

    def test_success_commits_claim_before_handler_and_completion_after_handler(self):
        claim_connection = FakeConnection(claimed_row())
        complete_connection = FakeConnection({"id": 41, "status": "succeeded"})
        connections = ConnectionSequence(claim_connection, complete_connection)
        heartbeat = FakeHeartbeat()
        seen = {}

        def handler(context):
            self.assertEqual(claim_connection.commits, 1)
            self.assertTrue(claim_connection.closed)
            self.assertEqual(len(connections.created), 1)
            self.assertFalse(hasattr(context, "lease_token"))
            seen["context"] = context
            return {"briefId": 17}

        events = []
        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry((("director.daily_brief", handler),)),
            connection_factory=connections,
            config=self.config(),
            emit_event=lambda event, **fields: events.append((event, fields)),
            heartbeat_factory=lambda **kwargs: heartbeat,
        )

        outcome = runner.run_once()

        self.assertTrue(outcome.processed)
        self.assertEqual(outcome.status, "succeeded")
        self.assertEqual(seen["context"].owner_company_id, 7)
        self.assertTrue(heartbeat.started)
        self.assertTrue(heartbeat.stopped)
        self.assertEqual(complete_connection.commits, 1)
        self.assertTrue(complete_connection.closed)
        complete_params = complete_connection.cursor_value.calls[0][1]
        self.assertEqual(json.loads(complete_params[0]), {"briefId": 17})
        self.assertEqual([event for event, _ in events], ["job_claimed", "job_succeeded"])

    def test_handler_failure_is_retried_in_a_fresh_transaction_without_secret_logs(self):
        claim_connection = FakeConnection(
            claimed_row(correlation_id="do-not-log-correlation")
        )
        fail_connection = FakeConnection({"id": 41, "status": "queued"})
        connections = ConnectionSequence(claim_connection, fail_connection)
        heartbeat = FakeHeartbeat()
        events = []

        def handler(context):
            raise RuntimeError("password=do-not-log payload-secret")

        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry((("director.daily_brief", handler),)),
            connection_factory=connections,
            config=self.config(),
            emit_event=lambda event, **fields: events.append((event, fields)),
            heartbeat_factory=lambda **kwargs: heartbeat,
        )

        outcome = runner.run_once()

        self.assertEqual(outcome.status, "queued")
        self.assertEqual(fail_connection.commits, 1)
        stored_error = fail_connection.cursor_value.calls[0][1][1]
        self.assertNotIn("do-not-log", stored_error)
        self.assertNotIn("payload-secret", stored_error)
        serialized_events = json.dumps(events)
        self.assertNotIn("do-not-log", serialized_events)
        self.assertNotIn("payload-secret", serialized_events)
        self.assertNotIn("do-not-log-correlation", serialized_events)
        self.assertIn("RuntimeError", serialized_events)

    def test_runner_claims_only_registry_job_types_and_idles_without_work(self):
        claim_connection = FakeConnection(None)
        connections = ConnectionSequence(claim_connection)
        registry = AgentJobHandlerRegistry((("system.worker_probe", lambda context: {}),))
        runner = AgentJobRunner(
            registry=registry,
            connection_factory=connections,
            config=self.config(),
            emit_event=lambda *args, **kwargs: None,
        )

        outcome = runner.run_once()

        self.assertFalse(outcome.processed)
        self.assertEqual(outcome.status, "idle")
        claim_params = claim_connection.cursor_value.calls[0][1]
        self.assertEqual(claim_params[0], ["system.worker_probe"])
        self.assertEqual(len(connections.created), 1)

    def test_runner_claims_only_the_requested_job_id(self):
        claim_connection = FakeConnection(None)
        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry(
                (("director.daily_brief", lambda context: {}),)
            ),
            connection_factory=ConnectionSequence(claim_connection),
            config=self.config(),
            emit_event=lambda *args, **kwargs: None,
        )

        outcome = runner.run_once(job_id=73)

        self.assertFalse(outcome.processed)
        self.assertEqual(outcome.status, "idle")
        sql, params = claim_connection.cursor_value.calls[0]
        self.assertIn("WHERE id=%s", sql)
        self.assertEqual(params[0], 73)
        self.assertEqual(params[1], ["director.daily_brief"])

    def test_exact_revision_impact_job_is_allowlisted_without_fallback(self):
        claim_connection = FakeConnection(None)
        registry = build_default_handler_registry()
        runner = AgentJobRunner(
            registry=registry,
            connection_factory=ConnectionSequence(claim_connection),
            config=self.config(),
            emit_event=lambda *args, **kwargs: None,
        )

        outcome = runner.run_once(job_id=73)

        self.assertFalse(outcome.processed)
        self.assertEqual(outcome.status, "idle")
        sql, params = claim_connection.cursor_value.calls[0]
        self.assertIn("WHERE id=%s", sql)
        self.assertEqual(params[0], 73)
        self.assertEqual(params[1], list(registry.job_types))
        self.assertIn("estimate.revision_impact", params[1])

    def test_lost_lease_does_not_store_handler_result(self):
        claim_connection = FakeConnection(claimed_row())
        complete_connection = FakeConnection(None)
        connections = ConnectionSequence(claim_connection, complete_connection)
        events = []
        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry((("director.daily_brief", lambda context: {"ok": True}),)),
            connection_factory=connections,
            config=self.config(),
            emit_event=lambda event, **fields: events.append((event, fields)),
            heartbeat_factory=lambda **kwargs: FakeHeartbeat(),
        )

        outcome = runner.run_once()

        self.assertEqual(outcome.status, "lease_lost")
        self.assertEqual(events[-1][0], "job_lease_lost")

    def test_recovery_uses_registry_allowlist_and_its_own_transaction(self):
        recovery_connection = FakeConnection([{"id": 51}, {"id": 52}])
        connections = ConnectionSequence(recovery_connection)
        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry((("system.worker_probe", lambda context: {}),)),
            connection_factory=connections,
            config=self.config(),
            emit_event=lambda *args, **kwargs: None,
        )

        recovered = runner.recover_once()

        self.assertEqual(recovered, 2)
        self.assertEqual(recovery_connection.commits, 1)
        params = recovery_connection.cursor_value.calls[0][1]
        self.assertEqual(params[0], ["system.worker_probe"])

    def test_transaction_rolls_back_and_closes_connection_on_database_error(self):
        class BrokenCursor(FakeCursor):
            def execute(self, sql, params=()):
                raise OSError("database unavailable")

        connection = FakeConnection()
        connection.cursor_value = BrokenCursor()
        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry((("system.worker_probe", lambda context: {}),)),
            connection_factory=ConnectionSequence(connection),
            config=self.config(),
            emit_event=lambda *args, **kwargs: None,
        )

        with self.assertRaises(OSError):
            runner.run_once()

        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_json_event_contains_metadata_but_not_payload_or_result(self):
        output = io.StringIO()

        emit_json_event(
            "job_succeeded",
            stream=output,
            job_id=41,
            company_id=7,
            payload={"password": "secret"},
            result={"text": "private result"},
        )

        event = json.loads(output.getvalue())
        self.assertEqual(event["event"], "job_succeeded")
        self.assertEqual(event["jobId"], 41)
        self.assertEqual(event["companyId"], 7)
        self.assertNotIn("payload", event)
        self.assertNotIn("result", event)
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("private result", output.getvalue())

    def test_worker_id_is_bounded_and_process_specific(self):
        worker_id = build_worker_id(hostname="build-host", process_id=123)

        self.assertEqual(worker_id, "agent-worker:build-host:123")
        self.assertLessEqual(len(worker_id), 120)

    def test_runner_module_is_independent_from_the_http_application_and_model_provider(self):
        source = Path(__file__).with_name("runner.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.main", source)
        self.assertNotIn("import backend.main", source)
        self.assertNotIn("from fastapi", source.lower())
        self.assertNotIn("import fastapi", source.lower())
        self.assertNotIn("from openai", source.lower())
        self.assertNotIn("import openai", source.lower())
        self.assertNotIn("from anthropic", source.lower())
        self.assertNotIn("import anthropic", source.lower())

    def test_config_normalizes_environment_style_values(self):
        config = AgentJobRunnerConfig(
            worker_id=" agent-worker:test ",
            lease_seconds="60",
            heartbeat_interval_seconds="15",
            poll_interval_seconds="0.5",
            retry_delay_seconds="30",
            recovery_interval_seconds="60",
            recovery_limit="25",
        )

        self.assertEqual(config.worker_id, "agent-worker:test")
        self.assertEqual(config.lease_seconds, 60)
        self.assertEqual(config.poll_interval_seconds, 0.5)

    def test_runner_config_is_built_from_bounded_environment_values(self):
        with patch.dict(os.environ, {
            "AGENT_JOB_LEASE_SECONDS": "90",
            "AGENT_JOB_HEARTBEAT_SECONDS": "20",
            "AGENT_JOB_POLL_SECONDS": "0.25",
            "AGENT_JOB_RETRY_SECONDS": "45",
            "AGENT_JOB_RECOVERY_SECONDS": "75",
            "AGENT_JOB_RECOVERY_LIMIT": "30",
        }, clear=False):
            config = build_runner_config_from_environment(
                worker_id="agent-worker:controlled-cycle"
            )

        self.assertEqual(config.worker_id, "agent-worker:controlled-cycle")
        self.assertEqual(config.lease_seconds, 90)
        self.assertEqual(config.heartbeat_interval_seconds, 20)
        self.assertEqual(config.poll_interval_seconds, 0.25)
        self.assertEqual(config.retry_delay_seconds, 45)
        self.assertEqual(config.recovery_interval_seconds, 75)
        self.assertEqual(config.recovery_limit, 30)


class LeaseHeartbeatTests(unittest.TestCase):
    def test_heartbeat_extends_lease_in_a_short_transaction(self):
        connection = FakeConnection({"id": 41, "status": "running"})
        events = []
        heartbeat = LeaseHeartbeat(
            connection_factory=ConnectionSequence(connection),
            job_id=41,
            worker_id="agent-worker:test",
            lease_token=LEASE_TOKEN,
            lease_seconds=60,
            interval_seconds=15,
            emit_event=lambda event, **fields: events.append((event, fields)),
        )

        self.assertTrue(heartbeat.beat_once())
        self.assertEqual(connection.commits, 1)
        self.assertTrue(connection.closed)
        self.assertEqual(events, [])

    def test_heartbeat_reports_lease_loss_without_secret_fields(self):
        connection = FakeConnection(None)
        events = []
        heartbeat = LeaseHeartbeat(
            connection_factory=ConnectionSequence(connection),
            job_id=41,
            worker_id="agent-worker:test",
            lease_token=LEASE_TOKEN,
            lease_seconds=60,
            interval_seconds=15,
            emit_event=lambda event, **fields: events.append((event, fields)),
        )

        self.assertFalse(heartbeat.beat_once())
        self.assertEqual(events[0][0], "job_heartbeat_lease_lost")
        self.assertNotIn(LEASE_TOKEN, json.dumps(events))


class RunnerLoopTests(unittest.TestCase):
    def test_run_forever_can_stop_while_idle(self):
        stop_event = threading.Event()
        stop_event.set()
        runner = AgentJobRunner(
            registry=AgentJobHandlerRegistry((("system.worker_probe", lambda context: {}),)),
            connection_factory=ConnectionSequence(),
            config=AgentJobRunnerConfig(worker_id="agent-worker:test"),
            emit_event=lambda *args, **kwargs: None,
        )

        runner.run_forever(stop_event=stop_event)

    def test_once_mode_reports_only_error_class_and_returns_nonzero(self):
        fake_registry = SimpleNamespace(job_types=("system.worker_probe",))

        class FailingRunner:
            def recover_once(self):
                raise RuntimeError("password=must-not-be-printed")

        fake_runner = FailingRunner()
        output = io.StringIO()

        with patch(
            "backend.features.agent_jobs.runner.build_default_handler_registry",
            return_value=fake_registry,
        ), patch(
            "backend.features.agent_jobs.runner.AgentJobRunner",
            return_value=fake_runner,
        ), patch("backend.features.agent_jobs.runner.signal.signal"), redirect_stdout(output):
            exit_code = main(["--once", "--worker-id", "agent-worker:test"])

        self.assertEqual(exit_code, 1)
        self.assertIn("RuntimeError", output.getvalue())
        self.assertNotIn("must-not-be-printed", output.getvalue())

    def test_exact_once_skips_global_recovery_and_passes_job_id(self):
        fake_registry = SimpleNamespace(job_types=("director.daily_brief",))

        class ExactRunner:
            recovery_calls = 0
            requested_job_ids = []

            def recover_once(self):
                self.recovery_calls += 1

            def run_once(self, *, job_id=None):
                self.requested_job_ids.append(job_id)
                return SimpleNamespace(processed=True, status="succeeded")

        fake_runner = ExactRunner()

        with patch(
            "backend.features.agent_jobs.runner.build_default_handler_registry",
            return_value=fake_registry,
        ), patch(
            "backend.features.agent_jobs.runner.AgentJobRunner",
            return_value=fake_runner,
        ), patch("backend.features.agent_jobs.runner.signal.signal"):
            exit_code = main(
                ["--once", "--job-id", "73", "--worker-id", "agent-worker:test"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_runner.recovery_calls, 0)
        self.assertEqual(fake_runner.requested_job_ids, [73])

    def test_exact_once_returns_nonzero_when_target_cannot_be_claimed(self):
        fake_registry = SimpleNamespace(job_types=("director.daily_brief",))

        class IdleRunner:
            def run_once(self, *, job_id=None):
                return SimpleNamespace(processed=False, status="idle")

        output = io.StringIO()
        with patch(
            "backend.features.agent_jobs.runner.build_default_handler_registry",
            return_value=fake_registry,
        ), patch(
            "backend.features.agent_jobs.runner.AgentJobRunner",
            return_value=IdleRunner(),
        ), patch("backend.features.agent_jobs.runner.signal.signal"), redirect_stdout(output):
            exit_code = main(
                ["--once", "--job-id", "73", "--worker-id", "agent-worker:test"]
            )

        self.assertEqual(exit_code, 2)
        stopped = [
            json.loads(line)
            for line in output.getvalue().splitlines()
            if '"event":"runner_stopped"' in line
        ][0]
        self.assertEqual(stopped["jobId"], 73)
        self.assertEqual(stopped["status"], "not_claimed")

    def test_job_id_is_rejected_without_once_mode(self):
        with self.assertRaises(SystemExit) as raised:
            main(["--job-id", "73", "--worker-id", "agent-worker:test"])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
