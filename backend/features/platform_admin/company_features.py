from decimal import Decimal, InvalidOperation
import json

import psycopg2.extras
from fastapi import Depends, HTTPException


JEV_FEATURE_CODE = "jev_procurement"
MAX_MONTHLY_FEE = Decimal("10000000.00")
MAX_SEARCH_TERMS = 20
JEV_PROVIDERS = ("B2B-Center", "Росэлторг", "Фабрикант", "ЕИС")


def _source_providers(value):
    if not isinstance(value, list) or len(value) > len(JEV_PROVIDERS):
        raise HTTPException(status_code=422, detail="Выберите источники JEV из доступного списка")
    result = []
    for item in value:
        if item not in JEV_PROVIDERS:
            raise HTTPException(status_code=422, detail="Выбран неизвестный источник JEV")
        if item not in result:
            result.append(item)
    if not result:
        raise HTTPException(status_code=422, detail="Выберите хотя бы один источник поиска")
    return result


def _search_terms(value):
    if not isinstance(value, list) or len(value) > MAX_SEARCH_TERMS:
        raise HTTPException(status_code=422, detail="Укажите не более 20 поисковых фраз списком")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise HTTPException(status_code=422, detail="Поисковые фразы должны быть текстом")
        term = " ".join(item.split())
        if len(term) < 2 or len(term) > 80:
            raise HTTPException(status_code=422, detail="Каждая поисковая фраза должна быть длиной от 2 до 80 символов")
        key = term.casefold()
        if key not in seen:
            result.append(term)
            seen.add(key)
    return result


