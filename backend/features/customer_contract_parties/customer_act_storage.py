"""Freeze signed KS-2/KS-3 parties from one exact signed customer contract."""

import json
import re

from fastapi import HTTPException

from .snapshot import contract_snapshot_digest, is_customer_contract


ACT_TYPES = frozenset(("акт кс-2", "акт кс-3"))
DOCUMENT_SELECT = """SELECT d.id,d.company_id,d.project_id,d.side,d.doc_type,d.number,d.doc_date,
    d.counterparty,d.amount,d.scan_url,d.sign_status,d.basis_contract_document_id,
    d.party_snapshot_json,d.party_snapshot_hash,p.name AS project_name,p.client_id
    FROM project_documents d
    JOIN projects p ON p.id=d.project_id AND p.company_id=d.company_id
    WHERE d.id=%s FOR UPDATE OF d,p"""
DOCUMENT_KEYS = ("id", "company_id", "project_id", "side", "doc_type", "number", "doc_date",
                 "counterparty", "amount", "scan_url", "sign_status", "basis_contract_document_id",
                 "party_snapshot_json", "party_snapshot_hash", "project_name", "client_id")
CONTRACT_KEYS = ("id", "company_id", "project_id", "side", "doc_type", "number", "doc_date",
                 "contract_version", "party_snapshot_json", "party_snapshot_hash", "customer_client_id",
                 "sign_status", "scan_url")
FILE_KEYS = ("id", "company_id", "project_id", "deletion_status")


def _mapping(row, keys):
    if isinstance(row, dict):
        return row
    if isinstance(row, (list, tuple)):
        return dict(zip(keys, row))
    return None


def _json(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            return None
    return None


def _positive(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _text(value):
    return str(value or "").strip()


def is_customer_work_act(side, document_type):
    return _text(side).casefold() == "customer" and _text(document_type).casefold() in ACT_TYPES


def _source_file(cur, document):
    match = re.fullmatch(r"/tenant-files/([1-9][0-9]*)/content", _text(document.get("scan_url")))
    if not match:
        raise HTTPException(409, "Загрузите подписанный КС в защищённое хранилище компании")
    file_id = int(match.group(1))
    cur.execute("""SELECT id,company_id,project_id,COALESCE(deletion_status,'active')
        FROM file_ownership WHERE id=%s FOR UPDATE""", (file_id,))
    source = _mapping(cur.fetchone(), FILE_KEYS)
    if (not source or source["company_id"] != document["company_id"]
            or source["project_id"] != document["project_id"]
            or source["deletion_status"] != "active"):
        raise HTTPException(403, "Подписанный КС не принадлежит выбранной компании и объекту")
    return source


def _contract(cur, document):
    contract_id = _positive(document.get("basis_contract_document_id"))
    if not contract_id:
        raise HTTPException(409, "Выберите подписанный договор с заказчиком для КС")
    cur.execute("""SELECT id,company_id,project_id,side,doc_type,number,doc_date,
        contract_version,party_snapshot_json,party_snapshot_hash,customer_client_id,
        sign_status,scan_url FROM project_documents WHERE id=%s FOR SHARE""", (contract_id,))
    contract = _mapping(cur.fetchone(), CONTRACT_KEYS)
    saved = _json((contract or {}).get("party_snapshot_json"))
    if (not contract or contract["company_id"] != document["company_id"]
            or contract["project_id"] != document["project_id"]
            or not is_customer_contract(contract.get("side"), contract.get("doc_type"))
            or _text(contract.get("sign_status")) != "Подписан"
            or not _text(contract.get("scan_url"))
            or not saved):
        raise HTTPException(409, "Договор-основание не является подписанным договором этого объекта")
    if contract.get("customer_client_id") != document.get("client_id"):
        raise HTTPException(409, "Заказчик договора не совпадает с заказчиком объекта")
    if contract_snapshot_digest(saved) != _text(contract.get("party_snapshot_hash")):
        raise HTTPException(409, "Снимок сторон договора-основания повреждён")
    if (_positive((saved.get("executor") or {}).get("companyId")) != contract["company_id"]
            or _positive((saved.get("customer") or {}).get("clientId")) != contract["customer_client_id"]
            or _positive((saved.get("project") or {}).get("id")) != contract["project_id"]):
        raise HTTPException(409, "Стороны договора-основания не соответствуют его владельцу и объекту")
    return contract, saved


def freeze_customer_act_if_ready(cur, document_id, actor):
    cur.execute(DOCUMENT_SELECT, (document_id,))
    document = _mapping(cur.fetchone(), DOCUMENT_KEYS)
    if not document:
        raise HTTPException(404, "Документ объекта не найден")
    existing = _json(document.get("party_snapshot_json"))
    if existing is not None:
        return existing
    if not is_customer_work_act(document.get("side"), document.get("doc_type")):
        return None
    if _text(document.get("sign_status")) != "Подписан":
        return None
    if not _text(document.get("scan_url")):
        raise HTTPException(409, "Загрузите подписанный КС перед фиксацией сторон")

    source = _source_file(cur, document)
    contract, contract_snapshot = _contract(cur, document)
    snapshot = {
        "schemaVersion": 1,
        "documentKind": "customerWorkAct",
        "executor": contract_snapshot["executor"],
        "customer": contract_snapshot["customer"],
        "project": contract_snapshot["project"],
        "contractBasis": {
            "documentId": contract["id"],
            "number": _text(contract.get("number")),
            "date": _text(contract.get("doc_date")),
            "version": _positive(contract.get("contract_version")) or 1,
            "partySnapshotHash": _text(contract.get("party_snapshot_hash")),
        },
        "document": {
            "id": document["id"],
            "documentType": _text(document.get("doc_type")),
            "number": _text(document.get("number")),
            "date": _text(document.get("doc_date")),
            "amount": _text(document.get("amount")),
        },
        "source": {"fileId": source["id"], "fileUrl": _text(document.get("scan_url"))},
        "frozenBy": {
            "userId": _positive((actor or {}).get("id")),
            "name": _text((actor or {}).get("name") or (actor or {}).get("email")),
        },
        "missingOptionalRequisites": list(contract_snapshot.get("missingOptionalRequisites") or []),
    }
    digest = contract_snapshot_digest(snapshot)
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cur.execute("UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s", (source["id"],))
    cur.execute("""UPDATE project_documents
        SET party_snapshot_json=%s::jsonb,party_snapshot_hash=%s,party_snapshot_frozen_at=NOW(),
            customer_client_id=%s
        WHERE id=%s AND company_id=%s""",
        (encoded, digest, document["client_id"], document_id, document["company_id"]))
    return snapshot
