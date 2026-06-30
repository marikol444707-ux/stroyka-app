import base64
import csv
import datetime as dt
import io
import json
import mimetypes
import os
import re
import textwrap
import urllib.parse
import uuid
import zipfile
from datetime import datetime, timedelta, date
from typing import Optional
import xml.etree.ElementTree as ET

import psycopg2.extras
from fastapi import Depends, File, Form, HTTPException, Request, Response, UploadFile


PLATFORM_VIEW_ROLES = ("system_owner", "platform_admin", "platform_support", "billing_admin")
PLATFORM_MANAGE_ROLES = ("system_owner", "platform_admin")
PLATFORM_BILLING_ROLES = ("system_owner", "platform_admin", "billing_admin")
PLATFORM_TEAM_ROLES = ("system_owner",)
PLATFORM_SUPPORT_ROLES = ("system_owner", "platform_admin", "platform_support")
PLATFORM_STAFF_ROLES = ("platform_admin", "platform_support", "billing_admin")
CLIENT_USER_EXCLUDED_ROLES = ("system_owner", "platform_admin", "platform_support", "billing_admin")

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


def _payment_event_action_label(status: str) -> str:
    labels = {
        "received": "Получено",
        "needs_review": "Нужна проверка",
        "payment_recorded": "Платеж зачислен",
    }
    return labels.get(status or "", status or "Получено")


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


def _generate_billing_document_pdf(document: dict, company: dict, current_user: dict, save_upload_bytes=None) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Для генерации PDF установите reportlab: pip install -r requirements.txt") from exc

    regular_font, bold_font = _register_pdf_font()
    today_parts = dt.datetime.utcnow().strftime("%Y/%m/%d").split("/")
    rel_dir_parts = ["platform-billing", *today_parts]

    number = document.get("number") or f"DOC-{document.get('id')}"
    filename = _safe_pdf_segment(number, "billing-document") + "-" + str(uuid.uuid4())[:8] + ".pdf"

    label = _billing_document_type_label(document.get("document_type"))
    title = f"{label} {number}"
    if document.get("document_type") == "invoice":
        title = f"Счет на оплату {number}"
    elif document.get("document_type") == "act":
        title = f"Акт оказанных услуг {number}"

    operator = _operator_requisites()
    output_buffer = io.BytesIO()
    c = canvas.Canvas(output_buffer, pagesize=A4)
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

    pdf_content = output_buffer.getvalue()
    if save_upload_bytes:
        saved = save_upload_bytes(
            pdf_content,
            filename,
            project_name="_platform",
            context="billing-documents",
            content_type="application/pdf",
        )
        return saved.get("url") or ""

    upload_root = os.getenv("UPLOAD_DIR", "uploads").strip() or "uploads"
    output_dir = os.path.join(upload_root, *rel_dir_parts)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "wb") as output_file:
        output_file.write(pdf_content)
    file_url = "/uploads/" + urllib.parse.quote("/".join([*rel_dir_parts, filename]), safe="/")
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


def _system_payment_event_filter_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def _system_payment_event_enrich(row: dict) -> dict:
    item = dict(row or {})
    provider = (item.get("provider") or "").strip().lower()
    provider_status = item.get("provider_status")
    document_id = item.get("billing_document_id")
    document_status = item.get("billing_document_status")
    document_provider = (item.get("billing_payment_provider") or "").strip().lower()
    event_currency = (item.get("currency") or "RUB").strip().upper()
    document_currency = (item.get("billing_document_currency") or "RUB").strip().upper()
    success_status = _payment_event_success_status(provider, provider_status)
    amount_matches = _money_matches(item.get("amount"), item.get("billing_document_amount"))
    provider_matches = not document_provider or document_provider == provider
    currency_matches = event_currency == document_currency
    can_confirm = bool(
        item.get("trusted")
        and document_id
        and item.get("billing_document_number")
        and document_status not in ("closed", "cancelled")
        and provider_matches
        and success_status
        and amount_matches
        and currency_matches
        and item.get("action_status") != "payment_recorded"
        and not item.get("payment_id")
    )
    reasons = []
    if not item.get("trusted"):
        reasons.append("событие не доверенное")
    if not document_id:
        reasons.append("нет связи с платежным документом")
    elif not item.get("billing_document_number"):
        reasons.append("платежный документ не найден")
    if document_status in ("closed", "cancelled"):
        reasons.append("документ уже закрыт или аннулирован")
    if document_provider and not provider_matches:
        reasons.append("провайдер не совпадает с документом")
    if provider_status and not success_status:
        reasons.append("статус провайдера не подтверждает оплату")
    if document_id and item.get("billing_document_amount") is not None and not amount_matches:
        reasons.append("сумма не совпадает с документом")
    if document_id and not currency_matches:
        reasons.append("валюта не совпадает с документом")
    if item.get("action_status") == "payment_recorded" or item.get("payment_id"):
        reasons.append("платеж уже зачислен")
    item["providerLabel"] = _payment_provider_label(provider)
    item["actionStatusLabel"] = _payment_event_action_label(item.get("action_status"))
    item["successStatus"] = success_status
    item["amountMatches"] = amount_matches
    item["providerMatches"] = provider_matches
    item["currencyMatches"] = currency_matches
    item["canConfirm"] = can_confirm
    item["reviewReason"] = "; ".join(reasons) if reasons else ("готово к ручному зачислению" if can_confirm else "принято в журнал")
    return item


