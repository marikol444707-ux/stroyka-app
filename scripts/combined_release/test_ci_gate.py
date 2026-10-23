"""Offline tests only. Every HTTP GET is injected or urllib's opener is mocked."""

import copy
import io
import json
import ssl
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch
import urllib.request

import ci_gate as gate

RUN_ID = 123456
HEAD = "a" * 40
ATTEMPT = 2
RUN_PATH = gate.API_ROOT + "/actions/runs/" + str(RUN_ID)
COMMIT_PATH = gate.API_ROOT + "/git/commits/" + HEAD
JOBS_PREFIX = RUN_PATH + "/attempts/2/jobs?per_page=100&page="
START = "2026-10-22T20:00:00Z"
END = "2026-10-22T20:10:00Z"


def run():
    return {"id": RUN_ID, "event": "push", "head_branch": gate.BRANCH, "path": gate.WORKFLOW_PATH,
            "status": "completed", "conclusion": "success", "run_attempt": ATTEMPT,
            "workflow_id": 100, "head_sha": HEAD,
            "repository": {"full_name": gate.REPOSITORY, "private": False},
            "head_repository": {"full_name": gate.REPOSITORY, "private": False}}


def job(identifier=789, name="build"):
    return {"id": identifier, "run_id": RUN_ID, "run_attempt": ATTEMPT, "head_sha": HEAD,
            "name": name, "status": "completed", "conclusion": "success",
            "started_at": START, "completed_at": END,
            "steps": [{"name": name, "number": i + 1, "status": "completed", "conclusion": "success",
                       "started_at": START, "completed_at": END} for i, name in enumerate(gate.REQUIRED_STEPS)]}


class Evidence:
    def __init__(self):
        self.run = run()
        self.final_run = None
        self.commit = {"sha": HEAD, "tree": {"sha": gate.EXPECTED_TREE}}
        self.jobs = [job()]
        self.calls = []
        self.run_reads = 0
        self.page_override = None

    def get(self, path):
        self.calls.append(path)
        if path == RUN_PATH:
            self.run_reads += 1
            return copy.deepcopy(self.final_run if self.run_reads > 1 and self.final_run is not None else self.run)
        if path == COMMIT_PATH:
            return copy.deepcopy(self.commit)
        if path.startswith(JOBS_PREFIX):
            page = int(path[len(JOBS_PREFIX):])
            if self.page_override:
                return self.page_override(page)
            return {"total_count": len(self.jobs), "jobs": copy.deepcopy(self.jobs[(page - 1) * 100:page * 100])}
        raise AssertionError("Unexpected API path")


