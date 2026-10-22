#!/usr/bin/env python3
"""Run profile-specific JEV searches over SSH and import them by company."""

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

from scripts.jev_push_commercial_report import build_request, build_targets_request


SSH_COMMAND = [
    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o",
    "StrictHostKeyChecking=yes", "stroyka-dev-agent", "sudo -n stroyka-jev commercial-search",
]
SSH_PROFILE_COMMAND = [
    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o",
    "StrictHostKeyChecking=yes", "stroyka-dev-agent",
    "sudo -n stroyka-jev commercial-search --profile-stdin",
]
KEYCHAIN_SERVICE = "stroyka-jev-opportunity-ingest"
KEYCHAIN_ACCOUNT = "stroyka26.pro"


def integration_key(environ=None, *, runner=None):
    values = os.environ if environ is None else environ
    key = str(values.get("JEV_OPPORTUNITY_INGEST_KEY") or "").strip()
    if key:
        if len(key) < 32:
            raise ValueError("invalid_integration_key")
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
    key = result.stdout.strip()
    if len(key) < 32:
        raise ValueError("invalid_integration_key")
    return key


def run_search(profile=None, *, runner=None):
    run = runner or subprocess.run
    command = SSH_PROFILE_COMMAND if profile is not None else SSH_COMMAND
    options = {"capture_output": True, "text": True, "timeout": 320, "check": False}
    if profile is not None:
        options["input"] = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    result = run(command, **options)
    try:
        report = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("jev_search_returned_invalid_report") from error
    if not isinstance(report, dict) or not isinstance(report.get("sources"), list):
        raise ValueError("jev_search_returned_invalid_report")
    # A remote nonzero exit may still contain a useful partial report if one
    # source failed; import remains safe because all rows enter review status.
    if result.returncode and not (
        report.get("confirmed") or report.get("review") or report.get("government_review")
        or report.get("sources")
    ):
        raise ValueError("jev_search_failed_without_candidates")
    if profile is not None and report.get("companyId") != profile.get("companyId"):
        raise ValueError("jev_search_profile_mismatch")
    return report


def push_report(report, *, api_url, ingest_key, target_company_id=None, opener=None):
    request, count = build_request(report, api_url=api_url, ingest_key=ingest_key,
                                  target_company_id=target_company_id)
    open_url = opener or urlopen
    with open_url(request, timeout=20) as response:
        result = json.loads(response.read(64 * 1024).decode("utf-8"))
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("stroyka_rejected_report")
    return {"sent": count, "result": result}


def fetch_search_targets(*, api_url, ingest_key, opener=None):
    request = build_targets_request(api_url=api_url, ingest_key=ingest_key)
    open_url = opener or urlopen
    with open_url(request, timeout=20) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("jev_targets_too_large")
    payload = json.loads(raw.decode("utf-8"))
    targets = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(targets, list):
        raise ValueError("jev_targets_invalid")
    for target in targets:
        if (not isinstance(target, dict) or type(target.get("companyId")) is not int
                or target["companyId"] <= 0 or target.get("region") != "Ставропольский край"
                or not isinstance(target.get("searchTerms"), list)
                or not isinstance(target.get("sourceProviders"), list)
                or not target["sourceProviders"]):
            raise ValueError("jev_targets_invalid")
    if len({target["companyId"] for target in targets}) != len(targets):
        raise ValueError("jev_targets_invalid")
    return targets


def main(*, runner=None, opener=None, environ=None):
    values = os.environ if environ is None else environ
    try:
        key = integration_key(values)
        api_url = values.get("JEV_OPPORTUNITY_API_URL", "https://stroyka26.pro")
        targets = fetch_search_targets(api_url=api_url, ingest_key=key, opener=opener)
        if not targets:
            raise ValueError("jev_no_enabled_companies")
        results = []
        for profile in targets:
            report = run_search(profile=profile, runner=runner)
            result = push_report(
                report,
                api_url=api_url,
                ingest_key=key,
                target_company_id=profile["companyId"],
                opener=opener,
            )
            results.append({"companyId": profile["companyId"], **result})
        print(json.dumps({"ok": True, "companiesProcessed": len(results), "results": results}, ensure_ascii=False))
        return 0
    except HTTPError as error:
        print(json.dumps({"ok": False, "http_status": error.code, "error": "api_rejected_report"}))
    except (OSError, TimeoutError, URLError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error) if str(error).startswith(("missing_", "invalid_", "jev_", "stroyka_")) else type(error).__name__}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
