#!/usr/bin/env python3
import datetime as dt
import json
import os
import subprocess
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
INTERNAL_CHAT_ID = os.getenv("MAX_BOT_ADAPTER_SMOKE_CHAT_ID", f"codex-max-internal-{RUN_ID}")
INTERNAL_GROUP_CHAT_ID = os.getenv("MAX_BOT_ADAPTER_GROUP_CHAT_ID", f"-codex-max-group-{RUN_ID}")
MARKETING_CHAT_ID = os.getenv("MAX_BOT_ADAPTER_MARKETING_CHAT_ID", f"codex-max-marketing-{RUN_ID}")
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


def smoke_company_id():
    requested = str(env_value("SMOKE_COMPANY_ID") or "").strip()
    requested_id = None
    if requested:
        try:
            requested_id = int(requested)
        except ValueError as exc:
            raise SystemExit("SMOKE_COMPANY_ID должен быть положительным числом") from exc
        if requested_id <= 0:
            raise SystemExit("SMOKE_COMPANY_ID должен быть положительным числом")
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    if requested_id:
        cur.execute(
            "SELECT id FROM companies WHERE id=%s AND COALESCE(active,TRUE)=TRUE",
            (requested_id,),
        )
    else:
        cur.execute("SELECT id FROM companies WHERE COALESCE(active,TRUE)=TRUE ORDER BY id LIMIT 2")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if requested_id and len(rows) == 1:
        return int(rows[0][0])
    if not requested_id and len(rows) == 1:
        return int(rows[0][0])
    raise SystemExit("Нужно задать SMOKE_COMPANY_ID: активная компания не определена однозначно")


