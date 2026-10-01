"""Transactional freezing of a signed contractor contract."""

import json
import re

from fastapi import HTTPException

from .snapshot import build_contract_snapshot, snapshot_digest


def _mapping(row, keys):
    if isinstance(row, dict):
        return row
    return dict(zip(keys, row)) if isinstance(row, (tuple, list)) else None


def freeze_contract(cur, contract_id, company_id, scan_url, actor):
    cur.execute("""SELECT id,company_id,project_id,project_name,brigade_name,contractor_type,
        contractor_id,status,signed_at,contract_scan_url,party_snapshot_json
        FROM brigade_contracts WHERE id=%s AND company_id=%s FOR UPDATE""", (contract_id, company_id))
    contract = _mapping(cur.fetchone(), (
        "id", "company_id", "project_id", "project_name", "brigade_name", "contractor_type",
        "contractor_id", "status", "signed_at", "contract_scan_url", "party_snapshot_json",
    ))
    if not contract:
        raise HTTPException(404, "Договор исполнителя не найден")
    if contract.get("party_snapshot_json") is not None:
        raise HTTPException(409, "Подписанный договор уже сохранён и не изменяется")
    if not contract.get("contractor_id"):
        raise HTTPException(409, "Выберите точную карточку исполнителя перед подписанием")
    match = re.fullmatch(r"/tenant-files/([1-9][0-9]*)/content", str(scan_url or "").strip())
    if not match:
        raise HTTPException(409, "Загрузите подписанный оригинал в защищённое хранилище")
    file_id = int(match.group(1))
    cur.execute("""SELECT id,company_id,project_id,COALESCE(deletion_status,'active')
        FROM file_ownership WHERE id=%s FOR UPDATE""", (file_id,))
    source = _mapping(cur.fetchone(), ("id", "company_id", "project_id", "deletion_status"))
    if (not source or source["company_id"] != company_id
            or source["project_id"] != contract["project_id"] or source["deletion_status"] != "active"):
        raise HTTPException(403, "Оригинал договора не принадлежит выбранной компании и объекту")
    cur.execute("""SELECT company_id,full_name,inn,kpp,ogrn,legal_address,director_name,
        director_position,basis,bank_name,bik,rs,ks FROM company_requisites
        WHERE company_id=%s FOR SHARE""", (company_id,))
    company = _mapping(cur.fetchone(), ("company_id", "full_name", "inn", "kpp", "ogrn",
        "legal_address", "director_name", "director_position", "basis", "bank_name", "bik", "rs", "ks"))
    if not company:
        raise HTTPException(409, "Заполните реквизиты компании перед подписанием договора")
    cur.execute("""SELECT mp.user_id,mp.full_name,mp.passport,mp.inn,mp.contract_type,
        mp.bank_account,mp.bank_name,mp.phone,mp.ogrnip,mp.kpp,mp.ogrn,mp.legal_address,
        mp.bank_bik,mp.bank_corr,mp.signatory_name,mp.signatory_position,mp.signatory_basis
        FROM master_profiles mp JOIN users u ON u.id=mp.user_id
        WHERE mp.user_id=%s AND COALESCE(u.active,TRUE)=TRUE
          AND (u.company_id=%s OR EXISTS(SELECT 1 FROM user_company_roles r
              WHERE r.user_id=u.id AND r.company_id=%s AND COALESCE(r.active,TRUE)=TRUE))
        FOR SHARE OF mp,u""", (contract["contractor_id"], company_id, company_id))
    contractor = _mapping(cur.fetchone(), ("user_id", "full_name", "passport", "inn", "contract_type",
        "bank_account", "bank_name", "phone", "ogrnip", "kpp", "ogrn", "legal_address",
        "bank_bik", "bank_corr", "signatory_name", "signatory_position", "signatory_basis"))
    if not contractor:
        raise HTTPException(409, "Заполните карточку выбранного исполнителя перед подписанием договора")
    cur.execute("SELECT CURRENT_DATE")
    contract["signed_at"] = str(cur.fetchone()[0])
    contract["contract_scan_url"] = str(scan_url).strip()
    contract["source_file_id"] = file_id
    snapshot = build_contract_snapshot(contract, company, contractor, actor)
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = snapshot_digest(snapshot)
    cur.execute("UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s", (file_id,))
    cur.execute("""UPDATE brigade_contracts SET status='Подписан',signed_at=CURRENT_DATE,
        contract_scan_url=%s,party_snapshot_json=%s::jsonb,party_snapshot_hash=%s,
        party_snapshot_frozen_at=NOW() WHERE id=%s AND company_id=%s""",
        (str(scan_url).strip(), encoded, digest, contract_id, company_id))
    return snapshot
