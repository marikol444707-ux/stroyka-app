import datetime as dt
import json
import re
import time
import urllib.parse
import uuid

import psycopg2.extras
from fastapi import Depends, File, HTTPException, Request, UploadFile

from .upload_policy import (
    MAX_PUBLIC_LEAD_FILE_BYTES,
    MAX_PUBLIC_LEAD_FILES,
    public_upload_rate_exceeded,
    validate_public_lead_file,
)
from ..crm.writer_ownership import resolve_public_lead_owner


SITE_PRICE_GROUP_LABELS = {
    "house_wall": "Дом: материал стен",
    "house_package": "Дом: комплектация",
    "repair_object": "Ремонт: тип объекта",
    "repair_condition": "Ремонт: состояние",
    "repair_level": "Ремонт: уровень",
    "material_mode": "Материалы",
    "commerce_type": "Коммерция: тип бизнеса",
    "commerce_level": "Коммерция: формат",
    "reconstruction_scope": "Реконструкция: объём",
}


def _site_list_value(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, tuple):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
    return []


def _site_int(value, default=0):
    try:
        return int(float(value or 0))
    except Exception:
        return default


def _public_text(value, limit: int = 255) -> str:
    return str(value or "").strip()[:limit]


def _public_comparison_url(value) -> str:
    raw = _public_text(value, 500)
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
        params = urllib.parse.parse_qs(parsed.query)
    except (TypeError, ValueError):
        return ""
    if parsed.scheme != "https" or parsed.netloc not in {"stroyka26.pro", "www.stroyka26.pro"}:
        return ""
    if parsed.path not in {"", "/"} or not params.get("project") or not params.get("compare"):
        return ""
    return raw


def _public_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return _public_text(forwarded.split(",")[0], 80)
    return _public_text(request.client.host if request.client else "unknown", 80)


