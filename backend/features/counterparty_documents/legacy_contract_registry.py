"""Guarded, reversible registry backfill for reviewed legacy contracts.

The command never infers a contract from names, numbers or amounts.  A row is
eligible only when all immutable IDs saved with the reviewed snapshot still
agree with the offer, party version, source file and tenant owner.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extensions
import psycopg2.extras


_MODULE_PATH = Path(__file__).resolve()
ROOT = Path(os.getenv("STROYKA_ROOT") or (
    _MODULE_PATH.parents[3] if len(_MODULE_PATH.parents) > 3 else Path.cwd()
))
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_LEGACY_CONTRACT_REGISTRY"
ROLLBACK_CONFIRMATION = "ROLLBACK_LEGACY_CONTRACT_REGISTRY"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LOCK_KEY = 1735289307


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _canonical_sha(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _plan_sha(items):
    rows = [
        [item["contractVersionId"], item["companyId"], item["supplierId"],
         item["buyerCompanyId"], item["payerCompanyId"], item["snapshotHash"]]
        for item in items if item["status"] == "ready"
    ]
    return _canonical_sha(sorted(rows))


def classify_contract(row):
    row = dict(row or {})
    contract_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    snapshot = row.get("snapshot_json") if isinstance(row.get("snapshot_json"), dict) else {}
    supplier_id = _positive_int((snapshot.get("supplier") or {}).get("supplierId"))
    buyer_id = _positive_int((snapshot.get("buyer") or {}).get("companyId"))
    payer_id = _positive_int((snapshot.get("payer") or {}).get("companyId"))
    base = {
        "contractVersionId": contract_id,
        "companyId": company_id,
        "offerId": _positive_int(row.get("offer_id")),
        "partyVersion": _positive_int(row.get("party_version")),
        "sourceFileId": _positive_int(row.get("source_file_id")),
        "supplierId": supplier_id,
        "buyerCompanyId": buyer_id,
        "payerCompanyId": payer_id,
        "snapshotHash": str(row.get("snapshot_hash") or "").lower(),
    }
    reasons = []
    if not all(base.values()):
        reasons.append("missing_saved_identity")
    if not SHA_RE.fullmatch(base["snapshotHash"] or "") or _canonical_sha(snapshot) != base["snapshotHash"]:
        reasons.append("snapshot_hash_mismatch")
    if not row.get("supplier_exists"):
        reasons.append("supplier_missing")
    if not row.get("buyer_exists") or not row.get("payer_exists"):
        reasons.append("company_missing")
    if not row.get("file_exists"):
        reasons.append("source_file_missing")
    elif _positive_int(row.get("file_company_id")) != company_id:
        reasons.append("source_file_foreign")
    elif str(row.get("deletion_status") or "") != "active":
        reasons.append("source_file_inactive")
    expected_party = (company_id, supplier_id, buyer_id, payer_id)
    actual_party = tuple(_positive_int(row.get(key)) for key in (
        "party_company_id", "party_supplier_id", "party_buyer_company_id", "party_payer_company_id"
    ))
    if not row.get("offer_exists"):
        reasons.append("offer_missing")
    elif (_positive_int(row.get("offer_company_id")), _positive_int(row.get("offer_supplier_id"))) != (company_id, supplier_id):
        reasons.append("offer_identity_mismatch")
    if not row.get("party_exists"):
        reasons.append("party_version_missing")
    elif actual_party != expected_party:
        reasons.append("party_identity_mismatch")

    registry_id = _positive_int(row.get("registry_id"))
    if registry_id:
        registry_identity = tuple(_positive_int(row.get(key)) for key in (
            "registry_company_id", "registry_supplier_id", "registry_buyer_company_id", "registry_payer_company_id"
        ))
        if reasons or registry_identity != expected_party:
            return {**base, "registryId": registry_id, "status": "quarantined",
                    "reasons": sorted(set(reasons + ["invalid_existing_registry_link"]))}
        return {**base, "registryId": registry_id, "status": "alreadyLinked", "reasons": []}
    if reasons:
        return {**base, "registryId": None, "status": "quarantined", "reasons": sorted(set(reasons))}
    return {**base, "registryId": None, "status": "ready", "reasons": []}


LOAD_SQL = """
SELECT c.*,
       (s.id IS NOT NULL) supplier_exists,
       (bc.id IS NOT NULL) buyer_exists, (pc.id IS NOT NULL) payer_exists,
       (f.id IS NOT NULL) file_exists, f.company_id file_company_id, f.deletion_status,
       (o.id IS NOT NULL) offer_exists, o.company_id offer_company_id, o.supplier_id offer_supplier_id,
       (p.id IS NOT NULL) party_exists, p.company_id party_company_id,
       p.supplier_id party_supplier_id, p.buyer_company_id party_buyer_company_id,
       p.payer_company_id party_payer_company_id,
       m.registry_id, r.company_id registry_company_id, r.supplier_id registry_supplier_id,
       r.buyer_company_id registry_buyer_company_id, r.payer_company_id registry_payer_company_id
  FROM supplier_contract_versions c
  LEFT JOIN suppliers s ON s.id=(CASE WHEN c.snapshot_json->'supplier'->>'supplierId' ~ '^[1-9][0-9]*$'
                                      THEN (c.snapshot_json->'supplier'->>'supplierId')::INTEGER END)
  LEFT JOIN companies bc ON bc.id=(CASE WHEN c.snapshot_json->'buyer'->>'companyId' ~ '^[1-9][0-9]*$'
                                        THEN (c.snapshot_json->'buyer'->>'companyId')::INTEGER END)
  LEFT JOIN companies pc ON pc.id=(CASE WHEN c.snapshot_json->'payer'->>'companyId' ~ '^[1-9][0-9]*$'
                                        THEN (c.snapshot_json->'payer'->>'companyId')::INTEGER END)
  LEFT JOIN file_ownership f ON f.id=c.source_file_id
  LEFT JOIN supplier_offers o ON o.id=c.offer_id
  LEFT JOIN supplier_deal_parties p
    ON p.offer_id=c.offer_id AND p.version=c.party_version AND p.company_id=c.company_id
  LEFT JOIN supplier_contract_registry_versions m ON m.contract_version_id=c.id
  LEFT JOIN supplier_contract_registry r ON r.id=m.registry_id AND r.company_id=m.company_id
 ORDER BY c.id
