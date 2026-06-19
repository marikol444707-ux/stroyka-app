#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras


CONFIRM_TOKEN = "CODEX_QA"
PATTERNS = [
    "%CODEX%",
    "%codex%",
    "%CODEX QA%",
    "%stroyka.local%",
    "%role-matrix%",
    "%smoke%",
    "%тест%",
]

ARTIFACT_TABLES = [
    ("users", ["name", "email", "role"], ["id", "name", "email", "role", "active"]),
    ("staff", ["name", "email", "specialization", "project"], ["id", "name", "email", "role", "project", "status"]),
    ("projects", ["name", "client"], ["id", "name", "client", "status", "archived"]),
    ("estimates", ["name", "project_name", "work_package", "status"], ["id", "name", "project_name", "work_package", "status"]),
    ("materials", ["name", "project", "category"], ["id", "name", "project", "category", "quantity"]),
    ("supply_requests", ["material_name", "project", "work_package", "notes", "created_by"], ["id", "material_name", "project", "work_package", "status"]),
    ("warehouse_invoices", ["supplier", "supplier_name", "accepted_by", "project", "added_by"], ["id", "number", "supplier_name", "project", "status", "date"]),
    ("work_journal", ["description", "room_name", "comment", "project", "master_name", "created_by"], ["id", "project", "description", "room_name", "status"]),
    ("hidden_works_acts", ["work_name", "project_name", "room_name", "comments"], ["id", "project_name", "work_name", "room_name", "status"]),
    ("interim_acts", ["master_name", "project", "work_package", "status"], ["id", "project", "master_name", "total_amount", "status"]),
    ("project_payments", ["project_name", "paid_by", "note"], ["id", "project_name", "amount", "paid_by", "note"]),
    ("brigade_contracts", ["project_name", "brigade_name", "notes", "work_package"], ["id", "project_name", "brigade_name", "total_amount", "status"]),
    ("brigade_contract_items", ["description", "work_package"], ["id", "contract_id", "description", "work_package", "status"]),
    ("expenses", ["description", "category", "project", "paid_by"], ["id", "project", "category", "amount", "description"]),
    ("own_expenses", ["description", "category", "project_name", "user_email"], ["id", "project_name", "user_email", "amount", "status"]),
    ("material_norm_suggestions", ["work_name", "material_name", "project_name", "source"], ["id", "project_name", "work_name", "material_name", "status"]),
]


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


def build_match(columns):
    clauses = []
    params = []
    for column in columns:
        for pattern in PATTERNS:
            clauses.append(f"COALESCE({column}::text, '') ILIKE %s")
            params.append(pattern)
    return " OR ".join(clauses), params


def find_table_artifacts(cur, table, match_columns, sample_columns):
    if not table_exists(cur, table):
        return []
    columns = existing_columns(cur, table)
    match = [column for column in match_columns if column in columns]
    sample = [column for column in sample_columns if column in columns]
    if not match or not sample:
        return []
    where_sql, params = build_match(match)
    order_sql = "id" if "id" in columns else sample[0]
    return fetch_rows(
        cur,
        f"SELECT {', '.join(sample)} FROM {table} WHERE {where_sql} ORDER BY {order_sql}",
        params,
    )


def find_artifacts(cur):
    artifacts = {
        table: find_table_artifacts(cur, table, match_columns, sample_columns)
        for table, match_columns, sample_columns in ARTIFACT_TABLES
    }
    return {table: rows for table, rows in artifacts.items() if rows}


def update_matching(cur, table, set_sql, match_columns, returning_columns, extra_where="TRUE"):
    if not table_exists(cur, table):
        return []
    columns = existing_columns(cur, table)
    match = [column for column in match_columns if column in columns]
    returning = [column for column in returning_columns if column in columns]
    if not match or not returning:
        return []
    where_sql, params = build_match(match)
    cur.execute(
        f"""
        UPDATE {table}
           SET {set_sql}
         WHERE {extra_where}
           AND ({where_sql})
        RETURNING {', '.join(returning)}
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def apply_cleanup(cur, *, disable_users=False):
    estimates = update_matching(
        cur,
        "estimates",
        "status='Черновик'",
        ["name", "project_name", "work_package", "status"],
        ["id", "name", "project_name", "work_package", "status"],
        "COALESCE(status,'') <> 'Черновик'",
    )
    supply_requests = update_matching(
        cur,
        "supply_requests",
        "status='Отменена'",
        ["material_name", "project", "work_package", "notes", "created_by"],
        ["id", "material_name", "project", "work_package", "status"],
        "COALESCE(status,'') NOT IN ('Отменена','Отменена с откатом','Отклонена')",
    )
    staff = update_matching(
        cur,
        "staff",
        "status='Уволен'",
        ["name", "email", "specialization", "project"],
        ["id", "name", "email", "role", "project", "status"],
        "COALESCE(status,'') <> 'Уволен'",
    )
    warehouse_invoices = update_matching(
        cur,
        "warehouse_invoices",
        "status='Аннулирован'",
        ["supplier", "supplier_name", "accepted_by", "project", "added_by"],
        ["id", "number", "supplier_name", "project", "status"],
        "COALESCE(status,'') <> 'Аннулирован'",
    )
    work_journal = update_matching(
        cur,
        "work_journal",
        "status='Отклонено'",
        ["description", "room_name", "comment", "project", "master_name", "created_by"],
        ["id", "project", "description", "room_name", "status"],
        "COALESCE(status,'') NOT IN ('Отклонено','Аннулировано')",
    )
    hidden_works_acts = update_matching(
        cur,
        "hidden_works_acts",
        "status='Аннулирован'",
        ["work_name", "project_name", "room_name", "comments"],
        ["id", "project_name", "work_name", "room_name", "status"],
        "COALESCE(status,'') <> 'Аннулирован'",
    )
    interim_acts = update_matching(
        cur,
        "interim_acts",
        "status='Аннулирован'",
        ["master_name", "project", "work_package", "status"],
        ["id", "project", "master_name", "total_amount", "status"],
        "COALESCE(status,'') <> 'Аннулирован'",
    )
    brigade_contracts = update_matching(
        cur,
        "brigade_contracts",
        "status='Аннулирован'",
        ["project_name", "brigade_name", "notes", "work_package"],
        ["id", "project_name", "brigade_name", "total_amount", "status"],
        "COALESCE(status,'') <> 'Аннулирован'",
    )
    brigade_contract_items = update_matching(
        cur,
        "brigade_contract_items",
        "status='Отменено'",
        ["description", "work_package"],
        ["id", "contract_id", "description", "work_package", "status"],
        "COALESCE(status,'') <> 'Отменено'",
    )
    users = []
    if disable_users:
        users = update_matching(
            cur,
            "users",
            "active=FALSE",
            ["name", "email", "role"],
            ["id", "name", "email", "role", "active"],
            "COALESCE(active, TRUE)=TRUE",
        )
    return {
        "estimatesChanged": estimates,
        "supplyRequestsChanged": supply_requests,
        "staffChanged": staff,
        "warehouseInvoicesChanged": warehouse_invoices,
        "workJournalChanged": work_journal,
        "hiddenWorksActsChanged": hidden_works_acts,
        "interimActsChanged": interim_acts,
        "brigadeContractsChanged": brigade_contracts,
        "brigadeContractItemsChanged": brigade_contract_items,
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
