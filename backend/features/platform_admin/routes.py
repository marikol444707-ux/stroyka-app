import datetime as dt
import json
import os
import re
import textwrap
import urllib.parse
import uuid
from datetime import datetime, timedelta, date
from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException, Request


PLATFORM_VIEW_ROLES = ("system_owner", "platform_admin", "platform_support", "billing_admin")
PLATFORM_MANAGE_ROLES = ("system_owner", "platform_admin")
PLATFORM_BILLING_ROLES = ("system_owner", "platform_admin", "billing_admin")
PLATFORM_TEAM_ROLES = ("system_owner",)
PLATFORM_SUPPORT_ROLES = ("system_owner", "platform_admin", "platform_support")
PLATFORM_STAFF_ROLES = ("platform_admin", "platform_support", "billing_admin")

PLATFORM_ROLE_LABELS = {
    "system_owner": "Владелец платформы",
    "platform_admin": "Администратор платформы",
    "platform_support": "Поддержка платформы",
    "billing_admin": "Биллинг платформы",
}


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


def _platform_role_label(role: str) -> str:
    return PLATFORM_ROLE_LABELS.get(role or "", role or "")


def _support_scope_label(scope: str) -> str:
    labels = {
        "read_only": "Только просмотр",
        "access_help": "Помощь с доступом",
        "billing_help": "Биллинг",
        "technical_check": "Техническая проверка",
    }
    return labels.get(scope or "", scope or "Только просмотр")


def _billing_document_type_label(document_type: str) -> str:
    labels = {
        "invoice": "Счет",
        "act": "Акт",
        "offer": "Коммерческое предложение",
    }
    return labels.get(document_type or "", document_type or "Документ")


def _billing_document_status_label(status: str) -> str:
    labels = {
        "draft": "Черновик",
        "issued": "Выставлен",
        "payment_expected": "Ожидает оплату",
        "closed": "Закрыт",
        "cancelled": "Аннулирован",
    }
    return labels.get(status or "", status or "Черновик")


def _payment_provider_label(provider: str) -> str:
    labels = {
        "manual": "Безнал / вручную",
        "yukassa": "ЮKassa",
        "robokassa": "Robokassa",
    }
    return labels.get(provider or "", provider or "Безнал / вручную")


