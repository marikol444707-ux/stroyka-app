import datetime as dt
import json
import uuid
from datetime import datetime, timedelta, date
from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException


SYSTEM_TARIFFS = [
    {
        "id": "demo",
        "name": "Демо",
        "monthlyFee": 0,
        "includedCompanies": 1,
        "maxProjects": 1,
        "maxUsers": 5,
        "ocrPages": 50,
        "storageGb": 2,
        "trialDays": 14,
        "audience": "Проверка системы на одном объекте.",
        "features": ["Базовая ERP", "Сметы", "Склад объекта", "Ограниченный OCR"],
    },
    {
        "id": "starter",
        "name": "Старт",
        "monthlyFee": 19900,
        "includedCompanies": 1,
        "maxProjects": 3,
        "maxUsers": 15,
        "ocrPages": 200,
        "storageGb": 10,
        "trialDays": 0,
        "audience": "Одна небольшая строительная компания.",
        "features": ["Объекты", "Сметы", "Склад", "Финансы", "Документы"],
    },
    {
        "id": "pro",
        "name": "Компания",
        "monthlyFee": 49900,
        "includedCompanies": 2,
        "maxProjects": 10,
        "maxUsers": 40,
        "ocrPages": 1000,
        "storageGb": 50,
        "trialDays": 0,
        "audience": "Рабочая стройкомпания с бухгалтерией и снабжением.",
        "features": ["Бухгалтерия", "Снабжение", "OCR накладных", "Роли", "Сводки"],
    },
    {
        "id": "group",
        "name": "Группа",
        "monthlyFee": 99000,
        "includedCompanies": 5,
        "maxProjects": 30,
        "maxUsers": 100,
        "ocrPages": 3000,
        "storageGb": 150,
        "trialDays": 0,
        "audience": "Несколько юрлиц или строительных компаний в одном окне.",
        "features": ["Общий кабинет группы", "Переключатель компаний", "Расширенный аудит", "Лимиты по аккаунту"],
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "monthlyFee": 150000,
        "includedCompanies": None,
        "maxProjects": None,
        "maxUsers": None,
        "ocrPages": None,
        "storageGb": None,
        "trialDays": 0,
        "audience": "Крупный клиент с индивидуальными условиями.",
        "features": ["Индивидуальные лимиты", "Домен", "API", "SLA", "Интеграции"],
    },
]


def _system_tariff(plan: str):
    plan_key = (plan or "demo").strip()
    return next((t for t in SYSTEM_TARIFFS if t["id"] == plan_key), SYSTEM_TARIFFS[0])


def _system_days_left(value):
    if not value:
        return None
    try:
        if isinstance(value, dt.datetime):
            target = value.date()
        elif isinstance(value, dt.date):
            target = value
        else:
            target = dt.date.fromisoformat(str(value)[:10])
        return (target - dt.date.today()).days
    except Exception:
        return None


