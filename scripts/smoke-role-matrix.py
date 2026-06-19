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
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
PASSWORD_HASH_ITERATIONS = 260000


ROLE_MATRIX = [
    {
        "role": "директор",
        "slug": "director",
        "must": ["/projects", "/users", "/system-status", "/ai-tasks"],
        "check": ["/estimates", "/materials", "/supply-requests", "/supply-history", "/work-journal", "/hidden-works-acts", "/interim-acts", "/project-payments", "/expenses", "/own-expenses"],
    },
    {
        "role": "зам_директора",
        "slug": "deputy",
        "must": ["/projects", "/users", "/system-status"],
        "check": ["/estimates", "/materials", "/supply-requests", "/work-journal", "/interim-acts", "/project-payments", "/expenses", "/own-expenses"],
    },
    {
        "role": "главный_инженер",
        "slug": "chief-engineer",
        "must": ["/projects", "/estimates", "/work-journal"],
        "check": ["/materials", "/supply-requests", "/hidden-works-acts", "/supervisor-acts"],
    },
    {
        "role": "прораб",
        "slug": "foreman",
        "must": ["/projects", "/estimates", "/work-journal"],
        "check": ["/materials", "/supply-requests", "/hidden-works-acts"],
    },
    {
        "role": "мастер",
        "slug": "master",
        "must": ["/projects", "/estimates", "/work-journal"],
        "check": ["/materials", "/supply-requests", "/own-expenses"],
    },
    {
        "role": "субподрядчик",
        "slug": "subcontractor",
        "must": ["/projects", "/estimates", "/work-journal"],
        "check": ["/materials", "/supply-requests", "/own-expenses"],
    },
    {
        "role": "сметчик",
        "slug": "estimator",
        "must": ["/projects", "/estimates"],
        "check": ["/materials", "/pricelists", "/ai-tasks"],
    },
    {
        "role": "снабженец",
        "slug": "supply",
        "must": ["/projects", "/materials", "/supply-requests", "/supply-history"],
        "check": ["/suppliers", "/supplier-offers", "/warehouse-invoices"],
    },
    {
        "role": "кладовщик",
        "slug": "warehouse",
        "must": ["/projects", "/materials", "/warehouse-invoices"],
        "check": ["/warehouse-main", "/warehouse-movements", "/supply-history"],
    },
    {
        "role": "бухгалтер",
        "slug": "accountant",
        "must": ["/projects", "/expenses", "/project-payments", "/own-expenses"],
        "check": ["/users", "/interim-acts", "/supplier-invoices", "/expense-reports"],
    },
    {
        "role": "технадзор",
        "slug": "tech-supervision",
        "must": ["/projects", "/work-journal", "/hidden-works-acts"],
        "check": ["/supervisor-acts", "/prescriptions"],
    },
    {
        "role": "заказчик",
        "slug": "customer",
        "must": ["/projects"],
        "check": ["/estimates", "/hidden-works-acts", "/supervisor-acts"],
    },
]


def load_env():
    values = {}
    env_path = ROOT / "backend" / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def connect_db():
    env = load_env()
    return psycopg2.connect(
        dbname=env.get("DB_NAME", os.getenv("DB_NAME", "stroyka")),
        user=env.get("DB_USER", os.getenv("DB_USER", "stroyka")),
        password=env.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "password123")),
        host=env.get("DB_HOST", os.getenv("DB_HOST", "localhost")),
        port=env.get("DB_PORT", os.getenv("DB_PORT", "5432")),
    )


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def first_project_and_package(cur):
    cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived, FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    if not project:
        raise RuntimeError("Нет активного проекта для role-matrix smoke")
    cur.execute(
        """
        SELECT work_package
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(work_package, '') <> ''
           AND COALESCE(status, '') <> 'Архив'
         ORDER BY CASE WHEN work_package LIKE 'CODEX%%' THEN 1 ELSE 0 END, id
         LIMIT 1
        """,
        (project["name"],),
    )
    package_row = cur.fetchone()
    return dict(project), (package_row["work_package"] if package_row else "")


def create_or_update_role_user(cur, project, package_name, role_def):
    email = f"role-matrix-{role_def['slug']}@stroyka.local"
    password = secrets.token_urlsafe(12)
    assigned_packages = [package_name] if package_name and role_def["role"] in ("мастер", "субподрядчик", "сметчик") else []
    assigned_projects = [project["name"]]
    password_hash = hash_password(password)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
    existing = cur.fetchone()
    values = (
        f"ROLE MATRIX {role_def['role']}",
        email,
        password_hash,
        role_def["role"],
        project["id"],
        project["name"],
        json.dumps(assigned_projects, ensure_ascii=False),
        json.dumps(assigned_packages, ensure_ascii=False),
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
                   locked_until=NULL,
                   reset_token=NULL,
                   reset_token_expires=NULL
             WHERE id=%s
         RETURNING id
            """,
            (*values, existing["id"]),
        )
    else:
        cur.execute(
            """
            INSERT INTO users
                (name, email, password, role, project_id, project_name, assigned_projects, assigned_packages, active)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, TRUE)
            RETURNING id
            """,
            values,
        )
    user_id = cur.fetchone()["id"]
    return {"id": user_id, "email": email, "password": password, "assignedPackages": assigned_packages}


def api_json(method, path, token=None, data=None):
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text) if text else None
            except json.JSONDecodeError:
                parsed = text
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text else None
        except json.JSONDecodeError:
            parsed = text
        return exc.code, parsed


def login(email, password):
    status, body = api_json("POST", "/login", data={"email": email, "password": password})
    if status != 200 or not isinstance(body, dict) or not body.get("authToken"):
        return None, status, body
    return body["authToken"], status, body


def row_count(body):
    if isinstance(body, list):
        return len(body)
    if isinstance(body, dict):
        for key in ("items", "data", "rows", "tasks"):
            if isinstance(body.get(key), list):
                return len(body[key])
    return None


def main():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project, package_name = first_project_and_package(cur)
    users = {}
    for role_def in ROLE_MATRIX:
        users[role_def["role"]] = create_or_update_role_user(cur, project, package_name, role_def)
    conn.commit()
    cur.close()
    conn.close()

    failures = []
    warnings = []
    role_results = []
    for role_def in ROLE_MATRIX:
        user = users[role_def["role"]]
        token, login_status, login_body = login(user["email"], user["password"])
        role_result = {
            "role": role_def["role"],
            "email": user["email"],
            "login": login_status,
            "assignedPackages": user["assignedPackages"],
            "endpoints": {},
        }
        if not token:
            failures.append({"role": role_def["role"], "reason": "login failed", "status": login_status, "body": login_body})
            role_results.append(role_result)
            continue
        for path in list(dict.fromkeys(role_def["must"] + role_def["check"])):
            status, body = api_json("GET", path, token=token)
            role_result["endpoints"][path] = {"status": status, "rows": row_count(body)}
            if path in role_def["must"] and status != 200:
                failures.append({"role": role_def["role"], "path": path, "status": status})
            elif path in role_def["check"] and status not in (200, 403):
                warnings.append({"role": role_def["role"], "path": path, "status": status})
        role_results.append(role_result)

    summary = {
        "ok": not failures,
        "baseUrl": BASE_URL,
        "projectName": project["name"],
        "workPackage": package_name,
        "checkedRoles": len(role_results),
        "failures": failures,
        "warnings": warnings,
        "roles": role_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
