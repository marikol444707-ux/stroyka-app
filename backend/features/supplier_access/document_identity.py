import re


def _text(mapping, *keys):
    for key in keys:
        value = (mapping or {}).get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def build_document_supplier_payload(data, fallback_name=""):
    data = data if isinstance(data, dict) else {}
    requisites = data.get("supplierRequisites") or data.get("supplier_requisites") or {}
    requisites = requisites if isinstance(requisites, dict) else {}

    def value(*keys):
        return _text(requisites, *keys) or _text(data, *keys)

    return {
        "supplierName": value("name", "supplierName", "supplier_name", "supplier") or str(fallback_name or "").strip(),
        "supplierInn": _digits(value("inn", "supplierInn", "supplier_inn")),
        "supplierKpp": _digits(value("kpp", "supplierKpp", "supplier_kpp")),
        "supplierOgrn": _digits(value("ogrn", "ogrnip", "supplierOgrn", "supplier_ogrn")),
        "legalAddress": value("legalAddress", "legal_address"),
        "bank": value("bank"),
        "bik": _digits(value("bik")),
        "bankAccount": _digits(value("bankAccount", "bank_account", "account")),
        "corrAccount": _digits(value("corrAccount", "corr_account", "korAccount", "kor_account")),
        "signerName": value("signerName", "signer_name", "directorName", "director_name"),
        "signerBasis": value("signerBasis", "signer_basis", "directorPosition", "director_position"),
    }


def has_legal_supplier_identity(payload):
    payload = payload if isinstance(payload, dict) else {}
    inn = _digits(_text(payload, "supplierInn", "supplier_inn", "inn"))
    ogrn = _digits(_text(payload, "supplierOgrn", "supplier_ogrn", "ogrn", "ogrnip"))
    return len(inn) in (10, 12) or len(ogrn) in (13, 15)
