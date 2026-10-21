import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Query

from .service import build_candidate_record


def register_job_candidates_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    allowed_roles = {str(role).strip() for role in deps["allowed_roles"]}

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
                    RETURNING id, (xmax=0) AS inserted
                """, (
                    company_id, candidate["source"], candidate["source_name"], candidate["source_item_id"], candidate["identity_key"],
                    candidate["url"], candidate["title"], candidate["description"], candidate["published_at"],
                    candidate["region"], psycopg2.extras.Json(candidate["work_types"]), candidate["price"],
                    candidate["deadline"], candidate["evidence"], candidate["status"],
                    str(current_user.get("name") or current_user.get("email") or ""),
                ))
                row = cur.fetchone()
                if row["inserted"]:
                    created += 1
                else:
                    updated += 1
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
