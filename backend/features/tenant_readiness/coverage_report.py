"""Read-only M7 audit of tenant-registry coverage over the public schema."""

import json
import re
import sys
from collections import Counter

import psycopg2
import psycopg2.extras

from .report import REGISTRY_PATH, _db_config


TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
COMPANY_SIGNALS = {"company_id", "owner_scope"}
PROJECT_SIGNALS = {"project_id", "project_name", "project"}
OWNERSHIP_SIGNALS = COMPANY_SIGNALS | PROJECT_SIGNALS


def _unregistered_table(resource, columns):
    signals = sorted(set(columns or set()) & OWNERSHIP_SIGNALS)
    if set(signals) & COMPANY_SIGNALS:
        risk = "critical"
    elif set(signals) & PROJECT_SIGNALS:
        risk = "high"
    else:
        risk = "unclassified"
    return {
        "resource": resource,
        "risk": risk,
        "ownershipSignals": signals,
    }


def build_coverage_report(entries, schema_tables):
    entries = list(entries or [])
    schema_tables = {
        str(resource or "").strip(): set(columns or set())
        for resource, columns in dict(schema_tables or {}).items()
        if TABLE_RE.fullmatch(str(resource or "").strip())
    }
    registry_tables = [
        str(item.get("resource") or "").strip()
        for item in entries
        if item.get("kind") == "table"
        and TABLE_RE.fullmatch(str(item.get("resource") or "").strip())
    ]
    registry_counts = Counter(registry_tables)
    registered = set(registry_tables)
    schema = set(schema_tables)
    duplicate_tables = sorted(
        resource for resource, count in registry_counts.items() if count > 1
    )
    missing_tables = sorted(registered - schema)
    unregistered = [
        _unregistered_table(resource, schema_tables[resource])
        for resource in sorted(schema - registered)
    ]
    by_risk = Counter(item["risk"] for item in unregistered)
    ready = bool(registered) and not duplicate_tables and not missing_tables and not unregistered
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "reportConsistent": not duplicate_tables,
        "readyForRegistryFreeze": ready,
        "summary": {
            "registryEntries": len(entries),
            "registeredTables": len(registered),
            "registrySurfaces": sum(1 for item in entries if item.get("kind") == "surface"),
            "schemaTables": len(schema),
            "unregisteredTables": len(unregistered),
            "registeredTablesMissing": len(missing_tables),
            "duplicateRegistryTables": len(duplicate_tables),
        },
        "unregisteredByRisk": dict(sorted(by_risk.items())),
        "unregisteredTables": unregistered,
        "registeredTablesMissing": missing_tables,
        "duplicateRegistryTables": duplicate_tables,
        "nextAction": (
            "classify_unregistered_tables"
            if unregistered
            else "restore_missing_registry_tables"
            if missing_tables
            else "deduplicate_registry"
            if duplicate_tables
            else "registry_coverage_clean"
        ),
    }


def collect_schema_tables(cur):
    cur.execute(
        """SELECT c.table_name,c.column_name
             FROM information_schema.columns c
             JOIN information_schema.tables t
               ON t.table_schema=c.table_schema AND t.table_name=c.table_name
            WHERE c.table_schema='public' AND t.table_type='BASE TABLE'
            ORDER BY c.table_name,c.ordinal_position"""
    )
    tables = {}
    for raw in cur.fetchall() or []:
        row = dict(raw or {})
        resource = str(row.get("table_name") or "").strip()
        column = str(row.get("column_name") or "").strip()
        if TABLE_RE.fullmatch(resource) and column:
            tables.setdefault(resource, set()).add(column)
    return tables


def run_coverage_report(conn, entries):
    conn.set_session(readonly=True, autocommit=False)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        result = build_coverage_report(entries, collect_schema_tables(cur))
        conn.rollback()
        result["rolledBack"] = True
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main():
    conn = None
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        conn = psycopg2.connect(**_db_config())
        result = run_coverage_report(conn, registry.get("entries") or [])
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
