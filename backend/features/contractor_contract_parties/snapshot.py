"""Build an immutable contract snapshot from exact company and user records."""

import hashlib
import json

from fastapi import HTTPException


def _text(value):
    return str(value or "").strip()


def _positive(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _required(label, values):
    missing = [caption for caption, value in values if not _text(value)]
    if missing:
        raise HTTPException(409, "Заполните реквизиты %s: %s" % (label, ", ".join(missing)))


def build_contract_snapshot(contract, company, contractor, actor):
    company_id = _positive((company or {}).get("company_id"))
    contractor_id = _positive((contractor or {}).get("user_id"))
    if company_id != _positive((contract or {}).get("company_id")):
        raise HTTPException(409, "Компания договора не совпадает с выбранной компанией")
    if contractor_id != _positive((contract or {}).get("contractor_id")):
        raise HTTPException(409, "Карточка исполнителя не совпадает с договором")
    customer = {
        "companyId": company_id,
        "fullName": _text(company.get("full_name")), "inn": _text(company.get("inn")),
        "kpp": _text(company.get("kpp")), "ogrn": _text(company.get("ogrn")),
        "legalAddress": _text(company.get("legal_address")),
        "directorName": _text(company.get("director_name")),
        "directorPosition": _text(company.get("director_position")),
        "basis": _text(company.get("basis")), "bankName": _text(company.get("bank_name")),
        "bik": _text(company.get("bik")), "rs": _text(company.get("rs")),
        "ks": _text(company.get("ks")),
    }
    contractor_type = _text(contractor.get("contract_type") or contract.get("contractor_type"))
    performer = {
        "userId": contractor_id, "fullName": _text(contractor.get("full_name")),
        "type": contractor_type, "role": _text(contract.get("contractor_type")),
        "passport": _text(contractor.get("passport")),
        "inn": _text(contractor.get("inn")), "ogrnip": _text(contractor.get("ogrnip")),
        "kpp": _text(contractor.get("kpp")), "ogrn": _text(contractor.get("ogrn")),
        "legalAddress": _text(contractor.get("legal_address")),
        "phone": _text(contractor.get("phone")), "bankName": _text(contractor.get("bank_name")),
        "bankAccount": _text(contractor.get("bank_account")),
        "bankBik": _text(contractor.get("bank_bik")), "bankCorr": _text(contractor.get("bank_corr")),
        "signatoryName": _text(contractor.get("signatory_name")),
        "signatoryPosition": _text(contractor.get("signatory_position")),
        "signatoryBasis": _text(contractor.get("signatory_basis")),
    }
    _required("компании-заказчика", (
        ("название", customer["fullName"]), ("ИНН", customer["inn"]),
        ("юридический адрес", customer["legalAddress"]),
        ("подписант", customer["directorName"]), ("должность", customer["directorPosition"]),
        ("основание полномочий", customer["basis"]),
    ))
    required = [("ФИО", performer["fullName"]), ("ИНН", performer["inn"]),
                ("расчётный счёт", performer["bankAccount"]), ("банк", performer["bankName"])]
    lowered_type = (contractor_type + " " + _text(contract.get("contractor_type"))).casefold()
    if "ип" in lowered_type:
        required.append(("ОГРНИП", performer["ogrnip"]))
    if "ооо" in lowered_type:
        required.extend((("КПП", performer["kpp"]), ("ОГРН", performer["ogrn"]),
                         ("юридический адрес", performer["legalAddress"]),
                         ("подписант", performer["signatoryName"]),
                         ("должность подписанта", performer["signatoryPosition"]),
                         ("основание полномочий", performer["signatoryBasis"])))
    if any(marker in lowered_type for marker in ("гпх", "физ", "самозан")):
        required.append(("паспорт", performer["passport"]))
    _required("исполнителя", required)
    return {
        "schemaVersion": 1, "customer": customer, "contractor": performer,
        "project": {"id": _positive(contract.get("project_id")), "name": _text(contract.get("project_name"))},
        "contract": {"id": _positive(contract.get("id")), "signedAt": _text(contract.get("signed_at"))},
        "source": {"fileId": _positive(contract.get("source_file_id")),
                   "fileUrl": _text(contract.get("contract_scan_url"))},
        "frozenBy": {"userId": _positive((actor or {}).get("id")),
                     "name": _text((actor or {}).get("name") or (actor or {}).get("email"))},
    }


def snapshot_digest(snapshot):
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
