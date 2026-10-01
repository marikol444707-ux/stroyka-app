"""Freeze the addressed parties of an outgoing customer letter."""

import hashlib
import json

from fastapi import HTTPException


COMPANY_KEYS = ("company_id", "full_name", "short_name", "inn", "kpp", "ogrn",
                "legal_address", "phone", "email")
CUSTOMER_KEYS = ("id", "company_id", "name", "phone", "email", "inn", "kpp",
                 "ogrn", "legal_address")


def _mapping(row, keys):
    if isinstance(row, dict):
        return row
    if isinstance(row, (tuple, list)):
        return dict(zip(keys, row))
    return None


def _text(value):
    return str(value or "").strip()


def _positive(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def snapshot_digest(snapshot):
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_snapshot(project, company, customer, actor):
    company_id = _positive(company.get("company_id"))
    project_id = _positive(project.get("id"))
    customer_id = _positive(customer.get("id"))
    if not company_id or company_id != _positive(project.get("company_id")):
        raise HTTPException(409, "Компания письма не совпадает с компанией объекта")
    if company_id != _positive(customer.get("company_id")):
        raise HTTPException(409, "Заказчик письма относится к другой компании")
    if customer_id != _positive(project.get("client_id")):
        raise HTTPException(409, "Получатель письма не совпадает с заказчиком объекта")
    sender_name = _text(company.get("full_name"))
    recipient_name = _text(customer.get("name"))
    if not sender_name:
        raise HTTPException(409, "Заполните название своей компании перед отправкой письма")
    if not recipient_name:
        raise HTTPException(409, "Заполните название заказчика перед отправкой письма")
    return {
        "schemaVersion": 1,
        "sender": {
            "companyId": company_id,
            "fullName": sender_name,
            "shortName": _text(company.get("short_name")),
            "inn": _text(company.get("inn")),
            "kpp": _text(company.get("kpp")),
            "ogrn": _text(company.get("ogrn")),
            "legalAddress": _text(company.get("legal_address")),
            "phone": _text(company.get("phone")),
            "email": _text(company.get("email")),
        },
        "recipient": {
            "clientId": customer_id,
            "fullName": recipient_name,
            "inn": _text(customer.get("inn")),
            "kpp": _text(customer.get("kpp")),
            "ogrn": _text(customer.get("ogrn")),
            "legalAddress": _text(customer.get("legal_address")),
            "phone": _text(customer.get("phone")),
            "email": _text(customer.get("email")),
        },
        "project": {"id": project_id, "name": _text(project.get("name"))},
        "sentBy": {
            "userId": _positive(actor.get("id")),
            "name": _text(actor.get("name") or actor.get("email") or actor.get("role")),
        },
    }


def capture_snapshot(cur, parent, actor):
    company_id, project_id = parent["companyId"], parent["id"]
    cur.execute("""SELECT p.id,p.company_id,p.name,p.client_id FROM projects p
        WHERE p.id=%s AND p.company_id=%s FOR SHARE""", (project_id, company_id))
    project = _mapping(cur.fetchone(), ("id", "company_id", "name", "client_id"))
    if not project or not _positive(project.get("client_id")):
        raise HTTPException(409, "Выберите точную карточку заказчика в объекте перед отправкой письма")
    cur.execute("""SELECT c.id,
        COALESCE(NULLIF(r.full_name,''),NULLIF(c.name,''),'') AS full_name,
        COALESCE(NULLIF(r.short_name,''),NULLIF(c.short_name,''),'') AS short_name,
        COALESCE(NULLIF(r.inn,''),NULLIF(c.inn,''),'') AS inn,
        COALESCE(NULLIF(r.kpp,''),NULLIF(c.kpp,''),'') AS kpp,
        COALESCE(NULLIF(r.ogrn,''),NULLIF(c.ogrn,''),'') AS ogrn,
        COALESCE(NULLIF(r.legal_address,''),NULLIF(c.legal_address,''),'') AS legal_address,
        COALESCE(NULLIF(r.phone,''),NULLIF(c.phone,''),'') AS phone,
        COALESCE(NULLIF(r.email,''),NULLIF(c.email,''),'') AS email
        FROM companies c LEFT JOIN company_requisites r ON r.company_id=c.id
        WHERE c.id=%s AND COALESCE(c.active,TRUE) FOR SHARE OF c""", (company_id,))
    company = _mapping(cur.fetchone(), COMPANY_KEYS)
    if not company:
        raise HTTPException(409, "Карточка выбранной компании недоступна")
    cur.execute("""SELECT id,company_id,name,phone,email,inn,kpp,ogrn,legal_address
        FROM clients WHERE id=%s AND company_id=%s AND COALESCE(status,'')<>'Архив' FOR SHARE""",
        (project["client_id"], company_id))
    customer = _mapping(cur.fetchone(), CUSTOMER_KEYS)
    if not customer:
        raise HTTPException(409, "Карточка заказчика объекта недоступна")
    return build_snapshot(project, company, customer, actor), customer["id"]
