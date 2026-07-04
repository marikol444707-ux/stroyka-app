import datetime as dt
import json
import time

import psycopg2.extras
from fastapi import Depends, HTTPException, Request


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


def _public_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return _public_text(forwarded.split(",")[0], 80)
    return _public_text(request.client.host if request.client else "unknown", 80)


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


def _public_site_project(row: dict) -> dict:
    enhanced = _site_list_value(row.get("publicEnhancedImages"))
    images = enhanced or _site_list_value(row.get("publicImages")) or _site_list_value(row.get("publicOriginalImages"))
    main = (row.get("publicMainImageUrl") or "").strip()
    if main and main not in images:
        images = [main] + images
    if not images:
        images = ["https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=84"]
    progress = _site_int(row.get("publicProgress"), _site_int(row.get("progress"), 0))
    return {
        "id": row.get("id"),
        "projectId": row.get("id"),
        "projectName": row.get("name") or "",
        "title": row.get("publicTitle") or row.get("name") or "",
        "category": row.get("publicCategory") or "house",
        "location": row.get("publicLocation") or "",
        "area": row.get("publicArea") or "",
        "year": row.get("publicYear") or "",
        "stage": row.get("publicStage") or row.get("status") or "",
        "progress": max(0, min(100, progress)),
        "price": row.get("publicPriceLabel") or "",
        "term": row.get("publicTerm") or row.get("deadline") or "",
        "summary": row.get("publicSummary") or "",
        "result": row.get("publicResult") or "",
        "passport": row.get("publicPassport") or "",
        "tags": _site_list_value(row.get("publicTags")),
        "images": images,
        "isLive": bool(row.get("publicIsLive")),
        "aiStatus": row.get("publicAiStatus") or "Не обработано",
        "aiNotes": row.get("publicAiNotes") or "",
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
    system_project_name = deps["system_project_name"]
    lead_rate_limit_seconds = deps.get("public_lead_rate_limit_seconds", 0)
    lead_last_submit = deps.get("public_lead_last_submit", {})

    site_admin = require_roles(*leadership_roles)

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
            return [_public_site_project(dict(r)) for r in rows]
        finally:
            cur.close()
            conn.close()

    @app.get("/site/pricing")
    def get_site_pricing():
        rules = [r for r in _site_price_rules(get_db) if r.get("enabled")]
        return {
            "rules": rules,
            "groups": SITE_PRICE_GROUP_LABELS,
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
            cur.execute(
                """INSERT INTO crm_leads
                   (name,phone,email,source,budget,notes,stage,created_by,created_at,lead_type,review_status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (name, phone, email, source, budget, notes, "Новый", "Сайт", created_at, lead_type, review_status),
            )
            new_id = cur.fetchone()[0]
            action_payload = json.dumps({
                "type": "open_page",
                "page": "crm",
                "leadId": new_id,
                "source": "site",
            }, ensure_ascii=False)
            cur.execute("""
                INSERT INTO ai_tasks (
                    finding_id, project_name, title, description, assigned_role, assigned_to,
                    status, due_date, action_label, action_payload, dedupe_key, created_at, updated_at
                ) VALUES (NULL,%s,%s,%s,'директор','','Новое',NULL,'Открыть CRM',%s,%s,NOW(),NOW())
            """, (
                system_project_name,
                "Новая заявка с сайта: " + name,
                "Телефон: " + phone + (("\nEmail: " + email) if email else "") + (("\n\n" + notes) if notes else ""),
                action_payload,
                "SITE_LEAD:" + str(new_id),
            ))
            conn.commit()
            lead_last_submit[client_ip] = now
        finally:
            cur.close()
            conn.close()
        return {"ok": True, "id": new_id}

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
            if data.get("publicShowOnSite") and not str(data.get("publicTitle") or "").strip():
                if "publicTitle" not in data:
                    sets.append("public_title=%s")
                    vals.append(project_row.get("name") or "")
            if sets:
                sets.append("public_updated_at=NOW()")
                vals.append(id)
                cur.execute("UPDATE projects SET " + ", ".join(sets) + " WHERE id=%s", vals)
            cur.execute(f"""SELECT id,name,status,deadline,progress,{project_public_select} FROM projects WHERE id=%s""", (id,))
            row = cur.fetchone()
            conn.commit()
            if log_audit:
                log_audit(user_name=current_user.get("name",""), user_role=current_user.get("role",""),
                          action="update", entity_type="project_site_publication", entity_id=id,
                          description="Обновлена публикация объекта на сайт", project_name=project_row.get("name") or "")
            return {"ok": True, "project": dict(row), "siteProject": _public_site_project(dict(row))}
        finally:
            cur.close()
            conn.close()
