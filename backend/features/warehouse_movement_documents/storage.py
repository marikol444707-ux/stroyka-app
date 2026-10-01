"""Freeze the exact M-11 organization, route, actor and material at movement time."""

import hashlib
import json

from fastapi import HTTPException


def _text(value):
    return str(value or "").strip()


def _positive(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def snapshot_digest(snapshot):
    value = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def freeze_warehouse_movement(cur, movement_id, actor):
    cur.execute("""SELECT wm.*,c.name AS company_name,r.full_name,r.short_name,r.inn,r.kpp,
        r.ogrn,r.legal_address,r.actual_address,r.phone,r.email,
        (SELECT p.id FROM projects p WHERE p.company_id=wm.company_id AND p.name=wm.from_location ORDER BY p.id LIMIT 1) AS from_project_id,
        (SELECT p.id FROM projects p WHERE p.company_id=wm.company_id AND p.name=wm.to_location ORDER BY p.id LIMIT 1) AS to_project_id
        FROM warehouse_movements wm JOIN companies c ON c.id=wm.company_id
        LEFT JOIN company_requisites r ON r.company_id=wm.company_id
        WHERE wm.id=%s FOR UPDATE OF wm""", (movement_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Перемещение не найдено")
    row = dict(row)
    existing = row.get("document_snapshot_json")
    if isinstance(existing, str):
        existing = json.loads(existing)
    if existing:
        if snapshot_digest(existing) != _text(row.get("document_snapshot_hash")):
            raise HTTPException(409, "Снимок М-11 повреждён")
        return existing
    company_name = _text(row.get("full_name") or row.get("company_name"))
    if not company_name:
        raise HTTPException(409, "Заполните название компании перед перемещением")
    snapshot = {
        "schemaVersion": 1,
        "documentKind": "warehouseMovementM11",
        "company": {
            "companyId": _positive(row.get("company_id")),
            "fullName": company_name,
            "shortName": _text(row.get("short_name")),
            "inn": _text(row.get("inn")),
            "kpp": _text(row.get("kpp")),
            "ogrn": _text(row.get("ogrn")),
            "legalAddress": _text(row.get("legal_address")),
            "actualAddress": _text(row.get("actual_address")),
            "phone": _text(row.get("phone")),
            "email": _text(row.get("email")),
        },
        "document": {
            "movementId": row["id"],
            "date": _text(row.get("date")),
            "notes": _text(row.get("notes")),
            "workPackage": _text(row.get("work_package")) or "Основная",
        },
        "route": {
            "from": {"name": _text(row.get("from_location")), "projectId": _positive(row.get("from_project_id"))},
            "to": {"name": _text(row.get("to_location")), "projectId": _positive(row.get("to_project_id"))},
        },
        "actor": {
            "userId": _positive((actor or {}).get("id")),
            "name": _text((actor or {}).get("name") or (actor or {}).get("email")),
            "role": _text((actor or {}).get("role")),
        },
        "material": {
            "name": _text(row.get("material_name")),
            "quantity": _text(row.get("quantity")),
            "unit": _text(row.get("unit")),
        },
        "source": {
            "invoiceId": _positive(row.get("source_invoice_id")),
            "invoiceLineIndex": row.get("source_invoice_line_index"),
        },
    }
    digest = snapshot_digest(snapshot)
    cur.execute("""UPDATE warehouse_movements SET document_snapshot_json=%s::jsonb,
        document_snapshot_hash=%s,document_snapshot_frozen_at=NOW()
        WHERE id=%s AND company_id=%s""", (
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        digest, row["id"], row["company_id"],
    ))
    return snapshot
