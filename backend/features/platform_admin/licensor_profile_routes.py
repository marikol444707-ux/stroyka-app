"""HTTP routes for the platform licensor's reusable legal profile."""

import psycopg2.extras
from fastapi import Depends, HTTPException

try:
    from backend.features.platform_admin.client_contracts import normalize_legal_party
except ModuleNotFoundError:
    from features.platform_admin.client_contracts import normalize_legal_party


_PROFILE_COLUMNS = """
    id, platform_account_id, legal_form, legal_name, short_name, inn, kpp,
    ogrn, ogrnip, legal_address, phone, email, settlement_account, bank_name,
    bank_bik, correspondent_account, signatory_name, signatory_basis, active,
    created_at, updated_at
"""

_LEGAL_FORMS = frozenset({"individual_entrepreneur", "legal_entity"})
_FIELD_LIMITS = {
    "legalForm": 30,
    "legalName": 500,
    "shortName": 255,
    "inn": 12,
    "kpp": 9,
    "ogrn": 15,
    "ogrnip": 15,
    "legalAddress": 4000,
    "phone": 100,
    "email": 255,
    "settlementAccount": 20,
    "bankName": 500,
    "bankBik": 9,
    "correspondentAccount": 20,
    "signatoryName": 255,
    "signatoryBasis": 255,
}


def _validate_party(party):
    if not party["legalName"]:
        raise HTTPException(status_code=422, detail="Укажите полное наименование лицензиара.")
    if party["legalForm"] not in _LEGAL_FORMS:
        raise HTTPException(status_code=422, detail="Укажите корректный тип лицензиара.")
    for field, limit in _FIELD_LIMITS.items():
        if len(party[field]) > limit:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Поле профиля лицензиара слишком длинное.",
                    "field": field,
                    "maxLength": limit,
                },
            )


def _response(row, platform_account_id):
    if not row:
        return {
            "platformAccountId": platform_account_id,
            "configured": False,
            "profile": None,
        }
    source = dict(row)
    profile = {
        "id": source.get("id"),
        "platformAccountId": source.get("platform_account_id") or platform_account_id,
        "legalForm": source.get("legal_form") or "",
        "legalName": source.get("legal_name") or "",
        "shortName": source.get("short_name") or "",
        "inn": source.get("inn") or "",
        "kpp": source.get("kpp") or "",
        "ogrn": source.get("ogrn") or "",
        "ogrnip": source.get("ogrnip") or "",
        "legalAddress": source.get("legal_address") or "",
        "phone": source.get("phone") or "",
        "email": source.get("email") or "",
        "settlementAccount": source.get("settlement_account") or "",
        "bankName": source.get("bank_name") or "",
        "bankBik": source.get("bank_bik") or "",
        "correspondentAccount": source.get("correspondent_account") or "",
        "signatoryName": source.get("signatory_name") or "",
        "signatoryBasis": source.get("signatory_basis") or "",
        "active": source.get("active") is True,
        "createdAt": source.get("created_at"),
        "updatedAt": source.get("updated_at"),
    }
    return {
        "platformAccountId": platform_account_id,
        "configured": True,
        "profile": profile,
    }


def register_licensor_profile_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    view_roles = deps["view_roles"]
    manage_roles = deps["manage_roles"]
    write_audit = deps["write_audit"]

    @app.get("/system/licensor-profile")
    def system_licensor_profile(
        platformAccountId: int,
        _current_user: dict = Depends(require_roles(*view_roles)),
    ):
        if platformAccountId <= 0:
            raise HTTPException(status_code=422, detail="Укажите корректный аккаунт платформы.")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                f"""SELECT {_PROFILE_COLUMNS}
                    FROM platform_licensor_profiles
                    WHERE platform_account_id=%s AND active IS TRUE
                    ORDER BY id DESC
                    LIMIT 1""",
                (platformAccountId,),
            )
            return _response(cur.fetchone(), platformAccountId)
        finally:
            cur.close()
            conn.close()

    @app.put("/system/licensor-profile")
    def system_update_licensor_profile(
        data: dict,
        current_user: dict = Depends(require_roles(*manage_roles)),
    ):
        payload = data or {}
        try:
            platform_account_id = int(payload.get("platformAccountId") or 0)
        except (TypeError, ValueError):
            platform_account_id = 0
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if platform_account_id <= 0:
                raise HTTPException(status_code=422, detail="Укажите корректный аккаунт платформы.")
            cur.execute(
                "SELECT id FROM platform_accounts WHERE id=%s",
                (platform_account_id,),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Аккаунт платформы не найден.")

            party = normalize_legal_party(payload)
            _validate_party(party)

            cur.execute(
                """SELECT id
                   FROM platform_licensor_profiles
                   WHERE platform_account_id=%s AND active IS TRUE
                   ORDER BY id DESC
                   LIMIT 1""",
                (platform_account_id,),
            )
            existing = cur.fetchone()
            actor = (
                current_user.get("name")
                or current_user.get("email")
                or str(current_user.get("id") or "system")
            ) if isinstance(current_user, dict) else "system"
            values = (
                party["legalForm"], party["legalName"], party["shortName"],
                party["inn"], party["kpp"], party["ogrn"], party["ogrnip"],
                party["legalAddress"], party["phone"], party["email"],
                party["settlementAccount"], party["bankName"], party["bankBik"],
                party["correspondentAccount"], party["signatoryName"],
                party["signatoryBasis"], actor,
            )
            if existing:
                profile_id = existing["id"]
                cur.execute(
                    f"""UPDATE platform_licensor_profiles
                        SET legal_form=%s, legal_name=%s, short_name=%s, inn=%s,
                            kpp=%s, ogrn=%s, ogrnip=%s, legal_address=%s,
                            phone=%s, email=%s, settlement_account=%s,
                            bank_name=%s, bank_bik=%s, correspondent_account=%s,
                            signatory_name=%s, signatory_basis=%s,
                            updated_by=%s, updated_at=NOW()
                        WHERE id=%s
                        RETURNING {_PROFILE_COLUMNS}""",
                    values + (profile_id,),
                )
                audit_action = "platform_licensor_profile_updated"
            else:
                cur.execute(
                    f"""INSERT INTO platform_licensor_profiles
                        (platform_account_id, legal_form, legal_name, short_name,
                         inn, kpp, ogrn, ogrnip, legal_address, phone, email,
                         settlement_account, bank_name, bank_bik,
                         correspondent_account, signatory_name, signatory_basis,
                         created_by, updated_by)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING {_PROFILE_COLUMNS}""",
                    (platform_account_id,) + values + (actor,),
                )
                audit_action = "platform_licensor_profile_created"
            profile = cur.fetchone()
            write_audit(
                cur,
                current_user,
                audit_action,
                "platform_licensor_profile",
                profile.get("id") if profile else None,
                party["legalName"],
                platform_account_id=platform_account_id,
                details={"inn": party["inn"], "legalForm": party["legalForm"]},
            )
            conn.commit()
            return _response(profile, platform_account_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
