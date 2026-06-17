#!/usr/bin/env python3
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
TEST_EMAIL = os.getenv("STAFF_ACCESS_SMOKE_EMAIL", "staff-access-smoke@stroyka.local")
TEST_NAME = os.getenv("STAFF_ACCESS_SMOKE_NAME", "CODEX QA Персонал")


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


def api_json(method, path, token=None, data=None, expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


def login_status(email, password):
    status, body = api_json("POST", "/login", data={"email": email, "password": password})
    return status, body


def rows_from(body):
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("items", "data", "rows", "results"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


def first_value(row, keys):
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def choose_scope():
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("STAFF_ACCESS_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    if not project:
        cur.close()
        conn.close()
        raise SystemExit("FAIL: нет активного объекта для проверки доступа сотрудника")
    cur.execute(
        """
        SELECT DISTINCT COALESCE(NULLIF(work_package,''),'Основная') AS package
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(status,'Активная')='Активная'
         ORDER BY package
        """,
        (project["name"],),
    )
    packages = [row["package"] for row in cur.fetchall() if row["package"]]
    cur.close()
    conn.close()
    real_packages = [p for p in packages if not str(p).strip().lower().startswith("codex qa")]
    assigned_package = os.getenv("STAFF_ACCESS_PACKAGE", "").strip() or (real_packages[0] if real_packages else (packages[0] if packages else "Основная"))
    forbidden_package = next((p for p in real_packages if p != assigned_package), None)
    if not forbidden_package:
        forbidden_package = next((p for p in packages if p != assigned_package), "__CODEX_FORBIDDEN_PACKAGE__")
    return {
        "projectId": project["id"],
        "projectName": project["name"],
        "assignedPackage": assigned_package,
        "forbiddenPackage": forbidden_package,
        "packageCount": len(packages),
    }


def existing_staff_id():
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id
          FROM staff
         WHERE LOWER(COALESCE(email_work,''))=LOWER(%s)
            OR LOWER(COALESCE(email_personal,''))=LOWER(%s)
         ORDER BY id
         LIMIT 1
        """,
        (TEST_EMAIL, TEST_EMAIL),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["id"] if row else None


def staff_payload(scope, password):
    return {
        "name": TEST_NAME,
        "role": "Мастер",
        "phone": "+70000000000",
        "salary": 0,
        "project": scope["projectName"],
        "payType": "сдельная",
        "specialization": scope["assignedPackage"],
        "category": "CODEX QA",
        "employmentType": "тест",
        "status": "Активен",
        "emailWork": TEST_EMAIL,
        "email": TEST_EMAIL,
        "password": password,
        "systemRole": "мастер",
        "assignedProjects": [scope["projectName"]],
        "assignedPackages": [scope["assignedPackage"]],
        "notes": "Автотест доступа сотрудника через карточку персонала.",
    }


def create_or_update_staff(admin_token, scope, password):
    payload = staff_payload(scope, password)
    staff_id = existing_staff_id()
    if staff_id:
        _, body = api_json("PUT", f"/staff/{staff_id}", token=admin_token, data=payload, expected=200)
        action = "updated"
    else:
        _, body = api_json("POST", "/staff", token=admin_token, data=payload, expected=200)
        staff_id = body.get("id")
        action = "created"
    access = body.get("access") or {}
    if not access:
        raise SystemExit(f"FAIL /staff: доступ пользователя не создан/не обновлен. Body: {body}")
    if access.get("email") != TEST_EMAIL:
        raise SystemExit(f"FAIL /staff: неожиданный email доступа: {access}")
    if access.get("role") != "мастер":
        raise SystemExit(f"FAIL /staff: неожидаемая роль доступа: {access}")
    if scope["projectName"] not in (access.get("assignedProjects") or []):
        raise SystemExit(f"FAIL /staff: объект не назначен в доступ: {access}")
    if scope["assignedPackage"] not in (access.get("assignedPackages") or []):
        raise SystemExit(f"FAIL /staff: пакет работ не назначен в доступ: {access}")
    return {"id": staff_id, "access": access, "action": action}


def assert_project_scope(rows, endpoint, project_name):
    for row in rows:
        if not isinstance(row, dict):
            continue
        project = first_value(row, ("projectName", "project", "project_name"))
        if project and project != project_name:
            raise SystemExit(f"FAIL {endpoint}: чужой объект в выдаче: {project!r}, ожидали {project_name!r}")


def assert_package_scope(rows, endpoint, assigned_package):
    for row in rows:
        if not isinstance(row, dict):
            continue
        package = first_value(row, ("workPackage", "work_package"))
        if package and (package or "Основная") != assigned_package:
            raise SystemExit(f"FAIL {endpoint}: чужой пакет в выдаче: {package!r}, ожидали {assigned_package!r}")


def check_worker_scope(token, scope):
    counts = {}
    for endpoint in ("/projects", "/estimates", "/materials", "/supply-requests", "/work-journal", "/hidden-works-acts"):
        _, body = api_json("GET", endpoint, token=token, expected=200)
        rows = rows_from(body)
        assert_project_scope(rows, endpoint, scope["projectName"])
        if endpoint != "/projects":
            assert_package_scope(rows, endpoint, scope["assignedPackage"])
        counts[endpoint] = len(rows)
    return counts


def assert_forbidden_work_blocked(token, scope):
    if scope["forbiddenPackage"] == "__CODEX_FORBIDDEN_PACKAGE__":
        return "skipped: only one package"
    status, body = api_json(
        "POST",
        "/work-journal",
        token=token,
        data={
            "project": scope["projectName"],
            "description": "CODEX QA запрет чужого пакета из карточки персонала",
            "unit": "м2",
            "quantity": 1,
            "pricePerUnit": 1,
            "date": "2026-01-01",
            "status": "На проверке",
            "workPackage": scope["forbiddenPackage"],
            "roomName": "CODEX QA персонал",
        },
    )
    if status < 400:
        raise SystemExit(f"FAIL /work-journal: сотрудник смог записать работу в чужой пакет. Body: {body}")
    return f"blocked {status}"


def main():
    admin_email = require_env("SMOKE_EMAIL")
    admin_password = require_env("SMOKE_PASSWORD")
    admin_token = login(admin_email, admin_password)
    scope = choose_scope()

    first_password = secrets.token_urlsafe(12)
    staff = create_or_update_staff(admin_token, scope, first_password)
    worker_token = login(TEST_EMAIL, first_password)
    counts = check_worker_scope(worker_token, scope)
    forbidden_result = assert_forbidden_work_blocked(worker_token, scope)

    second_password = secrets.token_urlsafe(12)
    updated = create_or_update_staff(admin_token, scope, second_password)
    old_status, _ = login_status(TEST_EMAIL, first_password)
    if old_status == 200:
        raise SystemExit("FAIL password rotation: старый пароль сотрудника все еще входит")
    login(TEST_EMAIL, second_password)

    print(
        json.dumps(
            {
                "ok": True,
                "projectName": scope["projectName"],
                "assignedPackage": scope["assignedPackage"],
                "forbiddenPackage": scope["forbiddenPackage"],
                "packageCount": scope["packageCount"],
                "staffId": staff["id"],
                "staffAction": staff["action"],
                "passwordRotation": updated["access"].get("action"),
                "worker": TEST_EMAIL,
                "checked": [
                    "director creates/updates staff card",
                    "staff card creates/updates user access",
                    "worker login works with generated password",
                    "worker sees only assigned project/package",
                    "worker cannot create work in forbidden package",
                    "staff password rotation disables old password",
                ],
                "forbiddenWork": forbidden_result,
                "rowCounts": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
