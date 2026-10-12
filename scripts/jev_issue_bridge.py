#!/usr/bin/env python3
"""Allowlisted GitHub Issue -> existing HMAC-authenticated Jev QA smoke.

No arbitrary URLs, prompts, commands, credentials or evidence leave QA host.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from scripts.jev_qa_watch import call_worker, run_smoke, WatchError, worker_base

REPO = "marikol444707-ux/stroyka-app"
AUTHOR = "marikol444707-ux"
TITLE = "[JEV] QA smoke"
BODY = "JEV_QA_SMOKE_V1"
API = "https://api.github.com/repos/" + REPO
CODES = {"QA_WORKER_NOT_READY", "INVALID_JOB_ID", "UNKNOWN_JOB_STATUS", "POLL_TIMEOUT", "POLL_TIMEOUT_CANCEL_FAILED", "WORKER_API_UNAVAILABLE", "WORKER_RESPONSE_TOO_LARGE", "WORKER_RESPONSE_UNAUTHENTICATED", "INVALID_WORKER_RESPONSE", "TEXT_NOT_FOUND", "URL_NOT_VERIFIED", "TIMEOUT", "OTHER_FAILURE", "UNVERIFIED_RESULT", "AGENT_NOT_DONE", "AGENT_BLOCKED", "QA_ALERT_STOP", "READ_ONLY_VIOLATION", "UNEXPECTED_WATCH_ERROR", "BRIDGE_INTERRUPTED"}

class BridgeError(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def github(token, method, path, payload=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,255}", token):
        raise BridgeError("INVALID_GITHUB_TOKEN")
    if not (path == "/issues?state=open&per_page=100&sort=created&direction=desc" or re.fullmatch(r"/issues/[0-9]+(?:/comments)?", path)):
        raise BridgeError("INVALID_GITHUB_PATH")
    if method not in ("GET", "POST", "PATCH"):
        raise BridgeError("INVALID_GITHUB_METHOD")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stroyka-jev-issue-bridge/1"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            data = response.read(256 * 1024 + 1)
            if len(data) > 256 * 1024 or response.status not in (200, 201):
                raise BridgeError("GITHUB_API_ERROR")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise BridgeError("GITHUB_API_ERROR") from exc
    try:
        return json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise BridgeError("GITHUB_RESPONSE_INVALID") from exc

def eligible(issue, minimum=0):
    n = issue.get("number")
    return (type(n) is int and n > minimum and issue.get("state") == "open"
        and "pull_request" not in issue and issue.get("title") == TITLE
        and issue.get("body") == BODY and isinstance(issue.get("user"), dict)
        and issue["user"].get("login", "").lower() == AUTHOR)

def connect(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS tasks (number INTEGER PRIMARY KEY, state TEXT NOT NULL, report TEXT)")
    db.commit()
    return db

def safe_report(outcome, job_id=None, codes=()):
    return {"outcome": "passed" if outcome == "passed" else "failed",
            "job_id": job_id if isinstance(job_id, str) and re.fullmatch(r"[0-9a-f]{32}", job_id) else "none",
            "codes": sorted(set(codes) & CODES) or ([] if outcome == "passed" else ["UNEXPECTED_WATCH_ERROR"])}

def format_comment(report):
    return ("**Jev QA: " + report["outcome"].upper() + "**\n\n"
        + "Scenario: `authenticated-qa-menu-smoke` (read-only)\n"
        + "Job: `" + report["job_id"] + "`\n"
        + "Failure codes: `" + (", ".join(report["codes"]) or "none") + "`\n\n"
        + "No secrets, screenshots or raw browser content uploaded.")

def run_once(db, gh, worker, minimum=0):
    issues = gh("GET", "/issues?state=open&per_page=100&sort=created&direction=desc")
    if not isinstance(issues, list):
        raise BridgeError("GITHUB_ISSUES_INVALID")
    for issue in issues:
        if not isinstance(issue, dict) or not eligible(issue, minimum):
            continue
        n = issue["number"]
        row = db.execute("SELECT state,report FROM tasks WHERE number=?", (n,)).fetchone()
        if row is None:
            # Durable claim before touching the worker. Never replay after a crash.
            db.execute("INSERT INTO tasks VALUES (?, 'claimed', NULL)", (n,))
            db.commit()
            try:
                result = worker()
                report = safe_report(result.get("outcome"), result.get("job_id"), result.get("failure_codes") or [])
            except WatchError as exc:
                report = safe_report("failed", codes=[str(exc)])
            except Exception:
                report = safe_report("failed", codes=["UNEXPECTED_WATCH_ERROR"])
            db.execute("UPDATE tasks SET state='done',report=? WHERE number=?", (json.dumps(report), n))
            db.commit()
            row = ("done", json.dumps(report))
        if row[0] == "claimed":
            # If a process crashed, do not rerun a potentially submitted job.
            report = safe_report("failed", codes=["BRIDGE_INTERRUPTED"])
            db.execute("UPDATE tasks SET state='done',report=? WHERE number=?", (json.dumps(report), n))
            db.commit()
            row = ("done", json.dumps(report))
        if row[0] == "done":
            report = json.loads(row[1])
            gh("POST", f"/issues/{n}/comments", {"body": format_comment(report)})
            db.execute("UPDATE tasks SET state='reported' WHERE number=?", (n,))
            db.commit()
            print("JEV_ISSUE_REPORTED", n, report["outcome"], flush=True)
            row = ("reported", row[1])
        if row[0] == "reported":
            # A failed close is retried; the browser job is never replayed.
            gh("PATCH", f"/issues/{n}", {"state": "closed"})
            return  # One browser job per invocation; bounded systemd runtime.

def main():
    token = os.environ.get("JEV_CONTROL_GITHUB_TOKEN", "").strip()
    scoped = os.environ.get("JEV_WATCHER_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", scoped):
        raise BridgeError("MISSING_SCOPED_WATCHER_TOKEN")
    minimum = int(os.environ.get("JEV_CONTROL_MIN_ISSUE_NUMBER", "0"))
    port = os.environ.get("JEV_WATCH_PORT", "18084")
    dbpath = Path(os.environ.get("JEV_CONTROL_STATE_DB", "/var/lib/stroyka-jev-issue-bridge/tasks.db"))
    with connect(dbpath) as db:
        run_once(db,
            lambda method, path, payload=None: github(token, method, path, payload),
            lambda: run_smoke(lambda method, path: call_worker(worker_base(port), scoped, method, path)),
            minimum)

if __name__ == "__main__":
    try:
        main()
    except (BridgeError, WatchError, ValueError, OSError, sqlite3.Error) as exc:
        print("JEV_BRIDGE_ERROR=" + (str(exc) if isinstance(exc, (BridgeError, WatchError)) else type(exc).__name__), file=sys.stderr)
        raise SystemExit(1)
