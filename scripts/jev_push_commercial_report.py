#!/usr/bin/env python3
"""Send one JEV commercial-search JSON report to the scoped Stroyka intake endpoint."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from backend.features.job_candidates.service import jev_report_items
except ModuleNotFoundError:
    from features.job_candidates.service import jev_report_items


MAX_REPORT_BYTES = 1_000_000


def build_request(report, *, api_url, ingest_key):
    parsed = urlsplit(str(api_url or "").strip())
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("JEV_OPPORTUNITY_API_URL должен быть HTTPS-адресом сайта Стройки без пути")
    if len(str(ingest_key or "")) < 32:
        raise ValueError("Ключ импорта JEV не настроен или слишком короткий")
    items = jev_report_items(report)
    if not items:
        raise ValueError("В отчёте нет подтверждённых находок или записей для проверки")
    body = json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_REPORT_BYTES:
        raise ValueError("Отчёт JEV превышает лимит 1 МБ")
    request = Request(
        parsed.scheme + "://" + parsed.netloc + "/api/internal/jev/job-candidates",
        data=body,
        headers={"Content-Type": "application/json", "X-JEV-Ingest-Key": str(ingest_key)},
        method="POST",
    )
    return request, len(items)


def main():
    raw = sys.stdin.buffer.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        print(json.dumps({"ok": False, "error": "report_too_large"}))
        return 2
    try:
        report = json.loads(raw.decode("utf-8"))
        request, count = build_request(
            report,
            api_url=os.environ.get("JEV_OPPORTUNITY_API_URL"),
            ingest_key=os.environ.get("JEV_OPPORTUNITY_INGEST_KEY"),
        )
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read(64 * 1024).decode("utf-8"))
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise ValueError("unexpected_api_response")
        print(json.dumps({"ok": True, "sent": count, "result": result}, ensure_ascii=False))
        return 0
    except HTTPError as error:
        print(json.dumps({"ok": False, "http_status": error.code, "error": "api_rejected_report"}))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, URLError, TimeoutError, OSError) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
