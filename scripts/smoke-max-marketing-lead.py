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
CHAT_ID_FROM_ENV = bool(os.getenv("MAX_MARKETING_SMOKE_CHAT_ID"))
CHAT_ID = os.getenv("MAX_MARKETING_SMOKE_CHAT_ID", f"codex-max-marketing-{RUN_ID}")
TITLE = os.getenv("MAX_MARKETING_SMOKE_TITLE", f"CODEX MAX маркетинг {RUN_ID}")
CAMPAIGN = os.getenv("MAX_MARKETING_SMOKE_CAMPAIGN", f"codex-campaign-{RUN_ID}")


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


def cleanup(lead_id=None, channel_id=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        if lead_id:
            cur.execute("DELETE FROM crm_leads WHERE id=%s", (lead_id,))
        if channel_id and (not CHAT_ID_FROM_ENV or os.getenv("SMOKE_DELETE_CHANNEL") == "1"):
            cur.execute("DELETE FROM messenger_channels WHERE id=%s", (channel_id,))
        conn.commit()
        cur.close()
        print("cleanup: removed MAX marketing smoke rows")
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
    channel_id = None
    lead_id = None
    try:
        _, channel_body = api_json(
            "POST",
            "/messenger-channels",
            token=director_token,
            data={
                "provider": "max",
                "chatId": CHAT_ID,
                "title": TITLE,
                "channelType": "marketing",
                "sourceLabel": "MAX маркетинг",
                "campaignCode": CAMPAIGN,
                "defaultStage": "Новый",
                "enabled": True,
                "metadata": {"smokeRunId": RUN_ID, "purpose": "lead intake"},
            },
            expected=200,
        )
        channel = channel_body.get("channel") or {}
        channel_id = channel.get("id")
        if not channel_id:
            raise RuntimeError(f"messenger channel did not return id: {channel_body}")

        phone = "+7999" + RUN_ID[:7]
        _, lead_body = api_json(
            "POST",
            "/max/marketing-leads",
            data={
                "maxChatId": CHAT_ID,
                "maxUserId": f"lead-user-{RUN_ID}",
                "username": f"codex_lead_{RUN_ID}",
                "name": f"CODEX MAX лид {RUN_ID}",
                "phone": phone,
                "email": f"max-lead-{RUN_ID}@stroyka.local",
                "campaignCode": CAMPAIGN,
                "message": "Интересует ремонт под ключ, прошу связаться.",
                "sourceId": f"max-marketing-message-{RUN_ID}",
                "utm": {"source": "max", "campaign": CAMPAIGN},
            },
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        lead = lead_body.get("lead") or {}
        lead_id = lead.get("id")
        if not lead_id:
            raise RuntimeError(f"MAX marketing lead did not return lead id: {lead_body}")
        if not str(lead.get("source") or "").startswith("MAX:"):
            raise RuntimeError(f"CRM lead source is not MAX: {lead}")
        if CHAT_ID not in (lead.get("notes") or ""):
            raise RuntimeError(f"CRM lead notes do not include MAX chat id: {lead}")

        _, leads = api_json("GET", "/crm/lead-summaries", token=director_token, expected=200)
        crm_lead = next((item for item in leads if str(item.get("id")) == str(lead_id)), None)
        if not crm_lead:
            raise RuntimeError("MAX marketing lead is not visible in CRM lead summaries")
        if crm_lead.get("phone") != phone:
            raise RuntimeError(f"CRM lead phone mismatch: {crm_lead}")

        print(json.dumps({
            "ok": True,
            "channelId": channel_id,
            "leadId": lead_id,
            "chatId": CHAT_ID,
            "source": crm_lead.get("source"),
            "checked": [
                "marketing MAX channel is upserted",
                "MAX bot endpoint creates CRM lead",
                "CRM lead keeps channel/campaign context in notes",
                "lead is visible in /crm/lead-summaries",
            ],
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(lead_id, channel_id)


if __name__ == "__main__":
    main()
