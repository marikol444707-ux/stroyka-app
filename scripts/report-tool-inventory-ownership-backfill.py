#!/usr/bin/env python3
"""Read-only report of tool and inventory rows that still have no owner.

The script never updates the database. A project name or a creator name is
not treated as proof of a company. Set TOOL_INVENTORY_OWNERSHIP_REPORT=1 and
the usual DB_* variables.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg2

from backend.features.inventory_ownership.company_backfill import (
    apply_backfill,
    load_snapshot,
    owner_columns_present,
    plan_backfill,
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv != ["--dry-run"]:
        print("Поддерживается только --dry-run: отчёт читает базу и ничего не меняет.", file=sys.stderr)
        return 2
    if os.environ.get("TOOL_INVENTORY_OWNERSHIP_REPORT") != "1":
        print("Для отчёта установите TOOL_INVENTORY_OWNERSHIP_REPORT=1 и параметры DB_*.", file=sys.stderr)
        return 2
    connection = psycopg2.connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
    )
    connection.set_session(readonly=True, autocommit=True)
    try:
        with connection.cursor() as cur:
            if not owner_columns_present(cur):
                plan = plan_backfill(load_snapshot(cur, owner_columns=False))
                plan["columnsPresent"] = False
            else:
                plan = apply_backfill(cur, write=False)
                plan["columnsPresent"] = True
    finally:
        connection.close()
    report = {
        "dryRun": True,
        "columnsPresent": plan["columnsPresent"],
        "counts": plan["counts"],
        "wouldAssign": len(plan["assignments"]),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