def insert_internal_channel(company_id):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messenger_channels
            (company_id,provider,chat_id,title,channel_type,source_label,default_stage,enabled,metadata_json)
        VALUES
            (%s,'max',%s,%s,'internal','MAX внутренний бот','Новый',TRUE,%s::jsonb)
        ON CONFLICT (provider, chat_id) DO UPDATE SET
            title=EXCLUDED.title,
            company_id=COALESCE(messenger_channels.company_id,EXCLUDED.company_id),
            metadata_json=COALESCE(messenger_channels.metadata_json,'{}'::jsonb) || EXCLUDED.metadata_json,
            enabled=TRUE,
            updated_at=NOW()
        WHERE messenger_channels.company_id IS NULL
           OR messenger_channels.company_id=EXCLUDED.company_id
        RETURNING id
        """,
        (
            company_id,
            INTERNAL_CHAT_ID,
            CHANNEL_TITLE,
            json.dumps({"smokeRunId": RUN_ID, "purpose": "internal bot channel"}, ensure_ascii=False),
        ),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Smoke MAX-канал принадлежит другой компании")
    channel_id = row[0]
    conn.commit()
    cur.close()
    conn.close()
    return channel_id


def cleanup(lead_id=None, outbox_id=None, outbox_ids=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        cleanup_outbox_ids = []
        if outbox_id:
            cleanup_outbox_ids.append(outbox_id)
        cleanup_outbox_ids.extend(outbox_ids or [])
        for item_id in cleanup_outbox_ids:
            cur.execute("DELETE FROM messenger_outbox WHERE id=%s", (item_id,))
        if lead_id:
            cur.execute("DELETE FROM crm_leads WHERE id=%s", (lead_id,))
        if not os.getenv("MAX_BOT_ADAPTER_SMOKE_CHAT_ID"):
            cur.execute("DELETE FROM messenger_channels WHERE provider='max' AND chat_id=%s", (INTERNAL_CHAT_ID,))
        if not os.getenv("MAX_BOT_ADAPTER_GROUP_CHAT_ID"):
            cur.execute("DELETE FROM messenger_channels WHERE provider='max' AND chat_id=%s", (INTERNAL_GROUP_CHAT_ID,))
        if not os.getenv("MAX_BOT_ADAPTER_MARKETING_CHAT_ID"):
            cur.execute("DELETE FROM messenger_channels WHERE provider='max' AND chat_id=%s", (MARKETING_CHAT_ID,))
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


def insert_outbox(company_id):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messenger_outbox
            (owner_scope,company_id,provider,external_user_id,chat_id,event_type,entity_type,entity_id,
             title,body,payload_json,actions_json,status,priority)
        VALUES
            ('company',%s,'max',%s,%s,'codex_max_adapter_smoke','smoke',NULL,
             %s,%s,%s::jsonb,%s::jsonb,'queued',1)
        RETURNING id
        """,
        (
            company_id,
            f"codex-user-{RUN_ID}",
            INTERNAL_CHAT_ID,
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


def insert_legacy_outbox():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messenger_outbox
            (owner_scope,provider,external_user_id,chat_id,event_type,entity_type,entity_id,
             title,body,payload_json,actions_json,status,priority,last_error)
        VALUES
            ('legacy','max',%s,%s,'codex_max_adapter_legacy','smoke',NULL,
             %s,%s,'{}'::jsonb,'[]'::jsonb,'failed',9,'terminal smoke legacy')
        RETURNING id
        """,
        (
            f"codex-legacy-user-{RUN_ID}",
            f"codex-legacy-chat-{RUN_ID}",
            "CODEX MAX legacy smoke",
            "Terminal legacy row must stay outside worker scope.",
        ),
    )
    outbox_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return outbox_id


def insert_marketing_channel(company_id):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messenger_channels
            (company_id,provider,chat_id,title,channel_type,source_label,campaign_code,default_stage,enabled,metadata_json)
        VALUES
            (%s,'max',%s,%s,'marketing','MAX маркетинг',%s,'Новый',TRUE,%s::jsonb)
        ON CONFLICT (provider, chat_id) DO UPDATE SET
            title=EXCLUDED.title,
            channel_type='marketing',
            company_id=COALESCE(messenger_channels.company_id,EXCLUDED.company_id),
            source_label=EXCLUDED.source_label,
            campaign_code=EXCLUDED.campaign_code,
            enabled=TRUE,
            metadata_json=COALESCE(messenger_channels.metadata_json,'{}'::jsonb) || EXCLUDED.metadata_json,
            updated_at=NOW()
        WHERE messenger_channels.company_id IS NULL
           OR messenger_channels.company_id=EXCLUDED.company_id
        RETURNING id
        """,
        (
            company_id,
            MARKETING_CHAT_ID,
            f"CODEX MAX marketing {RUN_ID}",
            f"codex-max-adapter-{RUN_ID}",
            json.dumps({"smokeRunId": RUN_ID, "purpose": "explicit marketing channel"}, ensure_ascii=False),
        ),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Smoke marketing MAX-канал принадлежит другой компании")
    channel_id = row[0]
    conn.commit()
    cur.close()
    conn.close()
    return channel_id


def run_dispatch_cli(token):
    env = os.environ.copy()
    env["SMOKE_MAX_BOT_TOKEN"] = token
    env["BASE_URL"] = BASE_URL
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dispatch-max-outbox.py"),
            "--dry-run",
            "--limit",
            "5",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout or "{}")


