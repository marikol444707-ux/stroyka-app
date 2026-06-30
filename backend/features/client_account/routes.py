import datetime as dt

import psycopg2.extras
from fastapi import Depends, HTTPException

try:
    from backend.features.platform_admin.routes import SYSTEM_TARIFFS
except ModuleNotFoundError:
    from features.platform_admin.routes import SYSTEM_TARIFFS


CLIENT_ACCOUNT_ROLES = ("account_owner", "account_admin")
PLATFORM_STAFF_ROLES = ("system_owner", "platform_admin", "platform_support", "billing_admin")

CLIENT_ACCOUNT_ROLE_LABELS = {
    "account_owner": "Владелец клиентского аккаунта",
    "account_admin": "Администратор клиентского аккаунта",
}

CLIENT_USER_ROLE_LABELS = {
    **CLIENT_ACCOUNT_ROLE_LABELS,
    "директор": "Директор компании",
    "зам_директора": "Заместитель директора",
    "бухгалтер": "Бухгалтер",
    "прораб": "Прораб",
    "главный_инженер": "Главный инженер",
    "сметчик": "Сметчик",
    "кладовщик": "Кладовщик",
    "снабженец": "Снабженец",
    "мастер": "Мастер",
    "бригадир": "Бригадир",
    "субподрядчик": "Субподрядчик",
    "поставщик": "Поставщик",
    "менеджер_crm": "Менеджер CRM",
    "стройконтроль": "Стройконтроль",
    "технадзор": "Технадзор",
}

BILLING_DOCUMENT_TYPE_LABELS = {
    "invoice": "Счет",
    "act": "Акт",
    "offer": "КП",
}

BILLING_DOCUMENT_STATUS_LABELS = {
    "draft": "Черновик",
    "issued": "Выставлен",
    "payment_expected": "Ожидает оплату",
    "closed": "Закрыт",
    "cancelled": "Аннулирован",
}

FOLLOWUP_SOURCE_LABELS = {
    "demo": "Демо",
    "payment": "Оплата",
    "renewal": "Продление",
    "support": "Поддержка",
    "manual": "Вручную",
}

FOLLOWUP_STATUS_LABELS = {
    "open": "Открыта",
    "contacted": "Связались",
    "waiting": "Ждем клиента",
    "done": "Закрыта",
    "cancelled": "Отменена",
}

SUPPORT_SCOPE_LABELS = {
    "read_only": "Только просмотр",
    "access_help": "Помощь с доступом",
    "billing_help": "Биллинг",
    "technical_check": "Техническая проверка",
}


def _as_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except Exception:
        return None


def _as_float(value):
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _iso_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _tariff(plan):
    plan_key = (plan or "demo").strip()
    return next((item for item in SYSTEM_TARIFFS if item.get("id") == plan_key), SYSTEM_TARIFFS[0])


def _tariff_public(item):
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "monthlyFee": item.get("monthlyFee"),
        "includedCompanies": item.get("includedCompanies"),
        "maxProjects": item.get("maxProjects"),
        "maxUsers": item.get("maxUsers"),
        "ocrPages": item.get("ocrPages"),
        "storageGb": item.get("storageGb"),
        "features": item.get("features") or [],
    }


def _limit_warnings(tariff, usage):
    rules = [
        ("companies", "includedCompanies", "Компании"),
        ("projects", "maxProjects", "Объекты"),
        ("activeUsers", "maxUsers", "Активные пользователи"),
    ]
    warnings = []
    for usage_key, limit_key, label in rules:
        limit = tariff.get(limit_key)
        if limit in (None, ""):
            continue
        used = int(usage.get(usage_key) or 0)
        limit = int(limit)
        if used > limit:
            warnings.append({
                "level": "danger",
                "label": label,
                "message": f"{label}: {used} из {limit}. Лимит превышен, но доступ автоматически не блокируется.",
                "used": used,
                "limit": limit,
            })
        elif limit and used >= max(1, int(limit * 0.8)):
            warnings.append({
                "level": "warning",
                "label": label,
                "message": f"{label}: {used} из {limit}. Скоро понадобится расширение тарифа.",
                "used": used,
                "limit": limit,
            })
    return warnings


