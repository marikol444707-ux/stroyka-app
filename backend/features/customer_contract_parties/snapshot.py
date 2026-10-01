"""Build immutable customer-contract parties from authorized stored profiles."""

import hashlib
import json

from fastapi import HTTPException


CONTRACT_MARKERS = ("договор", "контракт", "соглаш")
PARTY_FIELDS = (
    "inn", "kpp", "ogrn", "legalAddress", "actualAddress", "phone", "email",
    "directorName", "directorPosition", "basis", "bankName", "bik", "rs", "ks",
)
ROW_FIELDS = {
    "legalAddress": "legal_address",
    "actualAddress": "actual_address",
    "directorName": "director_name",
    "directorPosition": "director_position",
    "bankName": "bank_name",
}
REQUIRED_FIELDS = ("fullName", "inn", "legalAddress", "directorName", "directorPosition", "basis")


def _text(value):
    return str(value or "").strip()


def _value(row, api_field):
    return _text((row or {}).get(ROW_FIELDS.get(api_field, api_field)))


def _positive(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def is_customer_contract(side, document_type):
    kind = _text(document_type).casefold()
    return _text(side).casefold() == "customer" and any(marker in kind for marker in CONTRACT_MARKERS)


def _party(row, *, identity_key, identity_value):
    full_name = _text((row or {}).get("full_name") or (row or {}).get("name"))
    party = {"fullName": full_name, identity_key: identity_value}
    party.update({field: _value(row, field) for field in PARTY_FIELDS})
    return party


def _validate_party(label, party):
    missing = [field for field in REQUIRED_FIELDS if not _text(party.get(field))]
    if missing:
        raise HTTPException(
            status_code=409,
            detail=f"Заполните реквизиты {label} перед фиксацией подписанного договора: " + ", ".join(missing),
        )


def build_customer_contract_snapshot(document, project, company, customer, actor):
    company_id = _positive((company or {}).get("company_id"))
    customer_id = _positive((customer or {}).get("id"))
    project_id = _positive((project or {}).get("id"))
    if not company_id or company_id != _positive((project or {}).get("company_id")):
        raise HTTPException(409, "Компания договора не совпадает с компанией объекта")
    if company_id != _positive((customer or {}).get("company_id")):
        raise HTTPException(409, "Заказчик относится к другой компании")
    if customer_id != _positive((project or {}).get("client_id")):
        raise HTTPException(409, "Заказчик договора не совпадает с заказчиком объекта")
    if project_id != _positive((document or {}).get("project_id")):
        raise HTTPException(409, "Договор относится к другому объекту")

    executor = _party(company, identity_key="companyId", identity_value=company_id)
    customer_party = _party(customer, identity_key="clientId", identity_value=customer_id)
    _validate_party("исполнителя", executor)
    _validate_party("заказчика", customer_party)
    missing_optional = [
        f"{side}.{field}"
        for side, party in (("executor", executor), ("customer", customer_party))
        for field in ("bankName", "bik", "rs", "ks") if not party.get(field)
    ]
    return {
        "schemaVersion": 1,
        "executor": executor,
        "customer": customer_party,
        "project": {"id": project_id, "name": _text((project or {}).get("name"))},
        "contract": {
            "number": _text((document or {}).get("number")),
            "date": _text((document or {}).get("doc_date")),
            "documentType": _text((document or {}).get("doc_type")),
            "version": _positive((document or {}).get("contract_version")) or 1,
            "revisesDocumentId": _positive((document or {}).get("revises_document_id")),
        },
        "source": {
            "fileId": _positive((document or {}).get("source_file_id")),
            "fileUrl": _text((document or {}).get("scan_url")),
        },
        "frozenBy": {
            "userId": _positive((actor or {}).get("id")),
            "name": _text((actor or {}).get("name") or (actor or {}).get("email")),
        },
        "missingOptionalRequisites": missing_optional,
    }


def contract_snapshot_digest(snapshot):
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
