import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from scripts import jev_commercial_search_and_import as workflow


def report_with_candidate():
    return {
        "region": "Ставропольский край",
        "sources": [{"name": "B2B-Center", "ok": True}],
        "confirmed": [{"source": "B2B-Center", "id": "lot-7",
                        "url": "https://example.org/lot-7", "title": "Ремонт кровли"}],
        "review": [],
        "excluded": {},
    }


class JevCommercialSearchAndImportTests(unittest.TestCase):
    def test_search_uses_fixed_ssh_command_and_parses_report(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stdout=json.dumps(report_with_candidate()))

        result = workflow.run_search(runner=runner)
        self.assertEqual(result["confirmed"][0]["id"], "lot-7")
        self.assertEqual(calls[0][0], workflow.SSH_COMMAND)
        self.assertEqual(calls[0][1]["timeout"], 260)
        self.assertNotIn("shell", calls[0][1])

    def test_search_accepts_partial_report_with_candidate_on_nonzero_exit(self):
        def runner(*args, **kwargs):
            return SimpleNamespace(returncode=1, stdout=json.dumps(report_with_candidate()))

        self.assertEqual(len(workflow.run_search(runner=runner)["confirmed"]), 1)

    def test_search_rejects_invalid_or_empty_failure_report(self):
        for stdout in ("not json", json.dumps({"sources": [], "confirmed": [], "review": []})):
            with self.subTest(stdout=stdout):
                with self.assertRaises(ValueError):
                    workflow.run_search(runner=lambda *a, **k: SimpleNamespace(returncode=1, stdout=stdout))

    def test_keychain_lookup_does_not_put_secret_in_command_arguments(self):
        secret = "k" * 40
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout=secret)

        with patch.object(workflow.sys, "platform", "darwin"):
            result = workflow.integration_key({}, runner=runner)
        self.assertEqual(result, secret)
        self.assertEqual(calls, [["security", "find-generic-password", "-w", "-s",
                                  workflow.KEYCHAIN_SERVICE, "-a", workflow.KEYCHAIN_ACCOUNT]])
        self.assertNotIn(secret, calls[0])

    def test_push_posts_report_to_configured_endpoint_and_reports_count(self):
        observed = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                observed["read_limit"] = limit
                return b'{"ok":true,"created":1}'

        def opener(request, timeout):
            observed.update(url=request.full_url, timeout=timeout,
                            body=json.loads(request.data), key=request.get_header("X-jev-ingest-key"))
            return Response()

        result = workflow.push_report(report_with_candidate(), api_url="https://stroyka26.pro",
                                      ingest_key="x" * 40, opener=opener)
        self.assertEqual(result, {"sent": 1, "result": {"ok": True, "created": 1}})
        self.assertEqual(observed["url"], "https://stroyka26.pro/api/internal/jev/job-candidates")
        self.assertEqual(observed["timeout"], 20)
        self.assertEqual(observed["key"], "x" * 40)
        self.assertEqual(observed["read_limit"], 64 * 1024)

    def test_main_runs_search_then_imports_and_never_prints_key(self):
        secret = "z" * 40
        events = []

        def runner(command, **kwargs):
            events.append("search")
            return SimpleNamespace(returncode=0, stdout=json.dumps(report_with_candidate()))

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return b'{"ok":true,"created":1}'

        def opener(request, timeout):
            events.append("push")
            self.assertEqual(request.get_header("X-jev-ingest-key"), secret)
            return Response()

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = workflow.main(runner=runner, opener=opener,
                                      environ={"JEV_OPPORTUNITY_INGEST_KEY": secret})
        self.assertEqual(exit_code, 0)
        self.assertEqual(events, ["search", "push"])
        self.assertNotIn(secret, stdout.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sent"], 1)

    def test_main_fails_cleanly_without_key_or_api_response(self):
        stdout = io.StringIO()
        events = []
        with patch.object(workflow.sys, "platform", "linux"), redirect_stdout(stdout):
            exit_code = workflow.main(
                runner=lambda *a, **k: events.append("search"),
                environ={},
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(events, [])
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": False, "error": "missing_integration_key"})


if __name__ == "__main__":
    unittest.main()