def _billing_state(company):
    if company.get("suspended_at"):
        return {"status": "soft_frozen", "label": "Мягко заморожена", "level": "danger"}
    payment_status = company.get("payment_status") or "active"
    if payment_status == "overdue":
        return {"status": "overdue", "label": "Просрочка", "level": "danger"}
    plan = company.get("plan") or "demo"
    if plan == "demo":
        trial_until = company.get("trial_until")
        if trial_until:
            try:
                target = trial_until.date() if isinstance(trial_until, dt.datetime) else trial_until
                if not isinstance(target, dt.date):
                    target = dt.date.fromisoformat(str(target)[:10])
                days_left = (target - dt.date.today()).days
                if days_left < 0:
                    return {"status": "trial_expired", "label": "Демо истекло", "level": "danger", "daysLeft": days_left}
                if days_left <= 3:
                    return {"status": "trial_expiring", "label": "Демо скоро закончится", "level": "warning", "daysLeft": days_left}
                return {"status": "trial_active", "label": "Демо активно", "level": "info", "daysLeft": days_left}
            except Exception:
                return {"status": "trial_unknown", "label": "Демо", "level": "info"}
        return {"status": "trial_unknown", "label": "Демо без даты", "level": "warning"}
    expires = company.get("plan_expires_at")
    if expires:
        try:
            target = expires.date() if isinstance(expires, dt.datetime) else expires
            if not isinstance(target, dt.date):
                target = dt.date.fromisoformat(str(target)[:10])
            days_left = (target - dt.date.today()).days
            if days_left < 0:
                return {"status": "payment_expired", "label": "Оплата истекла", "level": "danger", "daysLeft": days_left}
            if days_left <= 7:
                return {"status": "payment_expiring", "label": "Оплата скоро закончится", "level": "warning", "daysLeft": days_left}
        except Exception:
            pass
    return {"status": "active", "label": "Активна", "level": "success"}


def _company_row(row):
    item = dict(row)
    item["active"] = item.get("active") is not False
    item["projectsCount"] = int(item.pop("projects_count", 0) or 0)
    item["usersCount"] = int(item.pop("users_count", 0) or 0)
    item["activeUsersCount"] = int(item.pop("active_users_count", 0) or 0)
    item["trialUntil"] = _iso_date(item.pop("trial_until", None))
    item["planExpiresAt"] = _iso_date(item.pop("plan_expires_at", None))
    item["suspendedAt"] = _iso_date(item.pop("suspended_at", None))
    item["paymentStatus"] = item.pop("payment_status", None)
    item["shortName"] = item.pop("short_name", "") or ""
    item["contactName"] = item.pop("contact_name", "") or ""
    item["contactPhone"] = item.pop("contact_phone", "") or ""
    item["contactEmail"] = item.pop("contact_email", "") or ""
    item["billingState"] = _billing_state(row)
    return item


def _user_row(row):
    item = dict(row)
    role = item.get("role") or ""
    item["active"] = item.get("active") is not False
    item["roleLabel"] = CLIENT_USER_ROLE_LABELS.get(role, role)
    item["companyId"] = item.pop("company_id", None)
    item["companyName"] = item.pop("company_name", "") or ""
    platform_account_id = item.pop("platform_account_id", None)
    user_platform_account_id = item.pop("user_platform_account_id", None)
    item["platformAccountId"] = platform_account_id or user_platform_account_id
    item["twoFactorRequired"] = bool(item.pop("two_factor_required", False))
    item["twoFactorEnabled"] = bool(item.pop("two_factor_enabled", False))
    item["createdAt"] = _iso_date(item.pop("created_at", None))
    return item


def _billing_document_row(row):
    item = dict(row)
    document_type = item.get("document_type") or ""
    status = item.get("status") or ""
    item["documentType"] = document_type
    item["documentTypeLabel"] = BILLING_DOCUMENT_TYPE_LABELS.get(document_type, document_type)
    item["statusLabel"] = BILLING_DOCUMENT_STATUS_LABELS.get(status, status)
    item["amount"] = _as_float(item.get("amount"))
    item["companyName"] = item.pop("company_name", "") or ""
    item["platformAccountId"] = item.pop("platform_account_id", None)
    item["companyId"] = item.pop("company_id", None)
    item["issueDate"] = _iso_date(item.pop("issue_date", None))
    item["dueDate"] = _iso_date(item.pop("due_date", None))
    item["periodStart"] = _iso_date(item.pop("period_start", None))
    item["periodEnd"] = _iso_date(item.pop("period_end", None))
    item["paymentProvider"] = item.pop("payment_provider", "") or ""
    item["paymentUrl"] = item.pop("payment_url", "") or ""
    item["fileUrl"] = item.pop("file_url", "") or ""
    item["createdAt"] = _iso_date(item.pop("created_at", None))
    return item


