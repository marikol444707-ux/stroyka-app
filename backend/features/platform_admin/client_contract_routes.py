"""HTTP routes for previewing and creating platform client contracts."""

import json

import psycopg2.extras
from fastapi import Depends, HTTPException

try:
    from backend.features.platform_admin.client_contracts import (
        build_client_contract_preview,
        build_contract_number,
    )
except ModuleNotFoundError:
    from features.platform_admin.client_contracts import (
        build_client_contract_preview,
        build_contract_number,
    )


_CONTRACT_COLUMNS = """
    id, platform_account_id, company_id, licensor_profile_id,
    idempotency_key, request_fingerprint, contract_type, number,
    contract_date, starts_on, ends_on, plan, monthly_fee, currency,
    max_projects, max_users, status, terms_version,
    licensor_snapshot_json, client_snapshot_json, terms_snapshot_json,
    generated_file_url, signed_file_url, notes, issued_at, activated_at,
    terminated_at, created_at, updated_at
"""

_LICENSOR_COLUMNS = """
    id, platform_account_id, legal_form, legal_name, short_name, inn, kpp,
    ogrn, ogrnip, legal_address, phone, email, settlement_account, bank_name,
    bank_bik, correspondent_account, signatory_name, signatory_basis, active
"""


def _positive_int(value, field):
    if isinstance(value, bool):
        number = 0
    else:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = 0
    if number <= 0:
        raise HTTPException(
            status_code=422,
            detail="Укажите корректное значение поля {}.".format(field),
        )
    return number


def _iso_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _money(value):
    if value is None:
        return "0.00"
    try:
        return format(value, ".2f")
    except (TypeError, ValueError):
        return str(value)


def _contract_response(row):
    source = dict(row or {})
    return {
        "id": source.get("id"),
        "platformAccountId": source.get("platform_account_id"),
        "companyId": source.get("company_id"),
        "licensorProfileId": source.get("licensor_profile_id"),
        "idempotencyKey": source.get("idempotency_key") or "",
        "requestFingerprint": source.get("request_fingerprint") or "",
        "contractType": source.get("contract_type") or "",
        "number": source.get("number") or "",
        "contractDate": _iso_value(source.get("contract_date")),
        "startsOn": _iso_value(source.get("starts_on")),
        "endsOn": _iso_value(source.get("ends_on")),
        "plan": source.get("plan") or "",
        "monthlyFee": _money(source.get("monthly_fee")),
        "currency": source.get("currency") or "RUB",
        "maxProjects": source.get("max_projects"),
        "maxUsers": source.get("max_users"),
        "status": source.get("status") or "draft",
        "termsVersion": source.get("terms_version") or "",
        "licensorSnapshot": _json_object(source.get("licensor_snapshot_json")),
        "clientSnapshot": _json_object(source.get("client_snapshot_json")),
        "termsSnapshot": _json_object(source.get("terms_snapshot_json")),
        "generatedFileUrl": source.get("generated_file_url"),
        "signedFileUrl": source.get("signed_file_url"),
        "notes": source.get("notes"),
        "issuedAt": _iso_value(source.get("issued_at")),
        "activatedAt": _iso_value(source.get("activated_at")),
        "terminatedAt": _iso_value(source.get("terminated_at")),
        "createdAt": _iso_value(source.get("created_at")),
        "updatedAt": _iso_value(source.get("updated_at")),
    }


