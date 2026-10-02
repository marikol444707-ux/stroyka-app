#!/usr/bin/env python3
"""Protected production smoke for AI-control tenant isolation.

The script creates two uniquely named temporary companies, exercises the live
HTTP routes plus the automatic event runner, and removes every fixture in a
``finally`` block.  It never runs AI control against an existing project.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(os.getenv("STROYKA_APP_ROOT") or Path(__file__).resolve().parents[1]).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:12]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name: str, default: str = "") -> str:
    return os.getenv(name) or ENV.get(name, default)


def db_config() -> dict[str, str]:
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def api_json(method: str, path: str, *, token: str, data=None, headers=None, expected: int):
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request_headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    request = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {path}: backend returned non-JSON body: {text[:300]}") from exc


def assert_success(result: dict, project_name: str, reason: str) -> None:
    if result.get("ok") is not True:
        raise RuntimeError(f"{reason}: AI control did not return ok=true: {result}")
    if result.get("projectName") != project_name:
        raise RuntimeError(f"{reason}: foreign project returned: {result.get('projectName')!r}")


def assert_batch_scope(result: dict, project_name: str) -> None:
    rows = result.get("results") or []
    if result.get("ok") is not True or int(result.get("projects") or -1) != 1 or len(rows) != 1:
        raise RuntimeError(f"run-all did not stay inside the one-project fixture company: {result}")
    assert_success(rows[0], project_name, "run-all")


def assert_fixture_ownership(cur, company_id: int, project_id: int) -> dict[str, int]:
    counts = {}
    for table in ("ai_findings", "ai_tasks"):
        cur.execute(
            f"SELECT COUNT(*) AS count FROM {table} WHERE company_id=%s AND project_id=%s",
            (company_id, project_id),
        )
        counts[table] = int(cur.fetchone()["count"] or 0)
        cur.execute(
            f"""SELECT COUNT(*) AS count FROM {table}
                WHERE project_name=%s AND (company_id IS DISTINCT FROM %s OR project_id IS DISTINCT FROM %s)""",
            (FIXTURE["project_a_name"], company_id, project_id),
        )
        if int(cur.fetchone()["count"] or 0):
            raise RuntimeError(f"{table}: fixture project escaped its exact owner")
    if counts["ai_findings"] < 1:
        raise RuntimeError("AI control produced no owned finding for the incomplete fixture room")
    return counts


def assert_no_company_ai_rows(cur, company_id: int) -> None:
    for table in ("ai_findings", "ai_tasks"):
        cur.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE company_id=%s", (company_id,))
        if int(cur.fetchone()["count"] or 0):
            raise RuntimeError(f"{table}: cross-company attempt created records in the foreign company")


FIXTURE = {
    "company_a_name": f"CODEX AI smoke A {RUN_ID}",
    "company_b_name": f"CODEX AI smoke B {RUN_ID}",
    "project_a_name": f"CODEX AI project A {RUN_ID}",
    "project_b_name": f"CODEX AI project B {RUN_ID}",
    "email": f"ai-smoke-{RUN_ID}@stroyka.local",
}
IDS: dict[str, int] = {}


def create_fixture() -> str:
    conn = psycopg2.connect(**db_config())
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        for side in ("a", "b"):
            cur.execute(
                """INSERT INTO companies
                     (name,short_name,plan,active,payment_status,platform_account_id,max_projects,max_users)
                   VALUES (%s,%s,'pro',TRUE,'active',1,10,10) RETURNING id""",
                (FIXTURE[f"company_{side}_name"], FIXTURE[f"company_{side}_name"]),
            )
            IDS[f"company_{side}"] = int(cur.fetchone()["id"])
        cur.execute(
            """INSERT INTO users
                 (name,email,password,role,company_id,active,two_factor_required,two_factor_enabled,platform_account_id)
               VALUES (%s,%s,%s,'директор',%s,TRUE,TRUE,FALSE,1) RETURNING id""",
            ("CODEX AI smoke", FIXTURE["email"], "disabled-smoke-login", IDS["company_a"]),
        )
        IDS["user"] = int(cur.fetchone()["id"])
        cur.execute(
            """INSERT INTO user_company_roles
                 (user_id,platform_account_id,company_id,role,assigned_projects,assigned_packages,active,is_default)
               VALUES (%s,1,%s,'директор','[]'::jsonb,'[]'::jsonb,TRUE,TRUE)""",
            (IDS["user"], IDS["company_a"]),
        )
        for side in ("a", "b"):
            cur.execute(
                """INSERT INTO projects (name,client,status,company_id,archived)
                   VALUES (%s,'CODEX smoke','Активный',%s,FALSE) RETURNING id""",
                (FIXTURE[f"project_{side}_name"], IDS[f"company_{side}"]),
            )
            IDS[f"project_{side}"] = int(cur.fetchone()["id"])
        cur.execute(
            "INSERT INTO rooms (project,name) VALUES (%s,%s) RETURNING id",
            (FIXTURE["project_a_name"], "CODEX smoke room without dimensions"),
        )
        IDS["room"] = int(cur.fetchone()["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    from backend.auth import create_auth_token

    return create_auth_token(
        {
            "id": IDS["user"],
            "email": FIXTURE["email"],
            "name": "CODEX AI smoke",
            "role": "директор",
        },
        two_factor_passed=True,
    )


def cleanup_fixture() -> None:
    if not IDS:
        return
    conn = psycopg2.connect(**db_config())
    conn.autocommit = False
    cur = conn.cursor()
    try:
        company_ids = [value for key, value in IDS.items() if key.startswith("company_")]
        project_ids = [value for key, value in IDS.items() if key.startswith("project_")]
        if company_ids or project_ids:
            for table in ("ai_tasks", "ai_findings"):
                cur.execute(
                    f"DELETE FROM {table} WHERE company_id = ANY(%s) OR project_id = ANY(%s)",
                    (company_ids or [0], project_ids or [0]),
                )
        if IDS.get("room"):
            cur.execute("DELETE FROM rooms WHERE id=%s", (IDS["room"],))
        if IDS.get("user"):
            cur.execute("DELETE FROM user_sessions WHERE user_id=%s", (IDS["user"],))
            cur.execute("DELETE FROM user_company_roles WHERE user_id=%s", (IDS["user"],))
            cur.execute("DELETE FROM users WHERE id=%s", (IDS["user"],))
        if project_ids:
            cur.execute("DELETE FROM projects WHERE id = ANY(%s)", (project_ids,))
        if company_ids:
            cur.execute("DELETE FROM companies WHERE id = ANY(%s)", (company_ids,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main() -> None:
    token = ""
    try:
        token = create_fixture()
        headers_a = {"X-Company-Mode": "company", "X-Company-Id": str(IDS["company_a"])}
        headers_b = {"X-Company-Mode": "company", "X-Company-Id": str(IDS["company_b"])}

        single = api_json(
            "POST", "/ai-control/run", token=token, headers=headers_a, expected=200,
            data={"projectName": FIXTURE["project_a_name"], "reason": "protected-smoke-single"},
        )
        assert_success(single, FIXTURE["project_a_name"], "single")
        generated = api_json(
            "POST", "/ai-findings/generate", token=token, headers=headers_a, expected=200,
            data={"projectName": FIXTURE["project_a_name"], "reason": "protected-smoke-generate"},
        )
        assert_success(generated, FIXTURE["project_a_name"], "generate")
        batch = api_json(
            "POST", "/ai-control/run-all", token=token, headers=headers_a, expected=200,
            data={"reason": "protected-smoke-batch"},
        )
        assert_batch_scope(batch, FIXTURE["project_a_name"])

        from backend.main import _run_project_ai_control_safely

        automatic = _run_project_ai_control_safely(FIXTURE["project_a_name"], "protected-smoke-event")
        assert_success(automatic, FIXTURE["project_a_name"], "automatic event")

        api_json(
            "POST", "/ai-control/run", token=token, headers=headers_b, expected=403,
            data={"projectName": FIXTURE["project_b_name"]},
        )
        api_json(
            "POST", "/ai-control/run", token=token, headers=headers_a, expected=404,
            data={"projectName": FIXTURE["project_b_name"]},
        )
        api_json(
            "POST", "/ai-control/run-all", token=token,
            headers={"X-Company-Mode": "all_companies"}, expected=400, data={},
        )

        conn = psycopg2.connect(**db_config())
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        counts = assert_fixture_ownership(cur, IDS["company_a"], IDS["project_a"])
        assert_no_company_ai_rows(cur, IDS["company_b"])
        cur.execute(
            "INSERT INTO projects (name,client,status,company_id,archived) VALUES (%s,'CODEX smoke','Активный',%s,FALSE) RETURNING id",
            (FIXTURE["project_a_name"], IDS["company_b"]),
        )
        IDS["project_duplicate"] = int(cur.fetchone()["id"])
        conn.commit()
        cur.close()
        conn.close()

        api_json(
            "POST", "/ai-control/run", token=token, headers=headers_a, expected=409,
            data={"projectName": FIXTURE["project_a_name"]},
        )
        if _run_project_ai_control_safely(FIXTURE["project_a_name"], "protected-smoke-ambiguous-event") != {}:
            raise RuntimeError("automatic event did not fail closed for an ambiguous project name")

        conn = psycopg2.connect(**db_config())
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        assert_no_company_ai_rows(cur, IDS["company_b"])
        cur.close()
        conn.close()

        print(json.dumps({
            "ok": True,
            "checked": [
                "single /ai-control/run exact owner",
                "single /ai-findings/generate exact owner",
                "batch /ai-control/run-all selected-company scope",
                "automatic event exact owner",
                "foreign company header rejected",
                "foreign project rejected inside selected company",
                "all-companies user run rejected",
                "duplicate project name fails closed for manual and automatic runs",
                "foreign fixture company has no AI records",
            ],
            "fixtureOwnedRows": counts,
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup_fixture()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"FAIL smoke:ai-control-isolation: {exc}")
