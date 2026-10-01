"""Freeze M-15 issue and receipt parties without consulting later profile state."""

import hashlib
import json

from fastapi import HTTPException


TRANSFER_SELECT = """SELECT mt.id,mt.company_id,mt.project_id,mt.project_name,mt.from_location,
    mt.to_user_id,mt.to_person,mt.to_person_role,mt.work_package,mt.material_name,mt.quantity,
    mt.unit,mt.transfer_date,mt.notes,mt.created_by,mt.invoice_id,mt.invoice_line_key,
    mt.invoice_line_index,mt.invoice_number,mt.signed,mt.issue_party_snapshot_json,
    mt.issue_party_snapshot_hash,mt.receipt_party_snapshot_json,mt.receipt_party_snapshot_hash,
    c.name AS company_name,r.full_name,r.short_name,r.inn,r.kpp,r.ogrn,r.legal_address,
    r.actual_address,r.phone,r.email
    FROM material_transfers mt
    JOIN companies c ON c.id=mt.company_id
    LEFT JOIN company_requisites r ON r.company_id=mt.company_id
    WHERE mt.id=%s FOR UPDATE OF mt"""


def _text(value):
    return str(value or "").strip()


def _positive(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _json(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else None
        except (TypeError, ValueError):
            return None
    return None


def snapshot_digest(snapshot):
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load(cur, transfer_id):
    cur.execute(TRANSFER_SELECT, (transfer_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Передача материала не найдена")
    return dict(row)


def _actor(actor):
    return {
        "userId": _positive((actor or {}).get("id")),
        "name": _text((actor or {}).get("name") or (actor or {}).get("email")),
        "role": _text((actor or {}).get("role")),
    }


def _company(row):
    return {
        "companyId": _positive(row.get("company_id")),
        "fullName": _text(row.get("full_name") or row.get("company_name")),
        "shortName": _text(row.get("short_name")),
        "inn": _text(row.get("inn")),
        "kpp": _text(row.get("kpp")),
        "ogrn": _text(row.get("ogrn")),
        "legalAddress": _text(row.get("legal_address")),
        "actualAddress": _text(row.get("actual_address")),
        "phone": _text(row.get("phone")),
        "email": _text(row.get("email")),
    }


def _validated_issue(row):
    saved = _json(row.get("issue_party_snapshot_json"))
    if not saved:
        return None
    if snapshot_digest(saved) != _text(row.get("issue_party_snapshot_hash")):
        raise HTTPException(409, "Снимок выдачи материала повреждён")
    project = saved.get("project") or {}
    receiver = saved.get("intendedReceiver") or {}
    document = saved.get("document") or {}
    material = saved.get("material") or {}
    source = saved.get("source") or {}
    if (_positive((saved.get("company") or {}).get("companyId")) != row["company_id"]
            or _positive(project.get("id")) != row["project_id"]
            or _text(project.get("name")) != _text(row.get("project_name"))
            or _positive(receiver.get("userId")) != row["to_user_id"]
            or _text(receiver.get("name")) != _text(row.get("to_person"))
            or _text(receiver.get("role")) != _text(row.get("to_person_role"))
            or _positive(document.get("transferId")) != row["id"]
            or _text(document.get("date")) != _text(row.get("transfer_date"))
            or _text(document.get("fromLocation")) != _text(row.get("from_location"))
            or (_text(document.get("workPackage")) or "Основная") != (_text(row.get("work_package")) or "Основная")
            or _text(document.get("notes")) != _text(row.get("notes"))
            or _text(material.get("name")) != _text(row.get("material_name"))
            or _text(material.get("quantity")) != _text(row.get("quantity"))
            or _text(material.get("unit")) != _text(row.get("unit"))
            or _positive(source.get("invoiceId")) != _positive(row.get("invoice_id"))
            or source.get("invoiceLineIndex") != row.get("invoice_line_index")):
        raise HTTPException(409, "Снимок выдачи не соответствует компании, объекту или получателю")
    return saved


def freeze_material_transfer_issue(cur, transfer_id, actor):
    row = _load(cur, transfer_id)
    existing = _validated_issue(row)
    if existing:
        return existing
    if not row.get("company_id") or not row.get("project_id") or not row.get("to_user_id"):
        raise HTTPException(409, "Для документа выдачи нужны точные компания, объект и получатель")
    company = _company(row)
    if not company["fullName"]:
        raise HTTPException(409, "Заполните название компании перед выдачей материала")
    snapshot = {
        "schemaVersion": 1,
        "documentKind": "materialIssueM15",
        "company": company,
        "project": {"id": row["project_id"], "name": _text(row.get("project_name"))},
        "sender": _actor(actor),
        "intendedReceiver": {
            "userId": row["to_user_id"],
            "name": _text(row.get("to_person")),
            "role": _text(row.get("to_person_role")),
        },
        "document": {
            "transferId": row["id"],
            "date": _text(row.get("transfer_date")),
            "fromLocation": _text(row.get("from_location")),
            "workPackage": _text(row.get("work_package")) or "Основная",
            "notes": _text(row.get("notes")),
        },
        "material": {
            "name": _text(row.get("material_name")),
            "quantity": _text(row.get("quantity")),
            "unit": _text(row.get("unit")),
        },
        "source": {
            "invoiceId": _positive(row.get("invoice_id")),
            "invoiceLineKey": _text(row.get("invoice_line_key")),
            "invoiceLineIndex": row.get("invoice_line_index"),
            "invoiceNumber": _text(row.get("invoice_number")),
        },
    }
    digest = snapshot_digest(snapshot)
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cur.execute("""UPDATE material_transfers
        SET issue_party_snapshot_json=%s::jsonb,issue_party_snapshot_hash=%s,
            issue_party_snapshot_frozen_at=NOW()
        WHERE id=%s AND company_id=%s""", (encoded, digest, row["id"], row["company_id"]))
    return snapshot


def freeze_material_transfer_receipt(cur, transfer_id, actor):
    row = _load(cur, transfer_id)
    issue = _validated_issue(row)
    if not issue:
        raise HTTPException(409, "Историческую выдачу без снимка сторон нельзя подписать как новый документ")
    receiver = _actor(actor)
    if receiver["userId"] != row["to_user_id"]:
        raise HTTPException(403, "Подписать передачу материала может только зафиксированный получатель")
    existing = _json(row.get("receipt_party_snapshot_json"))
    if existing:
        if snapshot_digest(existing) != _text(row.get("receipt_party_snapshot_hash")):
            raise HTTPException(409, "Снимок приёмки материала повреждён")
        if (_positive(existing.get("transferId")) != row["id"]
                or _positive(existing.get("companyId")) != row["company_id"]
                or _positive(existing.get("projectId")) != row["project_id"]
                or _positive((existing.get("receiver") or {}).get("userId")) != row["to_user_id"]
                or _text(existing.get("issueSnapshotHash")) != _text(row.get("issue_party_snapshot_hash"))):
            raise HTTPException(409, "Снимок приёмки не соответствует выдаче материала")
        return existing
    if row.get("signed"):
        raise HTTPException(409, "Историческая подпись не содержит зафиксированного получателя")
    snapshot = {
        "schemaVersion": 1,
        "documentKind": "materialIssueReceipt",
        "transferId": row["id"],
        "companyId": row["company_id"],
        "projectId": row["project_id"],
        "receiver": receiver,
        "issueSnapshotHash": _text(row.get("issue_party_snapshot_hash")),
    }
    digest = snapshot_digest(snapshot)
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cur.execute("""UPDATE material_transfers
        SET signed=TRUE,signed_at=NOW(),receipt_party_snapshot_json=%s::jsonb,
            receipt_party_snapshot_hash=%s,receipt_party_snapshot_frozen_at=NOW()
        WHERE id=%s AND company_id=%s AND signed=FALSE""",
        (encoded, digest, row["id"], row["company_id"]))
    if cur.rowcount != 1:
        raise HTTPException(409, "Передача материала была подписана одновременно с запросом")
    return snapshot
