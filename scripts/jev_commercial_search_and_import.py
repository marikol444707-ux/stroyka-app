#!/usr/bin/env python3
"""Run the fixed JEV search over SSH and push its report into Stroyka."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.jev_push_commercial_report import build_request


SSH_COMMAND = [
    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o",
    "StrictHostKeyChecking=yes", "stroyka-dev-agent", "sudo -n stroyka-jev commercial-search",
]
KEYCHAIN_SERVICE = "stroyka-jev-opportunity-ingest"
KEYCHAIN_ACCOUNT = "stroyka26.pro"


def integration_key(environ=None, *, runner=None):
    values = os.environ if environ is None else environ
    key = str(values.get("JEV_OPPORTUNITY_INGEST_KEY") or "").strip()
    if key:
        return key
    if sys.platform != "darwin":
        raise ValueError("missing_integration_key")
    run = runner or subprocess.run
    result = run(
        ["security", "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError("missing_keychain_entry")
    return result.stdout.strip()


def run_search(*, runner=None):
    run = runner or subprocess.run
    result = run(SSH_COMMAND, capture_output=True, text=True, timeout=260, check=False)
    try:
        report = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("jev_search_returned_invalid_report") from error
    if not isinstance(report, dict) or not isinstance(report.get("sources"), list):
        raise ValueError("jev_search_returned_invalid_report")
    # A remote nonzero exit may still contain a useful partial report if one
    # source failed; import remains safe because all rows enter review status.
    if result.returncode and not (report.get("confirmed") or report.get("review")):
        raise ValueError("jev_search_failed_without_candidates")
    return report


def push_report(report, *, api_url, ingest_key, opener=None):
    request, count = build_request(report, api_url=api_url, ingest_key=ingest_key)
    open_url = opener or urlopen
    with open_url(request, timeout=20) as response:
        result = json.loads(response.read(64 * 1024).decode("utf-8"))
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("stroyka_rejected_report")
    return {"sent": count, "result": result}


def main(*, runner=None, opener=None, environ=None):
    values = os.environ if environ is None else environ
    try:
        key = integration_key(values)
        report = run_search(runner=runner)
        result = push_report(
            report,
            api_url=values.get("JEV_OPPORTUNITY_API_URL", "https://stroyka26.pro"),
            ingest_key=key,
            opener=opener,
        )
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0
    except HTTPError as error:
        print(json.dumps({"ok": False, "http_status": error.code, "error": "api_rejected_report"}))
    except (OSError, TimeoutError, URLError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error) if str(error).startswith(("missing_", "jev_", "stroyka_")) else type(error).__name__}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