class GateEvidenceTests(unittest.TestCase):
    def test_valid_receipt_binds_run_attempt_commit_tree_and_all_required_steps(self):
        evidence = Evidence()
        receipt = gate.verify_ci(RUN_ID, evidence.get)
        self.assertEqual(receipt["run_id"], RUN_ID)
        self.assertEqual(receipt["run_attempt"], 2)
        self.assertEqual(receipt["head_sha"], HEAD)
        self.assertEqual(receipt["tree_sha"], gate.EXPECTED_TREE)
        self.assertEqual(tuple(p["name"] for p in receipt["required_steps"]), gate.REQUIRED_STEPS)
        self.assertEqual(evidence.calls, [RUN_PATH, COMMIT_PATH, JOBS_PREFIX + "1", RUN_PATH])
        self.assertNotIn("token", json.dumps(receipt).lower())

    def test_installer_tree_binding_is_independent_from_application_tree(self):
        evidence=Evidence();installer_tree='c'*40
        evidence.commit['tree']['sha']=installer_tree
        with self.assertRaisesRegex(gate.CIGateError,'ci_source_tree_mismatch'):
            gate.verify_ci(RUN_ID,evidence.get)
        evidence=Evidence();evidence.commit['tree']['sha']=installer_tree
        receipt=gate.verify_ci(RUN_ID,evidence.get,expected_tree=installer_tree)
        self.assertEqual(receipt['tree_sha'],installer_tree)
    def test_run_id_has_no_boolean_string_zero_or_negative_bypass(self):
        for value in (None, True, False, 0, -1, "123456", 1.5, 2**63):
            fetch = Mock()
            with self.subTest(value=value), self.assertRaisesRegex(gate.CIGateError, "ci_run_id_required"):
                gate.verify_ci(value, fetch)
            fetch.assert_not_called()

    def test_exact_documented_branch_qualified_workflow_path_is_accepted(self):
        evidence = Evidence()
        evidence.run["path"] = gate.WORKFLOW_PATH + "@" + gate.BRANCH
        receipt = gate.verify_ci(RUN_ID, evidence.get)
        self.assertEqual(receipt["workflow_path"], gate.WORKFLOW_PATH)
        self.assertEqual(receipt["branch"], gate.BRANCH)
        self.assertEqual(evidence.calls, [RUN_PATH, COMMIT_PATH, JOBS_PREFIX + "1", RUN_PATH])

    def test_workflow_path_rejects_other_refs_suffixes_and_non_strings(self):
        for path in (gate.WORKFLOW_PATH + "@main", gate.WORKFLOW_PATH + "@" + HEAD,
                     gate.WORKFLOW_PATH + "@refs/heads/" + gate.BRANCH,
                     gate.WORKFLOW_PATH + "@" + gate.BRANCH + "/other",
                     gate.WORKFLOW_PATH + "@" + gate.BRANCH + "@main",
                     gate.WORKFLOW_PATH + "?ref=" + gate.BRANCH,
                     ".github/workflows/other.yml@" + gate.BRANCH,
                     gate.WORKFLOW_PATH + "@" + gate.BRANCH + "\n", None, [], {}):
            evidence = Evidence()
            evidence.run["path"] = path
            with self.subTest(path=path), self.assertRaisesRegex(gate.CIGateError, "ci_run_not_eligible"):
                gate.verify_ci(RUN_ID, evidence.get)
            self.assertEqual(evidence.calls, [RUN_PATH])

    def test_documented_jobs_without_run_attempt_remain_bound_to_attempt_endpoint(self):
        evidence = Evidence()
        del evidence.jobs[0]["run_attempt"]
        evidence.run["path"] += "@" + gate.BRANCH
        receipt = gate.verify_ci(RUN_ID, evidence.get)
        self.assertEqual(receipt["run_attempt"], ATTEMPT)
        self.assertEqual(receipt["head_sha"], HEAD)
        self.assertEqual(evidence.calls, [RUN_PATH, COMMIT_PATH, JOBS_PREFIX + "1", RUN_PATH])

    def test_supplied_job_attempt_is_never_ignored_or_coerced(self):
        for value in (None, False, True, 0, -1, 1, 3, "2", 2.0, [], {}):
            evidence = Evidence()
            evidence.jobs[0]["run_attempt"] = value
            with self.subTest(value=value), self.assertRaisesRegex(gate.CIGateError, "ci_job_identity_mismatch"):
                gate.verify_ci(RUN_ID, evidence.get)

    def test_missing_job_attempt_does_not_relax_other_identity_or_rerun_checks(self):
        for field, value in (("id", None), ("run_id", None), ("run_id", 1),
                             ("head_sha", None), ("head_sha", "b" * 40)):
            evidence = Evidence()
            del evidence.jobs[0]["run_attempt"]
            evidence.jobs[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(gate.CIGateError, "ci_job_identity_mismatch"):
                gate.verify_ci(RUN_ID, evidence.get)
        evidence = Evidence()
        del evidence.jobs[0]["run_attempt"]
        evidence.final_run = {**evidence.run, "run_attempt": ATTEMPT + 1}
        with self.assertRaisesRegex(gate.CIGateError, "ci_run_changed_during_verification"):
            gate.verify_ci(RUN_ID, evidence.get)

    def test_final_run_recheck_still_rejects_wrong_workflow_ref(self):
        evidence = Evidence()
        evidence.run["path"] += "@" + gate.BRANCH
        evidence.final_run = {**evidence.run, "path": gate.WORKFLOW_PATH + "@main"}
        with self.assertRaisesRegex(gate.CIGateError, "ci_run_not_eligible"):
            gate.verify_ci(RUN_ID, evidence.get)

    def test_rejects_wrong_run_branch_event_workflow_status_and_repo(self):
        mutations = [("id", 2), ("id", True), ("event", "pull_request"), ("event", "workflow_dispatch"),
                     ("head_branch", "main"), ("path", ".github/workflows/other.yml"),
                     ("status", "in_progress"), ("conclusion", "skipped"), ("conclusion", "failure"),
                     ("conclusion", "cancelled"), ("run_attempt", True), ("workflow_id", 0),
                     ("head_sha", "../../private"),
                     ("repository", {"full_name": "other/repo", "private": False}),
                     ("repository", {"full_name": gate.REPOSITORY, "private": True}),
                     ("head_repository", {"full_name": "fork/repo", "private": False})]
        for field, value in mutations:
            evidence = Evidence()
            evidence.run[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(gate.CIGateError):
                gate.verify_ci(RUN_ID, evidence.get)
            self.assertEqual(evidence.calls, [RUN_PATH])

    def test_commit_requires_exact_source_tree_and_commit_identity(self):
        for commit in ({}, {"sha": "b" * 40, "tree": {"sha": gate.EXPECTED_TREE}},
                       {"sha": HEAD, "tree": {"sha": "2224" + "0" * 36}}, {"sha": HEAD, "tree": None}):
            evidence = Evidence()
            evidence.commit = commit
            with self.assertRaisesRegex(gate.CIGateError, "ci_source_tree_mismatch"):
                gate.verify_ci(RUN_ID, evidence.get)

    def test_jobs_bound_to_exact_run_attempt_sha_and_success(self):
        for field, value in (("run_id", 2), ("run_attempt", 1), ("run_attempt", True), ("head_sha", "b" * 40),
                             ("status", "queued"), ("conclusion", "skipped"), ("name", "test-only"),
                             ("started_at", None), ("completed_at", "2026-10-22T19:00:00Z")):
            evidence = Evidence()
            evidence.jobs[0][field] = value
            with self.subTest(field=field), self.assertRaises(gate.CIGateError):
                gate.verify_ci(RUN_ID, evidence.get)

    def test_every_pg_concurrency_and_build_step_must_really_succeed(self):
        for index in range(len(gate.REQUIRED_STEPS)):
            for status, conclusion in (("completed", "skipped"), ("completed", "cancelled"), ("completed", "failure"), ("in_progress", None)):
                evidence = Evidence()
                evidence.jobs[0]["steps"][index].update(status=status, conclusion=conclusion)
                with self.subTest(name=gate.REQUIRED_STEPS[index], conclusion=conclusion), self.assertRaises(gate.CIGateError):
                    gate.verify_ci(RUN_ID, evidence.get)

    def test_missing_duplicated_or_unexecuted_steps_fail_closed(self):
        for mutation in (lambda s: s.pop(), lambda s: s.append({**s[0], "number": 500}),
                         lambda s: s[0].update(number=s[1]["number"]),
                         lambda s: s[0].update(started_at=None),
                         lambda s: s[0].update(completed_at="not-a-time")):
            evidence = Evidence()
            mutation(evidence.jobs[0]["steps"])
            with self.assertRaises(gate.CIGateError):
                gate.verify_ci(RUN_ID, evidence.get)

    def test_attempt_jobs_are_paginated_without_following_api_urls(self):
        evidence = Evidence()
        evidence.jobs += [job(i, "other") for i in range(1000, 1100)]
        evidence.jobs[-1]["url"] = "http://internal.invalid/private?token=secret"
        receipt = gate.verify_ci(RUN_ID, evidence.get)
        self.assertEqual(receipt["build_job_id"], 789)
        self.assertIn(JOBS_PREFIX + "2", evidence.calls)
        self.assertEqual(len(evidence.calls), 5)

    def test_missing_pages_inconsistent_counts_and_duplicate_jobs_rejected(self):
        for mode in ("missing", "changed", "duplicate", "too_many", "no_jobs"):
            evidence = Evidence()
            if mode == "duplicate":
                evidence.jobs.append(job())
            elif mode == "no_jobs":
                evidence.jobs = []
            elif mode == "too_many":
                evidence.page_override = lambda page: {"total_count": 1001, "jobs": []}
            else:
                evidence.page_override = lambda page, mode=mode: {
                    "total_count": 101 if page == 1 or mode == "missing" else 102,
                    "jobs": [job(i, "other") for i in range(100)] if page == 1 else [],
                }
            with self.subTest(mode=mode), self.assertRaises(gate.CIGateError):
                gate.verify_ci(RUN_ID, evidence.get)

    def test_two_build_jobs_are_ambiguous(self):
        evidence = Evidence()
        evidence.jobs.append(job(790))
        with self.assertRaisesRegex(gate.CIGateError, "ci_build_job_missing_or_ambiguous"):
            gate.verify_ci(RUN_ID, evidence.get)

    def test_concurrent_rerun_invalidates_receipt(self):
        evidence = Evidence()
        evidence.final_run = {**evidence.run, "run_attempt": 3}
        with self.assertRaisesRegex(gate.CIGateError, "ci_run_changed_during_verification"):
            gate.verify_ci(RUN_ID, evidence.get)

    def test_api_unavailable_does_not_allow_cached_or_manual_evidence(self):
        with self.assertRaisesRegex(gate.CIGateError, "^ci_api_unavailable$"):
            gate.verify_ci(RUN_ID, Mock(side_effect=OSError("sensitive-url?token=secret")))
        with self.assertRaisesRegex(gate.CIGateError, "ci_api_invalid_evidence"):
            gate.verify_ci(RUN_ID, Mock(return_value=True))


class SafeTransportTests(unittest.TestCase):
    def response(self, body=b'{}', content_type="application/json"):
        response = Mock()
        response.getcode.return_value = 200
        response.geturl.return_value = gate.API_ORIGIN + RUN_PATH
        response.headers = {"Content-Type": content_type}
        response.read.return_value = body
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_safe_https_request_uses_system_proxy_without_credentials_or_redirects(self):
        response = self.response()
        opener = Mock()
        opener.open.return_value = response
        with patch.object(gate.urllib.request, "build_opener", return_value=opener) as factory:
            self.assertEqual(gate.defaultsafeGET(RUN_PATH), {})
        handlers = factory.call_args.args
        proxy = next(h for h in handlers if isinstance(h, urllib.request.ProxyHandler))
        https = next(h for h in handlers if isinstance(h, urllib.request.HTTPSHandler))
        self.assertEqual(proxy.proxies, urllib.request.getproxies())
        self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(https._context.check_hostname)
        self.assertTrue(any(isinstance(h, gate._NoRedirect) for h in handlers))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, gate.API_ORIGIN + RUN_PATH)
        self.assertIsNone(request.get_header("Authorization"))
        self.assertIsNone(request.get_header("Cookie"))
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], gate.TIMEOUT_SECONDS)
        response.read.assert_called_once_with(gate.MAX_RESPONSE_BYTES + 1)

    def test_no_arbitrary_hosts_paths_redirects_or_queries(self):
        for path in ("https://api.github.com" + RUN_PATH, "//internal", "/repos/other/repo/actions/runs/1",
                     RUN_PATH + "?token=secret", RUN_PATH + "/../../secrets", RUN_PATH + "\nAuthorization: bad"):
            with patch.object(gate.urllib.request, "build_opener") as opener:
                with self.assertRaisesRegex(gate.CIGateError, "ci_api_path_refused"):
                    gate.defaultsafeGET(path)
                opener.assert_not_called()
        with self.assertRaisesRegex(gate.CIGateError, "ci_api_redirect_refused"):
            gate._NoRedirect().redirect_request(None, None, 302, "", {}, "http://internal.invalid")

    def test_http_failures_malformed_duplicate_oversize_and_redirected_bodies_fail_closed(self):
        cases = [self.response(b'[]'), self.response(b'{"id":1,"id":2}'), self.response(b'invalid'),
                 self.response(b'{}', "text/html"), self.response(b'x' * (gate.MAX_RESPONSE_BYTES + 1))]
        redirected = self.response()
        redirected.geturl.return_value = "https://other.invalid"
        cases.append(redirected)
        for response in cases:
            with patch.object(gate.urllib.request, "build_opener") as factory:
                factory.return_value.open.return_value = response
                with self.assertRaises(gate.CIGateError):
                    gate.defaultsafeGET(RUN_PATH)
        with patch.object(gate.urllib.request, "build_opener", side_effect=OSError("token=secret")):
            with self.assertRaisesRegex(gate.CIGateError, "^ci_api_unavailable$"):
                gate.defaultsafeGET(RUN_PATH)

    def test_cli_requires_run_id_has_no_skip_flag_and_sanitizes_gate_failure(self):
        for args in ([], ["--skip-ci"], ["--run-id", "not-an-id"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                gate.main(args)
        error = io.StringIO()
        with redirect_stderr(error), patch.object(gate, "verify_ci", side_effect=gate.CIGateError("ci_api_unavailable")):
            self.assertEqual(gate.main(["--run-id", str(RUN_ID)]), 2)
        self.assertEqual(error.getvalue(), "ci_api_unavailable\n")
        out = io.StringIO()
        with redirect_stdout(out), patch.object(gate, "verify_ci", return_value={"run_id": RUN_ID}):
            self.assertEqual(gate.main(["--run-id", str(RUN_ID)]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"run_id": RUN_ID})


if __name__ == "__main__":
    unittest.main()
