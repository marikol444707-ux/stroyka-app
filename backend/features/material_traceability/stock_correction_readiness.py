"""Read-only readiness report for future packaging stock corrections."""

import json
from collections import Counter

import psycopg2.extras

from .report import classify_rows, load_rows


def build_readiness_report(rows, *, receipt_lot_schema_exists):
    classified = classify_rows(rows or {})
    counts = Counter(item["status"] for item in classified)
    traceability_blockers = [item for item in classified if item["status"] != "linked"]
    schema_blockers = []
    if not receipt_lot_schema_exists:
        schema_blockers.append({
            "resource": "warehouse_receipt_lots",
            "reason": "receipt_lot_schema_missing",
            "message": "Агрегированный остаток не хранит остаток конкретной строки накладной.",
        })
    report_consistent = len(classified) == sum(counts[state] for state in ("linked", "unlinked", "broken"))
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "reportConsistent": report_consistent,
        "readyForReceiptLots": not schema_blockers,
        "readyForStockCorrection": report_consistent and not schema_blockers and not traceability_blockers,
        "summary": {
            "traceabilityRows": len(classified),
            "linked": counts["linked"],
            "unlinked": counts["unlinked"],
            "broken": counts["broken"],
            "schemaBlockers": len(schema_blockers),
            "traceabilityBlockers": len(traceability_blockers),
        },
        "schemaBlockers": schema_blockers,
        "traceabilityBlockers": traceability_blockers[:100],
        "blockerListTruncated": len(traceability_blockers) > 100,
    }


def run_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows = load_rows(cur)
            cur.execute("SELECT to_regclass('public.warehouse_receipt_lots') IS NOT NULL AS exists")
            schema = cur.fetchone() or {}
            result = build_readiness_report(rows, receipt_lot_schema_exists=bool(schema.get("exists")))
            conn.rollback()
            result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    print(json.dumps(run_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
