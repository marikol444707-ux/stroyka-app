"""Read-only report of supplier duplicate candidates."""

import json
from collections import defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100


def normalize_name(value):
    return " ".join(str(value or "").lower().replace("ё", "е").replace('"', "").split())


def normalize_digits(value):
    return "".join(char for char in str(value or "") if char.isdigit())


def _group(rows, key_name, key_fn):
    groups = defaultdict(list)
    for row in rows or []:
        key = key_fn(row)
        if key:
            groups[key].append(dict(row or {}))
    return [
        {"kind": key_name, "key": key, "supplierIds": sorted(row["id"] for row in group), "suppliers": group}
        for key, group in groups.items()
        if len(group) > 1
    ]


def build_report_from_rows(rows):
    suppliers = [dict(row or {}) for row in rows.get("suppliers", []) if row and row.get("id")]
    aliases = [dict(row or {}) for row in rows.get("aliases", []) if row]
    linked_pairs = sorted({
        tuple(sorted((int(row["supplier_id"]), int(row["related_supplier_id"]))))
        for row in aliases
        if row.get("source") == "manual_supplier_duplicate_link" and row.get("related_supplier_id")
    })
    exact = []
    for kind, field, formatter in (("inn", "inn", normalize_digits), ("ogrn", "ogrn", normalize_digits), ("email", "email", lambda value: str(value or "").strip().lower())):
        exact.extend(_group(suppliers, kind, lambda row, f=field, fn=formatter: fn(row.get(f))))
    exact_ids = {supplier_id for group in exact for supplier_id in group["supplierIds"]}
    name_candidates = _group(suppliers, "name", lambda row: normalize_name(row.get("name")))
    name_candidates = [group for group in name_candidates if not set(group["supplierIds"]).issubset(exact_ids)]
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "summary": {
            "supplierRows": len(suppliers),
            "manualLinkedPairs": len(linked_pairs),
            "strongIdentityGroups": len(exact),
            "nameOnlyCandidateGroups": len(name_candidates),
        },
        "manualLinkedPairs": [{"supplierIds": list(pair)} for pair in linked_pairs[:PREVIEW_LIMIT]],
        "strongIdentityGroups": exact[:PREVIEW_LIMIT],
        "nameOnlyCandidateGroups": name_candidates[:PREVIEW_LIMIT],
        "previewTruncated": any(len(items) > PREVIEW_LIMIT for items in (linked_pairs, exact, name_candidates)),
        "rolledBack": True,
    }


def run_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT id,name,inn,ogrn,email FROM suppliers ORDER BY id")
            suppliers = cur.fetchall() or []
            cur.execute("SELECT supplier_id,related_supplier_id,source FROM supplier_aliases ORDER BY id")
            aliases = cur.fetchall() or []
            result = build_report_from_rows({"suppliers": suppliers, "aliases": aliases})
            conn.rollback()
            return result
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


if __name__ == "__main__":
    main()
