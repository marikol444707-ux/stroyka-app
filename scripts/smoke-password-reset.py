#!/usr/bin/env python3
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
TEST_EMAIL = os.getenv("PASSWORD_RESET_SMOKE_EMAIL", "password-reset-smoke@stroyka.local")
TEST_NAME = os.getenv("PASSWORD_RESET_SMOKE_NAME", "CODEX QA Восстановление пароля")


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


def db_conn():
    return psycopg2.connect(**db_config())


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def api_json(method, path, data=None, expected=None):
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise SystemExit(f"FAIL {method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def login_status(email, password):
    status, body = api_json("POST", "/login", data={"email": email, "password": password})
    return status, body


def prepare_user():
    password = secrets.token_urlsafe(12)
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (TEST_EMAIL,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            """
            UPDATE users
               SET name=%s,
                   email=%s,
                   password=%s,
                   role='директор',
                   project_id=NULL,
                   project_name='',
                   assigned_projects='[]'::jsonb,
                   assigned_packages='[]'::jsonb,
                   reset_token=NULL,
                   reset_token_expires=NULL,
                   active=TRUE,
                   failed_login_count=0,
                   locked_until=NULL
             WHERE id=%s
         RETURNING id, name, email
            """,
            (TEST_NAME, TEST_EMAIL, hash_password(password), existing["id"]),
        )
    else:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active)
            VALUES
                (%s,%s,%s,'директор',NULL,'','[]'::jsonb,'[]'::jsonb,TRUE)
            RETURNING id, name, email
            """,
            (TEST_NAME, TEST_EMAIL, hash_password(password)),
        )
    row = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    row["password"] = password
    return row


def fetch_reset_code(user_id):
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT reset_token, reset_token_expires
          FROM users
         WHERE id=%s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not row["reset_token"]:
        raise SystemExit("FAIL reset request: код восстановления не записан в БД")
    return row["reset_token"], row["reset_token_expires"]


def check_reset_task_closed(user_id):
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT status
          FROM ai_tasks
         WHERE project_name='Система'
           AND dedupe_key=%s
         ORDER BY updated_at DESC, id DESC
         LIMIT 1
        """,
        (f"PASSWORD_RESET:{user_id}",),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["status"] if row else None


def clear_reset_state(user_id):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
           SET reset_token=NULL,
               reset_token_expires=NULL,
               failed_login_count=0,
               locked_until=NULL
         WHERE id=%s
        """,
        (user_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def main():
    user = prepare_user()
    new_password = secrets.token_urlsafe(14)

    try:
        old_status, _ = login_status(user["email"], user["password"])
        if old_status != 200:
            raise SystemExit(f"FAIL initial login: got {old_status}")

        _, reset_request = api_json(
            "POST",
            "/password-reset-request",
            data={"email": user["email"]},
            expected=200,
        )
        if not reset_request.get("ok"):
            raise SystemExit(f"FAIL reset request body: {reset_request}")

        code, expires = fetch_reset_code(user["id"])
        if not (str(code).isdigit() and len(str(code)) == 6):
            raise SystemExit(f"FAIL reset code format: {code!r}")
        if not expires:
            raise SystemExit("FAIL reset code: срок действия не задан")

        api_json(
            "POST",
            "/password-reset",
            data={"email": user["email"], "code": code, "newPassword": new_password},
            expected=200,
        )

        old_status, _ = login_status(user["email"], user["password"])
        if old_status == 200:
            raise SystemExit("FAIL old password: старый пароль продолжает работать")

        new_status, body = login_status(user["email"], new_password)
        if new_status != 200 or not body.get("authToken"):
            raise SystemExit(f"FAIL new password login: got {new_status}, body={body}")

        task_status = check_reset_task_closed(user["id"])
        if task_status and task_status != "Закрыто":
            raise SystemExit(f"FAIL reset ai task: статус {task_status!r}, ожидали 'Закрыто'")

        print(json.dumps({
            "ok": True,
            "email": user["email"],
            "emailSent": bool(reset_request.get("emailSent")),
            "aiTaskStatus": task_status,
            "checked": [
                "temporary user login",
                "password-reset-request",
                "reset code stored with expiry",
                "password-reset",
                "old password rejected",
                "new password accepted",
                "password reset task closed",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        try:
            clear_reset_state(user["id"])
        except Exception as exc:
            print(f"cleanup warning: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
