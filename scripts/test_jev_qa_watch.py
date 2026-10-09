"""Offline tests for the unattended JEVA QA watcher. No Docker/network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.jev_qa_watch import (
    QA_HOST, QA_URL, REQUIRED_CHECKS, WatchError, classify_failures,
    github_report, run_smoke, save_report, worker_base,
)


JOB_ID = "a" * 32


class FakeWorker:
    def __init__(self, status="passed", result=None):
        self.status = status
        self.result = result if result is not None else {
            "ok": True,
            "checks": sorted(REQUIRED_CHECKS),
            "failures": [],
        }
        self.calls = []

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == "/health":
            return {"ok": True, "environment": "qa"}
        if method == "POST" and path == "/jobs":
            return {"job_id": JOB_ID, "status": "queued"}
        if path == "/jobs/" + JOB_ID:
            return {"job_id": JOB_ID, "status": self.status, "result": self.result}
        raise AssertionError((method, path))


class JevQaWatchTest(unittest.TestCase):
    def test_only_loopback_port_is_allowed(self):
        self.assertEqual(worker_base("18088"), "http://127.0.0.1:18088")
        for value in ("80", "0", "65536", "127.0.0.1:18088", "http://evil", "18088/x"):
            with self.subTest(value=value), self.assertRaises(WatchError):
                worker_base(value)

    def test_read_only_goal_and_deterministic_assertions(self):
        worker = FakeWorker()
        report = run_smoke(worker, sleep=lambda _: None)
        self.assertEqual(report["outcome"], "passed")
        request = worker.calls[1]
        self.assertEqual(request[0:2], ("POST", "/jobs"))
        self.assertEqual(request[2]["url"], QA_URL)
        self.assertEqual(request[2]["expect_text"], ["Склад"])
        self.assertEqual(request[2]["expect_url_contains"], [QA_HOST])
        self.assertIn("Do not click", request[2]["goal"])
        self.assertNotIn("password", json.dumps(request[2]).lower())

    def test_agent_done_without_assertions_is_not_pass(self):
        worker = FakeWorker(result={"ok": True, "checks": ["agent_status=done"], "failures": []})
        self.assertEqual(run_smoke(worker, sleep=lambda _: None)["outcome"], "failed")

    def test_blocked_and_raw_error_text_are_redacted(self):
        secret = "private-cookie-value"
        worker = FakeWorker(status="failed", result={
            "ok": False,
            "checks": ["expect_text[0]:missing"],
            "failures": ["agent_status=blocked", "secret " + secret],
        })
        report = run_smoke(worker, sleep=lambda _: None)
        self.assertEqual(report["outcome"], "failed")
        self.assertIn("AGENT_BLOCKED", report["failure_codes"])
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn("secret", json.dumps(report))

    def test_unhealthy_worker_never_starts_job(self):
        worker = FakeWorker()
        def unhealthy(method, path, payload=None):
            if path == "/health":
                return {"ok": True, "environment": "production"}
            return worker(method, path, payload)
        with self.assertRaisesRegex(WatchError, "QA_WORKER_NOT_READY"):
            run_smoke(unhealthy, sleep=lambda _: None)
        self.assertEqual(worker.calls, [])

    def test_no_untrusted_failure_text_in_report(self):
        codes = classify_failures([
            "RuntimeError: api_token=DO_NOT_LEAK",
            "JevError: QA JavaScript alert observed and dismissed",
        ])
        self.assertEqual(codes, ["OTHER_FAILURE", "QA_ALERT_STOP"])

    def test_atomic_report_written_with_expected_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            report = {"outcome": "failed", "failure_codes": ["AGENT_BLOCKED"]}
            save_report(report, path)
            self.assertEqual(json.loads((path / "last.json").read_text()), report)
            self.assertEqual((path / "last.json").stat().st_mode & 0o777, 0o600)

    def test_github_comment_uses_fixed_url_and_no_raw_errors(self):
        captured = {}
        class FakeResponse:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): return False
        def fake_open(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()
        report = {
            "utc": "2026-10-09T06:00:00+00:00",
            "outcome": "failed",
            "job_id": JOB_ID,
            "checks": ["expect_text[0]:missing"],
            "failure_codes": ["TEXT_NOT_FOUND"],
        }
        with patch("scripts.jev_qa_watch.urllib.request.urlopen", side_effect=fake_open):
            github_report(report, "test-token")
        request = captured["request"]
        self.assertEqual(request.full_url, "https://api.github.com/repos/marikol444707-ux/stroyka-app/issues/311/comments")
        self.assertIn("TEXT_NOT_FOUND", request.data.decode())
        self.assertNotIn("test-token", request.data.decode())


if __name__ == "__main__":
    unittest.main()