def _system_payment_events_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Дата события",
        "Провайдер",
        "ID события",
        "Тип",
        "Статус провайдера",
        "Статус обработки",
        "Причина проверки",
        "Аккаунт",
        "Компания",
        "Документ",
        "Сумма события",
        "Сумма документа",
        "Валюта",
        "Платеж",
        "Обработал",
    ])
    for row in rows:
        writer.writerow([
            str(row.get("received_at") or "")[:19],
            row.get("providerLabel") or row.get("provider") or "",
            row.get("event_id") or "",
            row.get("event_type") or "",
            row.get("provider_status") or "",
            row.get("actionStatusLabel") or row.get("action_status") or "",
            row.get("reviewReason") or "",
            row.get("platform_account_name") or "",
            row.get("company_name") or "",
            row.get("billing_document_number") or "",
            row.get("amount") or "",
            row.get("billing_document_amount") or "",
            row.get("currency") or "",
            row.get("payment_id") or "",
            row.get("processed_by") or "",
        ])
    return output.getvalue()


def _system_digits(value, limit: int = None) -> str:
    result = re.sub(r"\D+", "", str(value or ""))
    return result[:limit] if limit else result


def _system_company_duplicate_rows(cur, inn: str, kpp: str = "", exclude_company_id: int = None) -> list[dict]:
    clean_inn = _system_digits(inn, 12)
    clean_kpp = _system_digits(kpp, 9)
    if not clean_inn:
        return []
    values = [clean_inn]
    exclude_sql = ""
    if exclude_company_id:
        exclude_sql = "AND c.id<>%s"
        values.append(exclude_company_id)
    cur.execute(f"""SELECT c.id, c.name, c.short_name, c.inn, c.kpp, c.active,
                          c.platform_account_id, pa.name AS platform_account_name,
                          c.contact_name, c.contact_phone, c.contact_email
                   FROM companies c
                   LEFT JOIN platform_accounts pa ON pa.id=c.platform_account_id
                   WHERE regexp_replace(COALESCE(c.inn,''), '\\D', '', 'g')=%s
                     {exclude_sql}
                   ORDER BY c.active DESC, c.id ASC
                   LIMIT 12""", tuple(values))
    rows = []
    for row in cur.fetchall():
        item = dict(row)
        item_kpp = _system_digits(item.get("kpp"), 9)
        item["matchType"] = "exact_inn_kpp" if clean_kpp and item_kpp == clean_kpp else "same_inn"
        item["blocking"] = item["matchType"] == "exact_inn_kpp" or not clean_kpp
        rows.append(item)
    return rows


def _system_account_usage(cur, platform_account_id: int = None, fallback_plan: str = "demo") -> dict:
    account = None
    if platform_account_id:
        cur.execute("""SELECT id, name, plan, status, active
                       FROM platform_accounts
                       WHERE id=%s""", (platform_account_id,))
        account = cur.fetchone()
    plan = (account or {}).get("plan") or fallback_plan or "demo"
    tariff = _system_tariff(plan)
    if platform_account_id:
        cur.execute("""SELECT COUNT(*) AS companies_count
                       FROM companies
                       WHERE platform_account_id=%s AND active=TRUE""", (platform_account_id,))
        companies_count = int((cur.fetchone() or {}).get("companies_count") or 0)
        cur.execute("""SELECT COUNT(*) AS users_count
                       FROM users u
                       JOIN companies c ON c.id=u.company_id
                       WHERE c.platform_account_id=%s AND u.active=TRUE""", (platform_account_id,))
        users_count = int((cur.fetchone() or {}).get("users_count") or 0)
        cur.execute("""SELECT COUNT(*) AS projects_count
                       FROM projects p
                       JOIN companies c ON c.id=p.company_id
                       WHERE c.platform_account_id=%s AND c.active=TRUE""", (platform_account_id,))
        projects_count = int((cur.fetchone() or {}).get("projects_count") or 0)
    else:
        companies_count = 0
        users_count = 0
        projects_count = 0
    return {
        "account": dict(account) if account else None,
        "plan": plan,
        "tariff": tariff,
        "companiesCount": companies_count,
        "usersCount": users_count,
        "projectsCount": projects_count,
    }


def _system_limit_item(label: str, used: int, projected: int, limit, key: str) -> Optional[dict]:
    if limit in (None, "", 0):
        return None
    try:
        numeric_limit = int(limit)
    except Exception:
        return None
    level = "ok"
    if projected > numeric_limit:
        level = "danger"
    elif projected >= numeric_limit:
        level = "warning"
    elif numeric_limit and projected / numeric_limit >= 0.8:
        level = "warning"
    return {
        "key": key,
        "label": label,
        "used": used,
        "projected": projected,
        "limit": numeric_limit,
        "level": level,
        "text": f"{label}: {projected}/{numeric_limit}",
    }


def _system_company_create_preview(cur, data: dict) -> dict:
    plan = data.get("plan") or "demo"
    platform_account_id = _system_payment_event_filter_int(data.get("platformAccountId") or data.get("platform_account_id"))
    inn = _system_digits(data.get("inn"), 12)
    kpp = _system_digits(data.get("kpp"), 9)
    duplicates = _system_company_duplicate_rows(cur, inn, kpp)
    usage = _system_account_usage(cur, platform_account_id, fallback_plan=plan)
    tariff = usage["tariff"] or {}
    projected_companies = usage["companiesCount"] + 1
    checks = [
        _system_limit_item("Компании", usage["companiesCount"], projected_companies, tariff.get("includedCompanies"), "companies"),
        _system_limit_item("Пользователи", usage["usersCount"], usage["usersCount"], tariff.get("maxUsers"), "users"),
        _system_limit_item("Объекты", usage["projectsCount"], usage["projectsCount"], tariff.get("maxProjects"), "projects"),
    ]
    limit_warnings = [item for item in checks if item and item["level"] != "ok"]
    blocking_reasons = []
    if platform_account_id and not usage.get("account"):
        blocking_reasons.append("Выбранный клиентский аккаунт не найден.")
    if any(item.get("blocking") for item in duplicates):
        blocking_reasons.append("Компания с таким ИНН" + (" и КПП" if kpp else "") + " уже есть в платформе.")
    if any(item.get("level") == "danger" for item in limit_warnings):
        blocking_reasons.append("Добавление компании превышает лимит текущего тарифа аккаунта.")
    return {
        "ok": True,
        "inn": inn,
        "kpp": kpp,
        "platformAccountId": platform_account_id,
        "account": usage["account"],
        "plan": usage["plan"],
        "tariff": {
            "id": tariff.get("id"),
            "name": tariff.get("name"),
            "includedCompanies": tariff.get("includedCompanies"),
            "maxProjects": tariff.get("maxProjects"),
            "maxUsers": tariff.get("maxUsers"),
        },
        "accountUsage": {
            "companies": usage["companiesCount"],
            "projectedCompanies": projected_companies,
            "users": usage["usersCount"],
            "projects": usage["projectsCount"],
        },
        "duplicates": duplicates,
        "limitWarnings": limit_warnings,
        "blockingReasons": blocking_reasons,
        "canCreate": not blocking_reasons,
    }


