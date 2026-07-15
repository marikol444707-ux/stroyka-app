"""Read-only M7 preflight for tenant constraints and pilot isolation."""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extras
from psycopg2 import sql


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "docs" / "m6-tenant-registry.json"
ENV_PATH = ROOT / "backend" / ".env"
TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _registry_blockers(entries):
    blockers = []
    for item in entries:
        resource = str(item.get("resource") or "").strip()
        state = str(item.get("companyState") or "").strip()
        kind = str(item.get("kind") or "").strip()
        access = str(item.get("accessState") or "").strip().lower()
        if kind == "surface" and state == "public_surface":
            blockers.append({"resource": resource, "reason": "public_surface_not_private"})
        elif state != "stored":
            blockers.append({"resource": resource, "reason": f"owner_state_{state or 'missing'}"})
        elif "pending" in access or "local" in access:
            blockers.append({"resource": resource, "reason": "runtime_release_pending"})
    return blockers


def _index_has_column(index, column):
    definition = index.get("definition") if isinstance(index, dict) else index
    return bool(re.search(rf"\b{re.escape(column)}\b", str(definition or ""), re.IGNORECASE))


def build_report(entries, table_facts):
    entries = list(entries or [])
    registry_blockers = _registry_blockers(entries)
    registry_blocked = {item["resource"] for item in registry_blockers}
    schema_blockers = []
    candidates = []
    tables = []

    stored_tables = [
        item for item in entries
        if item.get("kind") == "table" and item.get("companyState") == "stored"
    ]
    for item in stored_tables:
        resource = str(item.get("resource") or "").strip()
        fact = dict((table_facts or {}).get(resource) or {})
        columns = dict(fact.get("columns") or {})
        indexes = list(fact.get("indexes") or [])
        constraints = list(fact.get("constraints") or [])
        project_rows = int(fact.get("projectRows") or 0)
        resource_blockers = []
        if not TABLE_RE.fullmatch(resource):
            resource_blockers.append({"resource": resource, "reason": "invalid_table_identifier"})
        elif not fact.get("exists"):
            resource_blockers.append({"resource": resource, "reason": "table_missing"})
        elif "company_id" not in columns:
            resource_blockers.append({"resource": resource, "reason": "company_column_missing"})
        else:
            if not any(_index_has_column(index, "company_id") for index in indexes):
                resource_blockers.append({"resource": resource, "reason": "company_index_missing"})
            if project_rows and "project_id" in columns and not any(
                _index_has_column(index, "project_id") for index in indexes
            ):
                resource_blockers.append({"resource": resource, "reason": "project_index_missing"})
            if "owner_scope" in columns:
                owner_scope_null = int(fact.get("ownerScopeNullRows") or 0)
                company_owner_null = int(fact.get("companyOwnerNullRows") or 0)
                invalid_owner_scope = int(fact.get("invalidOwnerScopeRows") or 0)
                if owner_scope_null:
                    resource_blockers.append({
                        "resource": resource,
                        "reason": "owner_scope_missing",
                        "count": owner_scope_null,
                    })
                if company_owner_null:
                    resource_blockers.append({
                        "resource": resource,
                        "reason": "company_scope_owner_missing",
                        "count": company_owner_null,
                    })
                if invalid_owner_scope:
                    resource_blockers.append({
                        "resource": resource,
                        "reason": "owner_scope_invalid",
                        "count": invalid_owner_scope,
                    })
            else:
                company_null = int(fact.get("companyNullRows") or 0)
                if company_null:
                    resource_blockers.append({
                        "resource": resource,
                        "reason": "company_owner_missing",
                        "count": company_null,
                    })
            relationship_checks = (
                ("orphanCompanyRows", "company_not_found"),
                ("orphanProjectRows", "project_not_found"),
                ("mismatchedProjectRows", "project_company_mismatch"),
            )
            for field, reason in relationship_checks:
                count = int(fact.get(field) or 0)
                if count:
                    resource_blockers.append({
                        "resource": resource,
                        "reason": reason,
                        "count": count,
                    })
        schema_blockers.extend(resource_blockers)
        if resource not in registry_blocked and not resource_blockers:
            candidates.append(resource)
        tables.append({
            "resource": resource,
            "rows": int(fact.get("totalRows") or 0),
            "companyNullRows": int(fact.get("companyNullRows") or 0),
            "ownerScopeNullRows": int(fact.get("ownerScopeNullRows") or 0),
            "companyOwnerNullRows": int(fact.get("companyOwnerNullRows") or 0),
            "companyColumnNullable": bool((columns.get("company_id") or {}).get("nullable", True)),
            "ownerScopeColumn": "owner_scope" in columns,
            "companyIndex": any(_index_has_column(index, "company_id") for index in indexes),
            "projectRows": project_rows,
            "projectIndexRequired": bool(project_rows and "project_id" in columns),
            "projectIndex": not project_rows or "project_id" not in columns or any(
                _index_has_column(index, "project_id") for index in indexes
            ),
            "orphanCompanyRows": int(fact.get("orphanCompanyRows") or 0),
            "orphanProjectRows": int(fact.get("orphanProjectRows") or 0),
            "mismatchedProjectRows": int(fact.get("mismatchedProjectRows") or 0),
            "invalidOwnerScopeRows": int(fact.get("invalidOwnerScopeRows") or 0),
            "constraintCount": len(constraints),
        })

    states = Counter(str(item.get("companyState") or "missing") for item in entries)
    ready = bool(entries) and not registry_blockers and not schema_blockers
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "reportConsistent": len(tables) == len(stored_tables),
        "readyForConstraints": ready,
        "readyForPilotMatrix": False,
        "summary": {
            "registryEntries": len(entries),
            "storedTablesChecked": len(stored_tables),
            "registryBlockers": len(registry_blockers),
            "schemaBlockers": len(schema_blockers),
            "constraintCandidates": len(candidates),
        },
        "byCompanyState": dict(sorted(states.items())),
        "registryBlockers": registry_blockers,
        "schemaBlockers": schema_blockers,
        "constraintCandidates": sorted(candidates),
        "tables": sorted(tables, key=lambda item: item["resource"]),
        "pilotBlocker": "constraints_not_planned" if ready else "tenant_readiness_not_clean",
    }


