import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from dev_control.browser_worker.service import (
    JobRequest,
    _authorize,
    _chrome_alive,
    _configured,
    _evidence_max_bytes,
    _evidence_non_result_bytes,
    _evidence_ttl_seconds,
    _max_pending_jobs,
    _qa_base_is_nonproduction,
    _valid_job_id,
    _startup_selftest_enabled,
    _authorize_watcher_request,
    _watcher_scoped_token,
    _watcher_signature,
    _watcher_smoke_request,
    _watcher_seen_nonces,
    _watcher_nonce_lock,
    _worker_api_token,
    _commit_final_state,
    _jobs,
    _jobs_lock,
    _set_job,
    health,
    shutdown_worker,
)


STRONG_TOKEN = "a" * 64
WRONG_STRONG_TOKEN = "b" * 64


class BrowserWorkerServiceConfigTest(unittest.TestCase):

    def test_job_request_read_only_is_explicit_and_defaults_off(self):
        base = dict(url="https://qa.example.test/app", goal="Observe QA", expect_text=["Склад"])
        self.assertFalse(JobRequest(**base).read_only)
        self.assertTrue(JobRequest(**base, read_only=True).read_only)

    def test_configured_requires_test_environment_and_secrets(self):
        good = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "https://qa.example.test",
            "QA_ALLOWED_ORIGIN": "https://qa.example.test",
            "QA_ENVIRONMENT": "staging",
        }
        with patch.dict(os.environ, good, clear=True):
            self.assertTrue(_configured())

        bad = dict(good, QA_ENVIRONMENT="production")
        with patch.dict(os.environ, bad, clear=True):
            self.assertFalse(_configured())


    def test_remote_qa_requires_exact_explicit_allowlist(self):
        base = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_ENVIRONMENT": "staging",
            "QA_BASE_URL": "https://qa.example.test",
        }
        with patch.dict(os.environ, base, clear=True):
            self.assertFalse(_configured())
        with patch.dict(os.environ, {**base, "QA_ALLOWED_ORIGIN": "https://qa.example.test"}, clear=True):
            self.assertTrue(_configured())
        with patch.dict(os.environ, {**base, "QA_ALLOWED_ORIGIN": "https://other.example.test"}, clear=True):
            self.assertFalse(_configured())


    def test_malformed_allowlist_port_fails_closed(self):
        env = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_ENVIRONMENT": "staging",
            "QA_BASE_URL": "https://qa.example.test",
            "QA_ALLOWED_ORIGIN": "https://qa.example.test:notaport",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(_configured())
            self.assertEqual(health().status_code, 503)

    def test_known_production_ip_and_subdomains_are_denied(self):
        for url in ("https://147.45.237.127", "https://app.stroyka26.pro", "https://qa.stroyka.pro"):
            env = {
                "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
                "TIMEWEB_AI_API_KEY": "ai-secret",
                "QA_ENVIRONMENT": "staging",
                "QA_BASE_URL": url,
                "QA_ALLOWED_ORIGIN": url,
            }
            with self.subTest(url=url), patch.dict(os.environ, env, clear=True):
                self.assertFalse(_configured())

    def test_startup_selftest_is_local_only(self):
        base = {
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_ENVIRONMENT": "staging",
            "QA_SELFTEST_ON_START": "1",
        }
        with patch.dict(os.environ, {**base, "QA_BASE_URL": "http://127.0.0.1:8080"}, clear=True):
            self.assertTrue(_startup_selftest_enabled())
        with patch.dict(os.environ, {**base, "QA_BASE_URL": "https://stroyka26.pro"}, clear=True):
            self.assertFalse(_startup_selftest_enabled())


    def test_production_origin_is_denied_even_when_labeled_staging(self):
        env = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "https://stroyka26.pro",
            "QA_ENVIRONMENT": "staging",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(_qa_base_is_nonproduction())
            self.assertFalse(_configured())
            self.assertEqual(health().status_code, 503)


    @patch("dev_control.browser_worker.service.urllib.request.urlopen")
    def test_chrome_liveness_uses_cdp_version_endpoint(self, urlopen):
        response = unittest.mock.MagicMock()
        response.status = 200
        urlopen.return_value.__enter__.return_value = response
        with patch.dict(os.environ, {"BU_CDP_URL": "http://127.0.0.1:9222"}, clear=True):
            self.assertTrue(_chrome_alive())
        self.assertEqual(urlopen.call_args.args[0], "http://127.0.0.1:9222/json/version")

    @patch("dev_control.browser_worker.service.urllib.request.urlopen")
    def test_external_cdp_endpoint_is_rejected_without_network_probe(self, urlopen):
        env = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "https://qa.example.test",
            "QA_ALLOWED_ORIGIN": "https://qa.example.test",
            "QA_ENVIRONMENT": "staging",
            "BU_CDP_URL": "http://10.0.0.5:9222",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(_configured())
            self.assertFalse(_chrome_alive())
            self.assertEqual(health().status_code, 503)
        urlopen.assert_not_called()

    @patch("dev_control.browser_worker.service.urllib.request.urlopen")
    def test_external_cdp_websocket_is_rejected_without_network_probe(self, urlopen):
        env = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "https://qa.example.test",
            "QA_ALLOWED_ORIGIN": "https://qa.example.test",
            "QA_ENVIRONMENT": "staging",
            "BU_CDP_URL": "http://127.0.0.1:9222",
            "BU_CDP_WS": "ws://10.0.0.5:9222/devtools/browser/foreign",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(_configured())
            self.assertFalse(_chrome_alive())
            self.assertEqual(health().status_code, 503)
        urlopen.assert_not_called()

    def test_health_is_503_when_required_configuration_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(health().status_code, 503)


    def test_production_host_trailing_dot_is_denied(self):
        env = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "https://stroyka26.pro.",
            "QA_ENVIRONMENT": "staging",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(_qa_base_is_nonproduction())
            self.assertFalse(_configured())

    def test_non_http_qa_base_is_not_ready(self):
        env = {
            "DEV_CONTROL_API_TOKEN": STRONG_TOKEN,
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "ftp://qa.example.test",
            "QA_ENVIRONMENT": "staging",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(_configured())

    def test_job_ids_reject_path_traversal(self):
        self.assertTrue(_valid_job_id("a" * 32))
        self.assertTrue(_valid_job_id("startup-selftest"))
        self.assertFalse(_valid_job_id(".."))
        self.assertFalse(_valid_job_id("../outside"))


    def test_evidence_replacement_does_not_double_count_existing_result(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "000001.jpg").write_bytes(b"x" * 100)
            (folder / "result.json").write_bytes(b"old" * 1000)
            self.assertEqual(_evidence_non_result_bytes(folder), 100)

    def test_evidence_quota_is_bounded(self):
        with patch.dict(os.environ, {"QA_EVIDENCE_MAX_BYTES": "1"}, clear=True):
            self.assertEqual(_evidence_max_bytes(), 1024 * 1024)
        with patch.dict(os.environ, {"QA_EVIDENCE_MAX_BYTES": str(100 * 1024 * 1024)}, clear=True):
            self.assertEqual(_evidence_max_bytes(), 32 * 1024 * 1024)

    def test_evidence_ttl_is_bounded(self):
        with patch.dict(os.environ, {"QA_EVIDENCE_TTL_SECONDS": "1"}, clear=True):
            self.assertEqual(_evidence_ttl_seconds(), 60)
        with patch.dict(os.environ, {"QA_EVIDENCE_TTL_SECONDS": "999999"}, clear=True):
            self.assertEqual(_evidence_ttl_seconds(), 86400)

    def test_queue_limit_is_small_and_clamped(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_max_pending_jobs(), 2)
        with patch.dict(os.environ, {"QA_MAX_PENDING_JOBS": "999"}, clear=True):
            self.assertEqual(_max_pending_jobs(), 10)
        with patch.dict(os.environ, {"QA_MAX_PENDING_JOBS": "0"}, clear=True):
            self.assertEqual(_max_pending_jobs(), 1)
    def test_startup_selftest_record_survives_eviction_paths(self):
        with _jobs_lock:
            previous = dict(_jobs)
            _jobs.clear()
        try:
            with _jobs_lock:
                _jobs["startup-selftest"] = {"status": "passed", "result": {"ok": True}}
                for index in range(101):
                    _jobs[f"{index:032x}"] = {"status": "passed", "queue_pending": False}
            _set_job("f" * 32, status="passed")
            with _jobs_lock:
                self.assertIn("startup-selftest", _jobs)

            with _jobs_lock:
                _jobs.clear()
                _jobs["startup-selftest"] = {"status": "passed", "result": {"ok": True}}
                for index in range(101):
                    _jobs[f"{index:032x}"] = {"status": "passed", "queue_pending": False}
                _jobs["e" * 32] = {
                    "status": "running",
                    "cancel_requested": False,
                    "queue_pending": False,
                }
            _commit_final_state("e" * 32, {"ok": True, "evidence_files": []})
            with _jobs_lock:
                self.assertIn("startup-selftest", _jobs)
        finally:
            with _jobs_lock:
                _jobs.clear()
                _jobs.update(previous)

    def test_worker_token_requires_64_hex_characters(self):
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "short-secret"}, clear=True):
            self.assertEqual(_worker_api_token(), "")
            self.assertFalse(_configured())
            with self.assertRaises(HTTPException) as caught:
                _authorize("Bearer short-secret")
            self.assertEqual(caught.exception.status_code, 503)

        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": STRONG_TOKEN}, clear=True):
            self.assertEqual(_worker_api_token(), STRONG_TOKEN)

    def test_authorize_uses_strong_bearer_token(self):
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": STRONG_TOKEN}, clear=True):
            _authorize("Bearer " + STRONG_TOKEN)
            with self.assertRaises(HTTPException) as caught:
                _authorize("Bearer " + WRONG_STRONG_TOKEN)
            self.assertEqual(caught.exception.status_code, 401)

    def test_watcher_scoped_token_cannot_authorize_general_jobs(self):
        scoped = _watcher_scoped_token(STRONG_TOKEN)
        self.assertRegex(scoped, r"^[0-9a-f]{64}$")
        self.assertNotEqual(scoped, STRONG_TOKEN)
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": STRONG_TOKEN}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                _authorize("Bearer " + scoped)
            self.assertEqual(caught.exception.status_code, 401)

    def test_watcher_request_signature_is_path_bound_and_replay_protected(self):
        timestamp = "1700000000"
        nonce = "1" * 32
        scoped = _watcher_scoped_token(STRONG_TOKEN)
        signature = _watcher_signature(
            scoped, "GET", "/watcher/health", timestamp, nonce
        )
        with _watcher_nonce_lock:
            previous = dict(_watcher_seen_nonces)
            _watcher_seen_nonces.clear()
        try:
            with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": STRONG_TOKEN}, clear=True), patch(
                "dev_control.browser_worker.service.time.time", return_value=1700000000
            ):
                _authorize_watcher_request(
                    "GET", "/watcher/health", timestamp, nonce, signature
                )
                with self.assertRaises(HTTPException) as replay:
                    _authorize_watcher_request(
                        "GET", "/watcher/health", timestamp, nonce, signature
                    )
                self.assertEqual(replay.exception.status_code, 409)

                tampered_nonce = "2" * 32
                with self.assertRaises(HTTPException) as tampered:
                    _authorize_watcher_request(
                        "GET", "/watcher/jobs/" + "a" * 32,
                        timestamp,
                        tampered_nonce,
                        signature,
                    )
                self.assertEqual(tampered.exception.status_code, 401)
        finally:
            with _watcher_nonce_lock:
                _watcher_seen_nonces.clear()
                _watcher_seen_nonces.update(previous)

    def test_watcher_smoke_request_is_server_fixed_and_read_only(self):
        env = {"QA_BASE_URL": "https://qa.example.test/app", "JEV_WATCH_QA_URL": "https://qa.example.test/app"}
        with patch.dict(os.environ, env, clear=True):
            request = _watcher_smoke_request()
        self.assertTrue(request.read_only)
        self.assertEqual(request.url, "https://qa.example.test/app")
        self.assertEqual(request.expect_text, ["Склад"])
        self.assertEqual(request.expect_url_contains, ["qa.example.test"])
        self.assertEqual(request.issue_number, 311)


if __name__ == "__main__":
    unittest.main()
