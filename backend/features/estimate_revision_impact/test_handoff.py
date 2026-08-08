import ast
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.handoff import (
    estimate_revision_impact_enabled,
    handoff_estimate_revision_impact_transition,
)
from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
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
    }
    value.update(overrides)
    return value


def source():
    value = activation()
    return build_estimate_revision_source(
        company_id=value["company_id"],
        project_id=value["project_id"],
        estimate_id=value["estimate_id"],
        version=value["version"],
        sections=value["sections"],
    )


def queue_report(**overrides):
    plan = build_estimate_revision_impact_job_plan(source())
    value = {
        "ok": True,
        "dryRun": False,
        "writesAttempted": 1,
        "state": "enqueued",
        "companyId": 4,
        "projectId": 17,
        "estimateId": 52,
        "sourceRevision": source().source_revision,
        "jobType": "estimate.revision_impact",
        "idempotencyKey": plan.idempotency_key,
        "jobId": 81,
        "status": "queued",
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
        self.session_calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class EstimateRevisionImpactHandoffTests(unittest.TestCase):
    def test_feature_controls_are_disabled_by_default_and_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(estimate_revision_impact_enabled(4))

        for value in ("", "0", "false", "yes", "TRUE", "true "):
            with self.subTest(value=value), patch.dict(
                os.environ,
                {"ESTIMATE_REVISION_IMPACT_APPLY": value},
                clear=True,
            ):
                self.assertFalse(estimate_revision_impact_enabled(4))

        with patch.dict(os.environ, {
            "ESTIMATE_REVISION_IMPACT_APPLY": "true",
            "ESTIMATE_REVISION_IMPACT_COMPANY_IDS": "4,17",
        }, clear=True):
            self.assertTrue(estimate_revision_impact_enabled(4))
            self.assertTrue(estimate_revision_impact_enabled(17))
            self.assertFalse(estimate_revision_impact_enabled(5))

        for company_ids in ("", "4,all", "4, 17", "04", "0", "-4"):
            with self.subTest(company_ids=company_ids), patch.dict(
                os.environ,
                {
                    "ESTIMATE_REVISION_IMPACT_APPLY": "true",
                    "ESTIMATE_REVISION_IMPACT_COMPANY_IDS": company_ids,
                },
                clear=True,
            ):
                self.assertFalse(estimate_revision_impact_enabled(4))

        for company_id in (None, True, 0, -1, "4"):
            with self.subTest(company_id=company_id), patch.dict(
                os.environ,
                {
                    "ESTIMATE_REVISION_IMPACT_APPLY": "true",
                    "ESTIMATE_REVISION_IMPACT_COMPANY_IDS": "4",
                },
                clear=True,
            ):
                self.assertFalse(estimate_revision_impact_enabled(company_id))

    def test_disabled_activation_is_metadata_only_and_opens_no_connection(self):
        lines = []
        with patch.dict(os.environ, {}, clear=True):
            report = handoff_estimate_revision_impact_transition(
                **activation(),
                connection_factory=lambda: self.fail("connection must stay disabled"),
                log_fn=lines.append,
            )

        self.assertEqual(report, {
            "mode": "shadow",
            "state": "planned",
            "eventType": "estimate.version_activated",
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "jobType": "estimate.revision_impact",
            "enqueueAttempted": False,
            "writesAttempted": 0,
        })
        self.assertEqual(json.loads(lines[0]), report)
        self.assertNotIn("sourceRevision", lines[0])
        self.assertNotIn("idempotency", lines[0].lower())

    def test_ignored_or_invalid_activation_never_opens_connection(self):
        lines = []
        for changes in (
            {"previous_status": "Активная", "next_status": "Активная"},
            {"previous_status": "Активная", "next_status": "Черновик"},
            {"previous_status": "Черновик", "next_status": "Черновик"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(handoff_estimate_revision_impact_transition(
                    **activation(**changes),
                    enabled=True,
                    connection_factory=lambda: self.fail("ignored transition"),
                    log_fn=lines.append,
                ))
        self.assertEqual(lines, [])

        invalid = handoff_estimate_revision_impact_transition(
            **activation(project_id=None),
            enabled=True,
            connection_factory=lambda: self.fail("invalid source"),
            log_fn=lines.append,
        )
        self.assertEqual(invalid["mode"], "shadow")
        self.assertEqual(invalid["state"], "rejected")
        self.assertEqual(invalid["reasonCode"], "source_invalid")
        self.assertFalse(invalid["enqueueAttempted"])
        self.assertEqual(invalid["writesAttempted"], 0)

    def test_enabled_activation_commits_one_exact_source_queue_attempt(self):
        connection = FakeConnection()
        seen = []

        def prepare_job(cur, exact_source, *, apply, enqueue_job):
            seen.append((cur, exact_source, apply))
            enqueue_job(cur, marker=True)
            return queue_report()

        enqueue_calls = []
        report = handoff_estimate_revision_impact_transition(
            **activation(),
            enabled=True,
            connection_factory=lambda: connection,
            prepare_job=prepare_job,
            enqueue_job=lambda cur, **kwargs: enqueue_calls.append((cur, kwargs)),
            log_fn=lambda _line: None,
        )

        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0][0], connection.cursor_instance)
        self.assertEqual(seen[0][1], source())
        self.assertTrue(seen[0][2])
        self.assertEqual(enqueue_calls, [(connection.cursor_instance, {"marker": True})])
        self.assertEqual(connection.session_calls, [{
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        }])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertTrue(connection.closed)
        self.assertEqual(report, {
            "mode": "enqueue",
            "state": "enqueued",
            "eventType": "estimate.version_activated",
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "jobType": "estimate.revision_impact",
            "enqueueAttempted": True,
            "writesAttempted": 1,
            "jobId": 81,
            "status": "queued",
            "committed": True,
        })

    def test_exact_existing_job_commits_without_an_enqueue_write(self):
        connection = FakeConnection()
        report = handoff_estimate_revision_impact_transition(
            **activation(),
            enabled=True,
            connection_factory=lambda: connection,
            prepare_job=lambda *_args, **_kwargs: queue_report(
                state="existing",
                writesAttempted=0,
                status="succeeded",
            ),
            enqueue_job=lambda *_args, **_kwargs: self.fail("already exists"),
            log_fn=lambda _line: None,
        )
        self.assertEqual(report["state"], "existing")
        self.assertFalse(report["enqueueAttempted"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["committed"])
        self.assertEqual(connection.commits, 1)

    def test_connection_validation_or_enqueue_failure_is_bounded_and_rolled_back(self):
        cases = []

        def broken_connection():
            raise RuntimeError("database password=must-not-leak")

        def broken_enqueue(*_args, **_kwargs):
            raise RuntimeError("token=must-not-leak")

        cases.append((broken_connection, None, False, None))

        validation_connection = FakeConnection()
        cases.append((
            lambda: validation_connection,
            lambda *_args, **_kwargs: queue_report(projectId=18),
            False,
            validation_connection,
        ))

        enqueue_connection = FakeConnection()

        def enqueue_failure(cur, _source, *, apply, enqueue_job):
            self.assertTrue(apply)
            enqueue_job(cur)

        cases.append((
            lambda: enqueue_connection,
            enqueue_failure,
            True,
            enqueue_connection,
        ))

        for connection_factory, prepare_job, attempted, expected_connection in cases:
            with self.subTest(attempted=attempted, has_connection=expected_connection is not None):
                kwargs = {}
                if prepare_job is not None:
                    kwargs["prepare_job"] = prepare_job
                lines = []
                report = handoff_estimate_revision_impact_transition(
                    **activation(),
                    enabled=True,
                    connection_factory=connection_factory,
                    enqueue_job=broken_enqueue,
                    log_fn=lines.append,
                    **kwargs,
                )
                self.assertEqual(report["mode"], "enqueue")
                self.assertEqual(report["state"], "failed")
                self.assertEqual(report["reasonCode"], "queue_unavailable")
                self.assertEqual(report["enqueueAttempted"], attempted)
                self.assertEqual(report["writesAttempted"], 1 if attempted else 0)
                self.assertFalse(report["committed"])
                serialized = json.dumps(report, ensure_ascii=False)
                for forbidden in ("must-not-leak", "password", "token", "sourceRevision"):
                    self.assertNotIn(forbidden, serialized)
                self.assertEqual(json.loads(lines[-1]), report)
                if expected_connection is not None:
                    self.assertEqual(expected_connection.commits, 0)
                    self.assertEqual(expected_connection.rollbacks, 1)
                    self.assertTrue(expected_connection.closed)

    def test_all_three_activation_paths_call_handoff_after_commit(self):
        root = Path(__file__).resolve().parents[3]
        main_path = root / "backend/main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node

        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "handoff_estimate_revision_impact_transition"
        ]
        owners = []
        for call in calls:
            node = call
            while node in parent and not isinstance(node, ast.FunctionDef):
                node = parent[node]
            owners.append(node.name)
            function_source = ast.get_source_segment(
                main_path.read_text(encoding="utf-8"), node,
            )
            commit_offset = function_source.find("conn.commit()")
            handoff_offset = function_source.find(
                "handoff_estimate_revision_impact_transition("
            )
            self.assertGreater(handoff_offset, commit_offset)

        self.assertEqual(sorted(owners), [
            "create_estimate",
            "update_estimate",
            "update_estimate_status",
        ])

    def test_backend_working_directory_import_and_disabled_inventory(self):
        root = Path(__file__).resolve().parents[3]
        backend_dir = root / "backend"
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env["PYTHONPYCACHEPREFIX"] = "/tmp/stroyka-a75-handoff-pycache"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from features.estimate_revision_impact.handoff import estimate_revision_impact_enabled",
            ],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        for relative in (
            "deploy.sh",
            "ops/systemd/stroyka-director-daily-brief.service",
            "ops/systemd/stroyka-director-daily-brief.timer",
        ):
            content = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("ESTIMATE_REVISION_IMPACT_APPLY", content)
            self.assertNotIn("ESTIMATE_REVISION_IMPACT_COMPANY_IDS", content)
        main_source = (root / "backend/main.py").read_text(encoding="utf-8")
        self.assertNotIn("ESTIMATE_REVISION_IMPACT_APPLY", main_source)
        self.assertNotIn("ESTIMATE_REVISION_IMPACT_COMPANY_IDS", main_source)


if __name__ == "__main__":
    unittest.main()
