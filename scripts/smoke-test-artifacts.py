#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
STRICT = os.getenv("TEST_ARTIFACTS_STRICT", "").lower() in {"1", "true", "yes", "on"}
LIMIT = int(os.getenv("TEST_ARTIFACTS_SAMPLE_LIMIT", "5"))

PATTERNS = [
    "%CODEX%",
    "%codex%",
    "%CODEX QA%",
    "%stroyka.local%",
    "%role-matrix%",
    "%smoke%",
    "%тест%",
]

TABLES = [
    ("users", ["name", "email", "role"], ["id", "name", "email", "role", "active"]),
    ("staff", ["name", "email", "specialization", "project"], ["id", "name", "email", "role", "project"]),
    ("estimates", ["name", "project_name", "work_package", "status"], ["id", "name", "project_name", "work_package", "status"]),
    ("materials", ["name", "project", "category"], ["id", "name", "project", "category", "quantity"]),
    ("supply_requests", ["material_name", "project", "work_package", "notes", "created_by"], ["id", "material_name", "project", "work_package", "status"]),
    ("supplier_offers", ["supplier_name", "material_name", "comment", "notes"], ["id", "supplier_name", "material_name", "status"]),
    ("supply_deliveries", ["supplier_name", "driver_name", "project", "notes"], ["id", "supplier_name", "project", "status"]),
    ("warehouse_invoices", ["supplier", "accepted_by", "project", "notes"], ["id", "supplier", "project", "total", "date"]),
    ("work_journal", ["description", "room_name", "comment", "project_name", "created_by"], ["id", "project_name", "description", "room_name", "status"]),
    ("hidden_works_acts", ["work_description", "project_name", "room_name", "status"], ["id", "project_name", "work_description", "room_name", "status"]),
    ("interim_acts", ["contractor_name", "project_name", "notes", "status"], ["id", "project_name", "contractor_name", "total_amount", "status"]),
    ("project_payments", ["project_name", "paid_by", "note"], ["id", "project_name", "amount", "paid_by", "note"]),
    ("brigade_contracts", ["project_name", "brigade_name", "notes"], ["id", "project_name", "brigade_name", "total_amount", "status"]),
    ("brigade_contract_items", ["description", "room_name", "work_package"], ["id", "contract_id", "description", "work_package", "amount"]),
    ("expenses", ["description", "category", "project", "paid_by"], ["id", "project", "category", "amount", "description"]),
    ("own_expenses", ["description", "category", "project_name", "user_email"], ["id", "project_name", "user_email", "amount", "status"]),
    ("material_norm_suggestions", ["work_name", "material_name", "project_name", "source"], ["id", "project_name", "work_name", "material_name", "status"]),
]


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(name, default=""):
    env = load_env()
    return os.getenv(name) or env.get(name, default)


def connect_db():
    return psycopg2.connect(
        dbname=env_value("DB_NAME", "stroyka"),
        user=env_value("DB_USER", "stroyka"),
        password=env_value("DB_PASSWORD", "password123"),
        host=env_value("DB_HOST", "localhost"),
        port=env_value("DB_PORT", "5432"),
    )


def existing_columns(cur, table):
    cur.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema='public'
           AND table_name=%s
        """,
        (table,),
    )
    return {row["column_name"] for row in cur.fetchall()}


def table_exists(cur, table):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema='public'
               AND table_name=%s
        ) AS exists
        """,
        (table,),
    )
    return bool(cur.fetchone()["exists"])


def build_match(columns):
    clauses = []
    params = []
    for column in columns:
        for pattern in PATTERNS:
            clauses.append(f"COALESCE({column}::text, '') ILIKE %s")
            params.append(pattern)
    return " OR ".join(clauses), params


def inspect_table(cur, table, match_columns, sample_columns):
    if not table_exists(cur, table):
        return {"table": table, "exists": False, "count": 0, "samples": []}

    columns = existing_columns(cur, table)
    match = [column for column in match_columns if column in columns]
    sample = [column for column in sample_columns if column in columns]
    if not match:
        return {"table": table, "exists": True, "count": 0, "samples": [], "note": "no searchable columns"}

    where_sql, params = build_match(match)
    cur.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE {where_sql}", params)
    count = int(cur.fetchone()["count"] or 0)

    samples = []
    if count and sample:
        select_sql = ", ".join(sample)
        order_sql = "id" if "id" in columns else sample[0]
        cur.execute(
            f"SELECT {select_sql} FROM {table} WHERE {where_sql} ORDER BY {order_sql} LIMIT %s",
            params + [LIMIT],
        )
        samples = [dict(row) for row in cur.fetchall()]

    return {"table": table, "exists": True, "count": count, "samples": samples}


def main():
    try:
        conn = connect_db()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "database unavailable",
                    "detail": str(exc),
                    "hint": "Run this smoke on the server, or provide DB_* env vars for a reachable database.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    results = [inspect_table(cur, *spec) for spec in TABLES]
    cur.close()
    conn.close()

    findings = [row for row in results if row["count"] > 0]
    total = sum(row["count"] for row in findings)
    summary = {
        "ok": (not STRICT) or total == 0,
        "strict": STRICT,
        "totalArtifacts": total,
        "tablesWithArtifacts": len(findings),
        "findings": findings,
        "cleanup": {
            "dryRun": "python3 scripts/manage-test-artifacts.py",
            "safeApply": "python3 scripts/manage-test-artifacts.py --apply --confirm CODEX_QA",
            "safeApplyAndDisableTestUsers": "python3 scripts/manage-test-artifacts.py --apply --confirm CODEX_QA --disable-test-users",
            "note": "Smoke only reports. Cleanup script does not delete data; it changes safe statuses and can disable *.stroyka.local users.",
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if not summary["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
