import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from backend.features.agent_change_dispatch.shadow import (
    observe_estimate_activation_shadow,
    observe_estimate_activation_transition_shadow,
)


def activation(**overrides):
    value = {
        "company_id": 4,
        "project_id": 17,
        "estimate_id": 52,
        "version": "v2.0",
        "sections": [{"name": "Работы", "items": [{"name": "Секретная строка", "quantity": 2}]}],
    }
    value.update(overrides)
    return value


class EstimateActivationShadowTests(unittest.TestCase):
    def test_module_imports_from_backend_working_directory(self):
        backend_dir = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env["PYTHONPYCACHEPREFIX"] = "/tmp/stroyka-pycache"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from features.agent_change_dispatch.shadow import observe_estimate_activation_transition_shadow",
            ],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_builds_metadata_only_plan_without_enqueue_or_writes(self):
        lines = []

        report = observe_estimate_activation_shadow(
            **activation(),
            brief_date_provider=lambda: "2026-08-06",
            log_fn=lines.append,
        )

        self.assertEqual(report, {
            "mode": "shadow",
            "state": "planned",
            "eventType": "estimate.version_activated",
            "companyId": 4,
            "projectId": 17,
            "sourceType": "estimate",
            "sourceId": 52,
            "jobType": "director.daily_brief",
            "briefDate": "2026-08-06",
            "enqueueAttempted": False,
            "writesAttempted": 0,
        })
        self.assertEqual(json.loads(lines[0]), report)

    def test_log_excludes_estimate_content_and_dispatch_identity(self):
        lines = []

        observe_estimate_activation_shadow(
            **activation(),
            brief_date_provider=lambda: "2026-08-06",
            log_fn=lines.append,
        )

        self.assertNotIn("Секретная строка", lines[0])
        self.assertNotIn("sourceRevision", lines[0])
        self.assertNotIn("idempotency", lines[0].lower())
        self.assertNotIn("correlation", lines[0].lower())

    def test_same_activation_is_deterministic(self):
        first = observe_estimate_activation_shadow(
            **activation(),
            brief_date_provider=lambda: "2026-08-06",
            log_fn=lambda _line: None,
        )
        second = observe_estimate_activation_shadow(
            **activation(),
            brief_date_provider=lambda: "2026-08-06",
            log_fn=lambda _line: None,
        )

        self.assertEqual(first, second)

    def test_rejects_invalid_scope_or_sections_without_raising(self):
        for overrides in (
            {"company_id": 0},
            {"project_id": None},
            {"estimate_id": "52"},
            {"sections": None},
            {"sections": {"items": []}},
            {"sections": [{"quantity": float("nan")}]},
        ):
            with self.subTest(overrides=overrides):
                report = observe_estimate_activation_shadow(
                    **activation(**overrides),
                    brief_date_provider=lambda: "2026-08-06",
                    log_fn=lambda _line: None,
                )

                self.assertEqual(report["mode"], "shadow")
                self.assertEqual(report["state"], "rejected")
                self.assertEqual(report["eventType"], "estimate.version_activated")
                self.assertFalse(report["enqueueAttempted"])
                self.assertEqual(report["writesAttempted"], 0)
                self.assertNotIn("error", report)
                self.assertIn(
                    report["reasonCode"],
                    ("contract_rejected", "source_invalid"),
                )

    def test_clock_or_logger_failure_never_breaks_completed_business_action(self):
        def broken_clock():
            raise RuntimeError("clock unavailable")

        def broken_logger(_line):
            raise RuntimeError("logger unavailable")

        clock_report = observe_estimate_activation_shadow(
            **activation(),
            brief_date_provider=broken_clock,
            log_fn=lambda _line: None,
        )
        logger_report = observe_estimate_activation_shadow(
            **activation(),
            brief_date_provider=lambda: "2026-08-06",
            log_fn=broken_logger,
        )

        self.assertEqual(clock_report["state"], "rejected")
        self.assertEqual(clock_report["reasonCode"], "shadow_unavailable")
        self.assertEqual(logger_report["state"], "planned")

    def test_transition_observer_ignores_non_activation_changes(self):
        lines = []

        for previous_status, next_status in (
            ("Активная", "Активная"),
            ("Активная", "Черновик"),
            ("Черновик", "Черновик"),
        ):
            with self.subTest(previous_status=previous_status, next_status=next_status):
                report = observe_estimate_activation_transition_shadow(
                    previous_status=previous_status,
                    next_status=next_status,
                    **activation(),
                    brief_date_provider=lambda: "2026-08-06",
                    log_fn=lines.append,
                )
                self.assertIsNone(report)

        self.assertEqual(lines, [])

    def test_transition_observer_plans_create_or_draft_activation(self):
        for previous_status in (None, "Черновик"):
            with self.subTest(previous_status=previous_status):
                report = observe_estimate_activation_transition_shadow(
                    previous_status=previous_status,
                    next_status="Активная",
                    **activation(),
                    brief_date_provider=lambda: "2026-08-06",
                    log_fn=lambda _line: None,
                )
                self.assertEqual(report["state"], "planned")


if __name__ == "__main__":
    unittest.main()
