#!/usr/bin/env python3
import datetime as dt
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
TEST_EMAIL = os.getenv("OWN_EXPENSE_SMOKE_USER_EMAIL", "own-expense-smoke@stroyka.local")
TEST_NAME = os.getenv("OWN_EXPENSE_SMOKE_USER_NAME", "CODEX QA Мои траты")
TEST_ROLE = os.getenv("OWN_EXPENSE_SMOKE_USER_ROLE", "мастер")


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


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def api_json(method, path, token=None, data=None, expected=None):
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise SystemExit(f"FAIL {method} {path}: got {status}, expected {expected}. Body: {text[:500]}")
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


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken")
    if not token:
        raise SystemExit(f"FAIL login {email}: authToken не получен")
    return token


def prepare_temp_worker():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("OWN_EXPENSE_SMOKE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    if not project:
        cur.close()
        conn.close()
        raise SystemExit("FAIL: нет активного объекта для smoke «Мои траты»")

    password = secrets.token_urlsafe(12)
    password_hash = hash_password(password)
    assigned_projects = json.dumps([project["name"]], ensure_ascii=False)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (TEST_EMAIL,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            """
            UPDATE users
               SET name=%s,
                   email=%s,
                   password=%s,
                   role=%s,
                   project_id=%s,
                   project_name=%s,
                   assigned_projects=%s::jsonb,
                   assigned_packages='[]'::jsonb,
                   active=TRUE,
                   failed_login_count=0,
                   locked_until=NULL
             WHERE id=%s
            """,
            (
                TEST_NAME,
                TEST_EMAIL,
                password_hash,
                TEST_ROLE,
                project["id"],
                project["name"],
                assigned_projects,
                existing["id"],
            ),
        )
        user_id = existing["id"]
    else:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active)
            VALUES
                (%s,%s,%s,%s,%s,%s,%s::jsonb,'[]'::jsonb,TRUE)
            RETURNING id
            """,
            (
                TEST_NAME,
                TEST_EMAIL,
                password_hash,
                TEST_ROLE,
                project["id"],
                project["name"],
                assigned_projects,
            ),
        )
        user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": user_id, "name": TEST_NAME, "email": TEST_EMAIL, "password": password, "projectName": project["name"]}


def find_by_id(rows, row_id):
    for row in rows:
        if str(row.get("id")) == str(row_id):
            return row
    return None


def main():
    director_email = require_env("SMOKE_EMAIL")
    director_password = require_env("SMOKE_PASSWORD")
    director_token = login(director_email, director_password)
    worker = prepare_temp_worker()
    worker_token = login(worker["email"], worker["password"])
    description = f"codex web own expense smoke {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}"
    amount = 23.45
    own_expense_id = None

    try:
        _, created = api_json(
            "POST",
            "/own-expenses",
            token=worker_token,
            data={
                "projectName": worker["projectName"],
                "description": description,
                "amount": amount,
                "category": "other",
            },
            expected=200,
        )
        own_expense_id = created.get("id")
        expense_id = created.get("expenseId")
        if not own_expense_id or not expense_id:
            raise SystemExit(f"FAIL create: не получены id/expenseId: {created}")

        query = urllib.parse.urlencode({"project_name": worker["projectName"]})
        _, own_rows = api_json("GET", f"/own-expenses?{query}", token=director_token, expected=200)
        own_row = find_by_id(own_rows, own_expense_id)
        if not own_row:
            raise SystemExit("FAIL own-expenses: созданная трата не найдена")
        if own_row.get("employeeName") != TEST_NAME:
            raise SystemExit(f"FAIL own-expenses employee: {own_row}")
        if abs(float(own_row.get("amount") or 0) - amount) > 0.001:
            raise SystemExit(f"FAIL own-expenses amount: {own_row}")

        query = urllib.parse.urlencode({"project": worker["projectName"]})
        _, expense_rows = api_json("GET", f"/expenses?{query}", token=director_token, expected=200)
        expense_row = find_by_id(expense_rows, expense_id)
        if not expense_row:
            raise SystemExit("FAIL expenses: синхронный расход объекта не найден")
        if abs(float(expense_row.get("amount") or 0) - amount) > 0.001:
            raise SystemExit(f"FAIL expenses amount: {expense_row}")
        if expense_row.get("source") != "own_expense" or str(expense_row.get("ownExpenseId")) != str(own_expense_id):
            raise SystemExit(f"FAIL expenses source link: {expense_row}")

        api_json(
            "PUT",
            f"/own-expenses/{own_expense_id}",
            token=director_token,
            data={"status": "Возмещено", "approvedBy": "Codex smoke"},
            expected=200,
        )
        _, own_rows = api_json("GET", f"/own-expenses?{urllib.parse.urlencode({'project_name': worker['projectName']})}", token=director_token, expected=200)
        own_row = find_by_id(own_rows, own_expense_id)
        if not own_row or own_row.get("status") != "Возмещено":
            raise SystemExit(f"FAIL status update: {own_row}")

        print(json.dumps({
            "ok": True,
            "projectName": worker["projectName"],
            "worker": worker["email"],
            "ownExpenseId": own_expense_id,
            "expenseId": expense_id,
            "checked": ["web own-expenses create", "own_expenses list", "expenses sync", "status update"],
        }, ensure_ascii=False, indent=2))
    finally:
        if own_expense_id:
            try:
                api_json("DELETE", f"/own-expenses/{own_expense_id}", token=director_token, expected=200)
                print("cleanup: deleted own_expense and linked expense", own_expense_id)
            except Exception as exc:
                print(f"cleanup warning: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
