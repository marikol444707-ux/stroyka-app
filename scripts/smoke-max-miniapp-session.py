#!/usr/bin/env python3
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
TEST_EMAIL = os.getenv("MAX_MINIAPP_SMOKE_EMAIL", "max-miniapp-session-smoke@stroyka.local")
TEST_NAME = os.getenv("MAX_MINIAPP_SMOKE_NAME", "CODEX QA MAX MiniApp")
TEST_MAX_USER_ID = os.getenv("MAX_MINIAPP_SMOKE_USER_ID", f"codex-max-miniapp-{int(time.time())}")
PASSWORD_HASH_ITERATIONS = 260000


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


def api_json(method, path, data=None, token="", expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=50) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    try:
        return status, json.loads(text) if text else {}
    except json.JSONDecodeError:
        return status, {"raw": text}


def max_initdata_token():
    token = env_value("SMOKE_MAX_INITDATA_TOKEN") or env_value("MAX_BOT_API_TOKEN")
    token = (token or "").strip()
    if not token or token.lower() in {"change-me", "token", "***", "..."}:
        raise SystemExit("Нужно задать SMOKE_MAX_INITDATA_TOKEN или MAX_BOT_API_TOKEN")
    return token


def signed_max_init_data(bot_token, user_id, start_param=""):
    auth_date = str(int(time.time()))
    user = json.dumps({"id": str(user_id), "first_name": "CODEX", "last_name": "MiniApp"}, ensure_ascii=False, separators=(",", ":"))
    chat = json.dumps({"id": str(user_id), "type": "private"}, ensure_ascii=False, separators=(",", ":"))
    params = {
        "auth_date": auth_date,
        "chat": chat,
        "query_id": f"max-miniapp-smoke-{auth_date}",
        "start_param": start_param,
        "user": user,
    }
    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, launch_params.encode("utf-8"), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(params)


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_HASH_ITERATIONS).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def select_project(cur):
    project_name = os.getenv("MAX_MINIAPP_SMOKE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    row = cur.fetchone()
    return (row.get("id"), row.get("name")) if row else (None, "")


def create_linked_foreman():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        project_id, project_name = select_project(cur)
        assigned_projects = [project_name] if project_name else []
        cur.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=LOWER(%s))", (TEST_EMAIL,))
        cur.execute("DELETE FROM messenger_accounts WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=LOWER(%s))", (TEST_EMAIL,))
        cur.execute("DELETE FROM users WHERE LOWER(email)=LOWER(%s)", (TEST_EMAIL,))
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active,two_factor_required,two_factor_enabled)
            VALUES
                (%s,%s,%s,'прораб',%s,%s,%s::jsonb,'[]'::jsonb,TRUE,FALSE,FALSE)
            RETURNING id
            """,
            (
                TEST_NAME,
                TEST_EMAIL,
                hash_password("MaxMiniAppSmoke123!"),
                project_id,
                project_name,
                json.dumps(assigned_projects, ensure_ascii=False),
            ),
        )
        user_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO messenger_accounts
                (provider,user_id,external_user_id,chat_id,display_name,verified_at,enabled)
            VALUES
                ('max',%s,%s,%s,%s,NOW(),TRUE)
            RETURNING id
            """,
            (user_id, TEST_MAX_USER_ID, TEST_MAX_USER_ID, TEST_NAME),
        )
        account_id = cur.fetchone()["id"]
        conn.commit()
        return {"userId": user_id, "accountId": account_id, "projectName": project_name}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def cleanup():
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=LOWER(%s))", (TEST_EMAIL,))
        cur.execute("DELETE FROM messenger_accounts WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=LOWER(%s))", (TEST_EMAIL,))
        cur.execute("DELETE FROM users WHERE LOWER(email)=LOWER(%s)", (TEST_EMAIL,))
        conn.commit()
        cur.close()
        print("cleanup: removed MAX miniapp session smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def main():
    bot_token = max_initdata_token()
    account = create_linked_foreman()
    try:
        _, body = api_json(
            "POST",
            "/max/miniapp/session",
            data={"initData": signed_max_init_data(bot_token, TEST_MAX_USER_ID, "codex-miniapp-session")},
            expected=200,
        )
        user = body.get("user") or {}
        auth_token = user.get("authToken") or ""
        if not body.get("sessionCreated") or not auth_token:
            raise RuntimeError(f"MAX mini-app session не вернул authToken: {body}")
        if user.get("role") != "прораб":
            raise RuntimeError(f"MAX mini-app session вернул неверную роль: {body}")
        linked = body.get("linkedAccount") or {}
        if linked.get("employeeSource") != "users":
            raise RuntimeError(f"MAX mini-app session вернул неверный источник: {body}")
        _, projects = api_json("GET", "/projects", token=auth_token, expected=200)
        if not isinstance(projects, list):
            raise RuntimeError(f"authToken mini-app не открыл /projects: {projects}")
        print(json.dumps({
            "ok": True,
            "userId": account["userId"],
            "messengerAccountId": account["accountId"],
            "projectName": account["projectName"],
            "checked": [
                "MAX initData signature accepted",
                "linked MAX user resolves to Stroyka user",
                "non-2FA foreman receives authToken",
                "issued authToken opens protected /projects API",
            ],
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup()


if __name__ == "__main__":
    main()
