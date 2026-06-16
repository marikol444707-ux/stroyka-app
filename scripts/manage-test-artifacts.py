#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras


CONFIRM_TOKEN = "CODEX_QA"


def load_env():
    root = Path(__file__).resolve().parents[1]
    env_path = root / "backend" / ".env"
    values = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_db_config():
    env = load_env()
    return {
        "dbname": env.get("DB_NAME", os.getenv("DB_NAME", "stroyka")),
        "user": env.get("DB_USER", os.getenv("DB_USER", "stroyka")),
        "password": env.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "password123")),
        "host": env.get("DB_HOST", os.getenv("DB_HOST", "localhost")),
        "port": env.get("DB_PORT", os.getenv("DB_PORT", "5432")),
    }


def connect_db():
    return psycopg2.connect(**get_db_config())


def fetch_rows(cur, sql, params=()):
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def find_artifacts(cur):
    estimates = fetch_rows(
        cur,
        """
        SELECT id, name, project_name, work_package, smeta_type, status
          FROM estimates
         WHERE name ILIKE 'CODEX QA %%'
            OR COALESCE(work_package,'') ILIKE 'CODEX QA %%'
         ORDER BY id
        """,
    )
    supply_requests = fetch_rows(
        cur,
        """
        SELECT id, material_name, project, work_package, status, notes
          FROM supply_requests
         WHERE COALESCE(material_name,'') ILIKE 'CODEX QA %%'
            OR COALESCE(work_package,'') ILIKE 'CODEX QA %%'
            OR COALESCE(notes,'') ILIKE 'CODEX LIVE QA%%'
         ORDER BY id
        """,
    )
    users = fetch_rows(
        cur,
        """
        SELECT id, name, email, role, active
          FROM users
         WHERE LOWER(email) LIKE '%%test%%'
            OR LOWER(email) LIKE '%%codex%%'
            OR LOWER(email) LIKE '%%stroyka.local%%'
            OR LOWER(name) LIKE '%%тест%%'
            OR LOWER(name) LIKE '%%codex%%'
         ORDER BY id
        """,
    )
    return {
        "estimates": estimates,
        "supplyRequests": supply_requests,
        "users": users,
    }


def apply_cleanup(cur, *, disable_users=False):
    cur.execute(
        """
        UPDATE estimates
           SET status='Черновик'
         WHERE status <> 'Черновик'
           AND (name ILIKE 'CODEX QA %%' OR COALESCE(work_package,'') ILIKE 'CODEX QA %%')
        RETURNING id, name, project_name, work_package, status
        """
    )
    estimates = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        UPDATE supply_requests
           SET status='Отменена'
         WHERE COALESCE(status,'') NOT IN ('Отменена','Отменена с откатом','Отклонена')
           AND (
                COALESCE(material_name,'') ILIKE 'CODEX QA %%'
             OR COALESCE(work_package,'') ILIKE 'CODEX QA %%'
             OR COALESCE(notes,'') ILIKE 'CODEX LIVE QA%%'
           )
        RETURNING id, material_name, project, work_package, status
        """
    )
    supply_requests = [dict(row) for row in cur.fetchall()]
    users = []
    if disable_users:
        cur.execute(
            """
            UPDATE users
               SET active=FALSE
             WHERE active=TRUE
               AND LOWER(email) LIKE '%%stroyka.local%%'
            RETURNING id, name, email, role, active
            """
        )
        users = [dict(row) for row in cur.fetchall()]
    return {
        "estimatesChanged": estimates,
        "supplyRequestsChanged": supply_requests,
        "usersChanged": users,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Safe review/cleanup of Codex QA artifacts. Does not delete data."
    )
    parser.add_argument("--apply", action="store_true", help="Apply safe status changes")
    parser.add_argument("--confirm", default="", help=f"Required token for --apply: {CONFIRM_TOKEN}")
    parser.add_argument("--disable-test-users", action="store_true", help="Also disable *.stroyka.local test users")
    args = parser.parse_args()

    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"Refusing to apply. Pass: --confirm {CONFIRM_TOKEN}")

    conn = connect_db()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    before = find_artifacts(cur)
    result = {"mode": "dry-run", "before": before}
    if args.apply:
        result["mode"] = "apply"
        result["changed"] = apply_cleanup(cur, disable_users=args.disable_test_users)
        conn.commit()
        result["after"] = find_artifacts(cur)
    else:
        conn.rollback()
    cur.close()
    conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