def _settings(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = {}
    return value if isinstance(value, dict) else {}


def _monthly_fee(value):
    try:
        fee = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Укажите корректную ежемесячную цену") from error
    if not fee.is_finite() or fee < 0 or fee > MAX_MONTHLY_FEE:
        raise HTTPException(status_code=422, detail="Цена должна быть от 0 до 10 000 000 ₽ в месяц")
    return fee.quantize(Decimal("0.01"))


def _feature_company(row):
    settings = _settings(row.get("settings"))
    return {
        "companyId": int(row["company_id"]),
        "companyName": row.get("company_name") or "",
        "inn": row.get("inn") or "",
        "platformAccountId": row.get("platform_account_id"),
        "platformAccountName": row.get("platform_account_name") or "",
        "companyActive": bool(row.get("company_active")),
        "isPlatformOwner": int(row["company_id"]) == 1,
        "enabled": bool(row.get("enabled")),
        "monthlyFee": format(Decimal(str(row.get("monthly_fee") or 0)), ".2f"),
        "searchTerms": _search_terms(settings.get("searchTerms", [])),
        "sourceProviders": _source_providers(settings.get("sourceProviders", list(JEV_PROVIDERS))),
        "changedBy": row.get("changed_by") or "",
        "updatedAt": row.get("updated_at"),
    }


def register_company_feature_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    manage_roles = tuple(deps.get("manage_roles") or ("system_owner", "platform_admin"))
    write_audit = deps.get("write_audit")

    @app.get("/system/company-features/jev")
    def list_jev_company_features(current_user: dict = Depends(require_roles(*manage_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""
                SELECT c.id AS company_id, c.name AS company_name, c.inn,
                       c.active AS company_active, c.platform_account_id,
                       pa.name AS platform_account_name,
                       COALESCE(f.enabled, FALSE) AS enabled,
                       COALESCE(f.monthly_fee, 0) AS monthly_fee,
                       COALESCE(f.settings, '{}'::jsonb) AS settings,
                       COALESCE(f.changed_by, '') AS changed_by,
                       f.updated_at
                FROM public.companies c
                LEFT JOIN public.platform_accounts pa ON pa.id=c.platform_account_id
                LEFT JOIN public.platform_company_features f
                  ON f.company_id=c.id AND f.feature_code=%s
                ORDER BY COALESCE(pa.name, c.name), c.name, c.id
            """, (JEV_FEATURE_CODE,))
            rows = [_feature_company(row) for row in cur.fetchall()]
            potential = sum(
                (Decimal(row["monthlyFee"]) for row in rows
                 if row["enabled"] and row["companyActive"]),
                Decimal("0.00"),
            )
            return {
                "feature": JEV_FEATURE_CODE,
                "searchRegion": "Ставропольский край",
                "companies": rows,
                "enabledCompanies": sum(1 for row in rows if row["enabled"] and row["companyActive"]),
                "potentialMonthlyRevenue": format(potential, ".2f"),
            }
        finally:
            cur.close()
            conn.close()

    @app.put("/system/companies/{company_id}/features/jev")
    def update_jev_company_feature(
        company_id: int,
        data: dict,
        current_user: dict = Depends(require_roles(*manage_roles)),
    ):
        enabled = data.get("enabled")
        if type(enabled) is not bool:
            raise HTTPException(status_code=422, detail="Поле enabled должно быть true или false")
        monthly_fee = _monthly_fee(data.get("monthlyFee", 0))
        requested_terms = _search_terms(data["searchTerms"]) if "searchTerms" in data else None
        requested_providers = _source_providers(data["sourceProviders"]) if "sourceProviders" in data else None
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""
                SELECT id, name, inn, platform_account_id, active
                FROM public.companies WHERE id=%s
            """, (company_id,))
            company = cur.fetchone()
            if not company:
                raise HTTPException(status_code=404, detail="Клиентская организация не найдена")
            if enabled and not company.get("active", True):
                raise HTTPException(status_code=409, detail="Нельзя подключить функцию неактивной организации")
            if company_id == 1 and monthly_fee:
                raise HTTPException(status_code=422, detail="Для внутренней организации нельзя задавать плату")
            cur.execute("""
                SELECT enabled, monthly_fee, settings FROM public.platform_company_features
                WHERE company_id=%s AND feature_code=%s FOR UPDATE
            """, (company_id, JEV_FEATURE_CODE))
            previous = cur.fetchone() or {"enabled": False, "monthly_fee": 0}
            previous_settings = _settings(previous.get("settings"))
            settings = {
                **previous_settings,
                "region": "Ставропольский край",
                "searchTerms": requested_terms if requested_terms is not None
                else _search_terms(previous_settings.get("searchTerms", [])),
                "sourceProviders": requested_providers if requested_providers is not None
                else _source_providers(previous_settings.get("sourceProviders", list(JEV_PROVIDERS))),
            }
            changed_by = str(current_user.get("name") or current_user.get("email") or current_user.get("id") or "")
            cur.execute("""
                INSERT INTO public.platform_company_features
                    (company_id, feature_code, enabled, monthly_fee, settings, changed_by)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (company_id, feature_code) DO UPDATE SET
                    enabled=EXCLUDED.enabled,
                    monthly_fee=EXCLUDED.monthly_fee,
                    settings=EXCLUDED.settings,
                    changed_by=EXCLUDED.changed_by,
                    updated_at=NOW()
                RETURNING enabled, monthly_fee, updated_at
            """, (
                company_id, JEV_FEATURE_CODE, enabled, monthly_fee,
                psycopg2.extras.Json(settings), changed_by,
            ))
            saved = cur.fetchone()
            if write_audit:
                write_audit(
                    cur, current_user, "platform_company_feature_updated",
                    "company_feature", company_id, company.get("name"),
                    platform_account_id=company.get("platform_account_id"),
                    company_id=company_id,
                    details={
                        "feature": JEV_FEATURE_CODE,
                        "before": {
                            "enabled": bool(previous.get("enabled")),
                            "monthlyFee": str(previous.get("monthly_fee") or 0),
                            "searchTerms": _search_terms(previous_settings.get("searchTerms", [])),
                            "sourceProviders": _source_providers(previous_settings.get("sourceProviders", list(JEV_PROVIDERS))),
                        },
                        "after": {
                            "enabled": bool(saved.get("enabled")),
                            "monthlyFee": str(saved.get("monthly_fee") or 0),
                            "searchTerms": settings["searchTerms"],
                            "sourceProviders": settings["sourceProviders"],
                        },
                    },
                )
            conn.commit()
            return {
                "ok": True,
                "companyId": company_id,
                "enabled": bool(saved["enabled"]),
                "monthlyFee": format(Decimal(str(saved["monthly_fee"])), ".2f"),
                "searchTerms": settings["searchTerms"],
                "sourceProviders": settings["sourceProviders"],
                "updatedAt": saved.get("updated_at"),
                "message": "Цена сохранена как условие подключения; счёт выставляется отдельно по договору.",
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Не удалось изменить подключение JEV") from error
        finally:
            cur.close()
            conn.close()
