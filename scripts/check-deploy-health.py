#!/usr/bin/env python3
"""Poll the public health URL until the released commit is actually serving."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

HEALTH_URL = "https://stroyka26.pro/health"


def expected_version(sha):
    value = str(sha or "").strip().lower()
    if len(value) < 12 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("bad sha")
    # /health returns the first 12 characters. See runtime_version.app_version.
    return value[:12]


def release_is_healthy(payload, version):
    return (
        isinstance(payload, dict)
        and payload.get("ok") is True
        and payload.get("version") == version
    )


def assert_health_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "stroyka26.pro" or parts.path.rstrip("/") != "/health":
        raise ValueError("health url must be https://stroyka26.pro/health")


def fetch_health(url, timeout):
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    return json.loads(body)


def poll_health(url, sha, attempts, delay, timeout, fetch=fetch_health, sleep=time.sleep):
    assert_health_url(url)
    version = expected_version(sha)
    last = "ответа ещё не было"
    attempts = int(attempts)
    if attempts < 1:
        raise ValueError("attempts")
    for attempt in range(1, attempts + 1):
        try:
            payload = fetch(url, timeout)
            if release_is_healthy(payload, version):
                return True, version, "ok"
            last = "ok=%r version=%r" % (payload.get("ok") if isinstance(payload, dict) else None,
                                         payload.get("version") if isinstance(payload, dict) else None)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
            last = exc.__class__.__name__
        if attempt != attempts:
            sleep(delay)
    return False, version, last


def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверить https://stroyka26.pro/health")
    parser.add_argument("--url", default=HEALTH_URL)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=float, default=5)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args(argv)
    try:
        ready, version, detail = poll_health(
            args.url, args.sha, args.attempts, args.delay, args.timeout,
        )
    except ValueError as exc:
        print("ОШИБКА: %s" % exc, file=sys.stderr)
        return 2
    if ready:
        print("Сайт отвечает: ok=true, version=%s" % version)
        return 0
    print(
        "ОШИБКА: сайт не подтвердил коммит. Ожидалась version=%s. Последний ответ: %s"
        % (version, detail),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
