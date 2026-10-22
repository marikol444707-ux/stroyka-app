from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_KEYS = {"fbclid", "gclid", "yclid", "ref", "source", "utm_campaign", "utm_medium", "utm_source", "utm_term"}
_ALLOWED_SOURCES = {"eis", "public_web", "browser_agent", "manual"}


def jev_report_items(report):
    """Convert the public JEV search report into the narrow intake contract."""
    if not isinstance(report, dict):
        raise ValueError("Отчёт JEV должен быть объектом JSON")
    selected = []
    for decision in ("confirmed", "review", "government_review"):
        bucket = report.get(decision, [])
        if not isinstance(bucket, list):
            raise ValueError("Списки confirmed/review/government_review в отчёте JEV должны быть массивами")
        for row in bucket:
            if not isinstance(row, dict):
                raise ValueError("Строка отчёта JEV должна быть объектом")
            provider = str(row.get("provider") or row.get("source") or "JEV").strip()[:100]
            item_id = str(row.get("id") or "").strip()
            reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
            context = [str(row.get(key) or "").strip() for key in ("organizer", "procedure_type", "status", "regime")]
            context.extend(str(reason).strip() for reason in reasons)
            evidence = " · ".join(dict.fromkeys(value for value in context if value))[:4000]
            deadline = row.get("deadline_msk") or row.get("deadline")
            if deadline:
                try:
                    deadline = datetime.fromisoformat(str(deadline).replace("Z", "+00:00")).isoformat()
                except ValueError:
                    try:
                        deadline = datetime.strptime(str(deadline), "%d.%m.%Y %H:%M").replace(
                            tzinfo=timezone(timedelta(hours=3))
                        ).isoformat()
                    except ValueError:
                        deadline = None
            price = row.get("price")
            if price not in (None, ""):
                price_text = str(price).strip().lower().replace("₽", "").replace("руб.", "").replace("руб", "")
                price_text = "".join(price_text.split())
                if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", price_text):
                    price = re.sub(r"[.,]", "", price_text)
                elif re.fullmatch(r"\d+(?:[.,]\d+)?", price_text):
                    price = price_text.replace(",", ".")
                else:
                    price = None
            selected.append({
                "source": "browser_agent",
                "sourceName": provider,
                "sourceItemId": f"{provider}:{item_id}" if item_id else "",
                "url": row.get("url"),
                "title": row.get("title"),
                "description": row.get("description") or "",
                "publishedAt": row.get("published_at") or row.get("publishedAt"),
                "region": row.get("place") or row.get("region") or (
                    "" if row.get("region_scope") in {"not_filtered", "unknown"} else report.get("region") or ""
                ),
                "workTypes": row.get("work_types") or row.get("workTypes") or [],
                "price": price,
                "deadline": deadline,
                "evidence": evidence or f"JEV decision: {decision}",
            })
    if len(selected) > 200:
        raise ValueError("Отчёт JEV превышает лимит 200 кандидатов")
    return selected


def canonicalize_url(value):
    raw = str(value or "").strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Укажите публичную ссылку http или https")
    if parts.username or parts.password:
        raise ValueError("Ссылка не должна содержать логин или пароль")
    host = parts.hostname.lower().rstrip(".")
    if any(character.isspace() or ord(character) < 32 for character in host):
        raise ValueError("Некорректный адрес источника")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("Некорректный адрес источника") from error
    netloc = host
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    query = [(key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
             if key.lower() not in _TRACKING_KEYS and not key.lower().startswith("utm_")]
    normalized = urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip("/"), urlencode(query, doseq=True), ""))
    if len(normalized) > 4000:
        raise ValueError("Ссылка источника слишком длинная")
    return normalized


def _optional_date(value, label):
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Поле «{label}» должно содержать дату ISO 8601") from error


def _optional_price(value):
    if value in (None, ""):
        return None
    try:
        price = Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Цена должна быть числом") from error
    if not price.is_finite() or price < 0:
        raise ValueError("Цена должна быть конечным неотрицательным числом")
    return str(price)


def build_candidate_record(payload):
    data = payload if isinstance(payload, dict) else {}
    source = str(data.get("source") or "").strip().lower()
    if source not in _ALLOWED_SOURCES:
        raise ValueError("Неизвестный источник находки")
    url = canonicalize_url(data.get("url"))
    title = str(data.get("title") or "").strip()
    if not title:
        raise ValueError("Укажите название закупки или заказа")
    if len(title) > 500:
        raise ValueError("Название не должно превышать 500 символов")
    item_id = str(data.get("sourceItemId") or data.get("source_item_id") or "").strip()
    if len(item_id) > 255:
        raise ValueError("Идентификатор источника не должен превышать 255 символов")
    work_types = data.get("workTypes", data.get("work_types", []))
    if not isinstance(work_types, list):
        raise ValueError("Виды работ должны быть списком")
    work_types = list(dict.fromkeys(str(value).strip()[:120] for value in work_types if str(value or "").strip()))[:30]
    return {
        "source": source,
        "source_name": str(data.get("sourceName") or data.get("source_name") or "").strip()[:100],
        "source_item_id": item_id or None,
        "identity_key": f"id:{item_id}" if item_id else f"url:{sha256(url.encode('utf-8')).hexdigest()}",
        "url": url,
        "title": title,
        "description": str(data.get("description") or "").strip()[:10000],
        "published_at": _optional_date(data.get("publishedAt", data.get("published_at")), "Дата публикации"),
        "region": str(data.get("region") or "").strip()[:255],
        "work_types": work_types,
        "price": _optional_price(data.get("price")),
        "deadline": _optional_date(data.get("deadline"), "Срок подачи"),
        "evidence": str(data.get("evidence") or "").strip()[:4000],
        "status": "Нужно проверить",
    }
