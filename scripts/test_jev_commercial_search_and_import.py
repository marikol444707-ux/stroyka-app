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
        self.assertEqual(calls[0][1]["timeout"], 320)
        self.assertNotIn("shell", calls[0][1])

    def test_search_accepts_partial_report_with_candidate_on_nonzero_exit(self):
        def runner(*args, **kwargs):
            return SimpleNamespace(returncode=1, stdout=json.dumps(report_with_candidate()))

        self.assertEqual(len(workflow.run_search(runner=runner)["confirmed"]), 1)

    def test_search_keeps_empty_report_when_source_statuses_are_available(self):
        report = {"confirmed": [], "review": [], "government_review": [], "sources": [
            {"provider": "B2B-Center", "query": "ремонт", "ok": False,
             "status": "source_unavailable", "rows": 0},
        ]}
        runner = lambda *a, **k: SimpleNamespace(returncode=1, stdout=json.dumps(report))

        self.assertEqual(workflow.run_search(runner=runner)["sources"][0]["ok"], False)

    def test_profile_search_sends_json_over_stdin_and_checks_company_identity(self):
        profile = {"companyId": 8, "region": "Ставропольский край", "searchTerms": ["школа"],
                   "sourceProviders": ["B2B-Center"]}
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            report = report_with_candidate()
            report["companyId"] = 8
            return SimpleNamespace(returncode=0, stdout=json.dumps(report))

        self.assertEqual(workflow.run_search(profile, runner=runner)["companyId"], 8)
        self.assertEqual(calls[0][0], workflow.SSH_PROFILE_COMMAND)
        self.assertEqual(json.loads(calls[0][1]["input"]), profile)
        self.assertNotIn("shell", calls[0][1])

        with self.assertRaisesRegex(ValueError, "jev_search_profile_mismatch"):
            workflow.run_search({**profile, "companyId": 9}, runner=runner)

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
            def __init__(self, body=b'{"ok":true,"created":1}'):
                self.body = body
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                observed["read_limit"] = limit
                return self.body

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

    def test_push_scopes_report_to_requested_company(self):
        observed = {}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b'{"ok":true}'

        def opener(request, timeout):
            observed.update(body=json.loads(request.data), timeout=timeout)
            return Response()

        workflow.push_report(report_with_candidate(), api_url="https://stroyka26.pro",
                             ingest_key="x" * 40, target_company_id=8, opener=opener)
        self.assertEqual(observed["body"]["targetCompanyId"], 8)

    def test_fetch_targets_uses_authenticated_get_and_validates_profiles(self):
        profile = {"companyId": 8, "region": "Ставропольский край", "searchTerms": ["школа"],
                   "sourceProviders": ["B2B-Center"]}
        observed = {}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps({"targets": [profile]}).encode()

        def opener(request, timeout):
            observed.update(method=request.method, url=request.full_url, timeout=timeout,
                            key=request.get_header("X-jev-ingest-key"))
            return Response()

        targets = workflow.fetch_search_targets(api_url="https://stroyka26.pro", ingest_key="x" * 40,
                                                opener=opener)
        self.assertEqual(targets, [profile])
        self.assertEqual(observed, {"method": "GET", "url": "https://stroyka26.pro/api/internal/jev/job-candidates",
                                    "timeout": 20, "key": "x" * 40})

    def test_main_runs_search_then_imports_and_never_prints_key(self):
        secret = "z" * 40
        events = []
        profile = {"companyId": 8, "region": "Ставропольский край", "searchTerms": ["школа"],
                   "sourceProviders": ["B2B-Center"]}

        def runner(command, **kwargs):
            events.append("search")
            report = report_with_candidate()
            report["companyId"] = 8
            return SimpleNamespace(returncode=0, stdout=json.dumps(report))

        class Response:
            def __init__(self, body=b'{"ok":true,"created":1}'):
                self.body = body
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return self.body

        def opener(request, timeout):
            events.append(request.method)
            self.assertEqual(request.get_header("X-jev-ingest-key"), secret)
            if request.method == "GET":
                return Response(json.dumps({"targets": [profile]}).encode())
            self.assertEqual(json.loads(request.data)["targetCompanyId"], 8)
            return Response()

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = workflow.main(runner=runner, opener=opener,
                                      environ={"JEV_OPPORTUNITY_INGEST_KEY": secret})
        self.assertEqual(exit_code, 0)
        self.assertEqual(events, ["GET", "search", "POST"])
        self.assertNotIn(secret, stdout.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["companiesProcessed"], 1)
        self.assertEqual(payload["results"][0]["sent"], 1)

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

    def test_main_rejects_short_key_before_running_search(self):
        stdout = io.StringIO()
        events = []
        with redirect_stdout(stdout):
            exit_code = workflow.main(
                runner=lambda *a, **k: events.append("search"),
                environ={"JEV_OPPORTUNITY_INGEST_KEY": "short"},
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(events, [])
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": False, "error": "invalid_integration_key"})


if __name__ == "__main__":
    unittest.main()