def _load_company(cur, company_id):
    cur.execute(
        """SELECT c.id, c.platform_account_id, c.active, c.plan,
                  c.monthly_fee, c.max_projects, c.max_users,
                  COALESCE(NULLIF(cr.full_name,''), NULLIF(c.name,''), '') AS legal_name,
                  COALESCE(NULLIF(cr.short_name,''), NULLIF(c.short_name,''), '') AS short_name,
                  COALESCE(NULLIF(cr.inn,''), NULLIF(c.inn,''), '') AS inn,
                  COALESCE(NULLIF(cr.kpp,''), NULLIF(c.kpp,''), '') AS kpp,
                  COALESCE(cr.ogrn, '') AS ogrn,
                  COALESCE(cr.legal_address, '') AS legal_address,
                  COALESCE(NULLIF(cr.phone,''), NULLIF(c.contact_phone,''), '') AS phone,
                  COALESCE(NULLIF(cr.email,''), NULLIF(c.contact_email,''), '') AS email,
                  COALESCE(cr.rs, '') AS settlement_account,
                  COALESCE(cr.bank_name, '') AS bank_name,
                  COALESCE(cr.bik, '') AS bank_bik,
                  COALESCE(cr.ks, '') AS correspondent_account,
                  COALESCE(NULLIF(cr.director_name,''), NULLIF(c.contact_name,''), '') AS signatory_name,
                  COALESCE(cr.basis, '') AS signatory_basis
           FROM companies c
           LEFT JOIN company_requisites cr ON cr.company_id=c.id
           WHERE c.id=%s""",
        (company_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _load_licensor(cur, platform_account_id):
    cur.execute(
        """SELECT {}
           FROM platform_licensor_profiles
           WHERE platform_account_id=%s AND active IS TRUE
           ORDER BY id DESC
           LIMIT 1""".format(_LICENSOR_COLUMNS),
        (platform_account_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _load_contracts(cur, platform_account_id, company_id):
    cur.execute(
        """SELECT {}
           FROM platform_client_contracts
           WHERE platform_account_id=%s AND company_id=%s
           ORDER BY contract_date DESC, id DESC
           LIMIT 200""".format(_CONTRACT_COLUMNS),
        (platform_account_id, company_id),
    )
    return [dict(row) for row in cur.fetchall()]


def _load_preview_contracts(
    cur,
    platform_account_id,
    company_id,
    idempotency_key,
):
    cur.execute(
        """SELECT {}
           FROM platform_client_contracts
           WHERE platform_account_id=%s
             AND (company_id=%s OR idempotency_key=%s)
           ORDER BY contract_date DESC, id DESC
           LIMIT 500""".format(_CONTRACT_COLUMNS),
        (platform_account_id, company_id, idempotency_key),
    )
    return [dict(row) for row in cur.fetchall()]


def _defaulted_payload(payload, company, licensor, tariff_for_plan):
    prepared = dict(payload)
    prepared["companyId"] = company.get("id")
    if prepared.get("platformAccountId") in (None, ""):
        prepared["platformAccountId"] = company.get("platform_account_id")
    else:
        try:
            prepared["platformAccountId"] = int(prepared["platformAccountId"])
        except (TypeError, ValueError):
            pass
    if prepared.get("licensorProfileId") in (None, "") and licensor:
        prepared["licensorProfileId"] = licensor.get("id")
    elif prepared.get("licensorProfileId") not in (None, ""):
        try:
            prepared["licensorProfileId"] = int(prepared["licensorProfileId"])
        except (TypeError, ValueError):
            pass

    plan = prepared.get("plan") or company.get("plan") or "demo"
    tariff = tariff_for_plan(plan) or {}
    if not prepared.get("plan"):
        prepared["plan"] = plan

    defaults = {
        "monthlyFee": company.get("monthly_fee"),
        "maxProjects": company.get("max_projects"),
        "maxUsers": company.get("max_users"),
    }
    tariff_names = {
        "monthlyFee": "monthlyFee",
        "maxProjects": "maxProjects",
        "maxUsers": "maxUsers",
    }
    for field, value in defaults.items():
        if field not in prepared or prepared.get(field) in (None, ""):
            prepared[field] = (
                value if value is not None else tariff.get(tariff_names[field])
            )
    prepared.setdefault("currency", "RUB")
    prepared.setdefault("contractType", "platform_license")
    if not prepared.get("status"):
        prepared["status"] = "draft"
    if not prepared.get("termsVersion"):
        prepared["termsVersion"] = "platform-license-v1"
    return prepared


def _preview(cur, payload, tariff_for_plan):
    company_id = _positive_int(payload.get("companyId"), "companyId")
    company = _load_company(cur, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена.")
    if not company.get("platform_account_id"):
        raise HTTPException(
            status_code=409,
            detail="Компания не привязана к аккаунту платформы.",
        )
    if company.get("active") is False:
        raise HTTPException(status_code=409, detail="Компания неактивна.")

    platform_account_id = int(company["platform_account_id"])
    licensor = _load_licensor(cur, platform_account_id)
    prepared = _defaulted_payload(
        payload,
        company,
        licensor,
        tariff_for_plan,
    )
    existing = _load_preview_contracts(
        cur,
        platform_account_id,
        company_id,
        str(prepared.get("idempotencyKey") or "").strip(),
    )
    return build_client_contract_preview(
        prepared,
        company=company,
        licensor=licensor or {},
        existing_contracts=existing,
    ), existing


def _actor(current_user):
    if not isinstance(current_user, dict):
        return "system"
    return (
        current_user.get("name")
        or current_user.get("email")
        or str(current_user.get("id") or "system")
    )


def register_client_contract_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    view_roles = deps["view_roles"]
    manage_roles = deps["manage_roles"]
    tariff_for_plan = deps["tariff_for_plan"]
    write_audit = deps["write_audit"]

    @app.get("/system/client-contracts")
    def system_client_contracts(
        companyId: int,
        _current_user: dict = Depends(require_roles(*view_roles)),
    ):
        company_id = _positive_int(companyId, "companyId")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company = _load_company(cur, company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Компания не найдена.")
            platform_account_id = company.get("platform_account_id")
            if not platform_account_id:
                raise HTTPException(
                    status_code=409,
                    detail="Компания не привязана к аккаунту платформы.",
                )
            rows = _load_contracts(cur, int(platform_account_id), company_id)
            return {
                "companyId": company_id,
                "platformAccountId": int(platform_account_id),
                "items": [_contract_response(row) for row in rows],
            }
        finally:
            conn.rollback()
            cur.close()
            conn.close()

    @app.post("/system/client-contracts/preview")
    def system_client_contract_preview(
        data: dict,
        _current_user: dict = Depends(require_roles(*manage_roles)),
    ):
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="Ожидается объект договора.")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            preview, _existing = _preview(cur, data, tariff_for_plan)
            return preview
        finally:
            conn.rollback()
            cur.close()
            conn.close()

    @app.post("/system/client-contracts")
    def system_create_client_contract(
        data: dict,
        current_user: dict = Depends(require_roles(*manage_roles)),
    ):
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="Ожидается объект договора.")
        requested_status = str(data.get("status") or "draft").strip()
        if requested_status != "draft":
            raise HTTPException(
                status_code=422,
                detail="Новый договор можно создать только как черновик.",
            )

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            preview, existing = _preview(cur, data, tariff_for_plan)
            if preview["blockers"]:
                raise HTTPException(status_code=409, detail=preview)

            idempotent_id = preview.get("idempotentContractId")
            if idempotent_id is not None:
                row = next(
                    item for item in existing if item.get("id") == idempotent_id
                )
                conn.rollback()
                return {
                    "created": False,
                    "idempotent": True,
                    "contract": _contract_response(row),
                }

            contract = preview["contract"]
            cur.execute(
                "SELECT nextval(pg_get_serial_sequence('public.platform_client_contracts','id')) AS id"
            )
            contract_id = int(cur.fetchone()["id"])
            number = build_contract_number(
                int(contract["contractDate"][:4]),
                contract_id,
            )
            actor = _actor(current_user)
            cur.execute(
                """INSERT INTO platform_client_contracts
                   (id, platform_account_id, company_id, licensor_profile_id,
                    idempotency_key, request_fingerprint, contract_type, number,
                    contract_date, starts_on, ends_on, plan, monthly_fee,
                    currency, max_projects, max_users, status, terms_version,
                    licensor_snapshot_json, client_snapshot_json,
                    terms_snapshot_json, created_by, updated_by)
                   VALUES
                   (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    'draft',%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (platform_account_id, idempotency_key) DO NOTHING
                   RETURNING {}""".format(_CONTRACT_COLUMNS),
                (
                    contract_id,
                    contract["platformAccountId"],
                    contract["companyId"],
                    contract["licensorProfileId"],
                    contract["idempotencyKey"],
                    contract["requestFingerprint"],
                    contract["contractType"],
                    number,
                    contract["contractDate"],
                    contract["startsOn"],
                    contract["endsOn"],
                    contract["plan"],
                    contract["monthlyFee"],
                    contract["currency"],
                    contract["maxProjects"],
                    contract["maxUsers"],
                    contract["termsVersion"],
                    psycopg2.extras.Json(contract["licensorSnapshot"]),
                    psycopg2.extras.Json(contract["clientSnapshot"]),
                    psycopg2.extras.Json(contract["termsSnapshot"]),
                    actor,
                    actor,
                ),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    """SELECT {}
                       FROM platform_client_contracts
                       WHERE platform_account_id=%s AND idempotency_key=%s""".format(
                        _CONTRACT_COLUMNS
                    ),
                    (contract["platformAccountId"], contract["idempotencyKey"]),
                )
                row = cur.fetchone()
                if not row or row.get("request_fingerprint") != contract["requestFingerprint"]:
                    raise HTTPException(
                        status_code=409,
                        detail="Ключ повторного запроса уже использован для другого договора.",
                    )
                conn.rollback()
                return {
                    "created": False,
                    "idempotent": True,
                    "contract": _contract_response(row),
                }

            write_audit(
                cur,
                current_user,
                "platform_client_contract_created",
                "platform_client_contract",
                row.get("id"),
                row.get("number"),
                platform_account_id=contract["platformAccountId"],
                company_id=contract["companyId"],
                details={
                    "status": "draft",
                    "plan": contract["plan"],
                    "monthlyFee": contract["monthlyFee"],
                },
            )
            conn.commit()
            return {
                "created": True,
                "idempotent": False,
                "contract": _contract_response(row),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
