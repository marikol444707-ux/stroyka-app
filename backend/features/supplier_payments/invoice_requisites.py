"""Read-only payment requisites from an invoice's immutable contract version."""
import hashlib
import json

from fastapi import HTTPException


def _fail():
    raise HTTPException(409, "Реквизиты счёта и проверенного договора требуют сверки")


def _positive_id(value):
    if type(value) is not int or value <= 0:
        _fail()
    return value


def _text(party, field):
    value = party.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        _fail()
    return value


def _company(party):
    return {
        "companyId": _positive_id(party.get("companyId")),
        "fullName": _text(party, "fullName"),
        "inn": _text(party, "inn"),
        "kpp": _text(party, "kpp"),
    }


def _supplier(party):
    return {
        "supplierId": _positive_id(party.get("supplierId")),
        "fullName": _text(party, "fullName"),
        "inn": _text(party, "inn"),
        "kpp": _text(party, "kpp"),
        "bankName": _text(party, "bankName"),
        "bik": _text(party, "bik"),
        "rs": _text(party, "rs"),
        "ks": _text(party, "ks"),
    }


def invoice_requisites_projection(
    *, snapshot, snapshot_hash, contract_version_id, company_id, supplier_id,
):
    """Return only fields needed to identify the payer and prepare payment."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot_hash, str):
        _fail()
    try:
        encoded = json.dumps(
            snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        _fail()
    if hashlib.sha256(encoded.encode()).hexdigest() != snapshot_hash:
        _fail()
    try:
        payer = _company(snapshot["payer"])
        buyer = _company(snapshot["buyer"])
        supplier = _supplier(snapshot["supplier"])
    except (KeyError, AttributeError):
        _fail()
    if buyer["companyId"] != _positive_id(company_id):
        _fail()
    if supplier["supplierId"] != _positive_id(supplier_id):
        _fail()
    result = {
        "contractVersionId": _positive_id(contract_version_id),
        "contractNumber": _text(snapshot, "number"),
        "contractDate": _text(snapshot, "date"),
        "snapshotHash": snapshot_hash,
        "payer": payer,
        "supplier": supplier,
        "paymentTerms": _text(snapshot, "paymentTerms"),
    }
    if buyer != payer:
        result["buyer"] = buyer
    return result
