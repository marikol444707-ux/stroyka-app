import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from dev_control.jev_timeweb import (
    DEFAULT_MODEL,
    DEFAULT_SYSTEMONE_URL,
    JevError,
    JevTimewebClient,
)


class JevTimewebClientTest(unittest.TestCase):
    def test_from_env_requires_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(JevError, "TIMEWEB_AI_API_KEY"):
                JevTimewebClient.from_env()

    def test_from_env_uses_safe_defaults(self):
        with patch.dict(os.environ, {"TIMEWEB_AI_API_KEY": "secret"}, clear=True):
            client = JevTimewebClient.from_env()
        self.assertEqual(client.endpoint, DEFAULT_SYSTEMONE_URL)
        self.assertEqual(client.model, DEFAULT_MODEL)


    def test_rejects_non_timeweb_systemone_endpoint(self):
        with patch.dict(
            os.environ,
            {"TIMEWEB_AI_API_KEY": "secret", "JEV_SYSTEMONE_URL": "https://attacker.example/systemone"},
            clear=True,
        ):
            with self.assertRaisesRegex(JevError, "exactly the Timeweb"):
                JevTimewebClient.from_env()

    @patch("dev_control.jev_timeweb.urlopen")
    def test_manually_constructed_client_cannot_send_key_to_foreign_endpoint(self, mocked_urlopen):
        client = JevTimewebClient(api_key="secret", endpoint="https://attacker.example/systemone")
        with self.assertRaisesRegex(JevError, "exactly the Timeweb"):
            client.ask(state="test", questions={"q": {"type": "noul", "instructions": "test"}})
        mocked_urlopen.assert_not_called()

    @patch("dev_control.jev_timeweb.urlopen")
    def test_ask_accepts_structured_state_from_real_jev(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps(
            {"answers": {"operation": {"choice": "DONE", "probabilities": {"DONE": 1.0}, "confidence": 1.0}}}
        ).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response

        client = JevTimewebClient(api_key="secret")
        state = {
            "page": {"url": "https://example.test", "title": "Example", "text": "Ready"},
            "elements": [{"index": "1", "label": "Continue", "operations": ["CLICK"]}],
            "recent_actions": [],
        }
        result = client.ask(
            state=state,
            questions={"operation": {"type": "choice", "criteria": {"DONE": "done"}}},
        )

        self.assertIn("answers", result)
        sent = json.loads(mocked_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["state"], state)

    @patch("dev_control.jev_timeweb.urlopen")
    def test_ask_sends_bearer_model_state_and_questions(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps(
            {"answers": {"is_test": ["noul"]}}
        ).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response

        client = JevTimewebClient(api_key="top-secret")
        result = client.ask(
            state="state-value",
            questions={
                "is_test": {
                    "type": "noul",
                    "instructions": "question",
                }
            },
        )

        self.assertIn("answers", result)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, DEFAULT_SYSTEMONE_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer top-secret")

        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["model"], "jev-latest")
        self.assertEqual(sent["state"], "state-value")
        self.assertIn("is_test", sent["questions"])

    @patch("dev_control.jev_timeweb.urlopen")
    def test_ask_does_not_leak_key_in_http_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            DEFAULT_SYSTEMONE_URL,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"invalid api key"}'),
        )

        client = JevTimewebClient(api_key="do-not-print-me")
        with self.assertRaises(JevError) as caught:
            client.ask(
                state="test",
                questions={"q": {"type": "noul", "instructions": "test"}},
            )

        self.assertNotIn("do-not-print-me", str(caught.exception))
        self.assertIn("HTTP 401", str(caught.exception))

    @patch("dev_control.jev_timeweb.urlopen")
    def test_ask_rejects_response_without_answers(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"ok":true}'
        mocked_urlopen.return_value.__enter__.return_value = response

        client = JevTimewebClient(api_key="secret")
        with self.assertRaisesRegex(JevError, "answers"):
            client.ask(
                state="test",
                questions={"q": {"type": "noul", "instructions": "test"}},
            )

    def test_ask_rejects_empty_input_before_network(self):
        client = JevTimewebClient(api_key="secret")
        with self.assertRaisesRegex(JevError, "state"):
            client.ask(
                state=" ",
                questions={"q": {"type": "noul", "instructions": "test"}},
            )
        with self.assertRaisesRegex(JevError, "questions"):
            client.ask(state="test", questions={})


if __name__ == "__main__":
    unittest.main()
