"""Regression tests for owner-visible Jev run monitoring (#279)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

import dev_control.browser_worker.service as service
from dev_control.browser_worker.viewer import VIEWER_HTML, viewer_headers


class ViewerContractTest(unittest.TestCase):
    def test_viewer_keeps_token_out_of_url_and_persistent_storage(self):
        self.assertIn("sessionStorage", VIEWER_HTML)
        self.assertIn("Authorization", VIEWER_HTML)
        self.assertIn("/cancel", VIEWER_HTML)
        self.assertNotIn("localStorage", VIEWER_HTML)
        self.assertNotIn("?token=", VIEWER_HTML)
        self.assertNotIn("innerHTML", VIEWER_HTML)
        self.assertNotIn("tokenInput.value=token", VIEWER_HTML)
        self.assertIn("tokenInput.value=''", VIEWER_HTML)

    def test_viewer_binds_stop_to_rendered_run_and_discards_stale_details(self):
        self.assertIn("rendered!==selected", VIEWER_HTML)
        self.assertIn("const requested=selected", VIEWER_HTML)
        self.assertIn("selected!==requested||seq!==detailSeq", VIEWER_HTML)
        self.assertIn("const requested=rendered", VIEWER_HTML)

    def test_viewer_clears_old_frame_when_switching_or_no_image_exists(self):
        self.assertIn("function clearFrame()", VIEWER_HTML)
        self.assertIn("if(!latest){if(selected===requested&&seq===detailSeq)clearFrame();return;}", VIEWER_HTML)
        self.assertIn("rendered=null;detailSeq++;clearFrame()", VIEWER_HTML)

    def test_viewer_security_headers_deny_embedding_and_caching(self):
        headers = viewer_headers()
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])

    def test_commit_metadata_is_hex_only(self):
        value = service.JobRequest(url="http://127.0.0.1:8080/selftest-page", goal="test", expect_text=["x"], commit_sha="ABCDEF1")
        self.assertEqual(value.commit_sha, "abcdef1")
        with self.assertRaises(ValidationError):
            service.JobRequest(url="http://127.0.0.1:8080/selftest-page", goal="test", expect_text=["x"], commit_sha="../secret")


class ViewerJobAccessTest(unittest.TestCase):
    def setUp(self):
        self.old_accepting = service._accepting_jobs
        with service._jobs_lock:
            self.old_jobs = dict(service._jobs)
            service._jobs.clear()
        with service._active_process_lock:
            self.old_process = service._active_process
            self.old_active_job = service._active_job_id
            service._active_process = None
            service._active_job_id = None
        service._accepting_jobs = True

    def tearDown(self):
        with service._jobs_lock:
            service._jobs.clear()
            service._jobs.update(self.old_jobs)
        with service._active_process_lock:
            service._active_process = self.old_process
            service._active_job_id = self.old_active_job
        service._accepting_jobs = self.old_accepting

    def auth(self):
        return "Bearer viewer-secret"

    def test_get_job_exposes_redacted_progress_and_real_frame_names_only_after_auth(self):
        job_id = "a" * 32
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "viewer-secret", "QA_EVIDENCE_DIR": directory}, clear=True):
            root = Path(directory) / job_id
            root.mkdir()
            (root / "000000.jpg").write_bytes(b"jpeg")
            progress = {"phase": "action_complete", "history": [{"action": "Run test"}], "decisions": [{"operation": "CLICK"}], "updated_at_ms": 123}
            (root / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
            with service._jobs_lock:
                service._jobs[job_id] = {"status": "running", "metadata": {"display_name": "Synthetic"}}
            with self.assertRaises(HTTPException) as caught:
                service.get_job(job_id, None)
            self.assertEqual(caught.exception.status_code, 401)
            data = service.get_job(job_id, self.auth())
            self.assertEqual(data["progress"]["phase"], "action_complete")
            self.assertEqual(data["evidence_files"], [f"/jobs/{job_id}/evidence/000000.jpg"])

    def test_queued_cancel_is_idempotent_and_does_not_touch_other_job(self):
        first, second = "b" * 32, "c" * 32
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "viewer-secret"}, clear=True):
            with service._jobs_lock:
                service._jobs[first] = {"status": "queued", "cancel_requested": False}
                service._jobs[second] = {"status": "running", "cancel_requested": False}
            result = service.cancel_job(first, self.auth())
            self.assertEqual(result["status"], "cancelled")
            with service._jobs_lock:
                self.assertTrue(service._jobs[first]["cancel_requested"])
                self.assertEqual(service._jobs[second]["status"], "running")
            again = service.cancel_job(first, self.auth())
            self.assertTrue(again["already_finished"])

    def test_running_cancel_only_signals_matching_active_process(self):
        first, second = "d" * 32, "e" * 32
        process = Mock()
        process.is_alive.return_value = True
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "viewer-secret"}, clear=True):
            with service._jobs_lock:
                service._jobs[first] = {"status": "running", "cancel_requested": False}
                service._jobs[second] = {"status": "running", "cancel_requested": False}
            with service._active_process_lock:
                service._active_job_id = first
                service._active_process = process
            result = service.cancel_job(first, self.auth())
            self.assertEqual(result["status"], "cancelling")
            process.terminate.assert_called_once_with()
            process.reset_mock()
            service.cancel_job(second, self.auth())
            process.terminate.assert_not_called()

    @patch("dev_control.browser_worker.service.multiprocessing.get_context")
    def test_cancelled_queued_job_never_spawns_browser_process(self, get_context):
        job_id = "f" * 32
        with service._jobs_lock:
            service._jobs[job_id] = {"status": "cancelled", "cancel_requested": True}
        request = service.JobRequest(url="http://127.0.0.1:8080/selftest-page", goal="test", expect_text=["x"])
        service._execute(job_id, request)
        get_context.assert_not_called()
        with service._jobs_lock:
            self.assertEqual(service._jobs[job_id]["status"], "cancelled")
            self.assertTrue(service._jobs[job_id]["result"]["cancelled"])

    @patch("dev_control.browser_worker.service._executor.submit")
    def test_startup_selftest_clears_previous_fixed_evidence_before_queueing(self, submit):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "QA_EVIDENCE_DIR": directory,
                "QA_SELFTEST_ON_START": "1",
                "QA_BASE_URL": "http://127.0.0.1:8080",
                "QA_ENVIRONMENT": "test",
                "TIMEWEB_AI_API_KEY": "test-only",
            },
            clear=True,
        ):
            root = Path(directory) / "startup-selftest"
            root.mkdir()
            (root / "000000.jpg").write_bytes(b"old-frame")
            (root / "progress.json").write_text('{"phase":"old"}', encoding="utf-8")
            service.schedule_startup_selftest()
            self.assertFalse(root.exists())
            with service._jobs_lock:
                self.assertEqual(service._jobs["startup-selftest"]["status"], "queued")
            submit.assert_called_once()

    def test_job_list_requires_auth_and_returns_only_public_metadata(self):
        job_id = "1" * 32
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "viewer-secret"}, clear=True):
            with service._jobs_lock:
                service._jobs[job_id] = {"status": "passed", "created_at_ms": 10, "updated_at_ms": 11, "metadata": {"issue_number": 279, "commit_sha": "47943c2"}}
            with self.assertRaises(HTTPException):
                service.list_jobs(None)
            rows = service.list_jobs(self.auth())["jobs"]
            self.assertEqual(rows[0]["job_id"], job_id)
            self.assertEqual(rows[0]["metadata"]["issue_number"], 279)
            self.assertNotIn("result", rows[0])


if __name__ == "__main__":
    unittest.main()
