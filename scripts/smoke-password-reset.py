#!/usr/bin/env python3
import hashlib
import json
import os
import re
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
TEST_EMAIL_PREFIX = os.getenv("PASSWORD_RESET_SMOKE_EMAIL_PREFIX", "password-reset-smoke")
TEST_EMAIL_DOMAIN = os.getenv("PASSWORD_RESET_SMOKE_EMAIL_DOMAIN", "stroyka.local")
TEST_NAME = os.getenv("PASSWORD_RESET_SMOKE_NAME", "CODEX QA Восстановление пароля")
TWO_FACTOR_ROLES = {"директор", "зам_директора", "бухгалтер"}

DEFAULT_ROLES = [
    ("директор", "director"),
    ("зам_директора", "deputy"),
    ("главный_инженер", "chief-engineer"),
    ("прораб", "foreman"),
    ("кладовщик", "warehouse"),
    ("бухгалтер", "accountant"),
    ("снабженец", "supply"),
    ("стройконтроль", "construction-control"),
    ("менеджер_crm", "crm-manager"),
    ("сметчик", "estimator"),
    ("субподрядчик", "subcontractor"),
    ("мастер", "master"),
    ("бригадир", "brigadier"),
    ("технадзор", "tech-supervision"),
    ("заказчик", "customer"),
    ("поставщик", "supplier"),
    ("system_owner", "system-owner"),
]


def smoke_roles():
    raw = os.getenv("PASSWORD_RESET_SMOKE_ROLES", "").strip()
    if not raw:
        return DEFAULT_ROLES
    known = dict(DEFAULT_ROLES)
    roles = []
    for role in [item.strip() for item in raw.split(",") if item.strip()]:
        roles.append((role, known.get(role, role.replace("_", "-"))))
    return roles


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


def login_accepts_password(status, body):
    if status != 200 or not isinstance(body, dict):
        return False
    return bool(body.get("authToken") or body.get("twoFactorRequired") or body.get("twoFactorSetupRequired"))


def login_state(body):
    if not isinstance(body, dict):
        return type(body).__name__
    if body.get("authToken"):
        return "authToken"
    if body.get("twoFactorRequired"):
        return "twoFactorRequired"
    if body.get("twoFactorSetupRequired"):
        return "twoFactorSetupRequired"
    return ",".join(sorted(body.keys())) or "empty"


def test_email(slug):
    return f"{TEST_EMAIL_PREFIX}-{slug}@{TEST_EMAIL_DOMAIN}".lower()


def prepare_user(role, slug):
    email = test_email(slug)
    password = secrets.token_urlsafe(12)
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
    existing = cur.fetchone()
    name = f"{TEST_NAME} · {role}"
    if existing:
        cur.execute(
            """
            UPDATE users
               SET name=%s,
                   email=%s,
                   password=%s,
                   role=%s,
                   project_id=NULL,
                   project_name='',
                   assigned_projects='[]'::jsonb,
                   assigned_packages='[]'::jsonb,
                   reset_token=NULL,
                   reset_token_expires=NULL,
                   active=TRUE,
                   failed_login_count=0,
                   locked_until=NULL,
                   two_factor_required=%s,
                   two_factor_enabled=FALSE,
                   two_factor_secret=NULL,
                   two_factor_confirmed_at=NULL
             WHERE id=%s
         RETURNING id, name, email
            """,
            (name, email, hash_password(password), role, role in TWO_FACTOR_ROLES, existing["id"]),
        )
    else:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active,two_factor_required)
            VALUES
                (%s,%s,%s,%s,NULL,'','[]'::jsonb,'[]'::jsonb,TRUE,%s)
            RETURNING id, name, email
            """,
            (name, email, hash_password(password), role, role in TWO_FACTOR_ROLES),
        )
    row = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    row["password"] = password
    row["role"] = role
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
    if not row or not row["reset_token"]:
        cur.close()
        conn.close()
        raise SystemExit("FAIL reset request: код восстановления не записан в БД")
    token = str(row["reset_token"])
    expires = row["reset_token_expires"]
    if token.isdigit() and len(token) == 6:
        cur.close()
        conn.close()
        return token, expires, "legacy_plaintext"
    cur.execute(
        """
        SELECT description
          FROM ai_tasks
         WHERE project_name='Система'
           AND dedupe_key=%s
         ORDER BY updated_at DESC, id DESC
         LIMIT 1
        """,
        (f"PASSWORD_RESET:{user_id}",),
    )
    task = cur.fetchone()
    cur.close()
    conn.close()
    match = re.search(r"Код:\s*(\d{6})", task["description"] if task else "")
    if not match:
        raise SystemExit("FAIL reset request: код не найден в fallback-задаче для smoke email")
    return match.group(1), expires, "hashed"


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
               locked_until=NULL,
               two_factor_enabled=FALSE,
               two_factor_secret=NULL,
               two_factor_confirmed_at=NULL
         WHERE id=%s
        """,
        (user_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def check_role(role, slug):
    user = prepare_user(role, slug)
    new_password = secrets.token_urlsafe(14)

    try:
        old_status, old_body = login_status(user["email"], user["password"])
        if not login_accepts_password(old_status, old_body):
            raise RuntimeError(f"initial login rejected: status={old_status}, state={login_state(old_body)}")

        _, reset_request = api_json(
            "POST",
            "/password-reset-request",
            data={"email": user["email"]},
            expected=200,
        )
        if not reset_request.get("ok"):
            raise RuntimeError(f"reset request body: {reset_request}")

        code, expires, token_storage = fetch_reset_code(user["id"])
        if not (str(code).isdigit() and len(str(code)) == 6):
            raise RuntimeError(f"reset code format: {code!r}")
        if not expires:
            raise RuntimeError("reset code: срок действия не задан")
        if token_storage != "hashed":
            raise RuntimeError(f"reset code storage: ожидали hashed, получили {token_storage}")

        api_json(
            "POST",
            "/password-reset",
            data={"email": user["email"], "code": code, "newPassword": new_password},
            expected=200,
        )

        old_status, old_body = login_status(user["email"], user["password"])
        if login_accepts_password(old_status, old_body):
            raise RuntimeError("old password: старый пароль продолжает работать")

        new_status, body = login_status(user["email"], new_password)
        if not login_accepts_password(new_status, body):
            raise RuntimeError(f"new password login rejected: status={new_status}, state={login_state(body)}")

        task_status = check_reset_task_closed(user["id"])
        if task_status and task_status != "Закрыто":
            raise RuntimeError(f"reset ai task: статус {task_status!r}, ожидали 'Закрыто'")

        return {
            "role": role,
            "email": user["email"],
            "emailSent": bool(reset_request.get("emailSent")),
            "aiTaskStatus": task_status,
            "loginState": login_state(body),
            "checked": [
                "temporary user login",
                "password-reset-request",
                "reset code stored as hash with expiry",
                "password-reset",
                "old password rejected",
                "new password accepted",
                "password reset task closed",
            ],
        }
    finally:
        try:
            clear_reset_state(user["id"])
        except Exception as exc:
            print(f"cleanup warning: {exc}", file=sys.stderr)


def main():
    results = []
    failures = []
    for role, slug in smoke_roles():
        try:
            results.append(check_role(role, slug))
        except Exception as exc:
            failures.append({"role": role, "error": str(exc)})

    summary = {
        "ok": not failures,
        "baseUrl": BASE_URL,
        "checkedRoles": len(results),
        "failedRoles": len(failures),
        "roles": results,
        "failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
