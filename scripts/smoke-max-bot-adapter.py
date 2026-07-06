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
CHAT_ID = os.getenv("MAX_BOT_ADAPTER_SMOKE_CHAT_ID", f"codex-max-bot-{RUN_ID}")
CHANNEL_TITLE = os.getenv("MAX_BOT_ADAPTER_SMOKE_TITLE", f"CODEX MAX bot {RUN_ID}")


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


def api_json(method, path, data=None, headers=None, expected=None):
    request_headers = {"Content-Type": "application/json"}
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


def max_bot_token():
    token = env_value("SMOKE_MAX_BOT_TOKEN") or env_value("MAX_WEBHOOK_SECRET") or env_value("MAX_BOT_API_TOKEN")
    token = (token or "").strip()
    if not token or token.lower() in {"change-me", "token", "***", "..."}:
        raise SystemExit("Нужно задать реальный SMOKE_MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET или MAX_BOT_API_TOKEN")
    return token


def cleanup(lead_id=None, outbox_id=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        if outbox_id:
            cur.execute("DELETE FROM messenger_outbox WHERE id=%s", (outbox_id,))
        if lead_id:
            cur.execute("DELETE FROM crm_leads WHERE id=%s", (lead_id,))
        if not os.getenv("MAX_BOT_ADAPTER_SMOKE_CHAT_ID"):
            cur.execute("DELETE FROM messenger_channels WHERE provider='max' AND chat_id=%s", (CHAT_ID,))
        conn.commit()
        cur.close()
        print("cleanup: removed MAX bot adapter smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def insert_outbox():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messenger_outbox
            (provider,external_user_id,chat_id,event_type,entity_type,entity_id,
             title,body,payload_json,actions_json,status,priority)
        VALUES
            ('max',%s,%s,'codex_max_adapter_smoke','smoke',NULL,
             %s,%s,%s::jsonb,%s::jsonb,'queued',1)
        RETURNING id
        """,
        (
            f"codex-user-{RUN_ID}",
            CHAT_ID,
            "CODEX MAX smoke",
            "Проверяем сборку сообщения и inline-кнопки без реальной отправки.",
            json.dumps({"smokeRunId": RUN_ID}, ensure_ascii=False),
            json.dumps([{
                "id": "openPublication",
                "label": "Открыть",
                "kind": "link",
                "url": BASE_URL + "/?codexMaxSmoke=" + RUN_ID,
            }], ensure_ascii=False),
        ),
    )
    outbox_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return outbox_id


def main():
    token = max_bot_token()
    headers = {"X-Max-Bot-Api-Secret": token}
    lead_id = None
    outbox_id = None
    try:
        _, linked = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "bot_added",
                "timestamp": int(dt.datetime.now().timestamp()),
                "chat_id": CHAT_ID,
                "is_channel": True,
                "chat": {"id": CHAT_ID, "title": CHANNEL_TITLE},
                "user": {"id": f"owner-{RUN_ID}", "first_name": "CODEX", "last_name": "Owner"},
            },
            headers=headers,
            expected=200,
        )
        channel = ((linked.get("results") or [{}])[0]).get("channel") or {}
        if channel.get("chatId") != CHAT_ID:
            raise RuntimeError(f"MAX webhook did not link channel: {linked}")
        if channel.get("channelType") != "marketing":
            raise RuntimeError(f"MAX channel should be marketing for is_channel=true: {channel}")

        _, message = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "message_created",
                "timestamp": int(dt.datetime.now().timestamp()),
                "message": {
                    "mid": f"codex-message-{RUN_ID}",
                    "recipient": {"chat_id": CHAT_ID},
                    "sender": {"user_id": f"lead-user-{RUN_ID}", "username": f"codex_{RUN_ID}"},
                    "body": {"text": "Хочу консультацию по ремонту через MAX."},
                },
            },
            headers=headers,
            expected=200,
        )
        result = (message.get("results") or [{}])[0]
        if result.get("action") != "marketing_lead_created":
            raise RuntimeError(f"MAX message webhook did not create marketing lead: {message}")
        lead = result.get("lead") or {}
        lead_id = lead.get("id")
        if not lead_id or not str(lead.get("source") or "").startswith("MAX:"):
            raise RuntimeError(f"MAX webhook lead payload is wrong: {message}")

        outbox_id = insert_outbox()
        _, dispatch = api_json(
            "POST",
            "/max/outbox/dispatch?dry_run=true&limit=5",
            headers=headers,
            expected=200,
        )
        planned = next((item for item in dispatch.get("planned") or [] if item.get("id") == outbox_id), None)
        if not planned:
            raise RuntimeError(f"MAX dispatch dry-run did not include queued smoke outbox: {dispatch}")
        attachments = (planned.get("message") or {}).get("attachments") or []
        if not attachments or attachments[0].get("type") != "inline_keyboard":
            raise RuntimeError(f"MAX dispatch dry-run did not build inline keyboard: {planned}")

        print(json.dumps({
            "ok": True,
            "chatId": CHAT_ID,
            "channelId": channel.get("id"),
            "leadId": lead_id,
            "outboxId": outbox_id,
            "checked": [
                "MAX webhook secret header is accepted",
                "bot_added links MAX channel as marketing source",
                "message_created in marketing channel creates CRM lead",
                "outbox dispatch dry-run builds MAX message and inline keyboard",
            ],
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(lead_id, outbox_id)


if __name__ == "__main__":
    main()