def _system_company_billing_state(company: dict):
    if company.get("id") == 1:
        return {
            "status": "platform_owner",
            "label": "Владелец платформы",
            "level": "success",
            "reason": "Системная компания не участвует в заморозке.",
            "daysLeft": None,
        }
    if company.get("suspended_at"):
        return {
            "status": "soft_frozen",
            "label": "Мягко заморожен",
            "level": "danger",
            "reason": company.get("suspended_reason") or "Доступ ограничен владельцем платформы.",
            "daysLeft": None,
        }
    plan = company.get("plan") or "demo"
    payment_status = company.get("payment_status") or "active"
    if plan == "demo":
        days_left = _system_days_left(company.get("trial_until"))
        if days_left is None:
            return {"status": "trial_no_date", "label": "Демо без даты", "level": "warning", "reason": "Укажите дату окончания демо.", "daysLeft": None}
        if days_left < 0:
            return {"status": "trial_expired", "label": "Демо истекло", "level": "danger", "reason": f"Демо закончилось {abs(days_left)} дн. назад.", "daysLeft": days_left}
        if days_left <= 3:
            return {"status": "trial_expiring", "label": "Демо скоро закончится", "level": "warning", "reason": f"Осталось {days_left} дн.", "daysLeft": days_left}
        return {"status": "trial_active", "label": "Демо активно", "level": "info", "reason": f"Осталось {days_left} дн.", "daysLeft": days_left}
    days_left = _system_days_left(company.get("plan_expires_at"))
    if payment_status == "overdue":
        return {"status": "payment_overdue", "label": "Просрочка", "level": "danger", "reason": "Оплата помечена как просроченная.", "daysLeft": days_left}
    if days_left is not None:
        if days_left < 0:
            return {"status": "payment_expired", "label": "Оплата истекла", "level": "danger", "reason": f"Оплаченный период закончился {abs(days_left)} дн. назад.", "daysLeft": days_left}
        if days_left <= 7:
            return {"status": "payment_expiring", "label": "Оплата скоро закончится", "level": "warning", "reason": f"Осталось {days_left} дн.", "daysLeft": days_left}
    return {"status": "active_paid", "label": "Активен", "level": "success", "reason": "Оплата в порядке.", "daysLeft": days_left}