def _payment_provider_states() -> list:
    yukassa_shop = (os.getenv("YUKASSA_SHOP_ID") or os.getenv("YOOKASSA_SHOP_ID") or "").strip()
    yukassa_secret = (os.getenv("YUKASSA_SECRET_KEY") or os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
    robokassa_login = (os.getenv("ROBOKASSA_MERCHANT_LOGIN") or "").strip()
    robokassa_password = (os.getenv("ROBOKASSA_PASSWORD1") or "").strip()
    return [
        {
            "id": "manual",
            "label": _payment_provider_label("manual"),
            "configured": True,
            "mode": "manual",
            "message": "Ручной безнал: можно прикрепить счет/акт и потом зачислить факт оплаты отдельно.",
        },
        {
            "id": "yukassa",
            "label": _payment_provider_label("yukassa"),
            "configured": bool(yukassa_shop and yukassa_secret),
            "mode": "draft_only",
            "message": "Интеграционный слой подготовлен, внешний платеж не создается автоматически.",
        },
        {
            "id": "robokassa",
            "label": _payment_provider_label("robokassa"),
            "configured": bool(robokassa_login and robokassa_password),
            "mode": "draft_only",
            "message": "Интеграционный слой подготовлен, внешний платеж не создается автоматически.",
        },
    ]


def _operator_requisites() -> dict:
    return {
        "name": os.getenv("PLATFORM_OPERATOR_NAME", "Оператор платформы Stroyka ERP").strip() or "Оператор платформы Stroyka ERP",
        "inn": os.getenv("PLATFORM_OPERATOR_INN", "").strip(),
        "kpp": os.getenv("PLATFORM_OPERATOR_KPP", "").strip(),
        "ogrn": os.getenv("PLATFORM_OPERATOR_OGRN", "").strip(),
        "address": os.getenv("PLATFORM_OPERATOR_ADDRESS", "").strip(),
        "email": os.getenv("PLATFORM_OPERATOR_EMAIL", "").strip(),
        "phone": os.getenv("PLATFORM_OPERATOR_PHONE", "").strip(),
        "bankName": os.getenv("PLATFORM_OPERATOR_BANK_NAME", "").strip(),
        "bankBik": os.getenv("PLATFORM_OPERATOR_BANK_BIK", "").strip(),
        "bankAccount": os.getenv("PLATFORM_OPERATOR_BANK_ACCOUNT", "").strip(),
        "bankCorrAccount": os.getenv("PLATFORM_OPERATOR_BANK_CORR_ACCOUNT", "").strip(),
    }


def _payment_provider_by_id(provider: str) -> dict:
    provider_id = (provider or "manual").strip()
    return next((item for item in _payment_provider_states() if item["id"] == provider_id), None)


def _payment_event_success_status(provider: str, status: str) -> bool:
    normalized = str(status or "").strip().lower()
    if provider == "yukassa":
        return normalized in ("succeeded", "paid", "captured", "success")
    if provider == "robokassa":
        return normalized in ("ok", "paid", "success", "completed", "approved")
    return normalized in ("paid", "success", "completed")


def _money_matches(left, right) -> bool:
    try:
        return abs(float(left or 0) - float(right or 0)) <= 0.01
    except Exception:
        return False


def _safe_pdf_segment(value: str, fallback: str = "document") -> str:
    text = re.sub(r"[^A-Za-z0-9А-Яа-яёЁ._-]+", "-", str(value or "")).strip("-._")
    return (text[:70] or fallback)


def _format_money(value) -> str:
    try:
        return f"{float(value or 0):,.2f}".replace(",", " ").replace(".", ",") + " RUB"
    except Exception:
        return "0,00 RUB"


def _display_date(value) -> str:
    return str(value)[:10] if value else "-"


def _register_pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    regular_path = next((path for path in regular_candidates if os.path.exists(path)), None)
    bold_path = next((path for path in bold_candidates if os.path.exists(path)), None)
    if not regular_path:
        return "Helvetica", "Helvetica-Bold"
    if "StroykaSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("StroykaSans", regular_path))
    if bold_path and "StroykaSansBold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("StroykaSansBold", bold_path))
    return "StroykaSans", "StroykaSansBold" if bold_path else "StroykaSans"


def _draw_wrapped_pdf_line(canvas_obj, text: str, x: float, y: float, width_chars: int,
                           font_name: str, font_size: int = 10, leading: int = 14) -> float:
    canvas_obj.setFont(font_name, font_size)
    for line in textwrap.wrap(str(text or "-"), width=width_chars) or ["-"]:
        canvas_obj.drawString(x, y, line)
        y -= leading
    return y


def _generate_billing_document_pdf(document: dict, company: dict, current_user: dict) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Для генерации PDF установите reportlab: pip install -r requirements.txt") from exc

    regular_font, bold_font = _register_pdf_font()
    upload_root = os.getenv("UPLOAD_DIR", "uploads").strip() or "uploads"
    today_parts = dt.datetime.utcnow().strftime("%Y/%m/%d").split("/")
    rel_dir_parts = ["platform-billing", *today_parts]
    output_dir = os.path.join(upload_root, *rel_dir_parts)
    os.makedirs(output_dir, exist_ok=True)

    number = document.get("number") or f"DOC-{document.get('id')}"
    filename = _safe_pdf_segment(number, "billing-document") + "-" + str(uuid.uuid4())[:8] + ".pdf"
    output_path = os.path.join(output_dir, filename)
    file_url = "/uploads/" + urllib.parse.quote("/".join([*rel_dir_parts, filename]), safe="/")

    label = _billing_document_type_label(document.get("document_type"))
    title = f"{label} {number}"
    if document.get("document_type") == "invoice":
        title = f"Счет на оплату {number}"
    elif document.get("document_type") == "act":
        title = f"Акт оказанных услуг {number}"

    operator = _operator_requisites()
    c = canvas.Canvas(output_path, pagesize=A4)
    page_width, page_height = A4
    x = 48
    y = page_height - 54
    c.setFont(bold_font, 18)
    c.drawString(x, y, "Stroyka ERP")
    c.setFont(regular_font, 9)
    c.drawRightString(page_width - x, y + 3, "Платежный документ платформы")
    y -= 34
    c.setFont(bold_font, 16)
    c.drawString(x, y, title)
    y -= 26
    c.setFont(regular_font, 10)
    c.drawString(x, y, "Дата документа: " + _display_date(document.get("issue_date") or document.get("created_at")))
    c.drawString(310, y, "Оплатить до: " + _display_date(document.get("due_date")))
    y -= 22
    c.line(x, y, page_width - x, y)
    y -= 26

    c.setFont(bold_font, 11)
    c.drawString(x, y, "Получатель")
    y -= 16
    y = _draw_wrapped_pdf_line(c, operator["name"], x, y, 90, regular_font, 10)
    recipient_parts = []
    if operator["inn"]:
        recipient_parts.append("ИНН " + operator["inn"])
    if operator["kpp"]:
        recipient_parts.append("КПП " + operator["kpp"])
    if operator["ogrn"]:
        recipient_parts.append("ОГРН " + operator["ogrn"])
    if recipient_parts:
        y = _draw_wrapped_pdf_line(c, ", ".join(recipient_parts), x, y, 90, regular_font, 9, 12)
    if operator["address"]:
        y = _draw_wrapped_pdf_line(c, "Адрес: " + operator["address"], x, y, 90, regular_font, 9, 12)
    if operator["bankName"] or operator["bankBik"] or operator["bankAccount"]:
        bank_lines = [
            operator["bankName"],
            ("БИК " + operator["bankBik"]) if operator["bankBik"] else "",
            ("р/с " + operator["bankAccount"]) if operator["bankAccount"] else "",
            ("к/с " + operator["bankCorrAccount"]) if operator["bankCorrAccount"] else "",
        ]
        y = _draw_wrapped_pdf_line(c, "Банк: " + ", ".join([item for item in bank_lines if item]), x, y, 90, regular_font, 9, 12)
    contacts = []
    if operator["email"]:
        contacts.append(operator["email"])
    if operator["phone"]:
        contacts.append(operator["phone"])
    if contacts:
        y = _draw_wrapped_pdf_line(c, "Контакты: " + ", ".join(contacts), x, y, 90, regular_font, 9, 12)
    y -= 6
    c.setFont(bold_font, 11)
    c.drawString(x, y, "Плательщик")
    y -= 16
    payer = company.get("name") or document.get("company_name") or "-"
    inn = company.get("inn")
    kpp = company.get("kpp")
    if inn:
        payer += f", ИНН {inn}"
    if kpp:
        payer += f", КПП {kpp}"
    y = _draw_wrapped_pdf_line(c, payer, x, y, 90, regular_font, 10)
    if company.get("contact_email"):
        y = _draw_wrapped_pdf_line(c, "Email: " + company.get("contact_email"), x, y, 90, regular_font, 10)
    y -= 12

    c.setFont(bold_font, 11)
    c.drawString(x, y, "Основание")
    y -= 16
    period = f"{_display_date(document.get('period_start'))} - {_display_date(document.get('period_end'))}"
    description = "Доступ к Stroyka ERP и сопровождение аккаунта платформы"
    y = _draw_wrapped_pdf_line(c, description, x, y, 88, regular_font, 10)
    c.drawString(x, y, "Период: " + period)
    c.drawString(310, y, "Провайдер: " + _payment_provider_label(document.get("payment_provider")))
    y -= 26

    c.setFont(bold_font, 10)
    c.drawString(x, y, "Наименование")
    c.drawRightString(page_width - 190, y, "Кол-во")
    c.drawRightString(page_width - 110, y, "Цена")
    c.drawRightString(page_width - x, y, "Сумма")
    y -= 8
    c.line(x, y, page_width - x, y)
    y -= 18
    c.setFont(regular_font, 10)
    c.drawString(x, y, "Подписка / услуги платформы")
    c.drawRightString(page_width - 190, y, "1")
    c.drawRightString(page_width - 110, y, _format_money(document.get("amount")))
    c.drawRightString(page_width - x, y, _format_money(document.get("amount")))
    y -= 18
    c.line(x, y, page_width - x, y)
    y -= 24
    c.setFont(bold_font, 13)
    c.drawRightString(page_width - x, y, "Итого: " + _format_money(document.get("amount")))
    y -= 34

    c.setFont(regular_font, 9)
    y = _draw_wrapped_pdf_line(
        c,
        "Важно: этот документ является основанием для оплаты и не подтверждает поступление денег. "
        "Факт оплаты фиксируется в кабинете платформы отдельным платежом после проверки поступления.",
        x,
        y,
        110,
        regular_font,
        9,
        13,
    )
    if document.get("notes"):
        y -= 8
        y = _draw_wrapped_pdf_line(c, "Комментарий: " + str(document.get("notes")), x, y, 110, regular_font, 9, 13)
    y -= 26
    c.setFont(regular_font, 9)
    c.drawString(x, y, "Сформировал: " + (current_user.get("name") or current_user.get("email") or "-"))
    c.drawRightString(page_width - x, y, "Статус: " + _billing_document_status_label(document.get("status")))
    c.showPage()
    c.save()
    return file_url


def _extract_payment_event(provider: str, payload: dict) -> dict:
    provider_key = (provider or "").strip().lower()
    if provider_key == "yookassa":
        provider_key = "yukassa"
    obj = payload.get("object") if isinstance(payload.get("object"), dict) else {}
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    amount_data = obj.get("amount") if isinstance(obj.get("amount"), dict) else {}
    raw_document_id = (
        metadata.get("documentId") or metadata.get("document_id") or metadata.get("billingDocumentId")
        or payload.get("documentId") or payload.get("document_id") or payload.get("billingDocumentId")
        or payload.get("Shp_documentId") or payload.get("shp_document_id")
    )
    try:
        document_id = int(raw_document_id) if raw_document_id not in (None, "") else None
    except Exception:
        document_id = None
    raw_amount = (
        amount_data.get("value") or payload.get("OutSum") or payload.get("outSum")
        or payload.get("amount") or payload.get("Amount")
    )
    try:
        amount = float(str(raw_amount).replace(",", ".")) if raw_amount not in (None, "") else None
    except Exception:
        amount = None
    return {
        "provider": provider_key,
        "eventId": payload.get("id") or obj.get("id") or payload.get("InvId") or payload.get("invoiceId"),
        "eventType": payload.get("event") or payload.get("type") or payload.get("action") or "payment_event",
        "providerStatus": obj.get("status") or payload.get("Status") or payload.get("status") or payload.get("Result"),
        "documentId": document_id,
        "amount": amount,
        "currency": amount_data.get("currency") or payload.get("currency") or "RUB",
    }


async def _payment_webhook_payload(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {"raw": data}
        except Exception:
            return {}
    try:
        form = await request.form()
        return {key: form.get(key) for key in form.keys()}
    except Exception:
        raw = (await request.body()).decode("utf-8", "ignore")
        return {"raw": raw}


def register_platform_admin_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]

    @app.get("/system/tariffs")
    def system_tariffs_list(_current_user: dict = Depends(require_roles(*PLATFORM_VIEW_ROLES))):
        return SYSTEM_TARIFFS

    @app.get("/system/companies")
    def system_companies_list(_current_user: dict = Depends(require_roles(*PLATFORM_VIEW_ROLES))):
        """Полный список компаний с биллингом - только для системных ролей платформы."""
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
    def system_create_company(data: dict, current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
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
    def system_update_company(id: int, data: dict, current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
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
    def system_dashboard(_current_user: dict = Depends(require_roles(*PLATFORM_VIEW_ROLES))):
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
    def system_payments_list(_current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT p.*, c.name as company_name FROM company_payments p
                       LEFT JOIN companies c ON c.id=p.company_id
                       ORDER BY p.payment_date DESC LIMIT 200""")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @app.get("/system/payment-providers")
    def system_payment_providers(_current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        return _payment_provider_states()

    @app.get("/system/payment-events")
    def system_payment_events(_current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT e.*, d.number AS billing_document_number, c.name AS company_name,
                              pa.name AS platform_account_name
                       FROM platform_payment_events e
                       LEFT JOIN platform_billing_documents d ON d.id=e.billing_document_id
                       LEFT JOIN companies c ON c.id=e.company_id
                       LEFT JOIN platform_accounts pa ON pa.id=e.platform_account_id
                       ORDER BY e.received_at DESC
                       LIMIT 100""")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows

    @app.post("/system/payment-webhooks/{provider}")
    async def system_payment_webhook(provider: str, request: Request):
        provider_key = (provider or "").strip().lower()
        if provider_key == "yookassa":
            provider_key = "yukassa"
        if provider_key not in ("yukassa", "robokassa"):
            raise HTTPException(status_code=404, detail="Провайдер не поддерживается")
        webhook_token = os.getenv("PLATFORM_PAYMENT_WEBHOOK_TOKEN", "").strip()
        if not webhook_token:
            raise HTTPException(status_code=503, detail="Webhook платежей не включен: задайте PLATFORM_PAYMENT_WEBHOOK_TOKEN")
        supplied_token = request.headers.get("x-stroyka-webhook-token") or request.query_params.get("token")
        if supplied_token != webhook_token:
            raise HTTPException(status_code=401, detail="Недействительный webhook token")
        payload = await _payment_webhook_payload(request)
        event = _extract_payment_event(provider_key, payload)
        if event["provider"] not in ("yukassa", "robokassa"):
            raise HTTPException(status_code=400, detail="Недопустимый провайдер")

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        document = None
        if event.get("documentId"):
            cur.execute("""SELECT d.id, d.number, d.platform_account_id, d.company_id, d.amount, d.currency,
                                  c.name AS company_name
                           FROM platform_billing_documents d
                           LEFT JOIN companies c ON c.id=d.company_id
                           WHERE d.id=%s""", (event["documentId"],))
            document = cur.fetchone()
        platform_account_id = document.get("platform_account_id") if document else None
        company_id = document.get("company_id") if document else None
        cur.execute("""INSERT INTO platform_payment_events
                          (provider, event_id, event_type, provider_status, platform_account_id, company_id,
                           billing_document_id, amount, currency, trusted, action_status, payload_json, notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                    (event["provider"], event.get("eventId"), event.get("eventType"), event.get("providerStatus"),
                     platform_account_id, company_id, event.get("documentId"), event.get("amount"), event.get("currency") or "RUB",
                     True, "received", json.dumps(payload, ensure_ascii=False, default=str),
                     "Событие принято. Фактическая оплата не создана автоматически."))
        event_id = cur.fetchone()["id"]
        _system_write_audit(cur, {"name": "payment-webhook", "role": "system"}, "platform_payment_webhook_received",
            "platform_payment_event", event_id, event.get("eventId") or str(event_id),
            platform_account_id=platform_account_id, company_id=company_id,
            details={
                "provider": event["provider"],
                "eventType": event.get("eventType"),
                "providerStatus": event.get("providerStatus"),
                "billingDocumentId": event.get("documentId"),
                "billingDocumentNumber": document.get("number") if document else None,
                "amount": event.get("amount"),
                "actionStatus": "received",
                "autoPaymentCreated": False,
            })
        conn.close()
        return {
            "ok": True,
            "eventId": event_id,
            "documentFound": bool(document),
            "actionStatus": "received",
            "autoPaymentCreated": False,
            "message": "Событие провайдера принято в журнал. Факт оплаты не зачислен автоматически.",
        }

    @app.post("/system/payments")
    def system_create_payment(data: dict, current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
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

    @app.post("/system/payment-events/{id}/confirm")
    def system_confirm_payment_event(id: int, data: dict = None, current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        data = data or {}
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""SELECT e.*, d.number AS billing_document_number, d.status AS billing_document_status,
                                  d.amount AS billing_document_amount, d.currency AS billing_document_currency,
                                  d.payment_provider AS billing_payment_provider,
                                  d.period_start AS billing_period_start, d.period_end AS billing_period_end,
                                  d.platform_account_id AS document_platform_account_id,
                                  d.company_id AS document_company_id,
                                  c.name AS company_name
                           FROM platform_payment_events e
                           LEFT JOIN platform_billing_documents d ON d.id=e.billing_document_id
                           LEFT JOIN companies c ON c.id=COALESCE(e.company_id,d.company_id)
                           WHERE e.id=%s
                           FOR UPDATE OF e""", (id,))
            event = cur.fetchone()
            if not event:
                raise HTTPException(status_code=404, detail="Событие платежного провайдера не найдено")
            if event.get("payment_id") or event.get("action_status") == "payment_recorded":
                raise HTTPException(status_code=409, detail="По этому событию платеж уже зачислен")
            if not event.get("trusted"):
                raise HTTPException(status_code=400, detail="Событие не доверенное")
            if not event.get("billing_document_id"):
                raise HTTPException(status_code=400, detail="Событие не связано с платежным документом")
            if not event.get("billing_document_number"):
                raise HTTPException(status_code=404, detail="Платежный документ не найден")
            if event.get("billing_document_status") in ("closed", "cancelled"):
                raise HTTPException(status_code=400, detail="Платежный документ уже закрыт или аннулирован")
            provider = (event.get("provider") or "").strip().lower()
            document_provider = (event.get("billing_payment_provider") or "").strip().lower()
            if document_provider and document_provider != provider:
                raise HTTPException(status_code=400, detail="Провайдер события не совпадает с платежным документом")
            if not _payment_event_success_status(provider, event.get("provider_status")):
                raise HTTPException(status_code=400, detail="Статус провайдера не подтверждает успешную оплату")
            if not _money_matches(event.get("amount"), event.get("billing_document_amount")):
                raise HTTPException(status_code=400, detail="Сумма события не совпадает с платежным документом")
            event_currency = (event.get("currency") or "RUB").strip().upper()
            document_currency = (event.get("billing_document_currency") or "RUB").strip().upper()
            if event_currency != document_currency:
                raise HTTPException(status_code=400, detail="Валюта события не совпадает с платежным документом")

            company_id = event.get("company_id") or event.get("document_company_id")
            platform_account_id = event.get("platform_account_id") or event.get("document_platform_account_id")
            if not company_id:
                raise HTTPException(status_code=400, detail="Не найдена компания для зачисления платежа")
            period_start = data.get("periodStart") or data.get("period_start") or event.get("billing_period_start")
            period_end = data.get("periodEnd") or data.get("period_end") or event.get("billing_period_end")
            payment_date = data.get("paymentDate") or data.get("payment_date") or dt.date.today().isoformat()
            notes = (data.get("notes") or "").strip()
            base_note = "Зачислено вручную по событию провайдера #" + str(id)
            if notes:
                base_note += ". " + notes
            cur.execute("""INSERT INTO company_payments (company_id, amount, payment_date, method,
                                                          invoice_number, status, period_start, period_end,
                                                          notes, created_by)
                           VALUES (%s,%s,%s,%s,%s,'paid',%s,%s,%s,%s)
                           RETURNING id""",
                        (company_id, float(event.get("amount") or 0), payment_date, provider or "provider",
                         event.get("billing_document_number"), period_start or None, period_end or None,
                         base_note, current_user.get("name") or current_user.get("email")))
            payment_id = cur.fetchone()["id"]
            if period_end:
                cur.execute("""UPDATE companies
                               SET plan_expires_at=%s, payment_status='active',
                                   suspended_at=NULL, suspended_reason=NULL, active=TRUE
                               WHERE id=%s""", (period_end, company_id))
            cur.execute("""UPDATE platform_billing_documents
                           SET status='closed', updated_at=NOW()
                           WHERE id=%s
                           RETURNING *""", (event.get("billing_document_id"),))
            document = dict(cur.fetchone())
            processed_by = current_user.get("name") or current_user.get("email") or ""
            cur.execute("""UPDATE platform_payment_events
                           SET action_status='payment_recorded',
                               payment_id=%s,
                               processed_by=%s,
                               processed_at=NOW(),
                               notes=LEFT(COALESCE(notes,'') || %s, 4000)
                           WHERE id=%s
                           RETURNING *""",
                        (payment_id, processed_by, "\nОплата зачислена вручную: платеж #" + str(payment_id), id))
            updated_event = dict(cur.fetchone())
            _system_write_audit(cur, current_user, "platform_payment_event_confirmed", "platform_payment_event", id,
                event.get("event_id") or str(id), platform_account_id=platform_account_id, company_id=company_id,
                details={
                    "provider": provider,
                    "eventStatus": event.get("provider_status"),
                    "billingDocumentId": event.get("billing_document_id"),
                    "billingDocumentNumber": event.get("billing_document_number"),
                    "paymentId": payment_id,
                    "amount": float(event.get("amount") or 0),
                    "currency": event_currency,
                    "companyName": event.get("company_name"),
                    "documentClosed": True,
                })
            conn.commit()
            document["documentTypeLabel"] = _billing_document_type_label(document.get("document_type"))
            document["statusLabel"] = _billing_document_status_label(document.get("status"))
            return {"ok": True, "paymentId": payment_id, "event": updated_event, "document": document}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        finally:
            cur.close()
            conn.close()

    @app.get("/system/billing-documents")
    def system_billing_documents_list(_current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT d.*, c.name AS company_name, pa.name AS platform_account_name
                       FROM platform_billing_documents d
                       LEFT JOIN companies c ON c.id=d.company_id
                       LEFT JOIN platform_accounts pa ON pa.id=d.platform_account_id
                       ORDER BY d.created_at DESC
                       LIMIT 200""")
        rows = []
        for row in cur.fetchall():
            item = dict(row)
            item["documentTypeLabel"] = _billing_document_type_label(item.get("document_type"))
            item["statusLabel"] = _billing_document_status_label(item.get("status"))
            rows.append(item)
        conn.close()
        return rows

    @app.post("/system/billing-documents")
    def system_create_billing_document(data: dict, current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        company_id = data.get("companyId") or data.get("company_id")
        if not company_id:
            raise HTTPException(status_code=400, detail="Укажите компанию")
        document_type = (data.get("documentType") or data.get("document_type") or "invoice").strip()
        if document_type not in ("invoice", "act", "offer"):
            raise HTTPException(status_code=400, detail="Недопустимый тип документа")
        status = (data.get("status") or "draft").strip()
        if status not in ("draft", "issued", "payment_expected", "closed", "cancelled"):
            raise HTTPException(status_code=400, detail="Недопустимый статус документа")
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, platform_account_id FROM companies WHERE id=%s", (company_id,))
        company = cur.fetchone()
        if not company:
            conn.close()
            raise HTTPException(status_code=404, detail="Компания не найдена")
        cur.execute("""INSERT INTO platform_billing_documents
                          (platform_account_id, company_id, document_type, number, status, amount,
                           currency, issue_date, due_date, period_start, period_end,
                           payment_provider, payment_url, file_url, notes, created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING *""",
                    (company.get("platform_account_id"), company_id, document_type,
                     (data.get("number") or "").strip() or None, status, amount,
                     data.get("currency") or "RUB", data.get("issueDate") or data.get("issue_date") or None,
                     data.get("dueDate") or data.get("due_date") or None,
                     data.get("periodStart") or data.get("period_start") or None,
                     data.get("periodEnd") or data.get("period_end") or None,
                     data.get("paymentProvider") or data.get("payment_provider") or "manual",
                     data.get("paymentUrl") or data.get("payment_url"),
                     data.get("fileUrl") or data.get("file_url"),
                     data.get("notes"),
                     current_user.get("name") or current_user.get("email")))
        document = dict(cur.fetchone())
        if not document.get("number"):
            prefix = {"invoice": "INV", "act": "ACT", "offer": "OFFER"}.get(document_type, "DOC")
            number = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{int(document['id']):05d}"
            cur.execute("UPDATE platform_billing_documents SET number=%s WHERE id=%s RETURNING *", (number, document["id"]))
            document = dict(cur.fetchone())
        _system_write_audit(cur, current_user, "platform_billing_document_created", "platform_billing_document", document.get("id"),
            document.get("number"), platform_account_id=company.get("platform_account_id"), company_id=company_id,
            details={
                "documentType": document_type,
                "documentTypeLabel": _billing_document_type_label(document_type),
                "status": status,
                "statusLabel": _billing_document_status_label(status),
                "amount": amount,
                "companyName": company.get("name"),
                "paymentProvider": document.get("payment_provider"),
            })
        conn.close()
        document["documentTypeLabel"] = _billing_document_type_label(document.get("document_type"))
        document["statusLabel"] = _billing_document_status_label(document.get("status"))
        return {"ok": True, "document": document}

    @app.put("/system/billing-documents/{id}")
    def system_update_billing_document(id: int, data: dict, current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        status = (data.get("status") or "").strip()
        if status not in ("draft", "issued", "payment_expected", "closed", "cancelled"):
            raise HTTPException(status_code=400, detail="Недопустимый статус документа")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT d.*, c.name AS company_name
                       FROM platform_billing_documents d
                       LEFT JOIN companies c ON c.id=d.company_id
                       WHERE d.id=%s""", (id,))
        before = cur.fetchone()
        if not before:
            conn.close()
            raise HTTPException(status_code=404, detail="Документ не найден")
        cur.execute("""UPDATE platform_billing_documents
                       SET status=%s,
                           payment_url=COALESCE(%s, payment_url),
                           file_url=COALESCE(%s, file_url),
                           notes=COALESCE(%s, notes),
                           updated_at=NOW()
                       WHERE id=%s
                       RETURNING *""",
                    (status, data.get("paymentUrl") or data.get("payment_url"),
                     data.get("fileUrl") or data.get("file_url"), data.get("notes"), id))
        document = dict(cur.fetchone())
        _system_write_audit(cur, current_user, "platform_billing_document_updated", "platform_billing_document", id,
            document.get("number"), platform_account_id=document.get("platform_account_id"), company_id=document.get("company_id"),
            details={
                "beforeStatus": before.get("status"),
                "afterStatus": status,
                "afterStatusLabel": _billing_document_status_label(status),
                "amount": float(document.get("amount") or 0),
                "companyName": before.get("company_name"),
            })
        conn.close()
        document["documentTypeLabel"] = _billing_document_type_label(document.get("document_type"))
        document["statusLabel"] = _billing_document_status_label(document.get("status"))
        return {"ok": True, "document": document}

    @app.post("/system/billing-documents/{id}/generate-pdf")
    def system_generate_billing_document_pdf(id: int, current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT d.*, c.name AS company_name, c.inn, c.kpp, c.contact_email,
                              c.platform_account_id AS company_platform_account_id,
                              pa.name AS platform_account_name
                       FROM platform_billing_documents d
                       LEFT JOIN companies c ON c.id=d.company_id
                       LEFT JOIN platform_accounts pa ON pa.id=d.platform_account_id
                       WHERE d.id=%s""", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Документ не найден")
        document = dict(row)
        company = {
            "name": document.get("company_name"),
            "inn": document.get("inn"),
            "kpp": document.get("kpp"),
            "contact_email": document.get("contact_email"),
        }
        file_url = _generate_billing_document_pdf(document, company, current_user)
        cur.execute("""UPDATE platform_billing_documents
                       SET file_url=%s, updated_at=NOW()
                       WHERE id=%s
                       RETURNING *""", (file_url, id))
        updated = dict(cur.fetchone())
        _system_write_audit(cur, current_user, "platform_billing_document_pdf_generated", "platform_billing_document", id,
            updated.get("number"), platform_account_id=updated.get("platform_account_id"), company_id=updated.get("company_id"),
            details={
                "fileUrl": file_url,
                "documentType": updated.get("document_type"),
                "amount": float(updated.get("amount") or 0),
                "companyName": document.get("company_name"),
            })
        conn.close()
        updated["documentTypeLabel"] = _billing_document_type_label(updated.get("document_type"))
        updated["statusLabel"] = _billing_document_status_label(updated.get("status"))
        return {"ok": True, "fileUrl": file_url, "document": updated}

    @app.post("/system/billing-documents/{id}/prepare-payment")
    def system_prepare_billing_payment(id: int, data: dict, current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        provider = (data.get("provider") or data.get("paymentProvider") or data.get("payment_provider") or "manual").strip()
        provider_state = _payment_provider_by_id(provider)
        if not provider_state:
            raise HTTPException(status_code=400, detail="Недопустимый платежный провайдер")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT d.*, c.name AS company_name
                       FROM platform_billing_documents d
                       LEFT JOIN companies c ON c.id=d.company_id
                       WHERE d.id=%s""", (id,))
        before = cur.fetchone()
        if not before:
            conn.close()
            raise HTTPException(status_code=404, detail="Документ не найден")
        payment_url = data.get("paymentUrl") or data.get("payment_url") or before.get("payment_url")
        cur.execute("""UPDATE platform_billing_documents
                       SET payment_provider=%s,
                           payment_url=COALESCE(%s, payment_url),
                           status=CASE WHEN status IN ('draft','issued') THEN 'payment_expected' ELSE status END,
                           updated_at=NOW()
                       WHERE id=%s
                       RETURNING *""", (provider, payment_url, id))
        document = dict(cur.fetchone())
        draft_payload = {
            "provider": provider,
            "documentId": id,
            "number": document.get("number"),
            "amount": float(document.get("amount") or 0),
            "currency": document.get("currency") or "RUB",
            "description": f"Stroyka ERP {document.get('number') or id}",
            "returnUrl": data.get("returnUrl") or None,
        }
        _system_write_audit(cur, current_user, "platform_payment_provider_prepared", "platform_billing_document", id,
            document.get("number"), platform_account_id=document.get("platform_account_id"), company_id=document.get("company_id"),
            details={
                "provider": provider,
                "providerLabel": provider_state.get("label"),
                "providerConfigured": provider_state.get("configured"),
                "integrationMode": provider_state.get("mode"),
                "paymentLinkCreated": False,
                "companyName": before.get("company_name"),
            })
        conn.close()
        document["documentTypeLabel"] = _billing_document_type_label(document.get("document_type"))
        document["statusLabel"] = _billing_document_status_label(document.get("status"))
        return {
            "ok": True,
            "document": document,
            "provider": provider_state,
            "draftPayload": draft_payload,
            "paymentLinkCreated": False,
            "message": "Провайдер подготовлен. Внешний платеж не создавался, факт оплаты нужно зачислять отдельно.",
        }

    @app.get("/system/platform-users")
    def system_platform_users(_current_user: dict = Depends(require_roles(*PLATFORM_TEAM_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT id, name, email, role, active, company_id,
                              two_factor_required, two_factor_enabled, created_at
                       FROM users
                       WHERE role = ANY(%s)
                       ORDER BY role, name, email""", (list(PLATFORM_STAFF_ROLES) + ["system_owner"],))
        rows = []
        for row in cur.fetchall():
            item = dict(row)
            item["roleLabel"] = _platform_role_label(item.get("role"))
            rows.append(item)
        conn.close()
        return rows

    @app.post("/system/platform-users/invite")
    def system_invite_platform_user(data: dict, current_user: dict = Depends(require_roles(*PLATFORM_TEAM_ROLES))):
        role = (data.get("role") or "").strip()
        if role not in PLATFORM_STAFF_ROLES:
            raise HTTPException(status_code=400, detail="Недопустимая роль платформы")
        name = (data.get("name") or _platform_role_label(role)).strip()
        email = (data.get("email") or "").strip().lower()
        expires_days = max(1, min(int(data.get("expiresInDays") or 7), 30))
        expires = datetime.now() + timedelta(days=expires_days)
        code = str(uuid.uuid4())[:8].upper()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""INSERT INTO invite_codes
                          (code, role, preset_name, preset_category, created_by, expires_at)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       RETURNING *""",
                    (code, role, name, None, current_user.get("name") or current_user.get("email") or "system_owner", expires))
        row = dict(cur.fetchone())
        _system_write_audit(cur, current_user, "platform_user_invited", "platform_user_invite", row.get("id"),
            name, details={"role": role, "roleLabel": _platform_role_label(role), "email": email, "expiresAt": expires})
        conn.close()
        row["roleLabel"] = _platform_role_label(role)
        return row

    @app.put("/system/platform-users/{id}")
    def system_update_platform_user(id: int, data: dict, current_user: dict = Depends(require_roles(*PLATFORM_TEAM_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, email, role, active FROM users WHERE id=%s", (id,))
        before = cur.fetchone()
        if not before:
            conn.close()
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if before.get("role") == "system_owner":
            conn.close()
            raise HTTPException(status_code=400, detail="Владельца платформы нельзя менять этим действием")
        sets, vals = [], []
        if "active" in data:
            sets.append("active=%s")
            vals.append(bool(data.get("active")))
        if "role" in data:
            role = (data.get("role") or "").strip()
            if role not in PLATFORM_STAFF_ROLES:
                conn.close()
                raise HTTPException(status_code=400, detail="Недопустимая роль платформы")
            sets.append("role=%s")
            vals.append(role)
        if not sets:
            conn.close()
            return {"ok": False, "error": "no fields"}
        vals.append(id)
        cur.execute("UPDATE users SET " + ", ".join(sets) + " WHERE id=%s RETURNING id, name, email, role, active", vals)
        after = dict(cur.fetchone())
        _system_write_audit(cur, current_user, "platform_user_updated", "platform_user", id,
            after.get("name") or after.get("email"), details={"before": dict(before), "after": after})
        conn.close()
        after["roleLabel"] = _platform_role_label(after.get("role"))
        return {"ok": True, "user": after}

    @app.get("/system/support-sessions")
    def system_support_sessions(_current_user: dict = Depends(require_roles(*PLATFORM_SUPPORT_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT s.*, pa.name AS platform_account_name, c.name AS company_name
                       FROM platform_support_sessions s
                       LEFT JOIN platform_accounts pa ON pa.id=s.platform_account_id
                       LEFT JOIN companies c ON c.id=s.company_id
                       ORDER BY CASE WHEN s.status='active' THEN 0 ELSE 1 END, s.created_at DESC
                       LIMIT 200""")
        rows = []
        now = datetime.now()
        for row in cur.fetchall():
            item = dict(row)
            if item.get("status") == "active" and item.get("expires_at") and item["expires_at"] < now:
                item["status"] = "expired"
            item["scopeLabel"] = _support_scope_label(item.get("scope"))
            rows.append(item)
        conn.close()
        return rows

    @app.post("/system/support-sessions")
    def system_open_support_session(data: dict, current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
        reason = (data.get("reason") or "").strip()
        if len(reason) < 5:
            raise HTTPException(status_code=400, detail="Укажите причину режима поддержки")
        company_id = data.get("companyId") or data.get("company_id")
        platform_account_id = data.get("platformAccountId") or data.get("platform_account_id")
        scope = (data.get("scope") or "read_only").strip()
        hours = max(1, min(int(data.get("expiresInHours") or 24), 168))
        expires = datetime.now() + timedelta(hours=hours)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if company_id and not platform_account_id:
            cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
            company = cur.fetchone()
            platform_account_id = company.get("platform_account_id") if company else None
        cur.execute("""INSERT INTO platform_support_sessions
                          (platform_account_id, company_id, reason, scope, status, expires_at,
                           opened_by_user_id, opened_by_name)
                       VALUES (%s,%s,%s,%s,'active',%s,%s,%s)
                       RETURNING *""",
                    (platform_account_id, company_id, reason, scope, expires,
                     current_user.get("id"), current_user.get("name") or current_user.get("email")))
        session = dict(cur.fetchone())
        _system_write_audit(cur, current_user, "support_session_opened", "support_session", session.get("id"),
            reason[:120], platform_account_id=platform_account_id, company_id=company_id,
            details={"scope": scope, "scopeLabel": _support_scope_label(scope), "expiresAt": expires, "reason": reason})
        conn.close()
        session["scopeLabel"] = _support_scope_label(scope)
        return {"ok": True, "session": session}

    @app.put("/system/support-sessions/{id}")
    def system_update_support_session(id: int, data: dict, current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
        action = (data.get("action") or "close").strip()
        if action != "close":
            raise HTTPException(status_code=400, detail="Поддерживается только закрытие режима поддержки")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""UPDATE platform_support_sessions
                       SET status='closed',
                           closed_by_user_id=%s,
                           closed_by_name=%s,
                           closed_at=NOW()
                       WHERE id=%s
                       RETURNING *""",
                    (current_user.get("id"), current_user.get("name") or current_user.get("email"), id))
        session = cur.fetchone()
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail="Сессия поддержки не найдена")
        _system_write_audit(cur, current_user, "support_session_closed", "support_session", id,
            (session.get("reason") or "")[:120], platform_account_id=session.get("platform_account_id"),
            company_id=session.get("company_id"), details={"scope": session.get("scope")})
        conn.close()
        return {"ok": True}

    @app.get("/system/audit-log")
    def system_audit_log(limit: int = 120, companyId: Optional[int] = None,
                         platformAccountId: Optional[int] = None, action: Optional[str] = None,
                         search: Optional[str] = None,
                         _current_user: dict = Depends(require_roles(*PLATFORM_VIEW_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        safe_limit = max(1, min(int(limit or 120), 300))
        where, vals = [], []
        if platformAccountId:
            where.append("platform_account_id=%s")
            vals.append(platformAccountId)
        if companyId:
            where.append("company_id=%s")
            vals.append(companyId)
        if action:
            where.append("action=%s")
            vals.append(action)
        if search and search.strip():
            pattern = "%" + search.strip() + "%"
            where.append("""(actor_name ILIKE %s OR action ILIKE %s OR entity_type ILIKE %s
                             OR entity_name ILIKE %s OR details_json ILIKE %s)""")
            vals.extend([pattern, pattern, pattern, pattern, pattern])
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
