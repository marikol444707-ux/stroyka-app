#!/usr/bin/env python3
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import subprocess
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
TEST_EMAIL = os.getenv("ASSIGNMENT_SMOKE_MASTER_EMAIL", "assignment-master-smoke@stroyka.local")
TEST_NAME = os.getenv("ASSIGNMENT_SMOKE_MASTER_NAME", "CODEX QA Поручения мастер")
TEST_PASSWORD = os.getenv("ASSIGNMENT_SMOKE_MASTER_PASSWORD", "AssignmentSmoke123!")
OTHER_EMAIL = os.getenv("ASSIGNMENT_SMOKE_OTHER_EMAIL", "assignment-other-master-smoke@stroyka.local")
OTHER_NAME = os.getenv("ASSIGNMENT_SMOKE_OTHER_NAME", "CODEX QA Поручения другой мастер")
OTHER_PASSWORD = os.getenv("ASSIGNMENT_SMOKE_OTHER_PASSWORD", "AssignmentSmokeOther123!")


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


def totp_code(secret):
    secret = re.sub(r"\s+", "", str(secret or "")).upper()
    if not secret:
        raise RuntimeError("Нет TOTP secret для 2FA")
    secret += "=" * (-len(secret) % 8)
    key = base64.b32decode(secret, casefold=True)
    counter = int(time.time()) // 30
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
    return str(code).zfill(6)


def token_from_login_response(body, email):
    token = body.get("authToken")
    if token:
        return token
    if body.get("twoFactorSetupRequired"):
        setup_token = body.get("setupToken")
        secret = env_value("SMOKE_TOTP_SECRET") or body.get("manualKey") or ""
        if not setup_token or not secret:
            raise SystemExit(f"FAIL login {email}: 2FA setup не вернул setupToken/manualKey")
        _, confirmed = api_json(
            "POST",
            "/login/2fa/setup-confirm",
            data={"setupToken": setup_token, "code": totp_code(secret)},
            expected=200,
        )
        token = confirmed.get("authToken")
        if token:
            return token
        raise SystemExit(f"FAIL login {email}: authToken не получен после 2FA setup")
    if body.get("twoFactorRequired"):
        challenge_token = body.get("challengeToken")
        code = env_value("SMOKE_2FA_CODE") or (totp_code(env_value("SMOKE_TOTP_SECRET")) if env_value("SMOKE_TOTP_SECRET") else "")
        if not challenge_token or not code:
            raise SystemExit(f"FAIL login {email}: нужен SMOKE_2FA_CODE или SMOKE_TOTP_SECRET")
        _, verified = api_json(
            "POST",
            "/login/2fa/verify",
            data={"challengeToken": challenge_token, "code": code},
            expected=200,
        )
        token = verified.get("authToken")
        if token:
            return token
        raise SystemExit(f"FAIL login {email}: authToken не получен после 2FA")
    raise SystemExit(f"FAIL login {email}: authToken не получен")


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    return token_from_login_response(body, email)


def select_project():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("ASSIGNMENT_SMOKE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id,name,company_id FROM projects WHERE name=%s ORDER BY id LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id,name,company_id FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    cur.close()
    conn.close()
    if not project:
        raise SystemExit("FAIL: нет активного объекта для smoke поручений")
    if not project.get("company_id"):
        raise SystemExit("FAIL: у smoke-объекта не определена компания")
    return dict(project)


def ensure_worker(project_name, email, name, password, role="мастер"):
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "manage-temp-user.py"),
            "create",
            "--email",
            email,
            "--name",
            name,
            "--password",
            password,
            "--role",
            role,
            "--project",
            project_name,
            "--package",
            "Основная",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def insert_system_assignment(project, stamp):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor()
    project_id = project["id"]
    company_id = project["company_id"]
    cur.execute(
        """
        INSERT INTO ai_tasks (
            project_name, title, description, assigned_role, assigned_to, status,
            action_label, action_payload, dedupe_key, created_by,
            owner_scope, company_id, project_id, created_at, updated_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'company',%s,%s,NOW(),NOW())
        RETURNING id
        """,
        (
            project["name"],
            f"CODEX QA ИИ-поручение {stamp}",
            "Smoke: системное поручение должно быть скрыто из рабочего списка",
            "мастер",
            "",
            "Новое",
            "Открыть ИИ-контроль",
            json.dumps({"type": "room_measurement_review", "source": "system_rules"}, ensure_ascii=False),
            f"ROOM_CONTROL:assignment-smoke:{stamp}",
            "ИИ-контроль",
            company_id,
            project_id,
        ),
    )
    task_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return task_id