def collect_table_facts(cur, entries):
    table_names = sorted({
        str(item.get("resource") or "").strip()
        for item in entries
        if item.get("kind") == "table"
        and item.get("companyState") == "stored"
        and TABLE_RE.fullmatch(str(item.get("resource") or "").strip())
    })
    if not table_names:
        return {}

    facts = {name: {"exists": False, "columns": {}, "indexes": [], "constraints": []} for name in table_names}
    cur.execute(
        """SELECT table_name,column_name,is_nullable
             FROM information_schema.columns
            WHERE table_schema='public' AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (table_names,),
    )
    for row in cur.fetchall() or []:
        item = dict(row)
        table = str(item.get("table_name") or "")
        if table not in facts:
            continue
        facts[table]["exists"] = True
        facts[table]["columns"][str(item.get("column_name") or "")] = {
            "nullable": str(item.get("is_nullable") or "").upper() == "YES",
        }

    cur.execute(
        """SELECT tablename,indexname,indexdef
             FROM pg_indexes
            WHERE schemaname='public' AND tablename=ANY(%s)
            ORDER BY tablename,indexname""",
        (table_names,),
    )
    for row in cur.fetchall() or []:
        item = dict(row)
        table = str(item.get("tablename") or "")
        if table in facts:
            facts[table]["indexes"].append({
                "name": str(item.get("indexname") or ""),
                "definition": str(item.get("indexdef") or ""),
            })

    cur.execute(
        """SELECT rel.relname AS table_name,con.conname AS constraint_name
             FROM pg_constraint con
             JOIN pg_class rel ON rel.oid=con.conrelid
             JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname='public' AND rel.relname=ANY(%s)
            ORDER BY rel.relname,con.conname""",
        (table_names,),
    )
    for row in cur.fetchall() or []:
        item = dict(row)
        table = str(item.get("table_name") or "")
        if table in facts:
            facts[table]["constraints"].append(str(item.get("constraint_name") or ""))

    for table in table_names:
        columns = facts[table]["columns"]
        if not facts[table]["exists"]:
            continue
        if "company_id" not in columns:
            cur.execute(
                sql.SQL("SELECT COUNT(*) AS total_rows FROM {}").format(sql.Identifier(table))
            )
        else:
            count_fields = [
                sql.SQL("COUNT(*) AS total_rows"),
                sql.SQL("COUNT(*) FILTER (WHERE t.company_id IS NULL) AS company_null_rows"),
                sql.SQL(
                    "COUNT(*) FILTER (WHERE t.company_id IS NOT NULL AND c.id IS NULL) "
                    "AS orphan_company_rows"
                ),
            ]
            joins = [sql.SQL("LEFT JOIN companies c ON c.id=t.company_id")]
            if "owner_scope" in columns:
                count_fields.extend([
                    sql.SQL(
                        "COUNT(*) FILTER (WHERE t.owner_scope IS NULL) AS owner_scope_null_rows"
                    ),
                    sql.SQL(
                        "COUNT(*) FILTER (WHERE t.owner_scope='company' AND t.company_id IS NULL) "
                        "AS company_owner_null_rows"
                    ),
                    sql.SQL(
                        "COUNT(*) FILTER (WHERE t.owner_scope IS NOT NULL "
                        "AND t.owner_scope NOT IN ('company','platform','legacy')) "
                        "AS invalid_owner_scope_rows"
                    ),
                ])
            if "project_id" in columns:
                joins.append(sql.SQL("LEFT JOIN projects p ON p.id=t.project_id"))
                count_fields.extend([
                    sql.SQL(
                        "COUNT(*) FILTER (WHERE t.project_id IS NOT NULL) AS project_rows"
                    ),
                    sql.SQL(
                        "COUNT(*) FILTER (WHERE t.project_id IS NOT NULL AND p.id IS NULL) "
                        "AS orphan_project_rows"
                    ),
                    sql.SQL(
                        "COUNT(*) FILTER (WHERE t.project_id IS NOT NULL AND p.id IS NOT NULL "
                        "AND t.company_id IS DISTINCT FROM p.company_id) "
                        "AS mismatched_project_rows"
                    ),
                ])
            cur.execute(
                sql.SQL("SELECT {fields} FROM {table} t {joins}").format(
                    fields=sql.SQL(", ").join(count_fields),
                    table=sql.Identifier(table),
                    joins=sql.SQL(" ").join(joins),
                )
            )
        counts = dict(cur.fetchone() or {})
        facts[table].update({
            "totalRows": int(counts.get("total_rows") or 0),
            "companyNullRows": int(counts.get("company_null_rows") or 0),
            "ownerScopeNullRows": int(counts.get("owner_scope_null_rows") or 0),
            "companyOwnerNullRows": int(counts.get("company_owner_null_rows") or 0),
            "invalidOwnerScopeRows": int(counts.get("invalid_owner_scope_rows") or 0),
            "orphanCompanyRows": int(counts.get("orphan_company_rows") or 0),
            "projectRows": int(counts.get("project_rows") or 0),
            "orphanProjectRows": int(counts.get("orphan_project_rows") or 0),
            "mismatchedProjectRows": int(counts.get("mismatched_project_rows") or 0),
        })
    return facts


def run_report(conn, entries):
    conn.set_session(readonly=True, autocommit=False)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        result = build_report(entries, collect_table_facts(cur, entries))
        conn.rollback()
        result["rolledBack"] = True
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _db_config():
    env = _load_env()
    return {
        "dbname": os.getenv("DB_NAME") or env.get("DB_NAME") or "stroyka",
        "user": os.getenv("DB_USER") or env.get("DB_USER") or "stroyka",
        "password": os.getenv("DB_PASSWORD") or env.get("DB_PASSWORD") or "password123",
        "host": os.getenv("DB_HOST") or env.get("DB_HOST") or "localhost",
        "port": os.getenv("DB_PORT") or env.get("DB_PORT") or "5432",
    }


def main():
    conn = None
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        conn = psycopg2.connect(**_db_config())
        result = run_report(conn, registry.get("entries") or [])
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
