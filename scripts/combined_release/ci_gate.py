#!/usr/bin/env python3
"""Fail-closed, live public GitHub CI evidence for one immutable prepared tree.

No credentials, arbitrary URLs, cached/manual approvals, or deployment actions.
A successful receipt proves GitHub job/step conclusions for the pinned workflow
source; it is not a claim that individual test reports were parsed. The caller
must bind this module and receipt to its verified installation package.
"""

import argparse
from datetime import datetime, timezone
import json
import re
import ssl
import sys
import urllib.error
import urllib.request

REPOSITORY = "marikol444707-ux/stroyka-app"
BRANCH = "review/combined-supplier-invoice-assistant-20261022"
WORKFLOW_PATH = ".github/workflows/ci.yml"
# GitHub's Get a workflow run example uses a branch-qualified path (...@main).
# Accept only the pinned workflow, optionally qualified by our exact branch;
# do not strip arbitrary suffixes or accept another ref/workflow.
_WORKFLOW_RUN_PATHS = (WORKFLOW_PATH, WORKFLOW_PATH + "@" + BRANCH)
EXPECTED_TREE = "3f32f08e3a287953e12777b2b55360d653c5a937"
API_ORIGIN = "https://api.github.com"
API_ROOT = "/repos/" + REPOSITORY
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_JOBS = 1000
PAGE_SIZE = 100
TIMEOUT_SECONDS = 15

# Exact names from the pinned ci.yml. In particular, the PG/concurrency runner
# steps cannot be replaced by only the broad unittest discovery (which can skip
# opt-in database suites). Setup, compile, frontend, and installer checks are also
# mandatory; successful run/job conclusions alone are insufficient.
REQUIRED_STEPS = (
    "Checkout",
    "Set up Python",
    "Install Python dependencies",
    "Install document sandbox dependencies",
    "Compile backend",
    "Run backend tests",
    "Verify unified release transport and frontend backup",
    "Run supplier installer safety tests",
    "Run company-context PostgreSQL isolation tests",
    "Run acceptance-to-act PostgreSQL chain",
    "Run supplier quote and staff access PostgreSQL checks",
    "Run supplier access correction and packaging merge guards",
    "Run supplier notification delivery and requester boundaries",
    "Run supplier document and supply history company boundaries",
    "Run supplier manager assignments and revocation",
    "Run contractor identity audit and exact selection",
    "Set up Node",
    "Install frontend dependencies",
    "Run frontend tests",
    "Build frontend",
)

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_API_PATH = re.compile(
    re.escape(API_ROOT) + r"(?:/actions/runs/[1-9][0-9]{0,18}"
    r"(?:/attempts/[1-9][0-9]{0,18}/jobs\?per_page=100&page=[1-9][0-9]{0,2})?"
    r"|/git/commits/[0-9a-f]{40})\Z"
)


class CIGateError(RuntimeError):
    """Fixed, non-sensitive denial; callers must not continue installation."""


def _deny(code):
    raise CIGateError(code) from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _deny("ci_api_redirect_refused")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _deny("ci_api_invalid_json")
        value[key] = item
    return value


def defaultsafeGET(path):
    """GET a whitelisted relative API path using TLS, with no credentials.

    ProxyHandler() preserves the managed network proxy; redirects are
    denied, and API-provided URLs/Link headers are never followed. There is no
    environment-token, cookie, .netrc, insecure-TLS, or override-base-url option.
    """
    if type(path) is not str or not _API_PATH.fullmatch(path):
        _deny("ci_api_path_refused")
    url = API_ORIGIN + path
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stroyka-immutable-ci-gate/1",
    }, method="GET")
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            _NoRedirect(),
        )
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.getcode() != 200 or response.geturl() != url:
                _deny("ci_api_response_refused")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"application/json", "application/vnd.github+json"}:
                _deny("ci_api_invalid_json")
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            _deny("ci_api_response_too_large")
        result = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except CIGateError:
        raise
    except Exception:
        # Never echo response bodies, redirect targets, URLs, headers or keys.
        _deny("ci_api_unavailable")
    if type(result) is not dict:
        _deny("ci_api_invalid_json")
    return result


def _positive_int(value):
    return type(value) is int and 0 < value <= 9223372036854775807


def _get(fetch_json, path):
    try:
        result = fetch_json(path)
    except CIGateError:
        raise
    except Exception:
        _deny("ci_api_unavailable")
    if type(result) is not dict:
        _deny("ci_api_invalid_evidence")
    return result


def _run_identity(run, run_id):
    if (
        run.get("id") != run_id or type(run.get("id")) is not int
        or run.get("event") != "push"
        or run.get("head_branch") != BRANCH
        or run.get("path") not in _WORKFLOW_RUN_PATHS
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or not _positive_int(run.get("run_attempt"))
        or not _positive_int(run.get("workflow_id"))
        or type(run.get("head_sha")) is not str
        or not _SHA.fullmatch(run["head_sha"])
    ):
        _deny("ci_run_not_eligible")
    for key in ("repository", "head_repository"):
        repo = run.get(key)
        if type(repo) is not dict or repo.get("full_name") != REPOSITORY or repo.get("private") is not False:
            _deny("ci_repository_mismatch")
    return (run["id"], run["run_attempt"], run["workflow_id"], run["head_sha"])


