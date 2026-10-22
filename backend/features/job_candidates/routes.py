import hmac
import json
import re

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Query

from .service import build_candidate_record, jev_report_items


_JEV_PROVIDER_PREFIXES = {
    "b2b-center": "B2B-Center",
    "росэлторг": "Росэлторг",
    "фабрикант": "Фабрикант",
    "этп гпб": "ЭТП ГПБ",
    "сбер а": "Сбер А",
    "тэк-торг": "ТЭК-Торг",
    "торги федерации": "Торги Федерации",
    "р-тендер": "Р-ТЕНДЕР",
    "еис": "ЕИС",
}
_JEV_ACTIVE_PROVIDERS = (
    "B2B-Center", "Росэлторг", "Фабрикант", "ЭТП ГПБ", "Сбер А",
    "ТЭК-Торг", "Торги Федерации", "Р-ТЕНДЕР",
)


def _save_candidates(cur, *, company_id, candidates, created_by):
    created = updated = 0
    for candidate in candidates:
        cur.execute("""
            INSERT INTO public.crm_job_candidates (
                company_id, source, source_name, source_item_id, identity_key, url, title, description,
                published_at, region, work_types, price, deadline, evidence, status, created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO UPDATE SET
                source_item_id=COALESCE(crm_job_candidates.source_item_id, EXCLUDED.source_item_id),
                source_name=EXCLUDED.source_name, title=EXCLUDED.title, description=EXCLUDED.description,
                published_at=COALESCE(EXCLUDED.published_at, crm_job_candidates.published_at),
                region=EXCLUDED.region, work_types=EXCLUDED.work_types,
                price=COALESCE(EXCLUDED.price, crm_job_candidates.price),
                deadline=COALESCE(EXCLUDED.deadline, crm_job_candidates.deadline),
                evidence=EXCLUDED.evidence, last_seen_at=NOW(), updated_at=NOW()
            RETURNING (xmax=0) AS inserted
        """, (
            company_id, candidate["source"], candidate["source_name"], candidate["source_item_id"], candidate["identity_key"],
            candidate["url"], candidate["title"], candidate["description"], candidate["published_at"],
            candidate["region"], psycopg2.extras.Json(candidate["work_types"]), candidate["price"],
            candidate["deadline"], candidate["evidence"], candidate["status"], created_by,
        ))
        if cur.fetchone()["inserted"]:
            created += 1
        else:
            updated += 1
    return created, updated


def _matches_search_terms(candidate, settings):
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except ValueError:
            settings = {}
    terms = settings.get("searchTerms", []) if isinstance(settings, dict) else []
    providers = settings.get("sourceProviders") if isinstance(settings, dict) else None
    if isinstance(providers, list) and providers:
        source_name = str(candidate.get("source_name") or "").strip().casefold()
        provider = next((canonical for prefix, canonical in _JEV_PROVIDER_PREFIXES.items()
                         if source_name.startswith(prefix)), None)
        if provider not in providers:
            return False
    if not isinstance(terms, list) or not terms:
        return True
    text = " ".join(str(candidate.get(field) or "") for field in ("title", "description", "evidence")).casefold()
    text = " ".join(text.replace("ё", "е").split())
    text_words = re.findall(r"[\w-]+", text)
    for term in terms:
        if not isinstance(term, str):
            continue
        normalized_term = " ".join(term.casefold().replace("ё", "е").split())
        if normalized_term in text:
            return True
        term_words = re.findall(r"[\w-]+", normalized_term)
        if term_words and all(
            any(word.startswith(token[:max(4, len(token) - 2)]) for word in text_words)
            for token in term_words
        ):
            return True
    return False