"""


def _table_fingerprint(cur, table, columns):
    cur.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY {','.join(columns[:1])}")
    rows = []
    for row in cur.fetchall() or []:
        values = list(dict(row).values()) if isinstance(row, dict) else list(row)
        rows.append([str(value) if value is not None else None for value in values])
    return {"count": len(rows), "sha256": _canonical_sha(rows)}


def collect_plan(cur):
    cur.execute(LOAD_SQL)
    items = [classify_contract(row) for row in (cur.fetchall() or [])]
    cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE offer_id IS NULL) AS without_offer FROM supplier_invoices")
    invoice = dict(cur.fetchone() or {})
    baseline = {
        "contractVersions": _table_fingerprint(cur, "supplier_contract_versions", ["id", "company_id", "offer_id", "snapshot_hash"]),
        "registry": _table_fingerprint(cur, "supplier_contract_registry", ["id", "company_id", "supplier_id", "buyer_company_id", "payer_company_id", "archived", "state_version"]),
        "registryVersions": _table_fingerprint(cur, "supplier_contract_registry_versions", ["contract_version_id", "registry_id", "company_id"]),
        "supplierInvoices": {"count": int(invoice.get("total") or 0), "withoutOffer": int(invoice.get("without_offer") or 0)},
    }
    return {
        "ok": True,
        "readyCount": sum(i["status"] == "ready" for i in items),
        "alreadyLinkedCount": sum(i["status"] == "alreadyLinked" for i in items),
        "quarantinedCount": sum(i["status"] == "quarantined" for i in items),
        "planSha256": _plan_sha(items),
        "items": items,
        "baseline": baseline,
    }


def _lock(cur):
    cur.execute("SET LOCAL lock_timeout='5s'")
    cur.execute("SET LOCAL statement_timeout='120s'")
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
    cur.execute("""LOCK TABLE supplier_contract_versions, supplier_contract_registry,
        supplier_contract_registry_versions, supplier_contract_registry_events,
        supplier_deal_parties, supplier_offers, suppliers, companies, file_ownership
        IN SHARE ROW EXCLUSIVE MODE""")


def run(conn, *, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    if apply and (isinstance(expected_ready_count, bool) or not isinstance(expected_ready_count, int) or expected_ready_count < 0):
        raise ValueError("apply requires expected_ready_count")
    expected_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not SHA_RE.fullmatch(expected_sha):
        raise ValueError("apply requires expected_plan_sha256")
    conn.set_session(readonly=not apply, autocommit=False,
                     isolation_level=(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE if apply else None))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if apply:
            _lock(cur)
        result = collect_plan(cur)
        result.update({"mode": "apply" if apply else "dry-run", "dryRun": not apply,
                       "writesAttempted": 0, "rolledBack": False, "complete": False})
        if not apply:
            conn.rollback(); result["rolledBack"] = True
            return result
        if result["quarantinedCount"]:
            raise RuntimeError("quarantined contracts exist; review required")
        if result["readyCount"] != expected_ready_count or result["planSha256"] != expected_sha:
            raise RuntimeError("backfill plan changed; rerun dry-run")
        receipt_rows = []
        for item in result["items"]:
            if item["status"] != "ready":
                continue
            cur.execute("""INSERT INTO supplier_contract_registry
                (company_id,supplier_id,buyer_company_id,payer_company_id)
                VALUES (%s,%s,%s,%s) RETURNING id,created_at""",
                (item["companyId"], item["supplierId"], item["buyerCompanyId"], item["payerCompanyId"]))
            created = dict(cur.fetchone())
            cur.execute("""INSERT INTO supplier_contract_registry_versions
                (contract_version_id,registry_id,company_id) VALUES (%s,%s,%s)""",
                (item["contractVersionId"], created["id"], item["companyId"]))
            receipt_rows.append({"contractVersionId": item["contractVersionId"], "registryId": int(created["id"]),
                                 "companyId": item["companyId"], "snapshotHash": item["snapshotHash"]})
        receipt = {"schemaVersion": 1, "planSha256": result["planSha256"], "created": receipt_rows}
        receipt["receiptSha256"] = _canonical_sha(receipt)
        result.update({"writesAttempted": len(receipt_rows) * 2, "createdCount": len(receipt_rows), "receipt": receipt})
        post = collect_plan(cur)
        if post["readyCount"] or post["quarantinedCount"] or post["alreadyLinkedCount"] != result["alreadyLinkedCount"] + len(receipt_rows):
            raise RuntimeError("backfill postcheck failed")
        conn.commit(); result["complete"] = True
        return result
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close()


def rollback(conn, receipt):
    supplied = dict(receipt or {})
    receipt_sha = str(supplied.pop("receiptSha256", ""))
    if supplied.get("schemaVersion") != 1 or receipt_sha != _canonical_sha(supplied):
        raise ValueError("invalid rollback receipt")
    created = list(supplied.get("created") or [])
    conn.set_session(readonly=False, autocommit=False,
                     isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _lock(cur)
        for item in created:
            cur.execute("""SELECT r.archived,r.state_version,
                    (SELECT COUNT(*) FROM supplier_contract_registry_versions m WHERE m.registry_id=r.id AND m.company_id=r.company_id) member_count,
                    (SELECT COUNT(*) FROM supplier_contract_registry_events e WHERE e.registry_id=r.id AND e.company_id=r.company_id) event_count
                FROM supplier_contract_registry r WHERE r.id=%s AND r.company_id=%s FOR UPDATE""",
                (item["registryId"], item["companyId"]))
            state = cur.fetchone()
            if not state or state["archived"] or state["state_version"] != 0 or state["member_count"] != 1 or state["event_count"] != 0:
                raise RuntimeError("registry changed after backfill; rollback refused")
            cur.execute("""DELETE FROM supplier_contract_registry_versions
                WHERE contract_version_id=%s AND registry_id=%s AND company_id=%s""",
                (item["contractVersionId"], item["registryId"], item["companyId"]))
            if cur.rowcount != 1:
                raise RuntimeError("registry mapping changed; rollback refused")
            cur.execute("DELETE FROM supplier_contract_registry WHERE id=%s AND company_id=%s", (item["registryId"], item["companyId"]))
            if cur.rowcount != 1:
                raise RuntimeError("registry changed; rollback refused")
        conn.commit()
        return {"ok": True, "mode": "rollback", "deletedCount": len(created) * 2, "complete": True}
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close()


def _db_config():
    values = {}
    try:
        env_text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    except OSError:
        env_text = ""
    if env_text:
        for raw in env_text.splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1); values[key.strip()] = value.strip().strip("\"'")
    return {"dbname": os.getenv("DB_NAME") or values.get("DB_NAME") or "stroyka",
            "user": os.getenv("DB_USER") or values.get("DB_USER") or "stroyka",
            "password": os.getenv("DB_PASSWORD") or values.get("DB_PASSWORD") or "password123",
            "host": os.getenv("DB_HOST") or values.get("DB_HOST") or "localhost",
            "port": os.getenv("DB_PORT") or values.get("DB_PORT") or "5432"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe legacy contract registry backfill")
    mode = parser.add_mutually_exclusive_group(); mode.add_argument("--apply", action="store_true"); mode.add_argument("--rollback", metavar="RECEIPT_JSON")
    parser.add_argument("--confirm", default=""); parser.add_argument("--expected-ready-count", type=int); parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    if args.apply and (args.confirm != APPLY_CONFIRMATION or args.expected_ready_count is None or not SHA_RE.fullmatch(str(args.expected_plan_sha256 or ""))):
        parser.error("apply requires confirmation, expected count and plan SHA")
    if args.rollback and args.confirm != ROLLBACK_CONFIRMATION:
        parser.error("rollback requires confirmation")
    conn = psycopg2.connect(**_db_config())
    try:
        result = rollback(conn, json.loads(args.rollback)) if args.rollback else run(
            conn, apply=args.apply, expected_ready_count=args.expected_ready_count,
            expected_plan_sha256=args.expected_plan_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)); return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr); return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