def _followup_row(row):
    item = dict(row)
    source = item.get("source") or ""
    status = item.get("status") or "open"
    item["sourceLabel"] = FOLLOWUP_SOURCE_LABELS.get(source, source)
    item["statusLabel"] = FOLLOWUP_STATUS_LABELS.get(status, status)
    item["companyName"] = item.pop("company_name", "") or ""
    item["billingDocumentNumber"] = item.pop("billing_document_number", "") or ""
    item["platformAccountId"] = item.pop("platform_account_id", None)
    item["companyId"] = item.pop("company_id", None)
    item["billingDocumentId"] = item.pop("billing_document_id", None)
    item["contactName"] = item.pop("contact_name", "") or ""
    item["contactValue"] = item.pop("contact_value", "") or ""
    item["responsibleName"] = item.pop("responsible_name", "") or ""
    item["dueDate"] = _iso_date(item.pop("due_date", None))
    item["createdAt"] = _iso_date(item.pop("created_at", None))
    item["completedAt"] = _iso_date(item.pop("completed_at", None))
    return item


def _support_session_row(row):
    item = dict(row)
    scope = item.get("scope") or ""
    item["scopeLabel"] = SUPPORT_SCOPE_LABELS.get(scope, scope)
    item["companyName"] = item.pop("company_name", "") or ""
    item["platformAccountId"] = item.pop("platform_account_id", None)
    item["companyId"] = item.pop("company_id", None)
    item["openedByName"] = item.pop("opened_by_name", "") or ""
    item["closedByName"] = item.pop("closed_by_name", "") or ""
    item["expiresAt"] = _iso_date(item.pop("expires_at", None))
    item["createdAt"] = _iso_date(item.pop("created_at", None))
    item["closedAt"] = _iso_date(item.pop("closed_at", None))
    if item.get("status") == "active" and item.get("expiresAt"):
        try:
            expires_at = dt.datetime.fromisoformat(str(item["expiresAt"]))
            if expires_at < dt.datetime.now():
                item["status"] = "expired"
        except Exception:
            pass
    return item


def _resolve_account(cur, current_user):
    platform_account_id = _as_int(current_user.get("platformAccountId") or current_user.get("platform_account_id"))
    company_id = _as_int(current_user.get("companyId") or current_user.get("company_id"))
    if not platform_account_id and company_id:
        cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
        company = cur.fetchone()
        platform_account_id = _as_int(company.get("platform_account_id") if company else None)
    if not platform_account_id:
        raise HTTPException(status_code=403, detail="Клиентский аккаунт не назначен")
    cur.execute("""SELECT id, name, owner_name, contact_email, plan, status, active, created_at
                   FROM platform_accounts
                   WHERE id=%s""", (platform_account_id,))
    account = cur.fetchone()
    if not account:
        raise HTTPException(status_code=404, detail="Клиентский аккаунт не найден")
    return dict(account)