def register_job_candidates_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    allowed_roles = {str(role).strip() for role in deps["allowed_roles"]}
    jev_ingest_key = str(deps.get("jev_ingest_key") or "").strip()
    feature_enabled = deps.get("is_jev_enabled")

    def require_feature(cur, company_id):
        if feature_enabled:
            enabled = feature_enabled(cur, company_id)
        else:
            cur.execute("""
                SELECT enabled FROM public.platform_company_features
                WHERE company_id=%s AND feature_code='jev_procurement'
            """, (company_id,))
            row = cur.fetchone()
            enabled = bool(row and row.get("enabled"))
        if not enabled:
            raise HTTPException(
                status_code=403,
                detail="Поиск заказов JEV не подключён для выбранной организации",
            )

    def require_jev_ingest_key(provided_key):
        if len(jev_ingest_key) < 32:
            raise HTTPException(status_code=503, detail="Импорт JEV не настроен")
        if not hmac.compare_digest(provided_key, jev_ingest_key):
            raise HTTPException(status_code=401, detail="Недействительные данные интеграции")

    def selected_company(cur, user, action, company_id, company_mode):
        context = resolve_work_company_context(
            cur, user, None, action,
            x_company_id=company_id,
            x_company_mode=company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Выберите одну организацию для работы с кандидатами")
        actors = [dict(actor or {}) for actor in effective_company_actors(user, context)
                  if str((actor or {}).get("role") or "").strip() in allowed_roles]
        if not actors:
            raise HTTPException(status_code=403, detail="Недостаточно прав для работы с кандидатами заказов")
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Не удалось однозначно определить организацию")
        actor = actors[0]
        try:
            resolved_id = int(actor.get("companyId") or actor.get("company_id") or context.get("companyId"))
        except (TypeError, ValueError):
            resolved_id = 0
        if resolved_id <= 0:
            raise HTTPException(status_code=409, detail="Организация не определена")
        return resolved_id

    @app.get("/crm/job-candidates/access")
    def job_candidates_access(
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_id = selected_company(cur, current_user, "read", x_company_id, x_company_mode)
            cur.execute("""
                SELECT enabled, monthly_fee FROM public.platform_company_features
                WHERE company_id=%s AND feature_code='jev_procurement'
            """, (company_id,))
            row = cur.fetchone() or {}
            return {"enabled": bool(row.get("enabled")), "monthlyFee": str(row.get("monthly_fee") or "0")}
        finally:
            cur.close()
            conn.close()

    @app.get("/crm/job-candidates")
    def list_job_candidates(
        status: str = Query(default=""),
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_id = selected_company(cur, current_user, "read", x_company_id, x_company_mode)
            require_feature(cur, company_id)
            params = [company_id]
            status_sql = ""
            if status:
                if status not in {"Нужно проверить", "Подходит", "Не подходит", "Дубль"}:
                    raise HTTPException(status_code=422, detail="Неизвестный статус кандидата")
                status_sql = " AND status=%s"
                params.append(status)
            cur.execute("""
                SELECT id, company_id AS "companyId", source, source_item_id AS "sourceItemId",
                       source_name AS "sourceName",
                       url, title, description, published_at AS "publishedAt", region,
                       work_types AS "workTypes", price, deadline, evidence, status,
                       collected_at AS "collectedAt", last_seen_at AS "lastSeenAt",
                       reviewed_by AS "reviewedBy", reviewed_at AS "reviewedAt", review_note AS "reviewNote"
                FROM public.crm_job_candidates
                WHERE company_id=%s
            """ + status_sql + " ORDER BY collected_at DESC, id DESC LIMIT 500", tuple(params))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/job-candidates")
    def ingest_job_candidate(
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        try:
            candidate = build_candidate_record(data)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_id = selected_company(cur, current_user, "write", x_company_id, x_company_mode)
            require_feature(cur, company_id)
            cur.execute("""
                INSERT INTO public.crm_job_candidates (
                    company_id, source, source_name, source_item_id, identity_key, url, title, description,
                    published_at, region, work_types, price, deadline, evidence, status, created_by
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO UPDATE SET
                    source_item_id=COALESCE(crm_job_candidates.source_item_id, EXCLUDED.source_item_id),
                    title=EXCLUDED.title, description=EXCLUDED.description,
                    published_at=COALESCE(EXCLUDED.published_at, crm_job_candidates.published_at),
                    region=EXCLUDED.region, work_types=EXCLUDED.work_types,
                    price=COALESCE(EXCLUDED.price, crm_job_candidates.price),
                    deadline=COALESCE(EXCLUDED.deadline, crm_job_candidates.deadline),
                    evidence=EXCLUDED.evidence, last_seen_at=NOW(), updated_at=NOW()
                RETURNING id, (xmax=0) AS inserted, status
            """, (
                company_id, candidate["source"], candidate["source_name"], candidate["source_item_id"], candidate["identity_key"],
                candidate["url"], candidate["title"], candidate["description"], candidate["published_at"],
                candidate["region"], psycopg2.extras.Json(candidate["work_types"]), candidate["price"],
                candidate["deadline"], candidate["evidence"], candidate["status"],
                str(current_user.get("name") or current_user.get("email") or ""),
            ))
            row = cur.fetchone()
            conn.commit()
            return {"ok": True, "id": row["id"], "inserted": bool(row["inserted"]), "status": row["status"]}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Не удалось сохранить кандидата") from error
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/job-candidates/import-report")
    def import_job_candidate_report(
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items or len(items) > 200:
            raise HTTPException(status_code=422, detail="Отчёт должен содержать от 1 до 200 кандидатов")
        try:
            candidates = [build_candidate_record(item) for item in items]
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        created = 0
        updated = 0
        try:
            company_id = selected_company(cur, current_user, "write", x_company_id, x_company_mode)
            require_feature(cur, company_id)
            created, updated = _save_candidates(
                cur, company_id=company_id, candidates=candidates,
                created_by=str(current_user.get("name") or current_user.get("email") or ""),
            )
            conn.commit()
            return {"ok": True, "received": len(candidates), "created": created, "updated": updated}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Не удалось импортировать отчёт") from error
        finally:
            cur.close()
            conn.close()

    @app.get("/internal/jev/job-candidates")
    def list_jev_search_targets(x_jev_ingest_key: str = Header(default="", alias="X-JEV-Ingest-Key")):
        require_jev_ingest_key(x_jev_ingest_key)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""
                SELECT f.company_id, f.settings
                FROM public.platform_company_features f
                JOIN public.companies c ON c.id=f.company_id
                WHERE f.feature_code='jev_procurement'
                  AND f.enabled=TRUE
                  AND COALESCE(c.active, TRUE)=TRUE
                ORDER BY f.company_id
                FOR SHARE OF f
            """)
            targets = []
            for row in cur.fetchall():
                settings = row.get("settings")
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except ValueError:
                        settings = {}
                if not isinstance(settings, dict):
                    settings = {}
                targets.append({
                    "companyId": int(row["company_id"]),
                    "region": str(settings.get("region") or "Ставропольский край"),
                    "searchTerms": [term for term in settings.get("searchTerms", [])
                                    if isinstance(term, str)][:20]
                    if isinstance(settings.get("searchTerms", []), list) else [],
                    "sourceProviders": [provider for provider in settings.get("sourceProviders", _JEV_ACTIVE_PROVIDERS)
                                        if provider in _JEV_ACTIVE_PROVIDERS]
                    if isinstance(settings.get("sourceProviders", _JEV_ACTIVE_PROVIDERS), list)
                    else list(_JEV_ACTIVE_PROVIDERS),
                })
            return {"targets": targets}
        finally:
            cur.close()
            conn.close()

    @app.post("/internal/jev/job-candidates")
    def ingest_jev_report(data: dict, x_jev_ingest_key: str = Header(default="", alias="X-JEV-Ingest-Key")):
        require_jev_ingest_key(x_jev_ingest_key)
        target_company_id = data.get("targetCompanyId") if isinstance(data, dict) else None
        if target_company_id is not None and (type(target_company_id) is not int or target_company_id <= 0):
            raise HTTPException(status_code=422, detail="targetCompanyId должен быть положительным целым числом")
        try:
            body_size = len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            if body_size > 1_000_000:
                raise ValueError("Отчёт JEV превышает лимит размера")
            items = jev_report_items(data)
            if not items:
                raise ValueError("В отчёте JEV нет подтверждённых находок или записей для проверки")
            candidates = [build_candidate_record(item) for item in items]
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        created = 0
        updated = 0
        try:
            target_sql = " AND f.company_id=%s" if target_company_id is not None else ""
            params = (target_company_id,) if target_company_id is not None else ()
            cur.execute("""
                SELECT f.company_id, f.settings
                FROM public.platform_company_features f
                JOIN public.companies c ON c.id=f.company_id
                WHERE f.feature_code='jev_procurement'
                  AND f.enabled=TRUE
                  AND COALESCE(c.active, TRUE)=TRUE
            """ + target_sql + """
                ORDER BY f.company_id
                FOR SHARE OF f
            """, params)
            target_rows = cur.fetchall()
            if not target_rows:
                raise HTTPException(status_code=409, detail="JEV не подключён ни одной активной организации")
            target_results = []
            for target in target_rows:
                target_company_id = int(target["company_id"])
                company_candidates = [
                    candidate for candidate in candidates
                    if _matches_search_terms(candidate, target.get("settings"))
                ]
                target_created, target_updated = _save_candidates(
                    cur, company_id=target_company_id, candidates=company_candidates, created_by="JEV",
                )
                created += target_created
                updated += target_updated
                target_results.append({
                    "companyId": target_company_id,
                    "created": target_created,
                    "updated": target_updated,
                    "skippedByProfile": len(candidates) - len(company_candidates),
                })
            conn.commit()
            return {"ok": True, "targetCompanies": target_results, "received": len(candidates),
                    "created": created, "updated": updated,
                    "sourcesChecked": len(data.get("sources", [])) if isinstance(data.get("sources"), list) else 0,
                    "sourcesUnavailable": sum(
                        1 for source in data.get("sources", [])
                        if isinstance(source, dict) and source.get("ok") is not True
                    ) if isinstance(data.get("sources"), list) else 0}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Не удалось принять отчёт JEV") from error
        finally:
            cur.close()
            conn.close()

    @app.put("/crm/job-candidates/{candidate_id}/review")
    def review_job_candidate(
        candidate_id: int,
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        status = str(data.get("status") or "").strip()
        if status not in {"Подходит", "Не подходит", "Дубль"}:
            raise HTTPException(status_code=422, detail="Выберите решение: подходит, не подходит или дубль")
        note = str(data.get("reviewNote") or "").strip()[:2000]
        conn = get_db()
        cur = conn.cursor()
        try:
            company_id = selected_company(cur, current_user, "write", x_company_id, x_company_mode)
            require_feature(cur, company_id)
            cur.execute("""
                UPDATE public.crm_job_candidates
                SET status=%s, reviewed_by=%s, reviewed_at=NOW(), review_note=%s, updated_at=NOW()
                WHERE company_id=%s AND id=%s
            """, (status, str(current_user.get("name") or current_user.get("email") or ""), note, company_id, candidate_id))
            if cur.rowcount != 1:
                raise HTTPException(status_code=404, detail="Кандидат не найден в выбранной организации")
            conn.commit()
            return {"ok": True, "id": candidate_id, "status": status}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Не удалось сохранить решение") from error
        finally:
            cur.close()
            conn.close()
