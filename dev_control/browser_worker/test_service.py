import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from dev_control.browser_worker.service import _authorize, _configured, _max_pending_jobs, _startup_selftest_enabled


class BrowserWorkerServiceConfigTest(unittest.TestCase):
    def test_configured_requires_test_environment_and_secrets(self):
        good = {
            "DEV_CONTROL_API_TOKEN": "api-secret",
            "TIMEWEB_AI_API_KEY": "ai-secret",
            "QA_BASE_URL": "https://qa.example.test",
            "QA_ENVIRONMENT": "staging",
        }
        with patch.dict(os.environ, good, clear=True):
            self.assertTrue(_configured())

        bad = dict(good, QA_ENVIRONMENT="production")
        with patch.dict(os.environ, bad, clear=True):
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

    def test_queue_limit_is_small_and_clamped(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_max_pending_jobs(), 2)
        with patch.dict(os.environ, {"QA_MAX_PENDING_JOBS": "999"}, clear=True):
            self.assertEqual(_max_pending_jobs(), 10)
        with patch.dict(os.environ, {"QA_MAX_PENDING_JOBS": "0"}, clear=True):
            self.assertEqual(_max_pending_jobs(), 1)
    def test_authorize_uses_bearer_token(self):
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "expected"}, clear=True):
            _authorize("Bearer expected")
            with self.assertRaises(HTTPException) as caught:
                _authorize("Bearer wrong")
            self.assertEqual(caught.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