def register_client_account_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]

    @app.get("/account/dashboard")
    def client_account_dashboard(current_user: dict = Depends(require_roles(*CLIENT_ACCOUNT_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            account = _resolve_account(cur, current_user)
            account_id = int(account["id"])
            tariff = _tariff(account.get("plan"))

            cur.execute("""SELECT c.id, c.name, c.short_name, c.inn, c.kpp, c.plan, c.trial_until,
                                  c.plan_expires_at, c.payment_status, c.suspended_at, c.active,
                                  c.contact_name, c.contact_phone, c.contact_email,
                                  COUNT(DISTINCT p.id) AS projects_count,
                                  COUNT(DISTINCT u.id) AS users_count,
                                  COUNT(DISTINCT u.id) FILTER (WHERE COALESCE(u.active,TRUE)=TRUE) AS active_users_count
                           FROM companies c
                           LEFT JOIN projects p ON p.company_id=c.id
                           LEFT JOIN users u ON u.company_id=c.id AND NOT (COALESCE(u.role,'') = ANY(%s))
                           WHERE c.platform_account_id=%s AND c.id<>1
                           GROUP BY c.id
                           ORDER BY COALESCE(c.active,TRUE) DESC, c.name""",
                (list(PLATFORM_STAFF_ROLES), account_id))
            companies = [_company_row(row) for row in cur.fetchall()]

            cur.execute("""SELECT u.id, u.name, u.email, u.role, COALESCE(u.active,TRUE) AS active,
                                  u.company_id, u.platform_account_id AS user_platform_account_id,
                                  u.two_factor_required, u.two_factor_enabled, u.created_at,
                                  c.name AS company_name,
                                  COALESCE(u.platform_account_id,c.platform_account_id) AS platform_account_id
                           FROM users u
                           LEFT JOIN companies c ON c.id=u.company_id
                           WHERE COALESCE(u.platform_account_id,c.platform_account_id)=%s
                             AND NOT (COALESCE(u.role,'') = ANY(%s))
                           ORDER BY CASE WHEN u.role = ANY(%s) THEN 0 ELSE 1 END,
                                    COALESCE(u.active,TRUE) DESC,
                                    c.name NULLS LAST,
                                    u.name NULLS LAST,
                                    u.email""",
                (account_id, list(PLATFORM_STAFF_ROLES), list(CLIENT_ACCOUNT_ROLES)))
            users = [_user_row(row) for row in cur.fetchall()]

            cur.execute("""SELECT d.*, c.name AS company_name
                           FROM platform_billing_documents d
                           LEFT JOIN companies c ON c.id=d.company_id
                           WHERE COALESCE(d.platform_account_id,c.platform_account_id)=%s
                           ORDER BY d.issue_date DESC NULLS LAST, d.created_at DESC
                           LIMIT 50""", (account_id,))
            billing_documents = [_billing_document_row(row) for row in cur.fetchall()]

            cur.execute("""SELECT f.*, c.name AS company_name, d.number AS billing_document_number
                           FROM platform_followups f
                           LEFT JOIN companies c ON c.id=f.company_id
                           LEFT JOIN platform_billing_documents d ON d.id=f.billing_document_id
                           WHERE f.platform_account_id=%s
                             AND COALESCE(f.status,'open') NOT IN ('done','cancelled')
                           ORDER BY f.due_date NULLS LAST, f.created_at DESC
                           LIMIT 50""", (account_id,))
            followups = [_followup_row(row) for row in cur.fetchall()]

            cur.execute("""SELECT s.*, c.name AS company_name
                           FROM platform_support_sessions s
                           LEFT JOIN companies c ON c.id=s.company_id
                           WHERE s.platform_account_id=%s
                           ORDER BY CASE WHEN s.status='active' THEN 0 ELSE 1 END, s.created_at DESC
                           LIMIT 30""", (account_id,))
            support_sessions = [_support_session_row(row) for row in cur.fetchall()]

            usage = {
                "companies": len(companies),
                "activeCompanies": sum(1 for item in companies if item.get("active")),
                "projects": sum(int(item.get("projectsCount") or 0) for item in companies),
                "totalUsers": len(users),
                "activeUsers": sum(1 for item in users if item.get("active")),
                "billingDocuments": len(billing_documents),
                "openFollowups": len(followups),
                "activeSupportSessions": sum(1 for item in support_sessions if item.get("status") == "active"),
            }
            account_plan = account.get("plan") or "demo"
            return {
                "account": {
                    "id": account.get("id"),
                    "name": account.get("name") or "",
                    "ownerName": account.get("owner_name") or "",
                    "contactEmail": account.get("contact_email") or "",
                    "plan": account_plan,
                    "planLabel": tariff.get("name") or account_plan,
                    "status": account.get("status") or "",
                    "active": account.get("active") is not False,
                    "createdAt": _iso_date(account.get("created_at")),
                },
                "user": {
                    "id": current_user.get("id"),
                    "name": current_user.get("name") or "",
                    "email": current_user.get("email") or "",
                    "role": current_user.get("role") or "",
                    "roleLabel": CLIENT_ACCOUNT_ROLE_LABELS.get(current_user.get("role") or "", current_user.get("role") or ""),
                    "companyId": current_user.get("companyId") or current_user.get("company_id"),
                    "platformAccountId": account_id,
                },
                "tariff": _tariff_public(tariff),
                "usage": usage,
                "limitWarnings": _limit_warnings(tariff, usage),
                "companies": companies,
                "users": users,
                "billingDocuments": billing_documents,
                "followups": followups,
                "supportSessions": support_sessions,
            }
        finally:
            cur.close()
            conn.close()
