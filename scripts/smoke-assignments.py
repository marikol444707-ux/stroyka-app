#!/usr/bin/env python3
import datetime as dt
import json
import os
import subprocess
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
TEST_EMAIL = os.getenv("ASSIGNMENT_SMOKE_MASTER_EMAIL", "assignment-master-smoke@stroyka.local")
TEST_NAME = os.getenv("ASSIGNMENT_SMOKE_MASTER_NAME", "CODEX QA Поручения мастер")
TEST_PASSWORD = os.getenv("ASSIGNMENT_SMOKE_MASTER_PASSWORD", "AssignmentSmoke123!")


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


def api_json(method, path, token=None, data=None, expected=None):
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
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
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


def select_project():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("ASSIGNMENT_SMOKE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    cur.close()
    conn.close()
    if not project:
        raise SystemExit("FAIL: нет активного объекта для smoke поручений")
    return project["name"]


def ensure_master(project_name):
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "manage-temp-user.py"),
            "create",
            "--email",
            TEST_EMAIL,
            "--name",
            TEST_NAME,
            "--password",
            TEST_PASSWORD,
            "--role",
            "мастер",
            "--project",
            project_name,
            "--package",
            "Основная",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def cleanup(task_id):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        if task_id:
            cur.execute("DELETE FROM ai_task_attachments WHERE task_id=%s", (task_id,))
            cur.execute("DELETE FROM ai_task_reports WHERE task_id=%s", (task_id,))
            cur.execute("DELETE FROM ai_tasks WHERE id=%s", (task_id,))
        cur.execute("UPDATE users SET active=FALSE WHERE LOWER(email)=LOWER(%s)", (TEST_EMAIL,))
        conn.commit()
        cur.close()
        print("cleanup: removed assignment smoke rows")
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
    project_name = select_project()
    ensure_master(project_name)
    master_token = login(TEST_EMAIL, TEST_PASSWORD)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    task_id = None
    try:
        _, task = api_json(
            "POST",
            "/ai-tasks",
            token=director_token,
            data={
                "projectName": project_name,
                "title": f"CODEX QA поручение {stamp}",
                "description": "Проверить smoke-цепочку поручений",
                "assignedRole": "мастер",
                "assignedTo": TEST_NAME,
                "actionLabel": "Открыть объект",
                "actionPayload": json.dumps({"type": "manual_assignment", "dedupeKey": f"assignment-smoke:{stamp}"}, ensure_ascii=False),
                "dedupeKey": f"assignment-smoke:{stamp}",
            },
            expected=200,
        )
        task_id = task.get("id")
        if not task_id:
            raise RuntimeError(f"POST /ai-tasks не вернул id: {task}")

        _, accepted = api_json("POST", f"/ai-tasks/{task_id}/accept", token=master_token, data={}, expected=200)
        if accepted.get("status") != "В работе":
            raise RuntimeError(f"Поручение не взято в работу: {accepted}")

        _, report = api_json(
            "POST",
            f"/ai-tasks/{task_id}/reports",
            token=master_token,
            data={
                "text": "Smoke отчет: задача взята и выполнена",
                "attachments": [{"url": "/uploads/smoke/assignment-report.jpg", "type": "photo", "source": "smoke"}],
            },
            expected=200,
        )
        updated_task = report.get("task") or {}
        if updated_task.get("status") != "На проверке":
            raise RuntimeError(f"Отчет не перевел поручение на проверку: {report}")
        if int(updated_task.get("reportsCount") or 0) < 1:
            raise RuntimeError(f"Отчет не записался в счетчик поручения: {report}")

        _, assignments = api_json("GET", f"/assignments?project_name={urllib.parse.quote(project_name)}", token=director_token, expected=200)
        assignment = next((row for row in assignments if str(row.get("id")) == str(task_id)), None)
        if not assignment:
            raise RuntimeError("/assignments не вернул созданное поручение")
        if not assignment.get("latestReport"):
            raise RuntimeError("/assignments не вернул последний отчет")

        _, closed = api_json(
            "POST",
            f"/ai-tasks/{task_id}/close",
            token=director_token,
            data={"status": "Закрыто", "comment": "Smoke закрытие директором"},
            expected=200,
        )
        if (closed.get("task") or {}).get("status") != "Закрыто":
            raise RuntimeError(f"Поручение не закрылось директором: {closed}")

        print(json.dumps({
            "ok": True,
            "projectName": project_name,
            "taskId": task_id,
            "checked": [
                "director creates assignment in ai_tasks",
                "assigned master can take it into work",
                "master report with photo attachment is saved",
                "assignment moves to review after report",
                "director sees report through /assignments and closes task",
            ],
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        raise SystemExit(f"FAIL smoke:assignments: {exc}")
    finally:
        cleanup(task_id)


if __name__ == "__main__":
    main()