def main():
    token = max_bot_token()
    company_id = smoke_company_id()
    headers = {"X-Max-Bot-Api-Secret": token}
    lead_id = None
    outbox_id = None
    help_outbox_id = None
    identity_outbox_id = None
    legacy_outbox_id = None
    try:
        insert_internal_channel(company_id)
        _, linked = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "bot_added",
                "timestamp": int(dt.datetime.now().timestamp()),
                "chat_id": INTERNAL_CHAT_ID,
                "is_channel": True,
                "chat": {"id": INTERNAL_CHAT_ID, "title": CHANNEL_TITLE},
                "user": {"id": f"owner-{RUN_ID}", "first_name": "CODEX", "last_name": "Owner"},
            },
            headers=headers,
            expected=200,
        )
        channel = ((linked.get("results") or [{}])[0]).get("channel") or {}
        if channel.get("chatId") != INTERNAL_CHAT_ID:
            raise RuntimeError(f"MAX webhook did not link channel: {linked}")
        if channel.get("channelType") != "internal":
            raise RuntimeError(f"MAX bot channel should be internal by default: {channel}")

        _, internal_message = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "message_created",
                "timestamp": int(dt.datetime.now().timestamp()),
                "message": {
                    "mid": f"codex-internal-message-{RUN_ID}",
                    "recipient": {"chat_id": INTERNAL_CHAT_ID},
                    "sender": {"user_id": f"internal-user-{RUN_ID}", "username": f"codex_{RUN_ID}"},
                    "body": {"text": "тест"},
                },
            },
            headers=headers,
            expected=200,
        )
        internal_result = (internal_message.get("results") or [{}])[0]
        if internal_result.get("action") != "internal_help_queued":
            raise RuntimeError(f"Internal MAX test message should queue help response, not CRM lead: {internal_message}")
        help_outbox_id = internal_result.get("outboxId")
        if not help_outbox_id:
            raise RuntimeError(f"Internal MAX help response did not expose outbox id: {internal_message}")
        if internal_result.get("intent") != "help":
            raise RuntimeError(f"Internal MAX test message should be handled as help intent: {internal_message}")

        _, identity_message = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "message_created",
                "timestamp": int(dt.datetime.now().timestamp()),
                "message": {
                    "mid": f"codex-internal-id-{RUN_ID}",
                    "recipient": {"chat_id": INTERNAL_CHAT_ID},
                    "sender": {"user_id": f"internal-user-{RUN_ID}", "username": f"codex_{RUN_ID}"},
                    "body": {"text": "id"},
                },
            },
            headers=headers,
            expected=200,
        )
        identity_result = (identity_message.get("results") or [{}])[0]
        if identity_result.get("action") != "internal_help_queued" or identity_result.get("intent") != "identity":
            raise RuntimeError(f"Internal MAX id command should queue identity response: {identity_message}")
        identity_outbox_id = identity_result.get("outboxId")
        if not identity_outbox_id:
            raise RuntimeError(f"Internal MAX identity response did not expose outbox id: {identity_message}")

        _, random_group_message = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "message_created",
                "timestamp": int(dt.datetime.now().timestamp()),
                "message": {
                    "mid": f"codex-internal-random-{RUN_ID}",
                    "recipient": {"chat_id": INTERNAL_GROUP_CHAT_ID},
                    "sender": {"user_id": f"group-user-{RUN_ID}", "username": f"codex_group_{RUN_ID}"},
                    "body": {"text": "просто рабочий разговор"},
                },
            },
            headers=headers,
            expected=200,
        )
        random_group_result = (random_group_message.get("results") or [{}])[0]
        if random_group_result.get("action") != "message_ignored":
            raise RuntimeError(f"Random internal group message should stay silent: {random_group_message}")

        marketing_channel_id = insert_marketing_channel(company_id)
        _, message = api_json(
            "POST",
            "/max/webhook",
            data={
                "update_type": "message_created",
                "timestamp": int(dt.datetime.now().timestamp()),
                "message": {
                    "mid": f"codex-marketing-message-{RUN_ID}",
                    "recipient": {"chat_id": MARKETING_CHAT_ID},
                    "sender": {"user_id": f"lead-user-{RUN_ID}", "username": f"codex_lead_{RUN_ID}"},
                    "body": {"text": "Хочу консультацию по ремонту через MAX."},
                },
            },
            headers=headers,
            expected=200,
        )
        result = (message.get("results") or [{}])[0]
        if result.get("action") != "marketing_lead_created":
            raise RuntimeError(f"Explicit marketing MAX channel did not create CRM lead: {message}")
        lead = result.get("lead") or {}
        lead_id = lead.get("id")
        if not lead_id or not str(lead.get("source") or "").startswith("MAX:"):
            raise RuntimeError(f"MAX webhook lead payload is wrong: {message}")

        outbox_id = insert_outbox(company_id)
        legacy_outbox_id = insert_legacy_outbox()
        _, worker_items = api_json(
            "GET",
            "/max/outbox?status=all&limit=100",
            headers=headers,
            expected=200,
        )
        worker_ids = {int(item.get("id") or 0) for item in worker_items.get("items") or []}
        if outbox_id not in worker_ids:
            raise RuntimeError(f"Company-owned smoke outbox is missing from worker scope: {worker_items}")
        if legacy_outbox_id in worker_ids:
            raise RuntimeError(f"Terminal legacy outbox leaked into worker scope: {worker_items}")
        api_json(
            "POST",
            f"/max/outbox/{legacy_outbox_id}/status",
            data={"status": "queued"},
            headers=headers,
            expected=404,
        )
        _, status = api_json(
            "GET",
            "/max/bot/status",
            headers=headers,
            expected=200,
        )
        if not any(item.get("chatId") == INTERNAL_CHAT_ID and item.get("channelType") == "internal" for item in status.get("channels") or []):
            raise RuntimeError(f"MAX bot status does not expose internal channel: {status}")
        if not any(item.get("chatId") == MARKETING_CHAT_ID and item.get("channelType") == "marketing" for item in status.get("channels") or []):
            raise RuntimeError(f"MAX bot status does not expose explicit marketing channel: {status}")
        if int((status.get("outboxSummary") or {}).get("queued") or 0) < 1:
            raise RuntimeError(f"MAX bot status does not show queued outbox: {status}")

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

        _, skipped = api_json(
            "POST",
            f"/max/outbox/{outbox_id}/status",
            data={"status": "skipped", "error": "smoke transition"},
            headers=headers,
            expected=200,
        )
        skipped_item = skipped.get("item") or {}
        if skipped_item.get("status") != "skipped" or skipped_item.get("companyId") != company_id:
            raise RuntimeError(f"Company-owned outbox was not marked skipped: {skipped}")
        _, requeued = api_json(
            "POST",
            f"/max/outbox/{outbox_id}/status",
            data={"status": "queued"},
            headers=headers,
            expected=200,
        )
        if (requeued.get("item") or {}).get("status") != "queued":
            raise RuntimeError(f"Company-owned outbox was not requeued: {requeued}")

        cli_dispatch = run_dispatch_cli(token)
        cli_planned = next((item for item in cli_dispatch.get("planned") or [] if item.get("id") == outbox_id), None)
        if not cli_planned:
            raise RuntimeError(f"MAX dispatch CLI dry-run did not include queued smoke outbox: {cli_dispatch}")

        print(json.dumps({
            "ok": True,
            "internalChatId": INTERNAL_CHAT_ID,
            "internalChannelId": channel.get("id"),
            "marketingChatId": MARKETING_CHAT_ID,
            "marketingChannelId": marketing_channel_id,
            "leadId": lead_id,
            "outboxId": outbox_id,
            "legacyOutboxId": legacy_outbox_id,
            "companyId": company_id,
            "checked": [
                "MAX webhook secret header is accepted",
                "bot_added links MAX bot channel as internal by default",
                "message_created test in internal MAX channel queues help response without CRM lead",
                "message_created id in internal MAX channel queues identity binding response",
                "random internal MAX group message stays silent",
                "message_created in explicit marketing MAX channel creates CRM lead",
                "max bot status exposes channels and outbox through /max route",
                "worker list excludes terminal legacy outbox rows",
                "status callback cannot requeue terminal legacy outbox rows",
                "outbox dispatch dry-run builds MAX message and inline keyboard",
                "company-owned outbox status can move skipped -> queued",
                "outbox dispatch CLI dry-run is ready for cron/systemd timer",
            ],
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(
            lead_id,
            outbox_id,
            [item for item in (help_outbox_id, identity_outbox_id, legacy_outbox_id) if item],
        )


if __name__ == "__main__":
    main()
