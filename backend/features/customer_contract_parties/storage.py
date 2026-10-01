"""Transactional persistence for frozen customer-contract parties."""

import json
import re

from fastapi import HTTPException

from .snapshot import (
    build_customer_contract_snapshot,
    contract_snapshot_digest,
    is_customer_contract,
)


DOCUMENT_SELECT = """SELECT d.id,d.company_id,d.project_id,d.side,d.doc_type,d.number,d.doc_date,
    d.scan_url,d.sign_status,d.contract_version,d.revises_document_id,
    d.party_snapshot_json,d.party_snapshot_hash,
    p.name AS project_name,p.client_id
    FROM project_documents d
    JOIN projects p ON p.id=d.project_id AND p.company_id=d.company_id
    WHERE d.id=%s FOR UPDATE OF d,p"""
DOCUMENT_KEYS = ("id", "company_id", "project_id", "side", "doc_type", "number", "doc_date",
                 "scan_url", "sign_status", "contract_version", "revises_document_id",
                 "party_snapshot_json", "party_snapshot_hash",
                 "project_name", "client_id")
COMPANY_KEYS = ("company_id", "full_name", "inn", "kpp", "ogrn", "legal_address",
                "actual_address", "phone", "email", "director_name", "director_position",
                "basis", "bank_name", "bik", "rs", "ks")
CUSTOMER_KEYS = ("id", "company_id", "name", "phone", "email", "inn", "kpp", "ogrn",
                 "legal_address", "actual_address", "director_name", "director_position",
                 "basis", "bank_name", "bik", "rs", "ks")
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


def freeze_customer_contract_if_ready(cur, document_id, actor):
    cur.execute(DOCUMENT_SELECT, (document_id,))
    document = _mapping(cur.fetchone(), DOCUMENT_KEYS)
    if not document:
        raise HTTPException(404, "Документ объекта не найден")
    existing = _json(document.get("party_snapshot_json"))
    if existing is not None:
        return existing
    if (not is_customer_contract(document.get("side"), document.get("doc_type"))
            or str(document.get("sign_status") or "").strip() != "Подписан"
            or not str(document.get("scan_url") or "").strip()):
        return None
    company_id = document.get("company_id")
    project = {
        "id": document.get("project_id"),
        "company_id": company_id,
        "name": document.get("project_name"),
        "client_id": document.get("client_id"),
    }
    if not project["client_id"]:
        raise HTTPException(409, "Выберите точную карточку заказчика в объекте перед фиксацией договора")
    file_match = re.fullmatch(r"/tenant-files/([1-9][0-9]*)/content", str(document.get("scan_url") or "").strip())
    if not file_match:
        raise HTTPException(409, "Загрузите оригинал договора в защищённое хранилище компании")
    source_file_id = int(file_match.group(1))
    cur.execute("""SELECT id,company_id,project_id,COALESCE(deletion_status,'active')
        FROM file_ownership WHERE id=%s FOR UPDATE""", (source_file_id,))
    source_file = _mapping(cur.fetchone(), FILE_KEYS)
    if (not source_file or source_file["company_id"] != company_id
            or source_file["project_id"] != project["id"]
            or source_file["deletion_status"] != "active"):
        raise HTTPException(403, "Оригинал договора не принадлежит выбранной компании и объекту")
    document["source_file_id"] = source_file_id
    cur.execute("""SELECT company_id,full_name,inn,kpp,ogrn,legal_address,actual_address,
        phone,email,director_name,director_position,basis,bank_name,bik,rs,ks
        FROM company_requisites WHERE company_id=%s FOR SHARE""", (company_id,))
    company = _mapping(cur.fetchone(), COMPANY_KEYS)
    if not company:
        raise HTTPException(409, "Заполните реквизиты компании-исполнителя перед фиксацией договора")
    cur.execute("""SELECT id,company_id,name,phone,email,inn,kpp,ogrn,legal_address,actual_address,
        director_name,director_position,basis,bank_name,bik,rs,ks
        FROM clients WHERE id=%s AND company_id=%s AND COALESCE(status,'')<>'Архив' FOR SHARE""",
        (project["client_id"], company_id))
    customer = _mapping(cur.fetchone(), CUSTOMER_KEYS)
    if not customer:
        raise HTTPException(409, "Карточка заказчика договора недоступна в выбранной компании")
    snapshot = build_customer_contract_snapshot(document, project, company, customer, actor)
    digest = contract_snapshot_digest(snapshot)
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cur.execute("UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s", (source_file_id,))
    cur.execute("""UPDATE project_documents
        SET party_snapshot_json=%s::jsonb,party_snapshot_hash=%s,party_snapshot_frozen_at=NOW(),
            customer_client_id=%s
        WHERE id=%s AND company_id=%s""",
        (encoded, digest, customer["id"], document_id, company_id))
    return snapshot
