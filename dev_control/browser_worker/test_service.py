import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from dev_control.browser_worker.service import _authorize, _configured


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

    def test_authorize_uses_bearer_token(self):
        with patch.dict(os.environ, {"DEV_CONTROL_API_TOKEN": "expected"}, clear=True):
            _authorize("Bearer expected")
            with self.assertRaises(HTTPException) as caught:
                _authorize("Bearer wrong")
            self.assertEqual(caught.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
