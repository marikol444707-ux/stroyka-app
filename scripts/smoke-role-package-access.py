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
WORKER_EMAIL = os.getenv("ROLE_PACKAGE_WORKER_EMAIL", "role-package-worker@stroyka.local")
FOREMAN_EMAIL = os.getenv("ROLE_PACKAGE_FOREMAN_EMAIL", "role-package-foreman@stroyka.local")


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


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken")
    if not token:
        raise SystemExit(f"FAIL login {email}: authToken не получен")
    return token


def choose_scope():
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("ROLE_PACKAGE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    if not project:
        cur.close()
        conn.close()
        raise SystemExit("FAIL: нет активного объекта для проверки ролей")
    cur.execute(
        """
        SELECT DISTINCT COALESCE(NULLIF(work_package,''),'Основная') AS package
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(status,'')='Активная'
         ORDER BY package
        """,
        (project["name"],),
    )
    packages = [row["package"] for row in cur.fetchall() if row["package"]]
    cur.close()
    conn.close()
    real_packages = [p for p in packages if not str(p).strip().lower().startswith("codex qa")]
    assigned_package = os.getenv("ROLE_PACKAGE_ASSIGNED", "").strip() or (real_packages[0] if real_packages else (packages[0] if packages else "Основная"))
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


def create_or_update_user(email, name, role, project_id, project_name, packages):
    password = secrets.token_urlsafe(12)
    assigned_projects = json.dumps([project_name], ensure_ascii=False)
    assigned_packages = json.dumps(packages or [], ensure_ascii=False)
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
    existing = cur.fetchone()
    common = (
        name,
        email,
        hash_password(password),
        role,
        project_id,
        project_name,
        assigned_projects,
        assigned_packages,
    )
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
                   assigned_packages=%s::jsonb,
                   active=TRUE,
                   failed_login_count=0,
                   locked_until=NULL
             WHERE id=%s
         RETURNING id, name, email, role, project_name, assigned_packages
            """,
            common + (existing["id"],),
        )
    else:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active)
            VALUES
                (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE)
            RETURNING id, name, email, role, project_name, assigned_packages
            """,
            common,
        )
    row = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    row["password"] = password
    return row


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


def assert_project_scope(rows, endpoint, project_name, allow_templates=False):
    for row in rows:
        if not isinstance(row, dict):
            continue
        project = first_value(row, ("projectName", "project", "project_name"))
        if allow_templates and not project and row.get("isTemplate"):
            continue
        if project and project != project_name:
            raise SystemExit(f"FAIL {endpoint}: чужой объект в выдаче: {project!r}, ожидали {project_name!r}")


def assert_package_scope(rows, endpoint, assigned_package):
    for row in rows:
        if not isinstance(row, dict):
            continue
        package = first_value(row, ("workPackage", "work_package"))
        if package and (package or "Основная") != assigned_package:
            raise SystemExit(f"FAIL {endpoint}: чужой пакет в выдаче: {package!r}, ожидали {assigned_package!r}")


def check_endpoint_scope(token, endpoint, project_name, assigned_package=None, allow_templates=False):
    _, body = api_json("GET", endpoint, token=token, expected=200)
    rows = rows_from(body)
    assert_project_scope(rows, endpoint, project_name, allow_templates=allow_templates)
    if assigned_package:
        assert_package_scope(rows, endpoint, assigned_package)
    return len(rows)


def main():
    scope = choose_scope()
    worker = create_or_update_user(
        WORKER_EMAIL,
        "CODEX QA Исполнитель пакет",
        "субподрядчик",
        scope["projectId"],
        scope["projectName"],
        [scope["assignedPackage"]],
    )
    foreman = create_or_update_user(
        FOREMAN_EMAIL,
        "CODEX QA Прораб объект",
        "прораб",
        scope["projectId"],
        scope["projectName"],
        [],
    )
    worker_token = login(worker["email"], worker["password"])
    foreman_token = login(foreman["email"], foreman["password"])

    checked = []
    counts = {}
    for endpoint in ("/projects", "/estimates", "/materials", "/supply-requests", "/work-journal", "/interim-acts", "/hidden-works-acts"):
        counts[f"worker {endpoint}"] = check_endpoint_scope(
            worker_token,
            endpoint,
            scope["projectName"],
            assigned_package=scope["assignedPackage"] if endpoint != "/projects" else None,
            allow_templates=endpoint == "/estimates",
        )
    checked.append("worker sees only assigned project/package")

    for endpoint in ("/projects", "/estimates", "/materials", "/supply-requests", "/work-journal", "/interim-acts", "/hidden-works-acts"):
        counts[f"foreman {endpoint}"] = check_endpoint_scope(
            foreman_token,
            endpoint,
            scope["projectName"],
            assigned_package=None,
            allow_templates=endpoint == "/estimates",
        )
    checked.append("foreman sees assigned project without package lock")

    forbidden_data = {
        "masterId": worker["id"],
        "masterName": worker["name"],
        "project": scope["projectName"],
        "description": "CODEX QA запрет чужого пакета",
        "unit": "м2",
        "quantity": 1,
        "pricePerUnit": 1,
        "date": "2026-01-01",
        "status": "На проверке",
        "workPackage": scope["forbiddenPackage"],
        "roomName": "CODEX QA запрет",
    }
    status, body = api_json("POST", "/work-journal", token=worker_token, data=forbidden_data)
    if status < 400:
        raise SystemExit(f"FAIL /work-journal: исполнитель смог записать работу в чужой пакет. Body: {body}")
    checked.append("worker cannot create work in forbidden package")

    print(
        json.dumps(
            {
                "ok": True,
                "projectName": scope["projectName"],
                "assignedPackage": scope["assignedPackage"],
                "forbiddenPackage": scope["forbiddenPackage"],
                "packageCount": scope["packageCount"],
                "worker": worker["email"],
                "foreman": foreman["email"],
                "checked": checked,
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