def _system_user_filter_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def _system_client_user_row(row: dict) -> dict:
    item = dict(row or {})
    return {
        "id": item.get("id"),
        "name": item.get("name") or "",
        "email": item.get("email") or "",
        "role": item.get("role") or "",
        "active": item.get("active") is not False,
        "companyId": item.get("company_id"),
        "companyName": item.get("company_name") or "",
        "companyActive": item.get("company_active") is not False,
        "platformAccountId": item.get("platform_account_id"),
        "platformAccountName": item.get("platform_account_name") or "",
        "projectName": item.get("project_name") or "",
        "twoFactorRequired": bool(item.get("two_factor_required")),
        "twoFactorEnabled": bool(item.get("two_factor_enabled")),
        "createdAt": str(item.get("created_at") or "")[:19],
    }


CLIENT_CARD_KEYS = (
    "platformAccountName",
    "companyName",
    "shortName",
    "inn",
    "kpp",
    "ogrn",
    "contactName",
    "contactPosition",
    "contactPhone",
    "contactEmail",
    "legalAddress",
    "website",
    "notes",
)


def _client_card_text(value, limit=1200) -> str:
    return str(value or "").strip()[:limit]


def _client_card_digits(value) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _client_card_first_match(pattern: str, text: str, flags=re.IGNORECASE | re.MULTILINE, group=1) -> str:
    match = re.search(pattern, text or "", flags)
    if not match:
        return ""
    return _client_card_text(match.group(group), 500)


