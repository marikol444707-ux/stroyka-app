import json
import os
import unittest
from unittest.mock import patch

from backend.features.agent_change_dispatch.contract import (
    validate_agent_dispatch_plan,
)
from backend.features.agent_change_dispatch.handoff import (
    agent_change_dispatch_enabled,
    handoff_estimate_activation_transition,
)


def activation(**overrides):
    value = {
        "previous_status": "Черновик",
        "next_status": "Активная",
        "company_id": 4,
        "project_id": 17,
        "estimate_id": 52,
        "version": "v2.0",
        "sections": [{"name": "Работы", "items": []}],
        "brief_date_provider": lambda: "2026-08-06",
    }
    value.update(overrides)
    return value


class FakeCursor:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.cursor_kwargs = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **kwargs):
        self.cursor_kwargs = kwargs
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class AgentChangeHandoffTests(unittest.TestCase):
    def test_feature_flag_is_disabled_by_default_and_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(agent_change_dispatch_enabled(4))

        for value in ("", "0", "false", "yes", "TRUE ", "enabled"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"AGENT_CHANGE_DISPATCH_APPLY": value},
                    clear=True,
                ):
                    self.assertFalse(agent_change_dispatch_enabled(4))

        with patch.dict(
            os.environ,
            {"AGENT_CHANGE_DISPATCH_APPLY": "true"},
            clear=True,
        ):
            self.assertFalse(agent_change_dispatch_enabled(4))

        with patch.dict(
            os.environ,
            {
                "AGENT_CHANGE_DISPATCH_APPLY": "true",
                "AGENT_CHANGE_DISPATCH_COMPANY_IDS": "4,17",
            },
            clear=True,
        ):
            self.assertTrue(agent_change_dispatch_enabled(4))
            self.assertTrue(agent_change_dispatch_enabled(17))
            self.assertFalse(agent_change_dispatch_enabled(5))

        for company_ids in ("", "4,all", "4, 17", "04", "0", "-4"):
            with self.subTest(company_ids=company_ids):
                with patch.dict(
                    os.environ,
                    {
                        "AGENT_CHANGE_DISPATCH_APPLY": "true",
                        "AGENT_CHANGE_DISPATCH_COMPANY_IDS": company_ids,
                    },
                    clear=True,
                ):
                    self.assertFalse(agent_change_dispatch_enabled(4))

        for company_id in (None, True, 0, -1, "4"):
            with self.subTest(company_id=company_id):
                with patch.dict(
                    os.environ,
                    {
                        "AGENT_CHANGE_DISPATCH_APPLY": "true",
                        "AGENT_CHANGE_DISPATCH_COMPANY_IDS": "4",
                    },
                    clear=True,
                ):
                    self.assertFalse(agent_change_dispatch_enabled(company_id))

    def test_disabled_handoff_preserves_exact_shadow_behavior_without_connection(self):
        lines = []

        report = handoff_estimate_activation_transition(
            **activation(),
            enabled=False,
            connection_factory=lambda: self.fail("connection must stay disabled"),
            log_fn=lines.append,
        )

        self.assertEqual(report["mode"], "shadow")
        self.assertEqual(report["state"], "planned")
        self.assertFalse(report["enqueueAttempted"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(json.loads(lines[0]), report)

    def test_default_handoff_needs_flag_and_company_allowlist(self):
        with patch.dict(
            os.environ,
            {"AGENT_CHANGE_DISPATCH_APPLY": "true"},
            clear=True,
        ):
            report = handoff_estimate_activation_transition(
                **activation(),
                connection_factory=lambda: self.fail("allowlist is required"),
                log_fn=lambda _line: None,
            )

        self.assertEqual(report["mode"], "shadow")
        self.assertEqual(report["state"], "planned")

    def test_non_activation_transition_never_opens_connection(self):
        report = handoff_estimate_activation_transition(
            **activation(previous_status="Активная", next_status="Черновик"),
            enabled=True,
            connection_factory=lambda: self.fail("connection must not open"),
            log_fn=lambda _line: self.fail("ignored transition must not log"),
        )

        self.assertIsNone(report)

    def test_enabled_handoff_commits_one_exact_validated_queue_dispatch(self):
        connection = FakeConnection()
        dispatches = []
        lines = []

        def dispatch_plan(cursor, *, plan, apply):
            dispatches.append((cursor, validate_agent_dispatch_plan(plan), apply))
            return {
                "ok": True,
                "dryRun": False,
                "state": "enqueued",
                "enqueueAttempted": True,
                "writesAttempted": 1,
                "companyId": 4,
                "projectId": 17,
                "jobType": "director.daily_brief",
                "briefDate": "2026-08-06",
                "jobId": 81,
                "status": "queued",
            }

        report = handoff_estimate_activation_transition(
            **activation(),
            enabled=True,
            connection_factory=lambda: connection,
            dispatch_plan=dispatch_plan,
            log_fn=lines.append,
        )

        self.assertEqual(len(dispatches), 1)
        self.assertIs(dispatches[0][0], connection.cursor_instance)
        self.assertTrue(dispatches[0][2])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertTrue(connection.closed)
        self.assertEqual(report["mode"], "enqueue")
        self.assertEqual(report["state"], "enqueued")
        self.assertEqual(report["jobId"], 81)
        self.assertTrue(report["committed"])
        self.assertEqual(json.loads(lines[-1]), report)

    def test_existing_job_is_committed_as_idempotent_success(self):
        connection = FakeConnection()

        report = handoff_estimate_activation_transition(
            **activation(),
            enabled=True,
            connection_factory=lambda: connection,
            dispatch_plan=lambda *_args, **_kwargs: {
                "ok": True,
                "dryRun": False,
                "state": "existing",
                "enqueueAttempted": True,
                "writesAttempted": 1,
                "companyId": 4,
                "projectId": 17,
                "jobType": "director.daily_brief",
                "briefDate": "2026-08-06",
                "jobId": 81,
                "status": "succeeded",
            },
            log_fn=lambda _line: None,
        )

        self.assertEqual(report["state"], "existing")
        self.assertTrue(report["committed"])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)

    def test_connection_or_dispatch_failure_is_rolled_back_and_bounded(self):
        cases = []

        def broken_connection():
            raise RuntimeError("database password=secret")

        cases.append((broken_connection, None, None))

        dispatch_connection = FakeConnection()

        def broken_dispatch(*_args, **_kwargs):
            raise RuntimeError("queue token=secret")

        cases.append((lambda: dispatch_connection, broken_dispatch, dispatch_connection))

        for connection_factory, dispatch_plan, expected_connection in cases:
            with self.subTest(has_connection=expected_connection is not None):
                lines = []
                kwargs = {}
                if dispatch_plan is not None:
                    kwargs["dispatch_plan"] = dispatch_plan

                report = handoff_estimate_activation_transition(
                    **activation(),
                    enabled=True,
                    connection_factory=connection_factory,
                    log_fn=lines.append,
                    **kwargs,
                )

                self.assertEqual(report["mode"], "enqueue")
                self.assertEqual(report["state"], "failed")
                self.assertEqual(report["reasonCode"], "dispatch_unavailable")
                self.assertFalse(report["committed"])
                serialized = json.dumps(report, ensure_ascii=False)
                self.assertNotIn("secret", serialized)
                self.assertNotIn("password", serialized)
                self.assertNotIn("token", serialized)
                self.assertEqual(json.loads(lines[-1]), report)
                if expected_connection is not None:
                    self.assertEqual(expected_connection.commits, 0)
                    self.assertEqual(expected_connection.rollbacks, 1)
                    self.assertTrue(expected_connection.closed)


if __name__ == "__main__":
    unittest.main()
