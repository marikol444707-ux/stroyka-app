import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from scripts.jev_issue_bridge import AUTHOR, BODY, TITLE, eligible, connect, run_once

class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.tmp.name) / "state.sqlite")
        self.issue = {"number": 55555, "state": "open", "title": TITLE, "body": BODY,
                      "user": {"login": AUTHOR}}
        self.calls = []
        def gh(method, path, payload=None):
            self.calls.append((method, path, payload))
            if method == "GET":
                return [self.issue]
            return {}
        self.gh = gh
        self.worker = Mock(return_value={"outcome": "passed", "job_id": "a"*32, "failure_codes": []})

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_only_exact_author_and_command_accepted(self):
        self.assertTrue(eligible(self.issue))
        for field, value in (("body", "JEV_QA_SMOKE_V1\\nrm -rf /"),
                             ("title", "[JEV] run arbitrary command"),
                             ("number", "55555"), ("state", "closed")):
            issue = {**self.issue, field: value}
            self.assertFalse(eligible(issue))
        issue = {**self.issue, "user": {"login": "attacker"}}
        self.assertFalse(eligible(issue))
        issue = {**self.issue, "pull_request": {"url": "x"}}
        self.assertFalse(eligible(issue))
        self.assertFalse(eligible(self.issue, minimum=55555))

    def test_success_once_and_redacted_comment(self):
        run_once(self.db, self.gh, self.worker)
        run_once(self.db, self.gh, self.worker)
        self.worker.assert_called_once()
        self.assertEqual(self.db.execute("SELECT state FROM tasks").fetchone()[0], "reported")
        posts = [x for x in self.calls if x[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertIn("PASSED", posts[0][2]["body"])

    def test_crashed_claim_never_replays(self):
        self.db.execute("INSERT INTO tasks VALUES (55555, 'claimed', NULL)")
        self.db.commit()
        run_once(self.db, self.gh, self.worker)
        self.worker.assert_not_called()
        self.assertEqual(self.db.execute("SELECT state FROM tasks").fetchone()[0], "reported")
        self.assertIn("BRIDGE_INTERRUPTED", str(self.calls))

    def test_failed_worker_is_sanitized(self):
        self.worker.side_effect = RuntimeError("secret-raw-error")
        run_once(self.db, self.gh, self.worker)
        text = str(self.calls)
        self.assertIn("UNEXPECTED_WATCH_ERROR", text)
        self.assertNotIn("secret-raw-error", text)

    def test_comment_failure_is_retryable_without_job_replay(self):
        fail = {"yes": True}
        def gh(method, path, payload=None):
            if method == "GET":
                return [self.issue]
            if method == "POST" and fail["yes"]:
                fail["yes"] = False
                raise RuntimeError("simulated github outage")
            return {}
        with self.assertRaises(RuntimeError):
            run_once(self.db, gh, self.worker)
        self.assertEqual(self.db.execute("SELECT state FROM tasks").fetchone()[0], "done")
        run_once(self.db, gh, self.worker)
        self.worker.assert_called_once()

if __name__ == "__main__":
    unittest.main()