def _client_card_json(text: str) -> dict:
    raw = _client_card_text(text, 20000)
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    candidates = [raw]
    if start >= 0 and end > start:
        candidates.insert(0, raw[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            continue
    return {}


def _client_card_heuristic(text: str) -> dict:
    raw = text or ""
    compact = re.sub(r"\s+", " ", raw).strip()
    fields = {key: "" for key in CLIENT_CARD_KEYS}
    fields["contactEmail"] = _client_card_first_match(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", raw, re.IGNORECASE)
    fields["inn"] = _client_card_digits(_client_card_first_match(r"\bИНН\b[^\d]{0,20}(\d{10,12})", raw))[:12]
    fields["kpp"] = _client_card_digits(_client_card_first_match(r"\bКПП\b[^\d]{0,20}(\d{9})", raw))[:9]
    fields["ogrn"] = _client_card_digits(_client_card_first_match(r"\bОГРН(?:ИП)?\b[^\d]{0,20}(\d{13,15})", raw))[:15]
    phone = _client_card_first_match(r"((?:\+7|8)[\s(.-]*\d{3}[\s)./-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2})", raw)
    if not phone:
        phone = _client_card_first_match(r"(\+?\d[\d\s().-]{8,24}\d)", raw)
    fields["contactPhone"] = re.sub(r"\s+", " ", phone).strip()
    website = _client_card_first_match(r"((?:https?://)?(?:www\.)?[A-Z0-9][A-Z0-9\-]*(?:\.[A-Z0-9][A-Z0-9\-]*)+\S*)", raw, re.IGNORECASE)
    if fields["contactEmail"] and website and website in fields["contactEmail"] and not re.search(r"(?:https?://|www\.)" + re.escape(website), raw, re.IGNORECASE):
        website = ""
    fields["website"] = website
    fields["legalAddress"] = _client_card_first_match(r"(?:адрес|юр\.?\s*адрес|местонахождение)\s*[:\-]?\s*([^\n]{8,220})", raw)
    company = _client_card_first_match(r"((?:ООО|АО|ПАО|ЗАО|ИП)\s+[\"«]?[А-ЯЁA-Z0-9][^,\n;]{2,160})", raw)
    if company:
        company = re.sub(r"\s+(?:ИНН|КПП|ОГРН|тел\.?|email|e-mail).*$", "", company, flags=re.IGNORECASE).strip(" ,;")
    fields["companyName"] = company
    if company:
        fields["platformAccountName"] = re.sub(r"^(?:ООО|АО|ПАО|ЗАО|ИП)\s+", "", company, flags=re.IGNORECASE).strip(" \"«»")
        fields["shortName"] = fields["platformAccountName"][:80]
    person = _client_card_first_match(r"([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё.-]+){1,2})\s*(?:\n|,|$)", raw)
    if person and (not company or person not in company):
        fields["contactName"] = person
    position = _client_card_first_match(r"(?:должность|позиция)\s*[:\-]?\s*([^\n]{3,120})", raw)
    if not position:
        position = _client_card_first_match(r"\n\s*((?:директор|руководитель|собственник|учредитель|менеджер|главный инженер)[^\n]{0,80})", raw)
    fields["contactPosition"] = position
    note_bits = []
    if fields["ogrn"]:
        note_bits.append("ОГРН: " + fields["ogrn"])
    if fields["legalAddress"]:
        note_bits.append("Адрес: " + fields["legalAddress"])
    if fields["website"]:
        note_bits.append("Сайт: " + fields["website"])
    if fields["contactPosition"]:
        note_bits.append("Должность: " + fields["contactPosition"])
    if not company and compact:
        note_bits.append("Текст карты: " + compact[:500])
    fields["notes"] = "\n".join(note_bits)
    return fields


def _normalize_client_card_fields(ai_fields, fallback_fields) -> dict:
    fields = dict(fallback_fields or {})
    if isinstance(ai_fields, dict):
        for key in CLIENT_CARD_KEYS:
            value = ai_fields.get(key)
            if value not in (None, ""):
                fields[key] = _client_card_text(value, 3000)
    for key in CLIENT_CARD_KEYS:
        fields.setdefault(key, "")
    fields["inn"] = _client_card_digits(fields.get("inn"))[:12]
    fields["kpp"] = _client_card_digits(fields.get("kpp"))[:9]
    fields["ogrn"] = _client_card_digits(fields.get("ogrn"))[:15]
    fields["contactEmail"] = _client_card_text(fields.get("contactEmail"), 255).lower()
    fields["contactPhone"] = re.sub(r"\s+", " ", _client_card_text(fields.get("contactPhone"), 100))
    if fields.get("companyName") and not fields.get("platformAccountName"):
        fields["platformAccountName"] = re.sub(r"^(?:ООО|АО|ПАО|ЗАО|ИП)\s+", "", fields["companyName"], flags=re.IGNORECASE).strip(" \"«»")
    if fields.get("companyName") and not fields.get("shortName"):
        fields["shortName"] = fields.get("platformAccountName") or fields["companyName"][:80]
    return fields


def _decode_client_card_bytes(content: bytes, limit=32000) -> str:
    raw = (content or b"")[:limit]
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(encoding, errors="ignore")
        except Exception:
            continue
    return ""


def _strip_rtf_text(text: str) -> str:
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text or "")
    text = re.sub(r"\\[a-zA-Z]+\d* ?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", text).strip()


def _docx_client_card_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    parts = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            parts.append(node.text)
    return "\n".join(parts)


def _xlsx_client_card_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.iter():
                if item.tag.endswith("}si"):
                    text_parts = [node.text for node in item.iter() if node.tag.endswith("}t") and node.text]
                    shared_strings.append(" ".join(text_parts))
        rows = []
        sheet_names = [name for name in archive.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
        for sheet_name in sheet_names[:8]:
            root = ET.fromstring(archive.read(sheet_name))
            for row in root.iter():
                if not row.tag.endswith("}row"):
                    continue
                cells = []
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    cell_type = cell.attrib.get("t")
                    value = ""
                    for node in cell:
                        if node.tag.endswith("}v") and node.text is not None:
                            value = node.text
                            break
                    if cell_type == "s":
                        try:
                            value = shared_strings[int(value)]
                        except Exception:
                            pass
                    if value:
                        cells.append(str(value))
                if cells:
                    rows.append(" | ".join(cells))
                if len(rows) >= 400:
                    break
            if len(rows) >= 400:
                break
    return "\n".join(rows)


def _pdf_client_card_text(content: bytes) -> tuple[str, str]:
    reader_cls = None
    try:
        from pypdf import PdfReader
        reader_cls = PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
            reader_cls = PdfReader
        except Exception:
            reader_cls = None
    if not reader_cls:
        return "", "PDF принят. Если он сканированный, распознавание пойдет через AI/OCR; текстовый слой PDF на сервере недоступен."
    try:
        reader = reader_cls(io.BytesIO(content))
        pages = []
        for page in reader.pages[:20]:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(pages).strip(), ""
    except Exception as exc:
        return "", "Не удалось извлечь текстовый слой PDF: " + str(exc)


def _binary_client_card_text(content: bytes) -> str:
    raw = _decode_client_card_bytes(content, 64000)
    chunks = re.findall(r"[A-Za-zА-Яа-яЁё0-9@+().,;:_/\-\s]{4,}", raw)
    clean = "\n".join(re.sub(r"\s+", " ", chunk).strip() for chunk in chunks)
    return clean[:12000]


def _extract_client_card_file_text(filename: str, content_type: str, content: bytes) -> tuple[str, str]:
    name = (filename or "").lower()
    mime_type = (content_type or mimetypes.guess_type(filename or "")[0] or "").lower()
    try:
        if mime_type.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif")):
            return "", ""
        if name.endswith(".pdf") or mime_type == "application/pdf":
            return _pdf_client_card_text(content)
        if name.endswith(".docx"):
            return _docx_client_card_text(content), ""
        if name.endswith(".xlsx"):
            return _xlsx_client_card_text(content), ""
        if name.endswith((".txt", ".csv", ".md", ".json", ".xml", ".html", ".htm")) or mime_type.startswith("text/"):
            return _decode_client_card_bytes(content), ""
        if name.endswith(".rtf"):
            return _strip_rtf_text(_decode_client_card_bytes(content)), ""
        if name.endswith((".doc", ".xls")):
            text = _binary_client_card_text(content)
            return text, "" if text else "Старый Office-формат сохранен, но текст автоматически не извлекся. Лучше загрузить .docx/.xlsx/PDF или фото."
    except Exception as exc:
        return "", "Не удалось извлечь текст из файла: " + str(exc)
    return "", "Файл сохранен. Для этого формата автоматическое извлечение текста пока недоступно."


def _client_card_file_payload(filename: str, content_type: str, content: bytes) -> tuple[dict, str]:
    name = filename or "client-card"
    mime_type = (content_type or mimetypes.guess_type(name)[0] or "application/octet-stream").lower()
    name_lower = name.lower()
    if "heic" in mime_type or "heif" in mime_type or name_lower.endswith((".heic", ".heif")):
        raise HTTPException(status_code=422, detail="HEIC/HEIF нужно преобразовать в JPEG/PNG перед распознаванием карты клиента.")
    if mime_type == "application/pdf" or name_lower.endswith(".pdf"):
        return {
            "type": "input_file",
            "filename": name,
            "file_data": "data:application/pdf;base64," + base64.b64encode(content).decode("utf-8"),
        }, "pdf"
    if mime_type.startswith("image/"):
        return {
            "type": "input_image",
            "image_url": f"data:{mime_type};base64," + base64.b64encode(content).decode("utf-8"),
        }, "image"
    raise HTTPException(status_code=422, detail="Для карты клиента загрузите PDF или изображение.")


def _recognize_client_card_with_ai(file_content: bytes, file_name: str, content_type: str,
                                   source_text: str, api_key: str, folder_id: str) -> tuple[dict, list]:
    warnings = []
    if not (api_key and folder_id):
        return {}, ["AI/OCR не настроен: задайте YANDEX_API_KEY и YANDEX_FOLDER_ID."]
    try:
        import openai as oa
    except Exception as exc:
        return {}, ["AI-клиент недоступен: " + str(exc)]
    content = []
    if file_content:
        try:
            file_part, kind = _client_card_file_payload(file_name, content_type, file_content)
            content.append({"type": "input_text", "text": "Файл карты клиента: " + (file_name or kind)})
            content.append(file_part)
        except HTTPException as exc:
            warnings.append(str(exc.detail))
    if source_text:
        content.append({"type": "input_text", "text": "Извлеченный текст карты клиента:\n" + source_text[:16000]})
    if not content:
        return {}, warnings + ["Файл сохранен, но этот формат нельзя автоматически распознать. Заполните поля вручную или загрузите фото/PDF/Word/Excel."]
    content.append({"type": "input_text", "text": (
        "Распознай карту клиента/визитку/реквизиты потенциального клиента строительной ERP. "
        "Верни только JSON без markdown. Не выдумывай значения. Если поля нет — пустая строка. "
        "Нужно заполнить форму подключения клиентского аккаунта и первой компании. "
        "platformAccountName — группа/бренд клиента без ООО, companyName — полное юрлицо, shortName — короткое имя. "
        "contactName — ФИО контактного лица, contactPosition — должность. "
        "notes — только полезные дополнительные данные, которые некуда положить: адрес, сайт, ОГРН, должность, источник. "
        "Формат: {"
        "\"platformAccountName\":\"\","
        "\"companyName\":\"\","
        "\"shortName\":\"\","
        "\"inn\":\"\","
        "\"kpp\":\"\","
        "\"ogrn\":\"\","
        "\"contactName\":\"\","
        "\"contactPosition\":\"\","
        "\"contactPhone\":\"\","
        "\"contactEmail\":\"\","
        "\"legalAddress\":\"\","
        "\"website\":\"\","
        "\"notes\":\"\","
        "\"confidence\":0.0,"
        "\"warnings\":[]"
        "}"
    )})
    try:
        client = oa.OpenAI(api_key=api_key, base_url="https://ai.api.cloud.yandex.net/v1", project=folder_id)
        response = client.responses.create(
            model=f"gpt://{folder_id}/qwen3.6-35b-a3b/latest",
            temperature=0.1,
            instructions="Ты извлекаешь данные клиента из визитки, карточки организации или реквизитов. Верни только валидный JSON.",
            input=[{"role": "user", "content": content}],
            max_output_tokens=2500,
        )
        return _client_card_json(response.output_text or ""), warnings
    except Exception as exc:
        return {}, warnings + ["AI/OCR не смог распознать карту клиента: " + str(exc)]


def register_platform_admin_routes(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    save_upload_file = deps.get("save_upload_file")
    save_upload_bytes = deps.get("save_upload_bytes")
    yandex_api_key = deps.get("yandex_api_key") or ""
    yandex_folder_id = deps.get("yandex_folder_id") or ""

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
            cur.execute("""SELECT COALESCE(NULLIF(role,''),'без роли') AS role,
                                  COUNT(*) FILTER (WHERE COALESCE(active,TRUE)=TRUE) AS active_count,
                                  COUNT(*) AS total_count
                           FROM users
                           WHERE company_id=%s AND NOT (COALESCE(role,'') = ANY(%s))
                           GROUP BY 1
                           ORDER BY active_count DESC, total_count DESC, role""",
                (company["id"], list(CLIENT_USER_EXCLUDED_ROLES)))
            role_rows = [dict(row) for row in cur.fetchall()]
            company["users_by_role"] = [
                {"role": row["role"], "active": int(row["active_count"] or 0), "total": int(row["total_count"] or 0)}
                for row in role_rows
            ]
            company["users_active_count"] = sum(item["active"] for item in company["users_by_role"])
            company["users_count"] = sum(item["total"] for item in company["users_by_role"])
            cur.execute("SELECT COUNT(*) FROM projects WHERE company_id=%s", (company["id"],))
            company["projects_count"] = cur.fetchone()["count"]
            cur.execute("SELECT COALESCE(SUM(amount),0) as t FROM company_payments WHERE company_id=%s AND status='paid'", (company["id"],))
            company["total_paid"] = float(cur.fetchone()["t"] or 0)
            cur.execute("SELECT COUNT(*) FROM companies WHERE platform_account_id=%s AND active=TRUE", (company.get("platform_account_id") or company["id"],))
            company["account_companies_count"] = cur.fetchone()["count"]
            company["billing_state"] = _system_company_billing_state(company)
        conn.close()
        return rows

    @app.post("/system/client-card/recognize")
    async def system_recognize_client_card(
        file: Optional[UploadFile] = File(default=None),
        text: str = Form(default=""),
        current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES)),
    ):
        """Распознавание карты клиента для чернового заполнения формы подключения компании."""
        pasted_text = _client_card_text(text, 32000)
        file_content = b""
        file_url = ""
        file_name = ""
        content_type = ""
        warnings = []
        if file:
            file_name = file.filename or "client-card"
            content_type = file.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
            file_content = await file.read(12 * 1024 * 1024 + 1)
            if len(file_content) > 12 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Карта клиента слишком большая. Загрузите файл до 12 МБ.")
            file_text, file_warning = _extract_client_card_file_text(file_name, content_type, file_content)
            if file_warning:
                warnings.append(file_warning)
            if file_text:
                pasted_text = "\n\n".join(part for part in (pasted_text, file_text) if part)
            if save_upload_file:
                try:
                    file.file.seek(0)
                    saved = save_upload_file(file, project_name="_platform", context="client-cards")
                    file_url = saved.get("url") or ""
                except Exception as exc:
                    warnings.append("Файл распознан, но не сохранился в архив загрузок: " + str(exc))
        if not file_content and not pasted_text:
            raise HTTPException(status_code=400, detail="Загрузите карту клиента или вставьте текст.")

        fallback = _client_card_heuristic(pasted_text)
        ai_file_content = b""
        if file_content:
            file_name_lower = file_name.lower()
            content_type_lower = (content_type or "").lower()
            if file_name_lower.endswith(".pdf") or content_type_lower == "application/pdf" or content_type_lower.startswith("image/"):
                ai_file_content = file_content
        ai_fields, ai_warnings = _recognize_client_card_with_ai(
            ai_file_content,
            file_name,
            content_type,
            pasted_text,
            yandex_api_key,
            yandex_folder_id,
        )
        warnings.extend(ai_warnings or [])
        fields = _normalize_client_card_fields(ai_fields, fallback)
        if isinstance(ai_fields.get("warnings") if isinstance(ai_fields, dict) else None, list):
            warnings.extend(_client_card_text(item, 300) for item in ai_fields.get("warnings") if _client_card_text(item, 300))
        confidence = 0
        if isinstance(ai_fields, dict):
            try:
                confidence = float(ai_fields.get("confidence") or 0)
            except Exception:
                confidence = 0
        source = "ai" if ai_fields else ("heuristic" if any(fallback.values()) else "empty")
        if source == "empty":
            warnings.append("Не удалось уверенно выделить поля. Проверьте качество фото или заполните вручную.")

        conn = get_db()
        cur = conn.cursor()
        _system_write_audit(cur, current_user, "client_card_recognized", "client_card", None,
            fields.get("companyName") or fields.get("platformAccountName") or file_name,
            details={
                "source": source,
                "fileUrl": file_url,
                "confidence": confidence,
                "recognizedKeys": [key for key in CLIENT_CARD_KEYS if fields.get(key)],
                "autoCreatedCompany": False,
            })
        conn.close()
        return {
            "ok": True,
            "source": source,
            "fileUrl": file_url,
            "confidence": confidence,
            "fields": fields,
            "warnings": list(dict.fromkeys([w for w in warnings if w])),
            "message": "Поля распознаны как черновик. Компания не создана, пока вы не сохраните форму.",
        }

    @app.post("/system/companies/preview")
    def system_company_create_preview(data: dict, _current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
        """Предварительная проверка ИНН, аккаунта и лимитов перед созданием компании."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        preview = _system_company_create_preview(cur, data or {})
        conn.close()
        return preview

    @app.post("/system/companies")
    def system_create_company(data: dict, current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
        """Создание новой компании-клиента + инвайт-код ее директору."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        preview = _system_company_create_preview(cur, data or {})
        if not preview.get("canCreate"):
            conn.close()
            raise HTTPException(status_code=409, detail={
                "message": "Компания не создана: сначала разберите дубли или смените тариф/аккаунт.",
                "blockingReasons": preview.get("blockingReasons") or [],
                "duplicates": preview.get("duplicates") or [],
                "limitWarnings": preview.get("limitWarnings") or [],
                "preview": preview,
            })
        platform_account_id = data.get("platformAccountId")
        plan = preview.get("plan") if platform_account_id and preview.get("account") else (data.get("plan") or "demo")
        tariff = _system_tariff(plan)
        trial_days = int(data.get("trialDays") or 30)
        trial_until = (datetime.now() + timedelta(days=trial_days)).date() if plan == "demo" else None
        monthly_fee = float(data.get("monthlyFee") or tariff.get("monthlyFee") or 0)
        max_projects = int(data.get("maxProjects") or tariff.get("maxProjects") or 0) or None
        max_users = int(data.get("maxUsers") or tariff.get("maxUsers") or 0) or None
        inn = _system_digits(data.get("inn"), 12)
        kpp = _system_digits(data.get("kpp"), 9)
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
            (platform_account_id, data.get("name"), data.get("shortName"), inn, kpp,
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
                "duplicateCheck": {"inn": inn, "kpp": kpp, "duplicates": len(preview.get("duplicates") or [])},
                "limitPreview": preview.get("accountUsage"),
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

    @app.get("/system/client-users")
    def system_client_users(request: Request, _current_user: dict = Depends(require_roles(*PLATFORM_VIEW_ROLES))):
        """Пользователи клиентских компаний с фильтрами по аккаунту и юрлицу."""
        params = request.query_params
        platform_account_id = _system_user_filter_int(params.get("platformAccountId") or params.get("platform_account_id"))
        company_id = _system_user_filter_int(params.get("companyId") or params.get("company_id"))
        active = (params.get("active") or "").strip().lower()
        role = (params.get("role") or "").strip()
        search = (params.get("search") or "").strip()
        limit = _system_user_filter_int(params.get("limit")) or 500
        limit = min(max(limit, 1), 500)
        where = ["NOT (COALESCE(u.role,'') = ANY(%s))"]
        values = [list(CLIENT_USER_EXCLUDED_ROLES)]
        if platform_account_id:
            where.append("c.platform_account_id=%s")
            values.append(platform_account_id)
        if company_id:
            where.append("u.company_id=%s")
            values.append(company_id)
        if role:
            if role in CLIENT_USER_EXCLUDED_ROLES:
                return []
            where.append("u.role=%s")
            values.append(role)
        if active in ("true", "1", "active"):
            where.append("COALESCE(u.active,TRUE)=TRUE")
        elif active in ("false", "0", "inactive"):
            where.append("COALESCE(u.active,TRUE)=FALSE")
        if search:
            like = "%" + search + "%"
            where.append("(u.name ILIKE %s OR u.email ILIKE %s OR u.role ILIKE %s OR c.name ILIKE %s OR pa.name ILIKE %s)")
            values.extend([like] * 5)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""SELECT u.id, u.name, u.email, u.role, COALESCE(u.active,TRUE) AS active,
                              u.company_id, u.project_name, u.two_factor_required, u.two_factor_enabled, u.created_at,
                              c.name AS company_name, c.active AS company_active,
                              c.platform_account_id, pa.name AS platform_account_name
                       FROM users u
                       LEFT JOIN companies c ON c.id=u.company_id
                       LEFT JOIN platform_accounts pa ON pa.id=c.platform_account_id
                       WHERE {' AND '.join(where)}
                       ORDER BY pa.name NULLS LAST, c.name NULLS LAST, u.active DESC, u.name NULLS LAST, u.email
                       LIMIT %s""", tuple(values + [limit]))
        rows = [_system_client_user_row(row) for row in cur.fetchall()]
        conn.close()
        return rows

    @app.put("/system/client-users/{id}")
    def system_update_client_user(id: int, data: dict, current_user: dict = Depends(require_roles(*PLATFORM_MANAGE_ROLES))):
        """Безопасное отключение или перенос пользователя клиента между компаниями."""
        reason = (data.get("reason") or data.get("notes") or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="Укажите причину изменения доступа")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT u.id, u.name, u.email, u.role, COALESCE(u.active,TRUE) AS active,
                              u.company_id, u.project_name, u.two_factor_required, u.two_factor_enabled, u.created_at,
                              c.name AS company_name, c.active AS company_active,
                              c.platform_account_id, pa.name AS platform_account_name
                       FROM users u
                       LEFT JOIN companies c ON c.id=u.company_id
                       LEFT JOIN platform_accounts pa ON pa.id=c.platform_account_id
                       WHERE u.id=%s
                       FOR UPDATE""", (id,))
        before = cur.fetchone()
        if not before:
            conn.close()
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if before.get("role") in CLIENT_USER_EXCLUDED_ROLES:
            conn.close()
            raise HTTPException(status_code=400, detail="Платформенные роли меняются только во вкладке команды платформы")
        sets = []
        values = []
        action_parts = []
        target_company = None
        if "active" in data:
            sets.append("active=%s")
            values.append(data.get("active") is not False)
            sets.append("locked_until=NULL")
            action_parts.append("enabled" if data.get("active") is not False else "disabled")
        if data.get("companyId") not in (None, ""):
            target_company_id = _system_user_filter_int(data.get("companyId"))
            if not target_company_id:
                conn.close()
                raise HTTPException(status_code=400, detail="Некорректная компания")
            cur.execute("""SELECT c.id, c.name, c.platform_account_id, pa.name AS platform_account_name
                           FROM companies c
                           LEFT JOIN platform_accounts pa ON pa.id=c.platform_account_id
                           WHERE c.id=%s AND c.id<>1 AND COALESCE(c.active,TRUE)=TRUE AND c.platform_account_id IS NOT NULL""", (target_company_id,))
            target_company = cur.fetchone()
            if not target_company:
                conn.close()
                raise HTTPException(status_code=404, detail="Клиентская компания не найдена или отключена")
            before_account_id = before.get("platform_account_id")
            target_account_id = target_company.get("platform_account_id")
            if before_account_id and target_account_id and int(before_account_id) != int(target_account_id):
                conn.close()
                raise HTTPException(status_code=400, detail="Перенос между разными клиентскими аккаунтами запрещен. Сначала оформите отдельное решение в поддержке.")
            if int(target_company_id) != int(before.get("company_id") or 0):
                sets.extend(["company_id=%s", "project_id=NULL", "project_name=''", "assigned_projects='[]'::jsonb", "assigned_packages='[]'::jsonb"])
                values.append(target_company_id)
                action_parts.append("transferred")
        if not sets:
            conn.close()
            raise HTTPException(status_code=400, detail="Нет изменений")
        values.append(id)
        cur.execute("UPDATE users SET " + ", ".join(sets) + " WHERE id=%s", tuple(values))
        cur.execute("""SELECT u.id, u.name, u.email, u.role, COALESCE(u.active,TRUE) AS active,
                              u.company_id, u.project_name, u.two_factor_required, u.two_factor_enabled, u.created_at,
                              c.name AS company_name, c.active AS company_active,
                              c.platform_account_id, pa.name AS platform_account_name
                       FROM users u
                       LEFT JOIN companies c ON c.id=u.company_id
                       LEFT JOIN platform_accounts pa ON pa.id=c.platform_account_id
                       WHERE u.id=%s""", (id,))
        after = cur.fetchone()
        if "transferred" in action_parts:
            audit_action = "client_user_transferred"
        elif "disabled" in action_parts:
            audit_action = "client_user_disabled"
        elif "enabled" in action_parts:
            audit_action = "client_user_enabled"
        else:
            audit_action = "client_user_updated"
        _system_write_audit(cur, current_user, audit_action, "user", id, before.get("name") or before.get("email"),
            platform_account_id=after.get("platform_account_id"), company_id=after.get("company_id"),
            details={
                "reason": reason,
                "before": _system_client_user_row(before),
                "after": _system_client_user_row(after),
                "targetCompany": dict(target_company) if target_company else None,
            })
        conn.close()
        return {"ok": True, "user": _system_client_user_row(after)}

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
        cur.execute("""SELECT COUNT(*) as c FROM companies
                       WHERE plan<>'demo' AND plan_expires_at IS NOT NULL
                         AND plan_expires_at BETWEEN %s AND %s
                         AND suspended_at IS NULL
                         AND COALESCE(payment_status,'active') <> 'overdue'""",
                    (today, today + dt.timedelta(days=7)))
        payment_expiring = cur.fetchone()["c"]
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
            "paymentExpiring": payment_expiring,
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
    def system_payment_events(request: Request, _current_user: dict = Depends(require_roles(*PLATFORM_BILLING_ROLES))):
        params = request.query_params
        where = []
        values = []
        platform_account_id = _system_payment_event_filter_int(params.get("platformAccountId") or params.get("platform_account_id"))
        company_id = _system_payment_event_filter_int(params.get("companyId") or params.get("company_id"))
        document_id = _system_payment_event_filter_int(params.get("documentId") or params.get("billingDocumentId"))
        provider = (params.get("provider") or "").strip().lower()
        action_status = (params.get("actionStatus") or params.get("action_status") or "").strip()
        date_from = (params.get("dateFrom") or "").strip()
        date_to = (params.get("dateTo") or "").strip()
        search = (params.get("search") or "").strip()
        export_format = (params.get("export") or "").strip().lower()
        try:
            limit = max(1, min(5000 if export_format == "csv" else 500, int(params.get("limit") or 100)))
        except Exception:
            limit = 200 if export_format == "csv" else 100
        if platform_account_id:
            where.append("COALESCE(e.platform_account_id,d.platform_account_id)=%s")
            values.append(platform_account_id)
        if company_id:
            where.append("COALESCE(e.company_id,d.company_id)=%s")
            values.append(company_id)
        if document_id:
            where.append("e.billing_document_id=%s")
            values.append(document_id)
        if provider:
            where.append("LOWER(e.provider)=%s")
            values.append(provider)
        if action_status:
            where.append("e.action_status=%s")
            values.append(action_status)
        if date_from:
            where.append("e.received_at::date >= %s")
            values.append(date_from)
        if date_to:
            where.append("e.received_at::date <= %s")
            values.append(date_to)
        if search:
            like = "%" + search + "%"
            where.append("""(
                e.event_id ILIKE %s OR e.event_type ILIKE %s OR e.provider_status ILIKE %s
                OR d.number ILIKE %s OR c.name ILIKE %s OR pa.name ILIKE %s OR e.notes ILIKE %s
            )""")
            values.extend([like] * 7)
        where_sql = "WHERE " + " AND ".join(where) if where else ""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""SELECT e.*, d.number AS billing_document_number,
                              d.status AS billing_document_status,
                              d.amount AS billing_document_amount,
                              d.currency AS billing_document_currency,
                              d.payment_provider AS billing_payment_provider,
                              c.name AS company_name,
                              pa.name AS platform_account_name
                       FROM platform_payment_events e
                       LEFT JOIN platform_billing_documents d ON d.id=e.billing_document_id
                       LEFT JOIN companies c ON c.id=COALESCE(e.company_id,d.company_id)
                       LEFT JOIN platform_accounts pa ON pa.id=COALESCE(e.platform_account_id,d.platform_account_id)
                       {where_sql}
                       ORDER BY e.received_at DESC
                       LIMIT %s""", (*values, limit))
        rows = [_system_payment_event_enrich(dict(row)) for row in cur.fetchall()]
        conn.close()
        if export_format == "csv":
            csv_text = _system_payment_events_csv(rows)
            filename = "platform-payment-events-" + dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S") + ".csv"
            return Response(
                content="\ufeff" + csv_text,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
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
        action_status = "received"
        review_notes = ["Событие принято. Фактическая оплата не создана автоматически."]
        if not document:
            action_status = "needs_review"
            review_notes.append("Платежный документ не найден.")
        elif not _payment_event_success_status(event["provider"], event.get("providerStatus")):
            action_status = "needs_review"
            review_notes.append("Статус провайдера не подтверждает успешную оплату.")
        elif not _money_matches(event.get("amount"), document.get("amount")):
            action_status = "needs_review"
            review_notes.append("Сумма события не совпадает с платежным документом.")
        elif (event.get("currency") or "RUB").strip().upper() != (document.get("currency") or "RUB").strip().upper():
            action_status = "needs_review"
            review_notes.append("Валюта события не совпадает с платежным документом.")
        cur.execute("""INSERT INTO platform_payment_events
                          (provider, event_id, event_type, provider_status, platform_account_id, company_id,
                           billing_document_id, amount, currency, trusted, action_status, payload_json, notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                    (event["provider"], event.get("eventId"), event.get("eventType"), event.get("providerStatus"),
                     platform_account_id, company_id, event.get("documentId"), event.get("amount"), event.get("currency") or "RUB",
                     True, action_status, json.dumps(payload, ensure_ascii=False, default=str),
                     " ".join(review_notes)))
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
                "actionStatus": action_status,
                "autoPaymentCreated": False,
            })
        conn.close()
        return {
            "ok": True,
            "eventId": event_id,
            "documentFound": bool(document),
            "actionStatus": action_status,
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
        file_url = _generate_billing_document_pdf(document, company, current_user, save_upload_bytes=save_upload_bytes)
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
