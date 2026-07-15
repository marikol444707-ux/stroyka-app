#!/usr/bin/env python3
import datetime as dt
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:8]
CHAT_ID_FROM_ENV = bool(os.getenv("MAX_MARKETING_SMOKE_CHAT_ID"))
CHAT_ID = os.getenv("MAX_MARKETING_SMOKE_CHAT_ID", f"codex-max-marketing-{RUN_ID}")
TITLE = os.getenv("MAX_MARKETING_SMOKE_TITLE", f"CODEX MAX маркетинг {RUN_ID}")
CAMPAIGN = os.getenv("MAX_MARKETING_SMOKE_CAMPAIGN", f"codex-campaign-{RUN_ID}")
SMOKE_USER_EMAIL = f"max-marketing-smoke-{RUN_ID}@stroyka.local"


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


def smoke_company_id():
    raw = env_value("SMOKE_COMPANY_ID") or env_value("PUBLIC_SITE_COMPANY_ID")
    try:
        company_id = int(raw or 0)
    except (TypeError, ValueError):
        company_id = 0
    if company_id <= 0:
        raise SystemExit("Нужно задать SMOKE_COMPANY_ID или PUBLIC_SITE_COMPANY_ID")
    return company_id


def db_config():
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def b64url(data):
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def hash_password(password):
    salt = uuid.uuid4().hex
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def auth_token_for(user):
    payload = {
        "id": user.get("id"),
        "email": user.get("email") or "",
        "role": user.get("role") or "",
        "name": user.get("name") or "",
        "twoFactorPassed": True,
        "exp": int(time.time()) + 3600,
    }
    body = b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    secret = env_value("AUTH_SECRET") or (env_value("DB_PASSWORD", "password") + "|stroyka-auth")
    signature = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + b64url(signature)


def prepare_smoke_director():
    company_id = smoke_company_id()
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT id,platform_account_id FROM companies WHERE id=%s", (company_id,))
        company = cur.fetchone()
        if not company:
            raise RuntimeError(f"Smoke company #{company_id} not found")
        cur.execute(
            """
            INSERT INTO users (
                name,email,password,role,company_id,platform_account_id,
                assigned_projects,assigned_packages,active,two_factor_required,two_factor_enabled
            ) VALUES (%s,%s,%s,'директор',%s,%s,'[]'::jsonb,'[]'::jsonb,TRUE,FALSE,FALSE)
            RETURNING id,name,email,role
            """,
            (TITLE + " Director", SMOKE_USER_EMAIL, hash_password(uuid.uuid4().hex), company_id, company.get("platform_account_id")),
        )
        user = dict(cur.fetchone())
        cur.execute(
            """
            INSERT INTO user_company_roles (
                user_id,platform_account_id,company_id,role,assigned_projects,assigned_packages,active,is_default
            ) VALUES (%s,%s,%s,'директор','[]'::jsonb,'[]'::jsonb,TRUE,TRUE)
            """,
            (user["id"], company.get("platform_account_id"), company_id),
        )
        token = auth_token_for(user)
        conn.commit()
        return {**user, "token": token, "companyId": company_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


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


def max_bot_token():
    token = env_value("SMOKE_MAX_BOT_TOKEN") or env_value("MAX_WEBHOOK_SECRET") or env_value("MAX_BOT_API_TOKEN")
    token = (token or "").strip()
    if not token or token.lower() in {"change-me", "token", "***", "..."}:
        raise SystemExit("Нужно задать реальный SMOKE_MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET или MAX_BOT_API_TOKEN")
    return token


def cleanup(lead_id=None, channel_id=None, user_id=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        if lead_id:
            cur.execute("DELETE FROM crm_lead_documents WHERE lead_id=%s", (lead_id,))
            cur.execute("DELETE FROM crm_lead_tasks WHERE lead_id=%s", (lead_id,))
            cur.execute("DELETE FROM crm_leads WHERE id=%s", (lead_id,))
        if channel_id and (not CHAT_ID_FROM_ENV or os.getenv("SMOKE_DELETE_CHANNEL") == "1"):
            cur.execute("DELETE FROM messenger_channels WHERE id=%s", (channel_id,))
        if user_id:
            cur.execute("DELETE FROM audit_log WHERE user_id=%s", (user_id,))
            cur.execute("DELETE FROM user_company_roles WHERE user_id=%s", (user_id,))
            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
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
    bot_token = max_bot_token()
    director = prepare_smoke_director()
    director_token = director["token"]
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
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT company_id FROM messenger_channels WHERE id=%s", (channel_id,))
            channel_owner = cur.fetchone()
            cur.execute("SELECT company_id FROM crm_leads WHERE id=%s", (lead_id,))
            lead_owner = cur.fetchone()
        finally:
            cur.close()
            conn.close()
        if not channel_owner or not channel_owner.get("company_id"):
            raise RuntimeError(f"marketing channel has no stored company owner: {channel_owner}")
        if (lead_owner or {}).get("company_id") != channel_owner.get("company_id"):
            raise RuntimeError(
                f"MAX CRM lead owner does not match marketing channel: lead={lead_owner} channel={channel_owner}"
            )

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
                "CRM lead inherits exact stored marketing channel company",
            ],
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(lead_id, channel_id, director.get("id"))


if __name__ == "__main__":
    main()