def _system_write_audit(cur, current_user: dict, action: str, entity_type: str = None, entity_id: int = None,
                        entity_name: str = None, platform_account_id: int = None, company_id: int = None,
                        details: dict = None):
    safe_details = details or {}
    cur.execute("""INSERT INTO platform_audit_log
                   (actor_user_id, actor_name, actor_role, action, entity_type, entity_id, entity_name,
                    platform_account_id, company_id, details_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (current_user.get("id") if isinstance(current_user, dict) else None,
         current_user.get("name") if isinstance(current_user, dict) else "system_owner",
         current_user.get("role") if isinstance(current_user, dict) else None,
         action, entity_type, entity_id, entity_name,
         platform_account_id, company_id,
         json.dumps(safe_details, ensure_ascii=False, default=str)))


write_platform_audit = _system_write_audit


def register_platform_admin_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]

    @app.get("/system/tariffs")
    def system_tariffs_list(_current_user: dict = Depends(require_roles("system_owner"))):
        return SYSTEM_TARIFFS

    @app.get("/system/companies")
    def system_companies_list(_current_user: dict = Depends(require_roles("system_owner"))):
        """Полный список компаний с биллингом - только для владельца платформы."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT c.id, c.name, c.short_name, c.inn, c.contact_name, c.contact_phone, c.contact_email,
                              c.plan, c.trial_until, c.plan_expires_at, c.monthly_fee, c.payment_status,
                              c.suspended_at, c.suspended_reason, c.max_projects, c.max_users,
                              c.last_active_at, c.notes, c.active, c.created_at,
                              c.platform_account_id,
                              pa.name AS platform_account_name,
                              pa.status AS platform_account_status,
                              pa.plan AS platform_account_plan
                       FROM companies c
                       LEFT JOIN platform_accounts pa ON pa.id=c.platform_account_id
                       ORDER BY COALESCE(c.platform_account_id, c.id), c.id""")
        rows = [dict(r) for r in cur.fetchall()]
        for company in rows:
            cur.execute("SELECT COUNT(*) FROM users WHERE company_id=%s", (company["id"],))
            company["users_count"] = cur.fetchone()["count"]
            cur.execute("SELECT COUNT(*) FROM projects WHERE company_id=%s", (company["id"],))
            company["projects_count"] = cur.fetchone()["count"]
            cur.execute("SELECT COALESCE(SUM(amount),0) as t FROM company_payments WHERE company_id=%s AND status='paid'", (company["id"],))
            company["total_paid"] = float(cur.fetchone()["t"] or 0)
            cur.execute("SELECT COUNT(*) FROM companies WHERE platform_account_id=%s AND active=TRUE", (company.get("platform_account_id") or company["id"],))
            company["account_companies_count"] = cur.fetchone()["count"]
            company["billing_state"] = _system_company_billing_state(company)
        conn.close()
        return rows

    @app.post("/system/companies")
    def system_create_company(data: dict, current_user: dict = Depends(require_roles("system_owner"))):
        """Создание новой компании-клиента + инвайт-код ее директору."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        plan = data.get("plan") or "demo"
        tariff = _system_tariff(plan)
        trial_days = int(data.get("trialDays") or 30)
        trial_until = (datetime.now() + timedelta(days=trial_days)).date() if plan == "demo" else None
        monthly_fee = float(data.get("monthlyFee") or tariff.get("monthlyFee") or 0)
        max_projects = int(data.get("maxProjects") or tariff.get("maxProjects") or 0) or None
        max_users = int(data.get("maxUsers") or tariff.get("maxUsers") or 0) or None
        platform_account_id = data.get("platformAccountId")
        created_platform_account = False
        if not platform_account_id:
            account_name = (data.get("platformAccountName") or data.get("accountName") or data.get("name") or "").strip()
            cur.execute("""INSERT INTO platform_accounts (name, owner_name, contact_email, plan, status, notes)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (account_name, data.get("contactName"), data.get("contactEmail"),
                 plan, "trial" if plan == "demo" else "active", data.get("notes")))
            platform_account_id = cur.fetchone()["id"]
            created_platform_account = True
            _system_write_audit(cur, current_user, "platform_account_created", "platform_account",
                platform_account_id, account_name, platform_account_id=platform_account_id,
                details={"plan": plan, "status": "trial" if plan == "demo" else "active", "contactEmail": data.get("contactEmail")})
        cur.execute("""INSERT INTO companies (platform_account_id, name, short_name, inn, kpp, contact_name, contact_phone,
                                              contact_email, plan, trial_until, monthly_fee,
                                              payment_status, max_projects, max_users, active, notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (platform_account_id, data.get("name"), data.get("shortName"), data.get("inn"), data.get("kpp"),
             data.get("contactName"), data.get("contactPhone"), data.get("contactEmail"),
             plan, trial_until, monthly_fee,
             "trial" if plan == "demo" else "active",
             max_projects, max_users,
             True, data.get("notes")))
        new_id = cur.fetchone()["id"]
        invite_code = str(uuid.uuid4())[:8].upper()
        expires = datetime.now() + timedelta(days=30)
        cur.execute("INSERT INTO invite_codes (code, role, preset_name, expires_at, created_by) VALUES (%s,%s,%s,%s,%s)",
            (invite_code, "директор", data.get("name"), expires, data.get("createdBy") or "system_owner"))
        _system_write_audit(cur, current_user, "company_created", "company", new_id, data.get("name"),
            platform_account_id=platform_account_id, company_id=new_id,
            details={
                "createdPlatformAccount": created_platform_account,
                "plan": plan,
                "trialUntil": trial_until,
                "monthlyFee": monthly_fee,
                "maxProjects": max_projects,
                "maxUsers": max_users,
                "inviteCode": invite_code,
            })
        conn.close()
        return {"id": new_id, "inviteCode": invite_code, "trialUntil": str(trial_until) if trial_until else None}

    @app.put("/system/companies/{id}")
    def system_update_company(id: int, data: dict, current_user: dict = Depends(require_roles("system_owner"))):
        """Обновление компании: смена тарифа, продление триала, заморозка."""
        action = data.get("action")
        if id == 1 and action in ("suspend", "soft_suspend", "hard_suspend"):
            raise HTTPException(status_code=400, detail="system_owner company cannot be suspended")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT id, name, platform_account_id, plan, trial_until, plan_expires_at,
                              payment_status, suspended_at, active, max_projects, max_users
                       FROM companies WHERE id=%s""", (id,))
        before = cur.fetchone()
        if not before:
            conn.close()
            raise HTTPException(status_code=404, detail="company not found")
        sets, vals = [], []
        fields_map = [
            ("plan", "plan"), ("trialUntil", "trial_until"), ("planExpiresAt", "plan_expires_at"),
            ("monthlyFee", "monthly_fee"), ("paymentStatus", "payment_status"),
            ("maxProjects", "max_projects"), ("maxUsers", "max_users"),
            ("contactName", "contact_name"), ("contactPhone", "contact_phone"),
            ("contactEmail", "contact_email"), ("notes", "notes"), ("active", "active"),
        ]
        for js_key, db_col in fields_map:
            if js_key in data:
                sets.append(db_col + "=%s")
                vals.append(data[js_key])
        if action in ("suspend", "soft_suspend"):
            sets.append("suspended_at=%s")
            vals.append(datetime.now())
            sets.append("suspended_reason=%s")
            vals.append(data.get("reason") or "")
            sets.append("payment_status=%s")
            vals.append("soft_suspended")
            sets.append("active=%s")
            vals.append(True)
        elif action == "hard_suspend":
            sets.append("suspended_at=%s")
            vals.append(datetime.now())
            sets.append("suspended_reason=%s")
            vals.append(data.get("reason") or "")
            sets.append("payment_status=%s")
            vals.append("suspended")
            sets.append("active=%s")
            vals.append(False)
        elif action == "resume":
            sets.append("suspended_at=NULL")
            sets.append("suspended_reason=NULL")
            sets.append("payment_status=%s")
            vals.append(data.get("paymentStatus") or "active")
            sets.append("active=%s")
            vals.append(True)
        elif action == "mark_overdue":
            sets.append("payment_status=%s")
            vals.append("overdue")
        if not sets:
            conn.close()
            return {"ok": False, "error": "no fields"}
        vals.append(id)
        cur.execute("UPDATE companies SET " + ", ".join(sets) + " WHERE id=%s", vals)
        cur.execute("""SELECT id, name, platform_account_id, plan, trial_until, plan_expires_at,
                              payment_status, suspended_at, active, max_projects, max_users
                       FROM companies WHERE id=%s""", (id,))
        after = cur.fetchone()
        audit_action = {
            "soft_suspend": "company_soft_suspended",
            "suspend": "company_soft_suspended",
            "hard_suspend": "company_hard_suspended",
            "resume": "company_resumed",
            "mark_overdue": "company_marked_overdue",
        }.get(action, "company_updated")
        if not action and ("trialUntil" in data):
            audit_action = "company_trial_extended"
        if not action and ("plan" in data):
            audit_action = "company_tariff_changed"
        _system_write_audit(cur, current_user, audit_action, "company", id, after.get("name"),
            platform_account_id=after.get("platform_account_id"), company_id=id,
            details={"request": data, "before": dict(before), "after": dict(after)})
        conn.close()
        return {"ok": True}

    @app.get("/system/dashboard")
    def system_dashboard(_current_user: dict = Depends(require_roles("system_owner"))):
        """Сводка для главной страницы кабинета системы."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        today = date.today()
        cur.execute("SELECT COUNT(*) as c FROM platform_accounts WHERE active=TRUE")
        active_accounts = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM companies WHERE active=TRUE")
        active = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM companies WHERE plan='demo' AND active=TRUE")
        in_demo = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM companies WHERE suspended_at IS NOT NULL")
        suspended = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM companies WHERE payment_status='overdue'")
        overdue = cur.fetchone()["c"]
        cur.execute("""SELECT COUNT(*) as c FROM companies
                       WHERE plan='demo' AND trial_until IS NOT NULL AND trial_until BETWEEN %s AND %s""",
                    (today, today + dt.timedelta(days=3)))
        trial_expiring = cur.fetchone()["c"]
        cur.execute("""SELECT COUNT(*) as c FROM companies
                       WHERE plan='demo' AND trial_until IS NOT NULL AND trial_until < %s AND suspended_at IS NULL""", (today,))
        trial_expired = cur.fetchone()["c"]
        cur.execute("""SELECT COUNT(*) as c FROM companies
                       WHERE plan<>'demo' AND plan_expires_at IS NOT NULL AND plan_expires_at < %s AND suspended_at IS NULL""", (today,))
        payment_expired = cur.fetchone()["c"]
        cur.execute("SELECT COALESCE(SUM(amount),0) as t FROM company_payments WHERE status='paid' AND date_trunc('month', payment_date)=date_trunc('month', %s::date)", (today,))
        month_revenue = float(cur.fetchone()["t"] or 0)
        cur.execute("SELECT COALESCE(SUM(amount),0) as t FROM company_payments WHERE status='paid' AND date_trunc('year', payment_date)=date_trunc('year', %s::date)", (today,))
        year_revenue = float(cur.fetchone()["t"] or 0)
        cur.execute("SELECT COUNT(*) as c FROM demo_requests WHERE status='Новая'")
        new_demos = cur.fetchone()["c"]
        conn.close()
        return {
            "activeAccounts": active_accounts, "activeCompanies": active, "inDemo": in_demo, "suspended": suspended,
            "overdue": overdue, "monthRevenue": month_revenue, "yearRevenue": year_revenue,
            "newDemoRequests": new_demos,
            "trialExpiring": trial_expiring,
            "trialExpired": trial_expired,
            "paymentExpired": payment_expired,
        }

    @app.get("/system/payments")
    def system_payments_list(_current_user: dict = Depends(require_roles("system_owner"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT p.*, c.name as company_name FROM company_payments p
                       LEFT JOIN companies c ON c.id=p.company_id
                       ORDER BY p.payment_date DESC LIMIT 200""")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @app.post("/system/payments")
    def system_create_payment(data: dict, current_user: dict = Depends(require_roles("system_owner"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""INSERT INTO company_payments (company_id, amount, payment_date, method,
                                                      invoice_number, status, period_start, period_end,
                                                      notes, created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data.get("companyId"), float(data.get("amount") or 0), data.get("paymentDate") or None,
             data.get("method"), data.get("invoiceNumber"), data.get("status") or "paid",
             data.get("periodStart") or None, data.get("periodEnd") or None,
             data.get("notes"), data.get("createdBy")))
        new_id = cur.fetchone()["id"]
        if data.get("periodEnd") and data.get("companyId"):
            cur.execute("""UPDATE companies
                           SET plan_expires_at=%s, payment_status='active',
                               suspended_at=NULL, suspended_reason=NULL, active=TRUE
                           WHERE id=%s""",
                (data["periodEnd"], data["companyId"]))
        cur.execute("SELECT id, name, platform_account_id FROM companies WHERE id=%s", (data.get("companyId"),))
        company = cur.fetchone() or {}
        _system_write_audit(cur, current_user, "payment_added", "company_payment", new_id,
            data.get("invoiceNumber") or company.get("name"), platform_account_id=company.get("platform_account_id"),
            company_id=data.get("companyId"),
            details={
                "amount": float(data.get("amount") or 0),
                "paymentDate": data.get("paymentDate"),
                "periodStart": data.get("periodStart"),
                "periodEnd": data.get("periodEnd"),
                "method": data.get("method"),
                "companyName": company.get("name"),
            })
        conn.close()
        return {"id": new_id, "ok": True}

    @app.get("/system/audit-log")
    def system_audit_log(limit: int = 120, companyId: Optional[int] = None,
                         _current_user: dict = Depends(require_roles("system_owner"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        safe_limit = max(1, min(int(limit or 120), 300))
        where, vals = [], []
        if companyId:
            where.append("company_id=%s")
            vals.append(companyId)
        sql = """SELECT id, actor_user_id, actor_name, actor_role, action, entity_type, entity_id,
                        entity_name, platform_account_id, company_id, details_json, created_at
                 FROM platform_audit_log"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT %s"
        vals.append(safe_limit)
        cur.execute(sql, vals)
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            try:
                row["details"] = json.loads(row.get("details_json") or "{}")
            except Exception:
                row["details"] = {}
            row.pop("details_json", None)
        conn.close()
        return rows
