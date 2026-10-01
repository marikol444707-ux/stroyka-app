"""Tenant-scoped, human-readable RFQ email content and safe header metadata."""

import re
from datetime import datetime
from email.utils import getaddresses
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")


def _header_text(value, limit):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _single_email(value):
    raw = str(value or "").strip()
    if not raw or "\r" in raw or "\n" in raw:
        return ""
    parsed = getaddresses([raw])
    if len(parsed) != 1 or not parsed[0][1] or "@" not in parsed[0][1]:
        return ""
    return parsed[0][1].lower()


def _deadline(value):
    if not value:
        return ""
    current = value
    if isinstance(current, str):
        try:
            current = datetime.fromisoformat(current.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if not isinstance(current, datetime):
        return ""
    if current.tzinfo is None:
        current = current.replace(tzinfo=MOSCOW)
    return current.astimezone(MOSCOW).strftime("%d.%m.%Y, %H:%M") + " (МСК)"


def build_rfq_email(request_context, supplier_name=""):
    context = dict(request_context or {})
    request_id = int(context.get("id") or 0)
    company_name = _header_text(context.get("companyName"), 120) or "Компания-заказчик"
    sender_name = _header_text("Стройка · " + company_name, 78)
    reply_to = _single_email(context.get("contactEmail")) or _single_email(context.get("companyEmail"))
    subject = _header_text(f"Запрос КП №{request_id} от {company_name}", 180)
    greeting_name = _header_text(supplier_name, 120)
    lines = [
        "Здравствуйте" + (", " + greeting_name if greeting_name else "") + ".",
        "",
        company_name + " приглашает вас предоставить коммерческое предложение.",
        "Номер запроса: " + str(request_id),
        "Объект: " + (str(context.get("project") or "объект не указан").strip()),
        "Раздел: " + (str(context.get("workPackage") or "Основная").strip()),
    ]
    delivery_address = str(context.get("deliveryAddress") or "").strip()
    if delivery_address:
        lines.append("Адрес доставки: " + delivery_address)
    contact_parts = [
        _header_text(context.get("contactName"), 120),
        _single_email(context.get("contactEmail")),
        _header_text(context.get("contactPhone"), 100),
    ]
    contact_parts = [part for part in contact_parts if part]
    if contact_parts:
        lines.append("Контакт по заявке: " + " · ".join(contact_parts))
    deadline = _deadline(context.get("responseDueAt"))
    if deadline:
        lines.append("Срок ответа: " + deadline)
    item_lines = [str(line).strip() for line in (context.get("itemLines") or []) if str(line).strip()]
    if item_lines:
        lines.extend(["", "Позиции:", *item_lines])
    notes = str(context.get("notes") or "").strip()
    if notes:
        lines.extend(["", "Комментарий: " + notes])
    public_url = str(context.get("publicUrl") or "").strip()
    if public_url:
        lines.extend(["", "Открыть запрос и отправить КП:", public_url])
    if reply_to:
        lines.extend(["", "Если нужна дополнительная информация, ответьте на это письмо."])
    lines.extend([
        "",
        "Это автоматическое уведомление платформы «Стройка». Запрос направлен вашей компании заказчиком " + company_name + ".",
    ])
    return subject, "\n".join(lines), sender_name, reply_to
