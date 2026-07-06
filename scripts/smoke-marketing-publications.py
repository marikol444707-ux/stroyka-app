#!/usr/bin/env python3
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:8]
CHAT_ID = os.getenv("MARKETING_PUBLICATION_SMOKE_CHAT_ID", f"codex-marketing-pub-{RUN_ID}")
TITLE = f"CODEX QA публикация {RUN_ID}"
CAMPAIGN = f"codex-publication-{RUN_ID}"


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


def db_config():
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def api_json(method, path, token=None, data=None, headers=None, expected=None):
    request_headers = {"Content-Type": "application/json"}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if headers:
        request_headers.update(headers)
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=50) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def require_env(name):
    value = env_value(name, "")
    if not value:
        raise SystemExit(f"Нужно задать {name} в окружении или backend/.env")
    return value


def max_bot_token():
    token = env_value("SMOKE_MAX_BOT_TOKEN") or env_value("MAX_WEBHOOK_SECRET") or env_value("MAX_BOT_API_TOKEN")
    token = (token or "").strip()
    if not token or token.lower() in {"change-me", "token", "***", "..."}:
        raise SystemExit("Нужно задать реальный SMOKE_MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET или MAX_BOT_API_TOKEN")
    return token


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken")
    if not token:
        raise SystemExit(f"FAIL login {email}: authToken не получен")
    return token


def cleanup(publication_id=None, channel_id=None, outbox_ids=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        for outbox_id in outbox_ids or []:
            cur.execute("DELETE FROM messenger_outbox WHERE id=%s", (outbox_id,))
        if publication_id:
            cur.execute("DELETE FROM marketing_publications WHERE id=%s", (publication_id,))
        if channel_id and not os.getenv("MARKETING_PUBLICATION_SMOKE_CHAT_ID"):
            cur.execute("DELETE FROM messenger_channels WHERE id=%s", (channel_id,))
        conn.commit()
        cur.close()
        print("cleanup: removed marketing publication smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def main():
    admin_email = require_env("SMOKE_EMAIL")
    admin_password = require_env("SMOKE_PASSWORD")
    director_token = login(admin_email, admin_password)
    bot_token = max_bot_token()
    publication_id = None
    channel_id = None
    outbox_ids = []
    try:
        _, channel_body = api_json(
            "POST",
            "/messenger-channels",
            token=director_token,
            data={
                "provider": "max",
                "chatId": CHAT_ID,
                "title": f"CODEX MAX публикации {RUN_ID}",
                "channelType": "marketing",
                "sourceLabel": "MAX публикации",
                "campaignCode": CAMPAIGN,
                "enabled": True,
            },
            expected=200,
        )
        channel = channel_body.get("channel") or {}
        channel_id = channel.get("id")
        if not channel_id:
            raise RuntimeError(f"messenger channel did not return id: {channel_body}")

        _, created = api_json(
            "POST",
            "/marketing-publications",
            token=director_token,
            data={
                "title": TITLE,
                "body": "Проверяем связку публикаций сайта и MAX.",
                "publicationUrl": f"{BASE_URL}/?codexPublication={RUN_ID}#request",
                "targetSite": True,
                "targetMax": True,
                "channelIds": [channel_id],
                "utmCampaign": CAMPAIGN,
            },
            expected=200,
        )
        publication = created.get("publication") or {}
        publication_id = publication.get("id")
        if not publication_id:
            raise RuntimeError(f"marketing publication did not return id: {created}")

        _, published = api_json(
            "POST",
            f"/marketing-publications/{publication_id}/publish",
            token=director_token,
            data={"channelIds": [channel_id], "targetMax": True, "targetSite": True},
            expected=200,
        )
        outbox_ids = published.get("outboxIds") or []
        if not outbox_ids:
            raise RuntimeError(f"publication did not create MAX outbox message: {published}")
        publication = published.get("publication") or {}
        if publication.get("status") != "В очереди":
            raise RuntimeError(f"publication status after MAX publish is wrong: {publication}")
        if "utm_campaign=" + CAMPAIGN not in publication.get("publicationUrl", ""):
            raise RuntimeError(f"publication URL does not include campaign UTM: {publication}")

        _, outbox = api_json(
            "GET",
            "/max/outbox?limit=100",
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        queued = next((item for item in outbox.get("items") or [] if item.get("id") in outbox_ids), None)
        if not queued:
            raise RuntimeError("MAX outbox does not include marketing publication")
        if queued.get("eventType") != "marketing_publication":
            raise RuntimeError(f"wrong outbox event type: {queued}")
        if not any(action.get("id") == "openPublication" for action in queued.get("actions") or []):
            raise RuntimeError(f"outbox publication has no open action: {queued}")

        _, site_publications = api_json("GET", "/site/publications?limit=50", expected=200)
        if not any(item.get("id") == publication_id for item in site_publications):
            raise RuntimeError("publication is not visible in public site publications feed")

        print(json.dumps({
            "ok": True,
            "publicationId": publication_id,
            "channelId": channel_id,
            "outboxIds": outbox_ids,
            "checked": [
                "marketing publication is created",
                "publication publish queues MAX outbox message",
                "outbox message has openPublication action",
                "site/publications exposes published queued item",
            ],
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(publication_id, channel_id, outbox_ids)


if __name__ == "__main__":
    main()
