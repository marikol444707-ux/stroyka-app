#!/usr/bin/env python3
"""Run one unattended, non-mutating JEVA smoke check against isolated Stroyka QA.

The watcher never connects to production, handles no QA session cookie itself,
and never executes shell commands. Only the local QA worker may open Chrome.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

QA_URL = "https://stroyka-qa-gateway/app"
QA_HOST = "stroyka-qa-gateway"
SCENARIO = "authenticated-qa-menu-smoke"
GITHUB_REPORT_URL = (
    "https://api.github.com/repos/marikol444707-ux/stroyka-app/issues/311/comments"
)
REQUIRED_CHECKS = frozenset({
    "read_only_observation",
    "expect_text[0]:present",
    "expect_url_contains[0]:present",
})
ALLOWED_JOB_STATUS = frozenset({"queued", "running", "cancelling", "passed", "failed", "cancelled"})
ALLOWED_QA_ENVIRONMENTS = frozenset({"qa", "test", "staging"})
ALLOWED_CHECKS = REQUIRED_CHECKS | frozenset({
    "expect_text[0]:missing",
    "expect_url_contains[0]:missing",
})


class WatchError(Exception):
    """A sanitized failure category, never an upstream error body."""


def worker_base(port_value: str) -> str:
    if not re.fullmatch(r"[0-9]{4,5}", port_value):
        raise WatchError("INVALID_WORKER_PORT")
    port = int(port_value)
    if not 1024 <= port <= 65535:
        raise WatchError("INVALID_WORKER_PORT")
    return f"http://127.0.0.1:{port}"


def _watcher_signature(
    scoped_token: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes = b"",
) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", scoped_token):
        raise WatchError("INVALID_WATCHER_TOKEN")
    body_hash = hashlib.sha256(body).hexdigest()
    message = "\n".join((
        method.upper(),
        path,
        timestamp,
        nonce,
        body_hash,
    )).encode("utf-8")
    return hmac.new(
        bytes.fromhex(scoped_token),
        message,
        hashlib.sha256,
    ).hexdigest()


def call_worker(base: str, token: str, method: str, path: str):
    if method not in {"GET", "POST"} or not (
        path == "/watcher/health"
        or path == "/watcher/smoke"
        or re.fullmatch(r"/watcher/jobs/[0-9a-f]{32}", path)
        or re.fullmatch(r"/watcher/jobs/[0-9a-f]{32}/cancel", path)
    ):
        raise WatchError("INVALID_API_PATH")
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    signature = _watcher_signature(token, method, path, timestamp, nonce)
    request = urllib.request.Request(
        base + path,
        data=b"" if method == "POST" else None,
        method=method,
        headers={
            "X-Jev-Watcher-Time": timestamp,
            "X-Jev-Watcher-Nonce": nonce,
            "X-Jev-Watcher-Signature": signature,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            result = json.load(response)
    except Exception as exc:
        raise WatchError("WORKER_API_UNAVAILABLE") from exc
    if not isinstance(result, dict):
        raise WatchError("INVALID_WORKER_RESPONSE")
    return result


def run_smoke(call, *, sleep=time.sleep, monotonic=time.monotonic):
    health = call("GET", "/watcher/health")
    if (
        health.get("ok") is not True
        or str(health.get("environment") or "").lower() not in ALLOWED_QA_ENVIRONMENTS
        or health.get("watcher_target") != QA_URL
    ):
        raise WatchError("QA_WORKER_NOT_READY")

    created = call("POST", "/watcher/smoke")
    job_id = created.get("job_id")
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise WatchError("INVALID_JOB_ID")

    deadline = monotonic() + 85
    while monotonic() < deadline:
        state = call("GET", "/watcher/jobs/" + job_id)
        status = state.get("status")
        if status in {"passed", "failed", "cancelled"}:
            result = state.get("result") or {}
            if not isinstance(result, dict):
                result = {}
            checks = sorted({
                item for item in (result.get("checks") or [])
                if isinstance(item, str) and item in ALLOWED_CHECKS
            })
            success = (
                status == "passed"
                and result.get("ok") is True
                and REQUIRED_CHECKS.issubset(checks)
                and not result.get("failures")
            )
            return {
                "job_id": job_id,
                "job_status": status,
                "outcome": "passed" if success else "failed",
                "checks": checks,
                "failure_codes": [] if success else classify_failures(result.get("failures")),
            }
        if status not in ALLOWED_JOB_STATUS:
            raise WatchError("UNKNOWN_JOB_STATUS")
        sleep(3)
    try:
        cancelled = call("POST", "/watcher/jobs/" + job_id + "/cancel")
    except Exception as exc:
        raise WatchError("POLL_TIMEOUT_CANCEL_FAILED") from exc
    if not isinstance(cancelled, dict) or cancelled.get("status") not in {
        "cancelling", "cancelled", "passed", "failed"
    }:
        raise WatchError("POLL_TIMEOUT_CANCEL_FAILED")
    raise WatchError("POLL_TIMEOUT")


def classify_failures(raw):
    """No raw model/HTTP/exception messages are written to reports or GitHub."""
    codes = set()
    if not isinstance(raw, list):
        return ["UNVERIFIED_RESULT"]
    for value in raw:
        if not isinstance(value, str):
            continue
        lower = value.lower()
        if "read_only_action_detected" in lower:
            codes.add("READ_ONLY_VIOLATION")
        elif "javascript alert" in lower:
            codes.add("QA_ALERT_STOP")
        elif "agent_status=blocked" in lower:
            codes.add("AGENT_BLOCKED")
        elif "agent_status=" in lower:
            codes.add("AGENT_NOT_DONE")
        elif "expect_text" in lower:
            codes.add("TEXT_NOT_FOUND")
        elif "expect_url_contains" in lower:
            codes.add("URL_NOT_VERIFIED")
        elif "timeout" in lower:
            codes.add("TIMEOUT")
        else:
            codes.add("OTHER_FAILURE")
    return sorted(codes) or ["UNVERIFIED_RESULT"]


def save_report(report: dict, folder: Path) -> None:
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = (json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n").encode()
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=folder, prefix=".last-", delete=False
        ) as temp:
            temp_name = temp.name
            os.chmod(temp_name, 0o600)
            temp.write(payload)
        os.replace(temp_name, folder / "last.json")
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def github_report(report: dict, token: str) -> None:
    """Post only a fixed-format, redacted summary to one dedicated GitHub issue."""
    outcome = report["outcome"].upper()
    checks = ", ".join(report.get("checks") or []) or "none"
    failures = ", ".join(report.get("failure_codes") or []) or "none"
    body = (
        f"**JEVA QA scheduled smoke: {outcome}**\n\n"
        f"- Scenario: `{SCENARIO}` (read-only)\n"
        f"- UTC: `{report['utc']}`\n"
        f"- Job: `{report.get('job_id') or 'not-created'}`\n"
        f"- Checks: `{checks}`\n"
        f"- Failure codes: `{failures}`\n\n"
        "No credentials, screenshots, entered text, or raw model output attached."
    )
    request = urllib.request.Request(
        GITHUB_REPORT_URL,
        method="POST",
        data=json.dumps({"body": body}).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            if response.status != 201:
                raise WatchError("REPORT_DELIVERY_FAILED")
    except Exception as exc:
        raise WatchError("REPORT_DELIVERY_FAILED") from exc


def main() -> int:
    report = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": SCENARIO,
        "outcome": "failed",
        "job_id": None,
        "job_status": "not_started",
        "checks": [],
        "failure_codes": [],
    }
    token = os.environ.get("JEV_WATCHER_TOKEN", "").strip()
    try:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", token):
            raise WatchError("MISSING_OR_INVALID_WATCHER_TOKEN")
        base = worker_base(os.environ.get("JEV_WATCH_PORT", "18088"))
        result = run_smoke(lambda method, path: call_worker(
            base, token, method, path
        ))
        report.update(result)
    except WatchError as exc:
        report["failure_codes"] = [str(exc)]
    except Exception:
        report["failure_codes"] = ["UNEXPECTED_WATCH_ERROR"]

    try:
        save_report(report, Path("/var/lib/stroyka-jev-watch"))
    except OSError:
        print("JEVA WATCH: REPORT_WRITE_FAILED", file=sys.stderr)
        return 1

    notification_token = os.environ.get("JEV_WATCH_GITHUB_TOKEN", "").strip()
    if notification_token:
        try:
            github_report(report, notification_token)
        except WatchError:
            print("JEVA WATCH: REPORT_DELIVERY_FAILED", file=sys.stderr)
            return 1

    print("JEVA WATCH:", report["outcome"], report.get("job_id") or "no-job")
    return 0 if report["outcome"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
