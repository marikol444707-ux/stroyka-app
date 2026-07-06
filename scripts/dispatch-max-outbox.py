#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
DEFAULT_BASE_URL = "https://stroyka26.pro"


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name, default=""):
    return os.getenv(name) or ENV.get(name, default)


def max_bot_token():
    token = (
        env_value("SMOKE_MAX_BOT_TOKEN")
        or env_value("MAX_WEBHOOK_SECRET")
        or env_value("MAX_BOT_API_TOKEN")
    )
    token = str(token or "").strip()
    if not token or token.lower() in {"change-me", "token", "***", "..."}:
        raise SystemExit("Нужно задать SMOKE_MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET или MAX_BOT_API_TOKEN")
    return token


def api_json(base_url, path, token):
    url = base_url.rstrip("/") + path
    request = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Max-Bot-Token": token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"POST {path}: HTTP {exc.code}. {text[:900]}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"POST {path}: MAX dispatch endpoint недоступен: {exc.reason}")
    if status != 200:
        raise SystemExit(f"POST {path}: HTTP {status}. {text[:900]}")
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise SystemExit(f"POST {path}: backend вернул не JSON: {text[:900]}")


def build_parser():
    parser = argparse.ArgumentParser(description="Отправить очередь MAX messenger_outbox через Stroyka backend")
    parser.add_argument("--base-url", default=env_value("BASE_URL", DEFAULT_BASE_URL).rstrip("/"))
    parser.add_argument("--limit", type=int, default=int(env_value("MAX_OUTBOX_DISPATCH_LIMIT", "20") or 20))
    parser.add_argument("--dry-run", action="store_true", help="Только собрать payload, без отправки в MAX")
    parser.add_argument("--fail-on-failed", action="store_true", help="Вернуть exit code 2, если часть сообщений не отправилась")
    return parser


def main():
    args = build_parser().parse_args()
    limit = max(1, min(100, int(args.limit or 20)))
    query = urllib.parse.urlencode({
        "limit": limit,
        "dry_run": "true" if args.dry_run else "false",
    })
    result = api_json(args.base_url, f"/max/outbox/dispatch?{query}", max_bot_token())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_on_failed and result.get("failed"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