def _public_attachment_tokens(data: dict) -> list[str]:
    raw_tokens = data.get("attachmentTokens")
    if raw_tokens in (None, ""):
        return []
    if not isinstance(raw_tokens, list):
        raise HTTPException(status_code=422, detail="Некорректный список файлов")
    tokens = []
    for raw_token in raw_tokens:
        token = str(raw_token or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{32}", token):
            raise HTTPException(status_code=422, detail="Некорректный токен файла")
        if token not in tokens:
            tokens.append(token)
    if len(tokens) > MAX_PUBLIC_LEAD_FILES:
        raise HTTPException(status_code=422, detail="К заявке можно прикрепить не больше 5 файлов")
    return tokens


def _ensure_public_lead_uploads_schema(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public_lead_uploads (
            token VARCHAR(64) PRIMARY KEY,
            company_id INT NOT NULL,
            file_ownership_id INT NOT NULL,
            original_name TEXT NOT NULL,
            content_type VARCHAR(255) NOT NULL,
            size_bytes BIGINT NOT NULL,
            client_ip VARCHAR(80),
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            lead_id INT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_public_lead_uploads_file
        ON public_lead_uploads(file_ownership_id)
    """)


def _cleanup_expired_public_lead_uploads(get_db, delete_local_file, delete_s3_object, limit=20) -> int:
    if not delete_local_file or not delete_s3_object:
        return 0
    conn = get_db()
    cur = conn.cursor()
    cleaned = 0
    try:
        _ensure_public_lead_uploads_schema(cur)
        cur.execute("""
            SELECT u.token,u.file_ownership_id,f.file_url,COALESCE(f.storage_key,'')
            FROM public_lead_uploads u
            JOIN file_ownership f ON f.id=u.file_ownership_id
            WHERE u.status IN ('pending','cleanup_failed')
              AND u.expires_at<=NOW()
            ORDER BY u.expires_at,u.token
            LIMIT %s
            FOR UPDATE OF u SKIP LOCKED
        """, (max(1, min(int(limit or 20), 100)),))
        rows = cur.fetchall()
        for token, ownership_id, file_url, storage_key in rows:
            try:
                if storage_key:
                    delete_s3_object(storage_key)
                else:
                    delete_local_file(file_url, missing_ok=True)
                cur.execute("DELETE FROM public_lead_uploads WHERE token=%s", (token,))
                cur.execute("DELETE FROM file_ownership WHERE id=%s", (ownership_id,))
                cleaned += 1
            except Exception as error:
                cur.execute(
                    "UPDATE public_lead_uploads SET status='cleanup_failed' WHERE token=%s",
                    (token,),
                )
                cur.execute("""
                    UPDATE file_ownership
                       SET deletion_status='cleanup_failed',deletion_error=%s,
                           deletion_requested_at=NOW()
                     WHERE id=%s
                """, (_public_text(str(error), 1000), ownership_id))
        conn.commit()
        return cleaned
    except Exception:
        conn.rollback()
        return cleaned
    finally:
        cur.close()
        conn.close()


def _public_lead_notes(data: dict) -> str:
    parts = []
    comment = _public_text(data.get("comment") or data.get("notes"), 1200)
    if comment:
        parts.append("Комментарий: " + comment)
    calc = data.get("calculation") if isinstance(data.get("calculation"), dict) else {}
    if calc:
        calc_parts = [
            _public_text(calc.get("typeLabel"), 80),
            _public_text(calc.get("summary"), 300),
            _public_text(calc.get("rangeText"), 120),
        ]
        compact = " · ".join([x for x in calc_parts if x])
        if compact:
            parts.append("Расчёт сайта: " + compact)
    selected_project = data.get("selectedProject") if isinstance(data.get("selectedProject"), dict) else {}
    if selected_project:
        project_parts = []
        direction = _public_text(selected_project.get("directionTitle"), 160)
        project_code = _public_text(selected_project.get("projectCode"), 80)
        project_title = _public_text(selected_project.get("projectTitle"), 255)
        area = _public_text(selected_project.get("projectArea"), 80)
        floors = _public_text(selected_project.get("projectFloors"), 80)
        estimate = _public_text(selected_project.get("estimateRange") or selected_project.get("estimateFrom"), 120)
        project_url = _public_text(selected_project.get("projectUrl"), 500)
        if direction:
            project_parts.append("направление: " + direction)
        if project_code:
            project_parts.append("код: " + project_code)
        if project_title:
            project_parts.append("проект: " + project_title)
        if area:
            project_parts.append("площадь: " + area)
        if floors:
            project_parts.append("этажность: " + floors)
        if estimate:
            project_parts.append("ориентир: " + estimate)
        if project_url:
            project_parts.append("карточка: " + project_url)
        if project_parts:
            parts.append("Выбранный проект: " + " · ".join(project_parts))
        plot_check = selected_project.get("plotCheck") if isinstance(selected_project.get("plotCheck"), dict) else {}
        if plot_check:
            plot_parts = []
            for key, label in (
                ("statusLabel", ""),
                ("accessLabel", "подъезд: "),
                ("reliefLabel", "рельеф: "),
                ("utilitiesLabel", "сети: "),
            ):
                value = _public_text(plot_check.get(key), 120)
                if value:
                    plot_parts.append(label + value)
            plot_parts.append("геология: " + ("есть" if plot_check.get("geologyReady") is True else "нет"))
            plot_parts.append("геодезия: " + ("есть" if plot_check.get("geodesyReady") is True else "нет"))
            review_items = plot_check.get("reviewItems") if isinstance(plot_check.get("reviewItems"), list) else []
            review_text = ", ".join(
                item for item in (_public_text(value, 80) for value in review_items[:8]) if item
            )
            if review_text:
                plot_parts.append("проверить: " + review_text)
            parts.append("Участок: " + " · ".join(plot_parts))
        financing = selected_project.get("financing") if isinstance(selected_project.get("financing"), dict) else {}
        if financing and financing.get("status") == "indicative":
            financing_parts = []
            mode_label = _public_text(financing.get("modeLabel"), 120)
            down_percent_value = financing.get("downPaymentPercent")
            down_percent = _public_text(str(down_percent_value), 20) if down_percent_value is not None else ""
            down_range = _public_text(financing.get("downPaymentRange"), 120)
            term_label = _public_text(financing.get("termLabel"), 80)
            annual_rate_value = financing.get("annualRate")
            annual_rate = _public_text(str(annual_rate_value), 20) if annual_rate_value is not None else ""
            monthly_range = _public_text(financing.get("monthlyRange"), 120)
            if mode_label:
                financing_parts.append(mode_label)
            if down_percent:
                down_text = "первый взнос: " + down_percent + "%"
                if down_range:
                    down_text += " (" + down_range + ")"
                financing_parts.append(down_text)
            if term_label:
                financing_parts.append("срок: " + term_label)
            if annual_rate:
                financing_parts.append("примерная ставка: " + annual_rate + "%")
            if monthly_range:
                financing_parts.append("платёж: " + monthly_range)
            if financing_parts:
                financing_parts.append("предварительный сценарий, не банковское предложение")
                parts.append("Финансирование: " + " · ".join(financing_parts))
        comparison = selected_project.get("comparison") if isinstance(selected_project.get("comparison"), dict) else {}
        comparison_items = comparison.get("items") if isinstance(comparison.get("items"), list) else []
        if comparison.get("status") == "customer_shortlist" and comparison_items:
            selected_code = _public_text(comparison.get("selectedCode"), 80)
            compared_projects = []
            seen_codes = set()
            for item in comparison_items:
                if not isinstance(item, dict):
                    continue
                code = _public_text(item.get("code"), 80)
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                title = _public_text(item.get("title"), 180)
                estimate_range = _public_text(item.get("estimateRange"), 120)
                item_parts = [code]
                if title:
                    item_parts.append(title)
                if estimate_range:
                    item_parts.append(estimate_range)
                if code == selected_code:
                    item_parts.append("выбран")
                compared_projects.append(" — ".join(item_parts))
                if len(compared_projects) >= 3:
                    break
            if compared_projects:
                parts.append("Сравнение клиента: " + "; ".join(compared_projects))
                comparison_url = _public_comparison_url(comparison.get("comparisonUrl"))
                if comparison_url:
                    parts.append("Ссылка на сравнение: " + comparison_url)
    page = _public_text(data.get("page"), 120)
    if page:
        parts.append("Страница: " + page)
    referrer = _public_text(data.get("referrer"), 255)
    if referrer:
        parts.append("Referrer: " + referrer)
    submitted_at = _public_text(data.get("submittedAt"), 80)
    if submitted_at:
        parts.append("Время отправки формы: " + submitted_at)
    utm = data.get("utm") if isinstance(data.get("utm"), dict) else {}
    if utm:
        utm_parts = []
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"):
            value = _public_text(utm.get(key), 120)
            if value:
                utm_parts.append(key + "=" + value)
        if utm_parts:
            parts.append("UTM: " + " · ".join(utm_parts))
    return "\n".join(parts)[:4000]


def _public_site_project(row: dict):
    enhanced = _site_list_value(row.get("publicEnhancedImages"))
    images = enhanced or _site_list_value(row.get("publicImages")) or _site_list_value(row.get("publicOriginalImages"))
    main = (row.get("publicMainImageUrl") or "").strip()
    if main and main not in images:
        images = [main] + images
    images = [str(image).strip() for image in images if isinstance(image, str) and str(image).strip()]
    title = _public_text(row.get("publicTitle"), 255)
    if not title or not images:
        return None
    progress = _site_int(row.get("publicProgress"), 0)
    return {
        "id": row.get("id"),
        "title": title,
        "category": row.get("publicCategory") or "house",
        "location": row.get("publicLocation") or "",
        "area": row.get("publicArea") or "",
        "year": row.get("publicYear") or "",
        "stage": row.get("publicStage") or "",
        "progress": max(0, min(100, progress)),
        "price": row.get("publicPriceLabel") or "",
        "term": row.get("publicTerm") or "",
        "summary": row.get("publicSummary") or "",
        "result": row.get("publicResult") or "",
        "passport": row.get("publicPassport") or "",
        "tags": _site_list_value(row.get("publicTags")),
        "images": images,
        "isLive": bool(row.get("publicIsLive")),
    }


def _site_price_rule(row: dict) -> dict:
    group_key = row.get("group_key") or row.get("groupKey") or ""
    return {
        "id": row.get("id"),
        "groupKey": group_key,
        "groupLabel": SITE_PRICE_GROUP_LABELS.get(group_key, group_key),
        "itemKey": row.get("item_key") or row.get("itemKey") or "",
        "label": row.get("label") or "",
        "value": float(row.get("value") or 0),
        "valueType": row.get("value_type") or row.get("valueType") or "rate",
        "unit": row.get("unit") or "",
        "enabled": bool(row.get("enabled")),
        "sortOrder": int(row.get("sort_order") or row.get("sortOrder") or 0),
        "updatedAt": row.get("updated_at") or row.get("updatedAt"),
    }


def _site_price_rules(get_db) -> list[dict]:
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT id, group_key, item_key, label, value, value_type, unit, enabled, sort_order, updated_at
            FROM site_price_rules
            ORDER BY group_key, sort_order, id
        """)
        return [_site_price_rule(dict(r)) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def register_public_site_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    leadership_roles = deps["leadership_roles"]
    require_project_access = deps["require_project_access"]
    log_audit = deps.get("log_audit")
    project_public_select = deps["project_public_select"]
    lead_rate_limit_seconds = deps.get("public_lead_rate_limit_seconds", 0)
    lead_last_submit = deps.get("public_lead_last_submit", {})
    lead_uploads_enabled = bool(deps.get("public_site_lead_uploads_enabled", False))
    public_site_company_id = int(deps.get("public_site_company_id") or 0)
    save_upload_bytes = deps.get("save_upload_bytes")
    delete_local_file = deps.get("delete_local_file")
    delete_s3_object = deps.get("delete_s3_object")

    site_admin = require_roles(*leadership_roles)

    @app.post("/site/lead-files")
    async def create_site_lead_file(request: Request, file: UploadFile = File(...)):
        if not lead_uploads_enabled:
            raise HTTPException(status_code=404, detail="Загрузка файлов с сайта пока отключена")
        if not public_site_company_id or not save_upload_bytes:
            raise HTTPException(status_code=503, detail="Хранилище заявок не настроено")

        content = await file.read(MAX_PUBLIC_LEAD_FILE_BYTES + 1)
        validated = validate_public_lead_file(file.filename or "file", file.content_type or "", content)
        _cleanup_expired_public_lead_uploads(get_db, delete_local_file, delete_s3_object)
        token = uuid.uuid4().hex
        context = "public-site-lead-quarantine"
        namespace = f"company-{public_site_company_id}-common-{context}"

        conn = get_db()
        cur = conn.cursor()
        try:
            _ensure_public_lead_uploads_schema(cur)
            cur.execute("""
                SELECT COUNT(*)
                FROM public_lead_uploads
                WHERE client_ip=%s AND created_at>NOW() - INTERVAL '1 hour'
            """, (_public_client_ip(request),))
            recent_uploads = cur.fetchone()[0]
            if public_upload_rate_exceeded(recent_uploads):
                raise HTTPException(status_code=429, detail="Слишком много файлов. Попробуйте позже.")
            uploaded = save_upload_bytes(
                content,
                validated["filename"],
                namespace,
                context,
                validated["contentType"],
                "",
            )
            cur.execute("""
                INSERT INTO file_ownership (
                    company_id,project_id,file_url,storage_key,context,original_name,content_type,
                    uploaded_by_id,uploaded_by
                ) VALUES (%s,NULL,%s,%s,%s,%s,%s,NULL,'Публичный сайт')
                RETURNING id
            """, (
                public_site_company_id,
                uploaded.get("url"),
                uploaded.get("key") or "",
                context,
                validated["filename"],
                validated["contentType"],
            ))
            ownership_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO public_lead_uploads (
                    token,company_id,file_ownership_id,original_name,content_type,size_bytes,
                    client_ip,status,expires_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',NOW() + INTERVAL '1 hour')
            """, (
                token,
                public_site_company_id,
                ownership_id,
                validated["filename"],
                validated["contentType"],
                validated["size"],
                _public_client_ip(request),
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

        return {
            "ok": True,
            "token": token,
            "name": validated["filename"],
            "contentType": validated["contentType"],
            "size": validated["size"],
            "expiresInSeconds": 3600,
        }

    @app.get("/site/projects")
    def get_site_projects():
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(f"""
                SELECT id,name,status,deadline,progress,{project_public_select}
                FROM projects
                WHERE COALESCE(public_show_on_site,false)=true
                  AND COALESCE(archived,false)=false
                ORDER BY COALESCE(public_is_live,false) DESC, public_updated_at DESC NULLS LAST, id DESC
                LIMIT 60
            """)
            rows = cur.fetchall()
            projects = [_public_site_project(dict(row)) for row in rows]
            return [project for project in projects if project is not None]
        finally:
            cur.close()
            conn.close()

    @app.get("/site/pricing")
    def get_site_pricing():
        rules = [r for r in _site_price_rules(get_db) if r.get("enabled")]
        return {
            "rules": rules,
            "groups": SITE_PRICE_GROUP_LABELS,
            "capabilities": {
                "leadFileUploads": lead_uploads_enabled,
                "maxLeadFiles": MAX_PUBLIC_LEAD_FILES,
                "maxLeadFileMb": int(MAX_PUBLIC_LEAD_FILE_BYTES / 1024 / 1024),
            },
            "domains": {
                "public": "stroyka26.pro",
                "app": "app.stroyka26.pro",
                "api": "api.stroyka26.pro",
            },
        }

    @app.get("/site-price-rules")
    def get_site_price_rules(_current_user: dict = Depends(site_admin)):
        return _site_price_rules(get_db)

    @app.put("/site-price-rules/{rule_id}")
    def update_site_price_rule(rule_id: int, data: dict, current_user: dict = Depends(site_admin)):
        value = data.get("value")
        try:
            value = float(str(value).replace(" ", "").replace(",", "."))
        except Exception:
            raise HTTPException(status_code=400, detail="Некорректное значение прайса")
        if value < 0:
            raise HTTPException(status_code=400, detail="Значение не может быть отрицательным")
        label = _public_text(data.get("label"), 255)
        unit = _public_text(data.get("unit"), 50)
        enabled = bool(data.get("enabled", True))
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""
                UPDATE site_price_rules
                   SET label=COALESCE(NULLIF(%s,''), label),
                       value=%s,
                       unit=%s,
                       enabled=%s,
                       updated_at=NOW()
                 WHERE id=%s
             RETURNING id, group_key, item_key, label, value, value_type, unit, enabled, sort_order, updated_at
            """, (label, value, unit, enabled, rule_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Правило прайса не найдено")
            conn.commit()
            if log_audit:
                log_audit(user_name=current_user.get("name",""), user_role=current_user.get("role",""),
                          action="update", entity_type="site_price_rule", entity_id=rule_id,
                          description="Обновлен прайс публичного калькулятора: " + (row.get("label") or ""),
                          project_name="")
            return _site_price_rule(dict(row))
        finally:
            cur.close()
            conn.close()

    @app.post("/site/leads")
    def create_site_lead(data: dict, request: Request):
        lead_owner = resolve_public_lead_owner(public_site_company_id)
        client_ip = _public_client_ip(request)
        now = time.time()
        last = lead_last_submit.get(client_ip, 0)
        if lead_rate_limit_seconds > 0 and now - last < lead_rate_limit_seconds:
            raise HTTPException(status_code=429, detail="Заявка уже отправлена. Попробуйте чуть позже.")

        if _public_text(data.get("website") or data.get("honeypot"), 255):
            lead_last_submit[client_ip] = now
            return {"ok": True, "id": None, "status": "accepted"}

        if data.get("consentAccepted") is not True:
            raise HTTPException(status_code=422, detail="Нужно согласие на обработку персональных данных")

        phone = _public_text(data.get("phone"), 80)
        if not phone:
            raise HTTPException(status_code=422, detail="Укажите телефон")
        attachment_tokens = _public_attachment_tokens(data)
        if attachment_tokens and not lead_uploads_enabled:
            raise HTTPException(status_code=422, detail="Загрузка файлов с сайта пока отключена")

        name = _public_text(data.get("name") or "Заявка с сайта", 255)
        email = _public_text(data.get("email"), 255)
        source = _public_text(data.get("source") or "Сайт", 255)
        budget = data.get("budget") or 0
        notes = _public_lead_notes(data)
        consent_version = _public_text(data.get("consentVersion"), 120)
        legal_source = _public_text(data.get("legalSource") or data.get("page"), 255)
        user_agent = _public_text(data.get("userAgent") or request.headers.get("user-agent"), 255)
        legal_notes = [
            "Согласие ПД: принято",
            "Версия согласия: " + (consent_version or "не указана"),
            "Источник согласия: " + (legal_source or "не указан"),
            "IP: " + client_ip,
            "User-Agent: " + (user_agent or "не указан"),
        ]
        notes = (notes + ("\n\n" if notes else "") + "\n".join(legal_notes))[:4000]
        created_at = dt.datetime.utcnow().strftime("%Y-%m-%d")

        partner_type = _public_text(data.get("partnerType"), 80)
        lead_type = {
            "supplier": "Поставщик",
            "master": "Мастер",
            "brigade": "Бригадир",
            "subcontractor": "Субподрядчик",
        }.get(partner_type, "Клиент")
        review_status = "На проверке" if partner_type else "Новая"

        conn = get_db()
        cur = conn.cursor()
        try:
            pending_uploads = []
            if attachment_tokens:
                _ensure_public_lead_uploads_schema(cur)
                cur.execute("""
                    SELECT u.token,u.file_ownership_id,u.original_name,u.content_type,u.size_bytes
                    FROM public_lead_uploads u
                    WHERE u.token = ANY(%s)
                      AND u.company_id=%s
                      AND u.client_ip=%s
                      AND u.status='pending'
                      AND u.expires_at>NOW()
                    FOR UPDATE
                """, (attachment_tokens, public_site_company_id, client_ip))
                pending_uploads = cur.fetchall()
                if len(pending_uploads) != len(attachment_tokens):
                    raise HTTPException(status_code=422, detail="Один или несколько файлов недоступны или просрочены")
            cur.execute(
                """INSERT INTO crm_leads
                   (company_id,name,phone,email,source,budget,notes,stage,created_by,created_at,lead_type,review_status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    lead_owner["companyId"], name, phone, email, source, budget, notes,
                    "Новый", "Сайт", created_at, lead_type, review_status,
                ),
            )
            new_id = cur.fetchone()[0]
            for upload in pending_uploads:
                ownership_id = upload[1]
                cur.execute("""
                    INSERT INTO crm_lead_documents (
                        company_id,project_id,lead_id,doc_type,title,file_url,status,confidential,notes,uploaded_by
                    ) VALUES (%s,NULL,%s,'Файл с сайта',%s,%s,'Загружен',true,%s,'Публичный сайт')
                """, (
                    lead_owner["companyId"],
                    new_id,
                    upload[2],
                    "/tenant-files/" + str(ownership_id) + "/content",
                    "Получено вместе с публичной заявкой",
                ))
            if pending_uploads:
                cur.execute("""
                    UPDATE public_lead_uploads
                       SET status='attached',lead_id=%s
                     WHERE token = ANY(%s) AND status='pending'
                """, (new_id, attachment_tokens))
                if cur.rowcount != len(attachment_tokens):
                    raise HTTPException(status_code=409, detail="Не удалось закрепить все файлы за заявкой")
                cur.execute(
                    "UPDATE crm_leads SET document_status='Есть документы' WHERE id=%s",
                    (new_id,),
                )
            cur.execute("""
                INSERT INTO crm_lead_tasks (
                    company_id,project_id,lead_id,title,due_date,status,assigned_to,notes,created_by
                ) VALUES (%s,NULL,%s,'Связаться с заявителем','','Новая','',%s,'Сайт')
            """, (
                lead_owner["companyId"],
                new_id,
                "Телефон: " + phone + (("\nEmail: " + email) if email else "") + (("\n\n" + notes) if notes else ""),
            ))
            conn.commit()
            lead_last_submit[client_ip] = now
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        return {"ok": True, "id": new_id, "attachments": len(attachment_tokens)}

    @app.put("/projects/{id}/site-publication")
    def update_project_site_publication(id: int, data: dict, current_user: dict = Depends(site_admin)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT id,name,status,deadline,progress FROM projects WHERE id=%s", (id,))
            project_row = cur.fetchone()
            if not project_row:
                raise HTTPException(status_code=404, detail="Объект не найден")
            require_project_access(current_user, project_row.get("name") or "")
            fields = [
                ("publicShowOnSite", "public_show_on_site"),
                ("publicIsLive", "public_is_live"),
                ("publicStatus", "public_status"),
                ("publicTitle", "public_title"),
                ("publicCategory", "public_category"),
                ("publicLocation", "public_location"),
                ("publicArea", "public_area"),
                ("publicYear", "public_year"),
                ("publicStage", "public_stage"),
                ("publicProgress", "public_progress"),
                ("publicPriceLabel", "public_price_label"),
                ("publicTerm", "public_term"),
                ("publicSummary", "public_summary"),
                ("publicResult", "public_result"),
                ("publicPassport", "public_passport"),
                ("publicMainImageUrl", "public_main_image_url"),
                ("publicAiStatus", "public_ai_status"),
                ("publicAiNotes", "public_ai_notes"),
            ]
            sets, vals = [], []
            for js_key, db_col in fields:
                if js_key in data:
                    v = data.get(js_key)
                    if db_col == "public_progress":
                        v = max(0, min(100, _site_int(v)))
                    if db_col in ("public_title", "public_stage") and v is None:
                        v = ""
                    sets.append(db_col + "=%s")
                    vals.append(v)
            for js_key, db_col in (
                ("publicTags", "public_tags"),
                ("publicImages", "public_images"),
                ("publicOriginalImages", "public_original_images"),
                ("publicEnhancedImages", "public_enhanced_images"),
            ):
                if js_key in data:
                    sets.append(db_col + "=%s::jsonb")
                    vals.append(json.dumps(_site_list_value(data.get(js_key)), ensure_ascii=False))
            if sets:
                sets.append("public_updated_at=NOW()")
                vals.append(id)
                cur.execute("UPDATE projects SET " + ", ".join(sets) + " WHERE id=%s", vals)
            cur.execute(f"""SELECT id,name,status,deadline,progress,{project_public_select} FROM projects WHERE id=%s""", (id,))
            row = cur.fetchone()
            site_project = _public_site_project(dict(row))
            if row.get("publicShowOnSite") and site_project is None:
                conn.rollback()
                raise HTTPException(
                    status_code=422,
                    detail="Для публикации заполните отдельное публичное название и добавьте хотя бы одно фото",
                )
            conn.commit()
            if log_audit:
                log_audit(user_name=current_user.get("name",""), user_role=current_user.get("role",""),
                          action="update", entity_type="project_site_publication", entity_id=id,
                          description="Обновлена публикация объекта на сайт", project_name=project_row.get("name") or "")
            return {"ok": True, "project": dict(row), "siteProject": site_project}
        finally:
            cur.close()
            conn.close()
