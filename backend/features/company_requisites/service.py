"""Canonical company requisites normalization and persistence."""

import re


REQUISITE_FIELDS = (
    "fullName",
    "shortName",
    "inn",
    "kpp",
    "ogrn",
    "legalAddress",
    "actualAddress",
    "phone",
    "email",
    "directorName",
    "directorPosition",
    "basis",
    "bankName",
    "bik",
    "rs",
    "ks",
)

_ALIASES = {
    "fullName": ("fullName", "full_name", "companyName", "name"),
    "shortName": ("shortName", "short_name"),
    "inn": ("inn",),
    "kpp": ("kpp",),
    "ogrn": ("ogrn", "ogrnip"),
    "legalAddress": ("legalAddress", "legal_address"),
    "actualAddress": ("actualAddress", "actual_address"),
    "phone": ("phone", "contactPhone", "contact_phone"),
    "email": ("email", "contactEmail", "contact_email"),
    "directorName": ("directorName", "director_name", "contactName", "contact_name"),
    "directorPosition": (
        "directorPosition",
        "director_position",
        "contactPosition",
        "contact_position",
    ),
    "basis": ("basis",),
    "bankName": ("bankName", "bank_name"),
    "bik": ("bik",),
    "rs": ("rs", "settlementAccount", "settlement_account"),
    "ks": ("ks", "correspondentAccount", "correspondent_account"),
}

_LIMITS = {
    "fullName": 255,
    "shortName": 255,
    "legalAddress": 1000,
    "actualAddress": 1000,
    "phone": 50,
    "email": 255,
    "directorName": 255,
    "directorPosition": 100,
    "basis": 255,
    "bankName": 255,
}


def _text(value, limit=1000):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _digits(value, limit):
    return re.sub(r"\D+", "", str(value or ""))[:limit]


def _first(payload, aliases):
    for name in aliases:
        if name in payload:
            return payload.get(name) or ""
    return ""


def normalize_company_requisites(payload):
    """Return the one canonical legal profile accepted by settings and documents."""
    source = payload if isinstance(payload, dict) else {}
    result = {
        field: _text(_first(source, _ALIASES[field]), _LIMITS.get(field, 1000))
        for field in REQUISITE_FIELDS
    }
    result["inn"] = _digits(result["inn"], 12)
    result["kpp"] = _digits(result["kpp"], 9)
    result["ogrn"] = _digits(result["ogrn"], 15)
    result["bik"] = _digits(result["bik"], 9)
    result["rs"] = _digits(result["rs"], 20)
    result["ks"] = _digits(result["ks"], 20)
    result["email"] = result["email"].lower()

    is_individual_entrepreneur = (
        len(result["ogrn"]) == 15
        or result["fullName"].casefold().startswith("ип ")
        or "индивидуальн" in result["directorPosition"].casefold()
    )
    if not result["basis"]:
        result["basis"] = "записи в ЕГРИП" if is_individual_entrepreneur else "Устава"
    if not result["directorPosition"]:
        result["directorPosition"] = (
            "Индивидуальный предприниматель"
            if is_individual_entrepreneur
            else "Генеральный директор"
        )
    return result


def company_requisites_to_api(row, company_id=None):
    source = dict(row or {})
    return {
        "id": source.get("id"),
        "companyId": source.get("company_id") or company_id,
        "fullName": source.get("full_name") or "",
        "shortName": source.get("short_name") or "",
        "inn": source.get("inn") or "",
        "kpp": source.get("kpp") or "",
        "ogrn": source.get("ogrn") or "",
        "legalAddress": source.get("legal_address") or "",
        "actualAddress": source.get("actual_address") or "",
        "phone": source.get("phone") or "",
        "email": source.get("email") or "",
        "directorName": source.get("director_name") or "",
        "directorPosition": source.get("director_position") or "",
        "basis": source.get("basis") or "",
        "bankName": source.get("bank_name") or "",
        "bik": source.get("bik") or "",
        "rs": source.get("rs") or "",
        "ks": source.get("ks") or "",
    }


def upsert_company_requisites(cursor, company_id, payload):
    """Upsert requisites for the server-selected company, never a claimed id."""
    selected_company_id = int(company_id)
    if selected_company_id <= 0:
        raise ValueError("company_id must be positive")
    data = normalize_company_requisites(payload)
    cursor.execute(
        """INSERT INTO company_requisites
               (company_id,full_name,short_name,inn,kpp,ogrn,legal_address,actual_address,
                phone,email,director_name,director_position,basis,bank_name,bik,rs,ks)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (company_id) DO UPDATE SET
               full_name=EXCLUDED.full_name, short_name=EXCLUDED.short_name,
               inn=EXCLUDED.inn, kpp=EXCLUDED.kpp, ogrn=EXCLUDED.ogrn,
               legal_address=EXCLUDED.legal_address, actual_address=EXCLUDED.actual_address,
               phone=EXCLUDED.phone, email=EXCLUDED.email,
               director_name=EXCLUDED.director_name, director_position=EXCLUDED.director_position,
               basis=EXCLUDED.basis, bank_name=EXCLUDED.bank_name,
               bik=EXCLUDED.bik, rs=EXCLUDED.rs, ks=EXCLUDED.ks
           RETURNING id,company_id,full_name,short_name,inn,kpp,ogrn,legal_address,
                     actual_address,phone,email,director_name,director_position,basis,
                     bank_name,bik,rs,ks""",
        (selected_company_id, *(data[field] for field in REQUISITE_FIELDS)),
    )
    return cursor.fetchone()


def mirror_company_identity(cursor, company_id, payload):
    """Keep the platform company card as a summary projection of the legal profile."""
    data = normalize_company_requisites(payload)
    cursor.execute(
        """UPDATE companies SET
               name=COALESCE(NULLIF(%s,''),name),
               short_name=%s,
               inn=%s,
               kpp=%s,
               contact_name=%s,
               contact_phone=%s,
               contact_email=%s
           WHERE id=%s""",
        (
            data["fullName"],
            data["shortName"],
            data["inn"],
            data["kpp"],
            data["directorName"],
            data["phone"],
            data["email"],
            int(company_id),
        ),
    )