def verify_task_child_owners(task_id):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT t.owner_scope AS task_scope,
                   t.company_id AS task_company_id,
                   t.project_id AS task_project_id,
                   r.owner_scope AS report_scope,
                   r.company_id AS report_company_id,
                   r.project_id AS report_project_id,
                   a.owner_scope AS attachment_scope,
                   a.company_id AS attachment_company_id,
                   a.project_id AS attachment_project_id
              FROM ai_tasks t
              JOIN ai_task_reports r ON r.task_id=t.id
              JOIN ai_task_attachments a ON a.report_id=r.id AND a.task_id=t.id
             WHERE t.id=%s
             ORDER BY r.id DESC,a.id DESC
             LIMIT 1
            """,
            (task_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Отчёт или вложение поручения не найдены для owner-проверки")
        expected = (row["task_scope"], row["task_company_id"], row["task_project_id"])
        report_owner = (row["report_scope"], row["report_company_id"], row["report_project_id"])
        attachment_owner = (row["attachment_scope"], row["attachment_company_id"], row["attachment_project_id"])
        if report_owner != expected or attachment_owner != expected:
            raise RuntimeError(
                f"Owner отчёта/вложения не совпал с задачей: task={expected}, "
                f"report={report_owner}, attachment={attachment_owner}"
            )
    finally:
        cur.close()
        conn.close()


def cleanup(task_ids):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        ids = [task_id for task_id in (task_ids or []) if task_id]
        if ids:
            cur.execute("DELETE FROM ai_task_attachments WHERE task_id=ANY(%s)", (ids,))
            cur.execute("DELETE FROM ai_task_reports WHERE task_id=ANY(%s)", (ids,))
            cur.execute("DELETE FROM ai_tasks WHERE id=ANY(%s)", (ids,))
        cur.execute("UPDATE users SET active=FALSE WHERE LOWER(email)=ANY(%s)", ([TEST_EMAIL.lower(), OTHER_EMAIL.lower()],))
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
    project = select_project()
    project_name = project["name"]
    ensure_worker(project_name, TEST_EMAIL, TEST_NAME, TEST_PASSWORD)
    ensure_worker(project_name, OTHER_EMAIL, OTHER_NAME, OTHER_PASSWORD)
    master_token = login(TEST_EMAIL, TEST_PASSWORD)
    other_token = login(OTHER_EMAIL, OTHER_PASSWORD)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    task_id = None
    system_task_id = None
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
        system_task_id = insert_system_assignment(project, stamp)

        encoded_project = urllib.parse.quote(project_name)
        _, director_default = api_json("GET", f"/assignments?project_name={encoded_project}", token=director_token, expected=200)
        if any(str(row.get("id")) == str(system_task_id) for row in director_default):
            raise RuntimeError("/assignments по умолчанию показал ИИ-поручение")

        _, director_with_system = api_json(
            "GET",
            f"/assignments?project_name={encoded_project}&include_system=true",
            token=director_token,
            expected=200,
        )
        system_row = next((row for row in director_with_system if str(row.get("id")) == str(system_task_id)), None)
        if not system_row or not system_row.get("systemGenerated"):
            raise RuntimeError("/assignments?include_system=true не вернул системное поручение с признаком systemGenerated")

        _, master_assignments = api_json("GET", f"/assignments?project_name={encoded_project}", token=master_token, expected=200)
        if not any(str(row.get("id")) == str(task_id) for row in master_assignments):
            raise RuntimeError("назначенный мастер не видит свое поручение")
        if any(str(row.get("id")) == str(system_task_id) for row in master_assignments):
            raise RuntimeError("мастер увидел ИИ-поручение в рабочем списке")

        _, other_assignments = api_json("GET", f"/assignments?project_name={encoded_project}", token=other_token, expected=200)
        if any(str(row.get("id")) == str(task_id) for row in other_assignments):
            raise RuntimeError("другой мастер той же роли увидел поручение с точным исполнителем")
        api_json("POST", f"/ai-tasks/{task_id}/accept", token=other_token, data={}, expected=403)

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
        verify_task_child_owners(task_id)

        _, assignments = api_json("GET", f"/assignments?project_name={encoded_project}", token=director_token, expected=200)
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
                "default assignments hide AI-generated tasks",
                "include_system exposes AI-generated tasks for leadership",
                "assigned user sees exact assignment",
                "same-role non-assignee cannot see or accept exact assignment",
                "assigned master can take it into work",
                "master report with photo attachment is saved",
                "report and attachment inherit exact stored task owner",
                "assignment moves to review after report",
                "director sees report through /assignments and closes task",
            ],
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        raise SystemExit(f"FAIL smoke:assignments: {exc}")
    finally:
        cleanup([task_id, system_task_id])


if __name__ == "__main__":
    main()
