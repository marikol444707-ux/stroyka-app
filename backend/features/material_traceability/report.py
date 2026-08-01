"""Read-only report for receipt-line traceability before any stock correction."""

import json
from collections import Counter

import psycopg2.extras


PREVIEW_LIMIT = 100
TABLES = ("material_transfers", "warehouse_movements", "warehouse_history")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _text(value):
    return str(value or "").strip()


def _invoice_items(invoice):
    try:
        items = json.loads((invoice or {}).get("items") or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return items if isinstance(items, list) else []


def _item(table, record_id, status, reason, **extra):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        **extra,
    }


def classify_rows(rows):
    invoices = {
        _positive_int(row.get("id")): dict(row or {})
        for row in (rows.get("warehouse_invoices") or [])
        if _positive_int((row or {}).get("id"))
    }
    classified = []
    for row in (rows.get("material_transfers") or []):
        row = dict(row or {})
        company_id = _positive_int(row.get("company_id"))
        invoice_id = _positive_int(row.get("invoice_id"))
        line_index = row.get("invoice_line_index")
        try:
            line_index = int(line_index) if line_index is not None else None
        except (TypeError, ValueError):
            line_index = None
        base = {"companyId": company_id, "warehouseInvoiceId": invoice_id, "invoiceLineIndex": line_index}
        if not invoice_id:
            classified.append(_item("material_transfers", row.get("id"), "unlinked", "receipt_not_selected", **base))
            continue
        invoice = invoices.get(invoice_id)
        if not invoice:
            classified.append(_item("material_transfers", row.get("id"), "broken", "receipt_not_found", **base))
            continue
        if company_id != _positive_int(invoice.get("company_id")):
            classified.append(_item("material_transfers", row.get("id"), "broken", "receipt_company_mismatch", **base))
            continue
        if line_index is None:
            classified.append(_item("material_transfers", row.get("id"), "unlinked", "receipt_line_not_selected", **base))
            continue
        items = _invoice_items(invoice)
        if line_index < 0 or line_index >= len(items):
            classified.append(_item("material_transfers", row.get("id"), "broken", "receipt_line_not_found", **base))
            continue
        classified.append(_item("material_transfers", row.get("id"), "linked", "verified_receipt_line", **base))

    for table in ("warehouse_movements", "warehouse_history"):
        for row in (rows.get(table) or []):
            row = dict(row or {})
            classified.append(_item(
                table, row.get("id"), "unlinked", "receipt_reference_not_stored",
                companyId=_positive_int(row.get("company_id")),
            ))
    return classified


def build_report_from_rows(rows):
    classified = classify_rows(rows)
    statuses = ("linked", "unlinked", "broken")
    counts = Counter(item["status"] for item in classified)
    by_table = {}
    for table in TABLES:
        table_counts = Counter(item["status"] for item in classified if item["table"] == table)
        by_table[table] = {"totalRows": sum(table_counts.values()), **{status: table_counts[status] for status in statuses}}
    blockers = [item for item in classified if item["status"] != "linked"]
    return {
        "ok": True,
        "dryRun": True,
        "tables": list(TABLES),
        "writesAttempted": 0,
        "readyForStockCorrection": not blockers,
        "reportConsistent": len(classified) == sum(counts[status] for status in statuses),
        "summary": {"totalRows": len(classified), **{status: counts[status] for status in statuses}},
        "byTable": by_table,
        "linkedPreview": [item for item in classified if item["status"] == "linked"][:PREVIEW_LIMIT],
        "blockers": blockers[:PREVIEW_LIMIT],
        "blockerListTruncated": len(blockers) > PREVIEW_LIMIT,
        "rolledBack": True,
    }


def load_rows(cur):
    queries = {
        "warehouse_invoices": "SELECT id,company_id,items FROM warehouse_invoices ORDER BY id",
        "material_transfers": "SELECT id,company_id,invoice_id,invoice_line_index FROM material_transfers ORDER BY id",
        "warehouse_movements": "SELECT id,company_id FROM warehouse_movements ORDER BY id",
        "warehouse_history": "SELECT id,company_id FROM warehouse_history ORDER BY id",
    }
    result = {}
    for name, query in queries.items():
        cur.execute(query)
        result[name] = [dict(row or {}) for row in (cur.fetchall() or [])]
    return result


def run_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_report_from_rows(load_rows(cur))
            conn.rollback()
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