def _timestamp(value):
    if type(value) is not str or len(value) > 40:
        _deny("ci_execution_time_missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            _deny("ci_execution_time_missing")
        return stamp
    except (ValueError, OverflowError):
        _deny("ci_execution_time_missing")


def _successful_execution(record):
    if record.get("status") != "completed" or record.get("conclusion") != "success":
        _deny("ci_required_execution_not_successful")
    if _timestamp(record.get("completed_at")) < _timestamp(record.get("started_at")):
        _deny("ci_execution_time_invalid")


def _jobs(fetch_json, run_id, attempt):
    jobs = []
    total = None
    for page in range(1, MAX_JOBS // PAGE_SIZE + 1):
        payload = _get(fetch_json, API_ROOT + "/actions/runs/" + str(run_id)
                       + "/attempts/" + str(attempt) + "/jobs?per_page=100&page=" + str(page))
        count = payload.get("total_count")
        if type(count) is not int or not 1 <= count <= MAX_JOBS or (total is not None and count != total):
            _deny("ci_jobs_incomplete")
        total = count
        batch = payload.get("jobs")
        if type(batch) is not list or len(batch) != min(PAGE_SIZE, total - len(jobs)):
            _deny("ci_jobs_incomplete")
        if any(type(job) is not dict for job in batch):
            _deny("ci_jobs_invalid")
        jobs.extend(batch)
        if len(jobs) == total:
            return jobs
    _deny("ci_jobs_incomplete")


def verify_ci(run_id, fetch_json=defaultsafeGET, *, expected_tree=EXPECTED_TREE):
    """Return live immutable evidence or raise CIGateError; never accept a flag.

    fetch_json is dependency injection for offline tests, not a CLI bypass. The
    installer must call without overriding it. No approval receipt is read here.
    """
    if not _positive_int(run_id):
        _deny("ci_run_id_required")
    run_path = API_ROOT + "/actions/runs/" + str(run_id)
    identity = _run_identity(_get(fetch_json, run_path), run_id)
    _, attempt, workflow_id, head_sha = identity
    commit = _get(fetch_json, API_ROOT + "/git/commits/" + head_sha)
    tree = commit.get("tree")
    if commit.get("sha") != head_sha or type(tree) is not dict or tree.get("sha") != expected_tree:
        _deny("ci_source_tree_mismatch")

    jobs = _jobs(fetch_json, run_id, attempt)
    seen_ids = set()
    builds = []
    for job in jobs:
        if (not _positive_int(job.get("id")) or job["id"] in seen_ids
            or type(job.get("run_id")) is not int or job["run_id"] != run_id
            # The attempt-specific endpoint binds every returned job to attempt.
            # The documented response omits run_attempt; if supplied, it must
            # corroborate that binding, never contradict it or be coerced.
            or ("run_attempt" in job and
                (type(job["run_attempt"]) is not int or job["run_attempt"] != attempt))
            or job.get("head_sha") != head_sha):
            _deny("ci_job_identity_mismatch")
        seen_ids.add(job["id"])
        _successful_execution(job)
        if job.get("name") == "build":
            builds.append(job)
    if len(builds) != 1:
        _deny("ci_build_job_missing_or_ambiguous")
    build = builds[0]
    steps = build.get("steps")
    if type(steps) is not list or not 1 <= len(steps) <= 200 or any(type(step) is not dict for step in steps):
        _deny("ci_required_steps_missing")
    numbers = set()
    for step in steps:
        if not _positive_int(step.get("number")) or step["number"] in numbers:
            _deny("ci_step_identity_invalid")
        numbers.add(step["number"])
    proof = []
    for name in REQUIRED_STEPS:
        matching = [step for step in steps if step.get("name") == name]
        if len(matching) != 1:
            _deny("ci_required_steps_missing")
        _successful_execution(matching[0])
        proof.append({"name": name, "number": matching[0]["number"], "conclusion": "success"})

    # A run id is reused on rerun; pin the attempt and reject a concurrent rerun.
    if _run_identity(_get(fetch_json, run_path), run_id) != identity:
        _deny("ci_run_changed_during_verification")
    return {
        "schema_version": 1,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "workflow_path": WORKFLOW_PATH,
        "workflow_id": workflow_id,
        "run_id": run_id,
        "run_attempt": attempt,
        "event": "push",
        "head_sha": head_sha,
        "tree_sha": expected_tree,
        "build_job_id": build["id"],
        "conclusion": "success",
        "required_steps": proof,
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify live, pinned public CI before installation; fail closed when pending.")
    parser.add_argument("--run-id", required=True, type=int, help="positive GitHub Actions run id; no manual bypass")
    args = parser.parse_args(argv)
    try:
        receipt = verify_ci(args.run_id)
    except CIGateError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
