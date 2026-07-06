import datetime as dt
import hashlib
import json
import hmac
import secrets
import time
import urllib.parse
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Query

from .schema import ensure_messenger_schema


def _text(value, limit=255):
    return str(value or "").strip()[:limit]


def _payload_value(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _json_list(value):
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item or "").strip()]
    except Exception:
        pass
    return []


def _header_token(authorization: str) -> str:
    raw = str(authorization or "").strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw


def _safe_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(str(left or "").encode("utf-8"), str(right or "").encode("utf-8"))


def _bool_value(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "нет", "off")


def _int_or_none(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except Exception:
        return None


def _json_dict(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _json_array(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _iso_value(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value) if value else ""


def _max_actor_from_data(data: dict) -> tuple[str, str]:
    max_user_id = _payload_value(
        data,
        "maxUserId",
        "max_user_id",
        "userId",
        "user_id",
        "fromUserId",
        "senderId",
        "sender_id",
    )
    max_chat_id = _payload_value(data, "maxChatId", "max_chat_id", "chatId", "chat_id")
    if not max_user_id and not max_chat_id:
        raise HTTPException(status_code=400, detail="Нужен max_user_id или max_chat_id")
    return max_user_id, max_chat_id


def _invoice_preview_from_payload(payload: dict) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    photos = payload.get("photos") or payload.get("photoUrls") or []
    if isinstance(photos, str):
        photos = _json_list(photos)
    if not isinstance(photos, list):
        photos = []
    material_match = payload.get("materialMatch") or payload.get("material_match") or []
    if not isinstance(material_match, list):
        material_match = []
    return {
        "number": payload.get("number") or "",
        "date": payload.get("date") or "",
        "supplierName": payload.get("supplierName") or payload.get("supplier") or "",
        "supplierInn": payload.get("supplierInn") or payload.get("supplier_inn") or "",
        "supplierKpp": payload.get("supplierKpp") or payload.get("supplier_kpp") or "",
        "supplierOgrn": payload.get("supplierOgrn") or payload.get("supplier_ogrn") or "",
        "vat": payload.get("vat") or "",
        "totalBase": payload.get("totalBase") or payload.get("total_base") or 0,
        "totalVat": payload.get("totalVat") or payload.get("total_vat") or 0,
        "totalWithVat": payload.get("totalWithVat") or payload.get("total_with_vat") or 0,
        "photoUrl": payload.get("photoUrl") or payload.get("fileUrl") or "",
        "photos": photos,
        "pagesCount": payload.get("pagesCount") or payload.get("pages_count") or len(photos) or 1,
        "workPackage": payload.get("workPackage") or payload.get("work_package") or "",
        "warehouseTarget": payload.get("warehouseTarget") or payload.get("warehouse_target") or "",
        "selectedAction": payload.get("selectedAction") or payload.get("selected_action") or "",
        "materialMatch": material_match,
        "items": items,
    }


def _public_max_invoice_draft(row: dict, payload: dict = None, duplicate: bool = False) -> dict:
    row = row or {}
    payload = payload if isinstance(payload, dict) else _json_dict(row.get("payload_json"))
    recognition = _json_dict(row.get("recognition_json")) or _json_dict(payload.get("recognition"))
    status = row.get("status") or "draft"
    actions = []
    if status == "draft":
        actions = ["confirm", "reject"]
    elif status == "confirmed":
        actions = ["openWarehouseInvoice"]
    return {
        "ok": True,
        "mode": "preview",
        "draftToken": row.get("draft_token") or "",
        "status": status,
        "warehouseInvoiceId": row.get("warehouse_invoice_id"),
        "supplierInvoiceId": row.get("supplier_invoice_id"),
        "accountingStatus": row.get("accounting_status") or "",
        "accountingWarning": row.get("accounting_warning") or "",
        "duplicate": bool(duplicate),
        "projectName": row.get("project_name") or payload.get("project") or "",
        "location": row.get("location") or payload.get("location") or "",
        "sourceType": row.get("source_type") or payload.get("sourceType") or "",
        "sourceId": row.get("source_id") or payload.get("sourceId") or "",
        "recognized": bool(row.get("recognized")),
        "recognition": recognition,
        "invoiceDraft": _invoice_preview_from_payload(payload),
        "employeeName": row.get("employee_name") or payload.get("acceptedBy") or payload.get("addedBy") or "",
        "employeeRole": row.get("employee_role") or "",
        "messengerProvider": row.get("provider") or "max",
        "messengerAccountId": row.get("messenger_account_id"),
        "outboxId": row.get("outbox_id"),
        "expiresAt": _iso_value(row.get("expires_at")),
        "createdAt": _iso_value(row.get("created_at")),
        "updatedAt": _iso_value(row.get("updated_at")),
        "actions": actions,
    }


def _public_messenger_outbox_item(row: dict) -> dict:
    row = row or {}
    return {
        "id": row.get("id"),
        "provider": row.get("provider") or "",
        "messengerAccountId": row.get("messenger_account_id"),
        "userId": row.get("user_id"),
        "staffId": row.get("staff_id"),
        "externalUserId": row.get("external_user_id") or "",
        "chatId": row.get("chat_id") or "",
        "eventType": row.get("event_type") or "",
        "entityType": row.get("entity_type") or "",
        "entityId": row.get("entity_id"),
        "title": row.get("title") or "",
        "body": row.get("body") or "",
        "payload": _json_dict(row.get("payload_json")),
        "actions": _json_array(row.get("actions_json")),
        "status": row.get("status") or "",
        "priority": int(row.get("priority") or 5),
        "attempts": int(row.get("attempts") or 0),
        "providerMessageId": row.get("provider_message_id") or "",
        "lastError": row.get("last_error") or "",
        "nextAttemptAt": _iso_value(row.get("next_attempt_at")),
        "sentAt": _iso_value(row.get("sent_at")),
        "failedAt": _iso_value(row.get("failed_at")),
        "createdAt": _iso_value(row.get("created_at")),
        "updatedAt": _iso_value(row.get("updated_at")),
    }


def _invoice_confirm_patch(data: dict) -> dict:
    data = data or {}
    patch = {}
    recognized = _recognized_invoice_payload(data)
    if recognized:
        patch.update(recognized)
    for container_key in ("invoiceDraft", "invoice_draft", "payload", "data"):
        value = data.get(container_key)
        if isinstance(value, dict):
            patch.update(value)
    safe_keys = {
        "number",
        "date",
        "supplierName",
        "supplier",
        "supplierInn",
        "supplierKpp",
        "supplierOgrn",
        "vat",
        "totalBase",
        "totalVat",
        "totalWithVat",
        "photoUrl",
        "photos",
        "photoUrls",
        "pagesCount",
        "items",
        "positions",
        "workPackage",
        "work_package",
        "materialMatch",
    }
    for key in safe_keys:
        if key in data:
            patch[key] = data.get(key)
    return {key: value for key, value in patch.items() if key in safe_keys and value not in (None, "")}


def _max_invite_code_from_start_param(value: str) -> str:
    raw = _text(value, 512)
    for prefix in ("invite_", "invite-", "invite:", "inv_"):
        if raw.lower().startswith(prefix):
            return raw[len(prefix):].strip().upper()
    return raw.strip().upper()


def _split_query_pairs(raw: str):
    pairs = []
    for item in str(raw or "").split("&"):
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        pairs.append([key, value])
    return pairs


def _validate_max_init_data(init_data: str, bot_token: str, ttl_seconds: int) -> dict:
    if not bot_token:
        raise HTTPException(status_code=503, detail="MAX_BOT_API_TOKEN не настроен")
    pairs = _split_query_pairs(init_data)
    if not pairs:
        raise HTTPException(status_code=400, detail="MAX initData пустой")
    keys = [item[0] for item in pairs]
    duplicates = [key for key in set(keys) if keys.count(key) > 1]
    if duplicates:
        raise HTTPException(status_code=400, detail="MAX initData содержит повторяющиеся параметры")
    hash_items = [item for item in pairs if item[0] == "hash"]
    if len(hash_items) != 1 or not hash_items[0][1]:
        raise HTTPException(status_code=400, detail="MAX initData без hash")
    original_hash = hash_items[0][1]
    decoded = []
    for key, value in pairs:
        if key == "hash":
            continue
        decoded.append((key, urllib.parse.unquote_plus(value)))
    decoded.sort(key=lambda item: item[0])
    launch_params = "\n".join(f"{key}={value}" for key, value in decoded)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, launch_params.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, original_hash):
        raise HTTPException(status_code=403, detail="MAX initData подпись не прошла проверку")
    data = {key: value for key, value in decoded}
    auth_date = _int_or_none(data.get("auth_date"))
    if not auth_date:
        raise HTTPException(status_code=400, detail="MAX initData без auth_date")
    ttl = int(ttl_seconds or 3600)
    if ttl > 0 and abs(int(time.time()) - int(auth_date)) > ttl:
        raise HTTPException(status_code=403, detail="MAX initData устарел")
    user = _json_dict(data.get("user"))
    if not user.get("id"):
        raise HTTPException(status_code=400, detail="MAX initData без пользователя")
    chat = _json_dict(data.get("chat"))
    return {
        "ok": True,
        "user": user,
        "chat": chat,
        "startParam": data.get("start_param") or "",
        "queryId": data.get("query_id") or "",
        "authDate": auth_date,
    }


def _validate_max_contact(contact: dict, user_id: str, bot_token: str) -> dict:
    contact = contact if isinstance(contact, dict) else {}
    phone = _text(contact.get("phone"), 40).replace("+", "")
    auth_date = _text(contact.get("authDate") or contact.get("auth_date"), 40)
    original_hash = _text(contact.get("hash"), 200)
    if not phone or not auth_date or not original_hash:
        return {"valid": False, "phoneHash": "", "phoneTail": ""}
    params = [
        ("authDate", auth_date),
        ("phone", phone),
        ("userId", str(user_id or "")),
    ]
    params.sort(key=lambda item: item[0])
    payload = "\n".join(f"{key}={value}" for key, value in params)
    expected = hmac.new(bot_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, original_hash):
        return {"valid": False, "phoneHash": "", "phoneTail": ""}
    phone_hash = hmac.new(bot_token.encode("utf-8"), phone.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"valid": True, "phoneHash": phone_hash, "phoneTail": phone[-4:]}


def _public_invite(row: dict) -> dict:
    if not row:
        return {"valid": False}
    return {
        "valid": True,
        "code": row.get("code") or "",
        "role": row.get("role") or "",
        "projectName": row.get("project_name") or "",
        "assignedProjects": _json_list(row.get("assigned_projects")),
        "assignedPackages": _json_list(row.get("assigned_packages")),
        "companyId": row.get("company_id"),
        "platformAccountId": row.get("platform_account_id"),
        "presetName": row.get("preset_name") or "",
        "presetCategory": row.get("preset_category") or "",
    }


def _normalize_invoice_payload(data: dict, employee: dict) -> dict:
    source = data.get("data") if isinstance(data.get("data"), dict) else data
    payload = dict(source)
    if not payload.get("items") and isinstance(source.get("positions"), list):
        payload["items"] = source.get("positions")
    if not payload.get("number"):
        payload["number"] = source.get("invoiceNumber") or source.get("invoice_number") or source.get("documentNumber") or ""
    if not payload.get("date"):
        payload["date"] = source.get("invoiceDate") or source.get("invoice_date") or source.get("documentDate") or None
    if not payload.get("supplierName"):
        payload["supplierName"] = source.get("supplier") or source.get("supplier_name") or source.get("seller") or ""
    if not payload.get("photoUrl"):
        payload["photoUrl"] = source.get("photoUrl") or source.get("fileUrl") or data.get("photoUrl") or data.get("fileUrl") or ""
    if not payload.get("totalWithVat"):
        payload["totalWithVat"] = source.get("total_with_vat") or source.get("total") or source.get("amount") or 0
    if not payload.get("totalVat"):
        payload["totalVat"] = source.get("total_vat") or source.get("vatAmount") or 0
    if not payload.get("totalBase"):
        payload["totalBase"] = source.get("total_base") or 0

    normalized_items = []
    for raw_item in payload.get("items") or []:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        if not item.get("name"):
            item["name"] = item.get("title") or item.get("material") or item.get("product") or item.get("sourceText") or ""
        if not item.get("quantity"):
            item["quantity"] = item.get("qty") or item.get("count") or item.get("amount") or 0
        if not item.get("unit"):
            item["unit"] = item.get("measure") or item.get("uom") or "шт"
        if not item.get("price"):
            item["price"] = item.get("priceWithVat") or item.get("unitPriceWithVat") or item.get("unitPrice") or 0
        if not item.get("total"):
            item["total"] = item.get("lineTotalWithVat") or item.get("lineTotal") or 0
        normalized_items.append(item)

    payload["items"] = normalized_items
    payload["acceptedBy"] = payload.get("acceptedBy") or employee.get("name") or ""
    payload["addedBy"] = payload.get("addedBy") or employee.get("name") or ""
    return payload


def _recognized_invoice_payload(data: dict) -> dict:
    data = data or {}
    source = data.get("data") if isinstance(data.get("data"), dict) else {}
    for key in ("recognizedInvoice", "recognized_invoice", "scanData", "scan_data", "invoiceDraft", "invoice_draft"):
        value = data.get(key)
        if isinstance(value, dict):
            return value.get("data") if isinstance(value.get("data"), dict) else value
        value = source.get(key)
        if isinstance(value, dict):
            return value.get("data") if isinstance(value.get("data"), dict) else value
    return {}


def _invoice_scan_images(data: dict):
    data = data or {}
    source = data.get("data") if isinstance(data.get("data"), dict) else {}
    images = data.get("images") or data.get("pages") or source.get("images") or source.get("pages") or []
    if isinstance(images, (str, dict)):
        images = [images]
    if not isinstance(images, list):
        images = []
    image = data.get("image") or source.get("image")
    if image:
        images = [image] + images
    return images[:8]


def _apply_recognized_invoice_payload(payload: dict, recognized: dict) -> dict:
    recognized = recognized if isinstance(recognized, dict) else {}
    if not recognized:
        return payload
    next_payload = dict(payload or {})

    def set_if_empty(target_key, *source_keys):
        if next_payload.get(target_key) not in (None, "", [], 0):
            return
        for key in source_keys:
            value = recognized.get(key)
            if value not in (None, "", [], {}):
                next_payload[target_key] = value
                return

    set_if_empty("number", "number", "invoiceNumber", "documentNumber")
    set_if_empty("date", "date", "invoiceDate", "documentDate")
    set_if_empty("supplierName", "supplierName", "supplier", "seller", "shipper", "consignor")
    set_if_empty("supplierInn", "supplierInn", "supplier_inn", "inn")
    set_if_empty("supplierKpp", "supplierKpp", "supplier_kpp", "kpp")
    set_if_empty("supplierOgrn", "supplierOgrn", "supplier_ogrn", "ogrn")
    set_if_empty("totalBase", "totalBase", "total_base")
    set_if_empty("totalVat", "totalVat", "total_vat", "vatAmount")
    set_if_empty("totalWithVat", "totalWithVat", "total_with_vat", "amount", "total")
    set_if_empty("vat", "vat")
    set_if_empty("pagesCount", "pagesCount", "pages_count")
    set_if_empty("documentType", "documentType", "document_type")
    if not next_payload.get("items") and isinstance(recognized.get("items"), list):
        next_payload["items"] = recognized.get("items")
    if not next_payload.get("materialMatch") and isinstance(recognized.get("materialMatch"), list):
        next_payload["materialMatch"] = recognized.get("materialMatch")
    warnings = recognized.get("warnings") if isinstance(recognized.get("warnings"), list) else []
    next_payload["recognition"] = {
        "method": recognized.get("method") or recognized.get("recognitionMethod") or "max_ocr",
        "documentType": recognized.get("documentType") or recognized.get("document_type") or "",
        "confidence": recognized.get("confidence"),
        "warnings": warnings,
    }
    return next_payload


def _find_employee_by_messenger(cur, provider: str, external_user_id: str, chat_id: str) -> Optional[dict]:
    provider = _text(provider, 40).lower()
    external_user_id = _text(external_user_id, 120)
    chat_id = _text(chat_id, 120)
    if not provider or (not external_user_id and not chat_id):
        return None

    cur.execute(
        """
        SELECT u.id,u.name,u.role,u.project_name,u.assigned_projects,u.assigned_packages,ma.id,ma.display_name
          FROM messenger_accounts ma
          JOIN users u ON u.id=ma.user_id
         WHERE ma.provider=%s
           AND COALESCE(ma.enabled,TRUE)=TRUE
           AND COALESCE(u.active,TRUE)=TRUE
           AND ((%s<>'' AND ma.external_user_id=%s)
             OR (%s<>'' AND ma.chat_id=%s))
         ORDER BY ma.verified_at DESC NULLS LAST, ma.id DESC
         LIMIT 1
        """,
        (provider, external_user_id, external_user_id, chat_id, chat_id),
    )
    row = cur.fetchone()
    if row:
        return {
            "source": "users",
            "id": row[0],
            "name": row[1] or row[7] or "",
            "role": row[2] or "",
            "projectName": row[3] or "",
            "assignedProjects": _json_list(row[4]),
            "assignedPackages": _json_list(row[5]),
            "messengerAccountId": row[6],
        }

    cur.execute(
        """
        SELECT s.id,s.name,s.role,s.project,ma.id,ma.display_name
          FROM messenger_accounts ma
          JOIN staff s ON s.id=ma.staff_id
         WHERE ma.provider=%s
           AND COALESCE(ma.enabled,TRUE)=TRUE
           AND ((%s<>'' AND ma.external_user_id=%s)
             OR (%s<>'' AND ma.chat_id=%s))
         ORDER BY ma.verified_at DESC NULLS LAST, ma.id DESC
         LIMIT 1
        """,
        (provider, external_user_id, external_user_id, chat_id, chat_id),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "source": "staff",
        "id": row[0],
        "name": row[1] or row[5] or "",
        "role": row[2] or "",
        "projectName": row[3] or "",
        "assignedProjects": [row[3]] if row[3] else [],
        "assignedPackages": [],
        "messengerAccountId": row[4],
    }


def _employee_has_project_access(employee: dict, project_name: str, deps: dict) -> bool:
    if not project_name:
        return True
    role = employee.get("role") or ""
    if role in deps.get("finance_roles", ()) or role in deps.get("leadership_roles", ()):
        return True
    return project_name in deps["user_project_names"](employee)


def _source_id(data: dict, source: dict) -> str:
    return (
        data.get("sourceId")
        or data.get("maxMessageId")
        or data.get("messageId")
        or data.get("mid")
        or data.get("fileUniqueId")
        or data.get("fileToken")
        or source.get("sourceId")
        or source.get("maxMessageId")
        or source.get("messageId")
        or source.get("mid")
        or source.get("fileUniqueId")
        or source.get("fileToken")
        or None
    )


def register_messenger_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    create_warehouse_invoice_record = deps["create_warehouse_invoice_record"]
    scan_invoice = deps.get("scan_invoice")
    sync_supplier_invoice_from_warehouse = deps.get("sync_supplier_invoice_from_warehouse")
    warehouse_roles = deps["warehouse_roles"]
    leadership_roles = deps.get("leadership_roles") or ()
    main_warehouse_write_roles = deps.get("main_warehouse_write_roles") or ()
    max_bot_api_token = deps.get("max_bot_api_token") or ""
    max_webhook_secret = deps.get("max_webhook_secret") or ""
    max_initdata_ttl_seconds = int(deps.get("max_initdata_ttl_seconds") or 3600)
    supply_work_package = deps["supply_work_package"]
    hash_password = deps["hash_password"]
    prepare_user_access_scope = deps["prepare_user_access_scope"]
    safe_project_list = deps["safe_project_list"]
    role_requires_2fa = deps["role_requires_2fa"]
    max_registration_roles = deps.get("max_registration_roles") or (
        "прораб",
        "главный_инженер",
        "сметчик",
        "кладовщик",
        "снабженец",
        "мастер",
        "бригадир",
        "субподрядчик",
        "технадзор",
        "стройконтроль",
        "заказчик",
    )

    ensure_messenger_schema(get_db)

    def require_max_bot_token(
        authorization: Optional[str] = Header(default=None),
        x_max_bot_token: Optional[str] = Header(default=None),
        x_max_webhook_secret: Optional[str] = Header(default=None),
    ):
        expected_tokens = [token for token in (max_webhook_secret, max_bot_api_token) if token]
        if not expected_tokens:
            raise HTTPException(status_code=503, detail="MAX_BOT_API_TOKEN или MAX_WEBHOOK_SECRET не настроен")
        candidates = [
            _header_token(authorization or ""),
            _text(x_max_bot_token, 500),
            _text(x_max_webhook_secret, 500),
        ]
        if not any(
            candidate and any(_safe_compare(candidate, expected) for expected in expected_tokens)
            for candidate in candidates
        ):
            raise HTTPException(status_code=403, detail="Недостаточно прав MAX-бота")
        return {"role": "max_bot", "name": "MAX Bot"}

    def validate_max_launch(data: dict) -> dict:
        init_data = _text(data.get("initData") or data.get("init_data") or data.get("WebAppData"), 10000)
        validated = _validate_max_init_data(init_data, max_bot_api_token, max_initdata_ttl_seconds)
        user = validated["user"]
        chat = validated.get("chat") or {}
        contact_result = _validate_max_contact(data.get("contact") or {}, str(user.get("id") or ""), max_bot_api_token)
        return {**validated, "contact": contact_result, "maxUserId": str(user.get("id") or ""), "maxChatId": str(chat.get("id") or "")}

    def resolve_max_employee(max_user_id: str, max_chat_id: str) -> dict:
        conn = get_db()
        cur = conn.cursor()
        try:
            employee = _find_employee_by_messenger(cur, "max", max_user_id, max_chat_id)
        finally:
            cur.close()
            conn.close()
        if not employee:
            raise HTTPException(status_code=404, detail="Сотрудник с таким MAX не найден")
        if employee.get("role") not in warehouse_roles:
            raise HTTPException(status_code=403, detail="У сотрудника нет прав принимать складские накладные")
        return employee

    def build_max_invoice_context(data: dict) -> dict:
        data = data or {}
        max_user_id, max_chat_id = _max_actor_from_data(data)
        employee = resolve_max_employee(max_user_id, max_chat_id)

        source = data.get("data") if isinstance(data.get("data"), dict) else data
        project_name = (
            source.get("projectName")
            or source.get("project")
            or data.get("projectName")
            or data.get("project")
            or ""
        ).strip()
        location = (source.get("location") or data.get("location") or project_name or "Основной склад").strip()
        target_project = project_name or (location if location and location != "Основной склад" else "")
        if target_project and not _employee_has_project_access(employee, target_project, deps):
            raise HTTPException(status_code=403, detail="У сотрудника нет доступа к объекту")
        if not target_project and main_warehouse_write_roles and employee.get("role") not in main_warehouse_write_roles:
            raise HTTPException(
                status_code=403,
                detail="Прораб через MAX принимает накладные только на закрепленный объектный склад",
            )

        payload = _normalize_invoice_payload(data, employee)
        recognized = _recognized_invoice_payload(data)
        scan_result = None
        if not recognized and not payload.get("items"):
            images = _invoice_scan_images(data)
            if images and scan_invoice:
                scan_result = scan_invoice({"images": images, "projectName": target_project}, employee)
                if not scan_result or not scan_result.get("ok"):
                    raise HTTPException(
                        status_code=422,
                        detail=(scan_result or {}).get("error") or "ИИ не смог распознать MAX-накладную",
                    )
                recognized = scan_result.get("data") or {}
        if recognized:
            payload = _apply_recognized_invoice_payload(payload, recognized)
            payload = _normalize_invoice_payload(payload, employee)
        if not payload.get("items"):
            raise HTTPException(status_code=400, detail="MAX-накладная без распознанных позиций. Пришлите фото или recognizedInvoice.")
        payload["location"] = location or "Основной склад"
        payload["project"] = target_project
        payload["sourceType"] = payload.get("sourceType") or ("max_project_invoice" if target_project else "max_main_invoice")
        payload["sourceId"] = payload.get("sourceId") or _source_id(data, source)
        payload["workPackage"] = supply_work_package(
            payload.get("workPackage")
            or payload.get("work_package")
            or source.get("workPackage")
            or source.get("work_package")
        )

        return {
            "data": data,
            "source": source,
            "employee": employee,
            "maxUserId": max_user_id,
            "maxChatId": max_chat_id,
            "payload": payload,
            "projectName": target_project,
            "location": payload["location"],
            "sourceType": payload["sourceType"],
            "sourceId": payload.get("sourceId") or "",
            "recognized": bool(recognized),
            "scanResult": scan_result,
        }

    def select_existing_warehouse_by_source(cur, source_type: str, source_id: str):
        if not source_type or not source_id:
            return None
        cur.execute(
            """
            SELECT id,status,project,location,source_type,source_id,supplier_invoice_id,accounting_status
              FROM warehouse_invoices
             WHERE COALESCE(status,'Принята') <> 'Аннулирована'
               AND source_type=%s
               AND source_id=%s
             ORDER BY id DESC
             LIMIT 1
            """,
            (source_type, source_id),
        )
        return cur.fetchone()

    def apply_max_invoice_confirm_patch(payload: dict, data: dict, employee: dict) -> dict:
        patch = _invoice_confirm_patch(data)
        if not patch:
            return payload
        next_payload = dict(payload or {})
        if patch.get("positions") and not patch.get("items"):
            patch["items"] = patch.get("positions")
        next_payload.update({key: value for key, value in patch.items() if key != "positions"})
        next_payload = _apply_recognized_invoice_payload(next_payload, patch)
        next_payload = _normalize_invoice_payload(next_payload, employee)
        for key in ("location", "project", "sourceType", "sourceId", "workPackage"):
            if payload.get(key) not in (None, ""):
                next_payload[key] = payload.get(key)
        return next_payload

    def commit_max_invoice_payload(payload: dict, employee: dict, source_data: dict, recognized: bool) -> tuple[dict, dict]:
        result = create_warehouse_invoice_record(payload, employee)
        accounting_link = None
        if _bool_value((source_data or {}).get("syncAccounting"), True) and sync_supplier_invoice_from_warehouse:
            try:
                accounting_link = sync_supplier_invoice_from_warehouse(result.get("id"), payload, employee)
                result["supplierInvoiceId"] = accounting_link.get("id")
                result["accountingStatus"] = accounting_link.get("accountingStatus") or "На проверке"
            except Exception as exc:
                result["accountingWarning"] = getattr(exc, "detail", str(exc)) or "Не удалось связать бухгалтерскую первичку"
        result.update({
            "employeeName": employee.get("name", ""),
            "employeeSource": employee.get("source", ""),
            "messengerProvider": "max",
            "messengerAccountId": employee.get("messengerAccountId"),
            "projectName": payload.get("project") or "",
            "location": payload.get("location") or "",
            "sourceType": payload.get("sourceType") or "",
            "sourceId": payload.get("sourceId") or "",
            "recognized": bool(recognized or payload.get("recognition")),
            "recognition": payload.get("recognition") or {},
            "accountingLink": accounting_link,
        })
        return result, accounting_link

    def max_invoice_preview_actions(draft_token: str) -> list:
        return [
            {
                "id": "confirm",
                "label": "Принять на объектный склад",
                "kind": "callback",
                "method": "POST",
                "endpoint": "/max/warehouse-invoices/confirm",
                "payload": {"draftToken": draft_token},
            },
            {
                "id": "reject",
                "label": "Отклонить",
                "kind": "callback",
                "method": "POST",
                "endpoint": "/max/warehouse-invoices/reject",
                "payload": {"draftToken": draft_token},
            },
        ]

    def max_invoice_open_actions(invoice_id: int) -> list:
        return [
            {
                "id": "openWarehouseInvoice",
                "label": "Открыть накладную",
                "kind": "open_app",
                "path": "/app",
                "entityType": "warehouse_invoice",
                "entityId": invoice_id,
            }
        ]

    def max_invoice_message_body(payload: dict) -> str:
        preview = _invoice_preview_from_payload(payload)
        supplier = preview.get("supplierName") or "поставщик не указан"
        number = preview.get("number") or "без номера"
        project = payload.get("project") or payload.get("location") or "объект не указан"
        items_count = len(preview.get("items") or [])
        total = preview.get("totalWithVat") or preview.get("totalBase") or 0
        return f"{supplier}, № {number}, объект: {project}, позиций: {items_count}, сумма: {total}"

    def enqueue_max_outbox(cur, employee: dict, max_user_id: str, max_chat_id: str, event_type: str,
                           entity_type: str, entity_id: int, title: str, body: str,
                           payload: dict = None, actions: list = None, priority: int = 5) -> int:
        employee = employee or {}
        payload = payload if isinstance(payload, dict) else {}
        actions = actions if isinstance(actions, list) else []
        user_id = employee.get("id") if employee.get("source") == "users" else None
        staff_id = employee.get("id") if employee.get("source") == "staff" else None
        cur.execute(
            """
            INSERT INTO messenger_outbox
                (provider,messenger_account_id,user_id,staff_id,external_user_id,chat_id,
                 event_type,entity_type,entity_id,title,body,payload_json,actions_json,status,priority)
            VALUES
                ('max',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,'queued',%s)
            RETURNING id
            """,
            (
                employee.get("messengerAccountId"),
                user_id,
                staff_id,
                max_user_id or "",
                max_chat_id or max_user_id or "",
                event_type,
                entity_type,
                entity_id,
                title,
                body,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(actions, ensure_ascii=False),
                int(priority or 5),
            ),
        )
        row = cur.fetchone()
        return row.get("id") if isinstance(row, dict) else row[0]

    @app.get("/messenger-accounts")
    def list_messenger_accounts(current_user: dict = Depends(require_roles(*leadership_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
                SELECT ma.id,ma.provider,ma.user_id,ma.staff_id,ma.external_user_id,ma.chat_id,
                       ma.display_name,ma.verified_at,ma.enabled,
                       COALESCE(u.name,s.name,'') AS employee_name,
                       COALESCE(u.role,s.role,'') AS employee_role
                  FROM messenger_accounts ma
                  LEFT JOIN users u ON u.id=ma.user_id
                  LEFT JOIN staff s ON s.id=ma.staff_id
                 ORDER BY ma.id DESC
                 LIMIT 500
                """
            )
            return {
                "ok": True,
                "items": [
                    {
                        "id": row.get("id"),
                        "provider": row.get("provider") or "",
                        "userId": row.get("user_id"),
                        "staffId": row.get("staff_id"),
                        "externalUserId": row.get("external_user_id") or "",
                        "chatId": row.get("chat_id") or "",
                        "displayName": row.get("display_name") or "",
                        "verifiedAt": str(row.get("verified_at")) if row.get("verified_at") else "",
                        "enabled": bool(row.get("enabled", True)),
                        "employeeName": row.get("employee_name") or "",
                        "employeeRole": row.get("employee_role") or "",
                    }
                    for row in cur.fetchall()
                ],
            }
        finally:
            cur.close()
            conn.close()

    @app.post("/messenger-accounts")
    def upsert_messenger_account(data: dict, current_user: dict = Depends(require_roles(*leadership_roles))):
        data = data or {}
        provider = _text(data.get("provider") or "max", 40).lower()
        if provider not in ("max", "telegram"):
            raise HTTPException(status_code=400, detail="Поддерживаются только provider=max или provider=telegram")
        external_user_id = _text(
            data.get("externalUserId") or data.get("external_user_id") or data.get("maxUserId") or data.get("telegramId"),
            120,
        )
        chat_id = _text(data.get("chatId") or data.get("chat_id") or data.get("maxChatId") or data.get("telegramChatId"), 120)
        if not external_user_id and not chat_id:
            raise HTTPException(status_code=400, detail="Нужен externalUserId или chatId")

        user_id = _int_or_none(data.get("userId") or data.get("user_id"))
        staff_id = _int_or_none(data.get("staffId") or data.get("staff_id"))
        if bool(user_id) == bool(staff_id):
            raise HTTPException(status_code=400, detail="Укажите ровно один target: userId или staffId")

        display_name = _text(data.get("displayName") or data.get("display_name"), 255)
        phone_hash = _text(data.get("phoneHash") or data.get("phone_hash"), 255)
        enabled = _bool_value(data.get("enabled"), True)

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if user_id:
                cur.execute("SELECT id,name,role FROM users WHERE id=%s AND COALESCE(active,TRUE)=TRUE", (user_id,))
                target = cur.fetchone()
                if not target:
                    raise HTTPException(status_code=404, detail="Активный пользователь для привязки не найден")
            else:
                cur.execute("SELECT id,name,role FROM staff WHERE id=%s", (staff_id,))
                target = cur.fetchone()
                if not target:
                    raise HTTPException(status_code=404, detail="Сотрудник для привязки не найден")

            cur.execute(
                """
                SELECT id
                  FROM messenger_accounts
                 WHERE provider=%s
                   AND ((%s<>'' AND external_user_id=%s)
                     OR (%s<>'' AND chat_id=%s)
                     OR (%s IS NOT NULL AND user_id=%s)
                     OR (%s IS NOT NULL AND staff_id=%s))
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (provider, external_user_id, external_user_id, chat_id, chat_id, user_id, user_id, staff_id, staff_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """
                    UPDATE messenger_accounts
                       SET user_id=%s,
                           staff_id=%s,
                           external_user_id=%s,
                           chat_id=%s,
                           display_name=%s,
                           phone_hash=%s,
                           verified_at=NOW(),
                           enabled=%s,
                           updated_at=NOW()
                     WHERE id=%s
                 RETURNING id,provider,user_id,staff_id,external_user_id,chat_id,display_name,verified_at,enabled
                    """,
                    (user_id, staff_id, external_user_id, chat_id, display_name, phone_hash, enabled, existing["id"]),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO messenger_accounts
                        (provider,user_id,staff_id,external_user_id,chat_id,display_name,phone_hash,verified_at,enabled)
                    VALUES
                        (%s,%s,%s,%s,%s,%s,%s,NOW(),%s)
                 RETURNING id,provider,user_id,staff_id,external_user_id,chat_id,display_name,verified_at,enabled
                    """,
                    (provider, user_id, staff_id, external_user_id, chat_id, display_name, phone_hash, enabled),
                )
            row = cur.fetchone()
            conn.commit()
            return {
                "ok": True,
                "account": {
                    "id": row.get("id"),
                    "provider": row.get("provider") or "",
                    "userId": row.get("user_id"),
                    "staffId": row.get("staff_id"),
                    "externalUserId": row.get("external_user_id") or "",
                    "chatId": row.get("chat_id") or "",
                    "displayName": row.get("display_name") or "",
                    "verifiedAt": str(row.get("verified_at")) if row.get("verified_at") else "",
                    "enabled": bool(row.get("enabled", True)),
                    "employeeName": target.get("name") or "",
                    "employeeRole": target.get("role") or "",
                },
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/max/miniapp/validate")
    def validate_max_miniapp(data: dict):
        data = data or {}
        launch = validate_max_launch(data or {})
        invite_code = _max_invite_code_from_start_param(
            data.get("code") or data.get("inviteCode") or launch.get("startParam") or ""
        )
        linked = None
        invite = {"valid": False}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            employee = _find_employee_by_messenger(cur, "max", launch.get("maxUserId") or "", launch.get("maxChatId") or "")
            if employee:
                linked = {
                    "employeeName": employee.get("name") or "",
                    "employeeRole": employee.get("role") or "",
                    "employeeSource": employee.get("source") or "",
                    "messengerAccountId": employee.get("messengerAccountId"),
                    "projectName": employee.get("projectName") or "",
                    "assignedProjects": employee.get("assignedProjects") or [],
                }
            if invite_code:
                cur.execute("SELECT * FROM invite_codes WHERE code=%s", (invite_code,))
                invite_row = cur.fetchone()
                if invite_row:
                    if invite_row.get("used"):
                        invite = {"valid": False, "code": invite_code, "error": "Код уже использован"}
                    elif invite_row.get("expires_at") and invite_row["expires_at"] < dt.datetime.now():
                        invite = {"valid": False, "code": invite_code, "error": "Срок действия ссылки истек"}
                    else:
                        invite = _public_invite(invite_row)
                else:
                    invite = {"valid": False, "code": invite_code, "error": "Код не найден"}
            return {
                "ok": True,
                "maxUser": launch.get("user"),
                "maxChat": launch.get("chat"),
                "startParam": launch.get("startParam") or "",
                "contactVerified": bool((launch.get("contact") or {}).get("valid")),
                "phoneTail": (launch.get("contact") or {}).get("phoneTail") or "",
                "linkedAccount": linked,
                "invite": invite,
            }
        finally:
            cur.close()
            conn.close()

    @app.post("/max/register")
    def register_via_max(data: dict):
        data = data or {}
        launch = validate_max_launch(data)
        max_user = launch.get("user") or {}
        max_chat = launch.get("chat") or {}
        code = _max_invite_code_from_start_param(data.get("code") or data.get("inviteCode") or launch.get("startParam") or "")
        name = _text(
            data.get("name")
            or " ".join([_text(max_user.get("first_name"), 80), _text(max_user.get("last_name"), 80)]).strip()
            or max_user.get("username")
            or "MAX пользователь",
            255,
        )
        email = _text(data.get("email"), 255).lower()
        password = str(data.get("password") or "").strip()
        if not code or not email or not password:
            raise HTTPException(status_code=400, detail="Нужны код приглашения, email и пароль")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM invite_codes WHERE code=%s AND used=FALSE", (code,))
            invite = cur.fetchone()
            if not invite:
                raise HTTPException(status_code=400, detail="Неверный или использованный код")
            if invite.get("expires_at") and invite["expires_at"] < dt.datetime.now():
                raise HTTPException(status_code=400, detail="Код истек - попросите новую ссылку")
            role = invite.get("role") or ""
            if role not in max_registration_roles:
                raise HTTPException(status_code=400, detail="MAX-регистрация для этой роли пока закрыта. Используйте обычную регистрацию по приглашению.")
            cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")
            max_user_id = str(max_user.get("id") or "")
            max_chat_id = str(max_chat.get("id") or "") or max_user_id
            cur.execute(
                """SELECT id FROM messenger_accounts
                   WHERE provider='max' AND COALESCE(enabled,TRUE)=TRUE
                     AND ((%s<>'' AND external_user_id=%s) OR (%s<>'' AND chat_id=%s))
                   LIMIT 1""",
                (max_user_id, max_user_id, max_chat_id, max_chat_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Этот MAX уже привязан к другому пользователю")

            project_name = _text(invite.get("project_name"), 255)
            assigned_projects = safe_project_list(invite.get("assigned_projects"))
            assigned_packages = safe_project_list(invite.get("assigned_packages"))
            assigned_projects, assigned_packages = prepare_user_access_scope(cur, role, project_name, assigned_projects, assigned_packages)
            cur.execute("SELECT id FROM projects WHERE name=%s LIMIT 1", (project_name,))
            project_row = cur.fetchone()
            project_id = project_row.get("id") if project_row else None
            company_id = invite.get("company_id")
            platform_account_id = invite.get("platform_account_id")
            cur.execute(
                """
                INSERT INTO users
                    (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,company_id,platform_account_id,two_factor_required)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                RETURNING id,name,email,role,project_id,project_name,assigned_projects,assigned_packages,active,two_factor_required,two_factor_enabled,two_factor_confirmed_at
                """,
                (
                    name,
                    email,
                    hash_password(password),
                    role,
                    project_id,
                    project_name,
                    json.dumps(assigned_projects, ensure_ascii=False),
                    json.dumps(assigned_packages, ensure_ascii=False),
                    company_id,
                    platform_account_id,
                    role_requires_2fa(role),
                ),
            )
            user = cur.fetchone()
            contact = launch.get("contact") or {}
            cur.execute(
                """
                INSERT INTO messenger_accounts
                    (provider,user_id,external_user_id,chat_id,display_name,phone_hash,verified_at,enabled)
                VALUES
                    ('max',%s,%s,%s,%s,%s,NOW(),TRUE)
                RETURNING id
                """,
                (user["id"], max_user_id, max_chat_id, name, contact.get("phoneHash") or ""),
            )
            account_id = cur.fetchone()["id"]
            cur.execute("UPDATE invite_codes SET used=TRUE WHERE code=%s", (code,))
            conn.commit()
            return {
                "ok": True,
                "user": {
                    "id": user.get("id"),
                    "name": user.get("name") or "",
                    "email": user.get("email") or "",
                    "role": user.get("role") or "",
                    "projectName": user.get("project_name") or "",
                    "assignedProjects": _json_list(user.get("assigned_projects")),
                    "assignedPackages": _json_list(user.get("assigned_packages")),
                    "twoFactorRequired": bool(user.get("two_factor_required")) or role_requires_2fa(user.get("role") or ""),
                },
                "messengerAccountId": account_id,
                "contactVerified": bool(contact.get("valid")),
                "phoneTail": contact.get("phoneTail") or "",
                "nextAction": "login",
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/max/outbox")
    def list_max_outbox(
        limit: int = Query(default=50, ge=1, le=100),
        status: str = Query(default="queued"),
        _bot: dict = Depends(require_max_bot_token),
    ):
        status = _text(status, 40).lower()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if status and status != "all":
                cur.execute(
                    """
                    SELECT *
                      FROM messenger_outbox
                     WHERE provider='max'
                       AND status=%s
                       AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
                     ORDER BY priority ASC, id ASC
                     LIMIT %s
                    """,
                    (status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                      FROM messenger_outbox
                     WHERE provider='max'
                     ORDER BY id DESC
                     LIMIT %s
                    """,
                    (limit,),
                )
            return {"ok": True, "items": [_public_messenger_outbox_item(row) for row in cur.fetchall()]}
        finally:
            cur.close()
            conn.close()

    @app.post("/max/outbox/{message_id}/status")
    def update_max_outbox_status(message_id: int, data: dict, _bot: dict = Depends(require_max_bot_token)):
        data = data or {}
        status = _text(data.get("status"), 40).lower()
        if status not in ("queued", "sent", "failed", "skipped"):
            raise HTTPException(status_code=400, detail="Недопустимый статус MAX outbox")
        provider_message_id = _text(data.get("providerMessageId") or data.get("provider_message_id") or data.get("maxMessageId"), 255)
        error = _text(data.get("error") or data.get("lastError") or data.get("last_error"), 1000)
        retry_after = _int_or_none(data.get("retryAfterSeconds") or data.get("retry_after_seconds")) or 300
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if status == "sent":
                cur.execute(
                    """
                    UPDATE messenger_outbox
                       SET status='sent',
                           provider_message_id=%s,
                           sent_at=NOW(),
                           last_error='',
                           next_attempt_at=NULL,
                           updated_at=NOW()
                     WHERE provider='max' AND id=%s
                 RETURNING *
                    """,
                    (provider_message_id, message_id),
                )
            elif status == "failed":
                cur.execute(
                    """
                    UPDATE messenger_outbox
                       SET status='failed',
                           attempts=COALESCE(attempts,0)+1,
                           last_error=%s,
                           failed_at=NOW(),
                           next_attempt_at=NOW() + (%s || ' seconds')::interval,
                           updated_at=NOW()
                     WHERE provider='max' AND id=%s
                 RETURNING *
                    """,
                    (error or "MAX delivery failed", retry_after, message_id),
                )
            elif status == "queued":
                cur.execute(
                    """
                    UPDATE messenger_outbox
                       SET status='queued',
                           last_error='',
                           next_attempt_at=NULL,
                           updated_at=NOW()
                     WHERE provider='max' AND id=%s
                 RETURNING *
                    """,
                    (message_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE messenger_outbox
                       SET status='skipped',
                           last_error=%s,
                           updated_at=NOW()
                     WHERE provider='max' AND id=%s
                 RETURNING *
                    """,
                    (error, message_id),
                )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="MAX outbox message not found")
            conn.commit()
            return {"ok": True, "item": _public_messenger_outbox_item(row)}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/messenger-outbox")
    def list_messenger_outbox(
        provider: str = Query(default="max"),
        status: str = Query(default="queued"),
        limit: int = Query(default=100, ge=1, le=500),
        current_user: dict = Depends(require_roles(*leadership_roles)),
    ):
        provider = _text(provider or "max", 40).lower()
        status = _text(status, 40).lower()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if status and status != "all":
                cur.execute(
                    """
                    SELECT *
                      FROM messenger_outbox
                     WHERE provider=%s
                       AND status=%s
                     ORDER BY id DESC
                     LIMIT %s
                    """,
                    (provider, status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                      FROM messenger_outbox
                     WHERE provider=%s
                     ORDER BY id DESC
                     LIMIT %s
                    """,
                    (provider, limit),
                )
            return {"ok": True, "items": [_public_messenger_outbox_item(row) for row in cur.fetchall()]}
        finally:
            cur.close()
            conn.close()

    @app.post("/max/warehouse-invoices/preview")
    def preview_max_warehouse_invoice(data: dict, _bot: dict = Depends(require_max_bot_token)):
        context = build_max_invoice_context(data or {})
        payload = dict(context["payload"])
        draft_token = secrets.token_urlsafe(24)
        if not payload.get("sourceId"):
            payload["sourceId"] = "max-draft:" + draft_token
            context["sourceId"] = payload["sourceId"]

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if context["sourceId"]:
                cur.execute(
                    """
                    SELECT *
                      FROM max_invoice_drafts
                     WHERE provider='max'
                       AND source_id=%s
                     ORDER BY id DESC
                     LIMIT 1
                    """,
                    (context["sourceId"],),
                )
                existing_draft = cur.fetchone()
                if existing_draft:
                    if (
                        existing_draft.get("messenger_account_id")
                        and context["employee"].get("messengerAccountId")
                        and existing_draft.get("messenger_account_id") != context["employee"].get("messengerAccountId")
                    ):
                        raise HTTPException(status_code=409, detail="Этот MAX-источник уже привязан к другому сотруднику")
                    existing_draft["employee_name"] = context["employee"].get("name") or ""
                    existing_draft["employee_role"] = context["employee"].get("role") or ""
                    return _public_max_invoice_draft(existing_draft, duplicate=True)

                existing_invoice = select_existing_warehouse_by_source(cur, payload.get("sourceType"), payload.get("sourceId"))
                if existing_invoice:
                    preview_row = {
                        "draft_token": "",
                        "provider": "max",
                        "status": "confirmed",
                        "warehouse_invoice_id": existing_invoice.get("id"),
                        "supplier_invoice_id": existing_invoice.get("supplier_invoice_id"),
                        "accounting_status": existing_invoice.get("accounting_status") or "",
                        "project_name": existing_invoice.get("project") or payload.get("project") or "",
                        "location": existing_invoice.get("location") or payload.get("location") or "",
                        "source_type": payload.get("sourceType") or "",
                        "source_id": payload.get("sourceId") or "",
                        "recognized": context["recognized"],
                        "recognition_json": payload.get("recognition") or {},
                        "messenger_account_id": context["employee"].get("messengerAccountId"),
                        "employee_name": context["employee"].get("name") or "",
                        "employee_role": context["employee"].get("role") or "",
                    }
                    return _public_max_invoice_draft(preview_row, payload=payload, duplicate=True)

            cur.execute(
                """
                INSERT INTO max_invoice_drafts
                    (draft_token,provider,messenger_account_id,employee_source,employee_id,
                     max_user_id,max_chat_id,source_type,source_id,project_name,location,
                     payload_json,recognized,recognition_json,status,expires_at)
                VALUES
                    (%s,'max',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,'draft',NOW() + INTERVAL '7 days')
                RETURNING *
                """,
                (
                    draft_token,
                    context["employee"].get("messengerAccountId"),
                    context["employee"].get("source") or "",
                    context["employee"].get("id"),
                    context["maxUserId"],
                    context["maxChatId"],
                    payload.get("sourceType") or "",
                    payload.get("sourceId") or "",
                    payload.get("project") or "",
                    payload.get("location") or "",
                    json.dumps(payload, ensure_ascii=False),
                    context["recognized"],
                    json.dumps(payload.get("recognition") or {}, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
            outbox_payload = {
                "draftToken": row.get("draft_token"),
                "projectName": payload.get("project") or "",
                "location": payload.get("location") or "",
                "sourceType": payload.get("sourceType") or "",
                "sourceId": payload.get("sourceId") or "",
                "invoiceDraft": _invoice_preview_from_payload(payload),
            }
            row["outbox_id"] = enqueue_max_outbox(
                cur,
                context["employee"],
                context["maxUserId"],
                context["maxChatId"],
                "max_invoice_preview",
                "max_invoice_draft",
                row.get("id"),
                "Проверьте накладную",
                max_invoice_message_body(payload),
                payload=outbox_payload,
                actions=max_invoice_preview_actions(row.get("draft_token")),
                priority=3,
            )
            conn.commit()
            row["employee_name"] = context["employee"].get("name") or ""
            row["employee_role"] = context["employee"].get("role") or ""
            return _public_max_invoice_draft(row, payload=payload)
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            cur.execute(
                """
                SELECT *
                  FROM max_invoice_drafts
                 WHERE provider='max'
                   AND source_id=%s
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (payload.get("sourceId") or "",),
            )
            row = cur.fetchone()
            if not row:
                raise
            if (
                row.get("messenger_account_id")
                and context["employee"].get("messengerAccountId")
                and row.get("messenger_account_id") != context["employee"].get("messengerAccountId")
            ):
                raise HTTPException(status_code=409, detail="Этот MAX-источник уже привязан к другому сотруднику")
            row["employee_name"] = context["employee"].get("name") or ""
            row["employee_role"] = context["employee"].get("role") or ""
            return _public_max_invoice_draft(row, duplicate=True)
        finally:
            cur.close()
            conn.close()

    @app.post("/max/warehouse-invoices/confirm")
    def confirm_max_warehouse_invoice(data: dict, _bot: dict = Depends(require_max_bot_token)):
        data = data or {}
        draft_token = _text(data.get("draftToken") or data.get("draft_token"), 120)
        source = data.get("data") if isinstance(data.get("data"), dict) else data
        source_id = _text(data.get("sourceId") or source.get("sourceId") or _source_id(data, source), 255)
        if not draft_token and not source_id:
            raise HTTPException(status_code=400, detail="Нужен draftToken или sourceId MAX-черновика")

        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if draft_token:
                cur.execute("SELECT * FROM max_invoice_drafts WHERE draft_token=%s FOR UPDATE", (draft_token,))
            else:
                cur.execute(
                    """
                    SELECT *
                      FROM max_invoice_drafts
                     WHERE provider='max'
                       AND source_id=%s
                     ORDER BY id DESC
                     LIMIT 1
                     FOR UPDATE
                    """,
                    (source_id,),
                )
            draft = cur.fetchone()
            if not draft:
                raise HTTPException(status_code=404, detail="MAX-черновик накладной не найден")

            request_user_id = _payload_value(data, "maxUserId", "max_user_id", "userId", "user_id", "fromUserId", "senderId", "sender_id")
            request_chat_id = _payload_value(data, "maxChatId", "max_chat_id", "chatId", "chat_id")
            if request_user_id and draft.get("max_user_id") and request_user_id != draft.get("max_user_id"):
                raise HTTPException(status_code=403, detail="MAX-черновик создан другим пользователем")
            if request_chat_id and draft.get("max_chat_id") and request_chat_id != draft.get("max_chat_id"):
                raise HTTPException(status_code=403, detail="MAX-черновик создан в другом чате")

            if draft.get("status") == "confirmed" and draft.get("warehouse_invoice_id"):
                draft["employee_name"] = ""
                draft["employee_role"] = ""
                conn.commit()
                response = _public_max_invoice_draft(draft, duplicate=True)
                response["alreadyConfirmed"] = True
                return response
            if draft.get("status") == "rejected":
                raise HTTPException(status_code=409, detail="MAX-черновик уже отклонен")
            expires_at = draft.get("expires_at")
            if expires_at and expires_at < dt.datetime.now():
                cur.execute("UPDATE max_invoice_drafts SET status='expired', updated_at=NOW() WHERE id=%s", (draft["id"],))
                conn.commit()
                raise HTTPException(status_code=409, detail="Срок действия MAX-черновика истек")

            employee = _find_employee_by_messenger(cur, "max", draft.get("max_user_id") or "", draft.get("max_chat_id") or "")
            if not employee:
                raise HTTPException(status_code=404, detail="Сотрудник MAX для черновика не найден")
            if employee.get("role") not in warehouse_roles:
                raise HTTPException(status_code=403, detail="У сотрудника нет прав принимать складские накладные")

            payload = _json_dict(draft.get("payload_json"))
            payload = apply_max_invoice_confirm_patch(payload, data, employee)
            if not payload.get("items"):
                raise HTTPException(status_code=400, detail="MAX-черновик без позиций. Исправьте распознавание перед приемкой.")
            if payload.get("project") and not _employee_has_project_access(employee, payload.get("project"), deps):
                raise HTTPException(status_code=403, detail="У сотрудника нет доступа к объекту")
            if not payload.get("project") and main_warehouse_write_roles and employee.get("role") not in main_warehouse_write_roles:
                raise HTTPException(status_code=403, detail="Прораб через MAX принимает накладные только на закрепленный объектный склад")

            existing_invoice = select_existing_warehouse_by_source(cur, payload.get("sourceType"), payload.get("sourceId"))
            accounting_link = None
            already_confirmed = False
            if existing_invoice:
                result = {
                    "id": existing_invoice.get("id"),
                    "ok": True,
                    "alreadyExists": True,
                    "supplierInvoiceId": existing_invoice.get("supplier_invoice_id"),
                    "accountingStatus": existing_invoice.get("accounting_status") or "",
                }
                already_confirmed = True
            else:
                try:
                    result, accounting_link = commit_max_invoice_payload(
                        payload,
                        employee,
                        data,
                        bool(draft.get("recognized")),
                    )
                except HTTPException as exc:
                    if exc.status_code != 409:
                        raise
                    existing_invoice = select_existing_warehouse_by_source(cur, payload.get("sourceType"), payload.get("sourceId"))
                    if not existing_invoice:
                        raise
                    result = {
                        "id": existing_invoice.get("id"),
                        "ok": True,
                        "alreadyExists": True,
                        "supplierInvoiceId": existing_invoice.get("supplier_invoice_id"),
                        "accountingStatus": existing_invoice.get("accounting_status") or "",
                    }
                    already_confirmed = True

            cur.execute(
                """
                UPDATE max_invoice_drafts
                   SET status='confirmed',
                       payload_json=%s::jsonb,
                       warehouse_invoice_id=%s,
                       supplier_invoice_id=%s,
                       accounting_status=%s,
                       accounting_warning=%s,
                       confirmed_at=COALESCE(confirmed_at,NOW()),
                       updated_at=NOW()
                 WHERE id=%s
             RETURNING *
                """,
                (
                    json.dumps(payload, ensure_ascii=False),
                    result.get("id"),
                    result.get("supplierInvoiceId"),
                    result.get("accountingStatus") or "",
                    result.get("accountingWarning") or "",
                    draft["id"],
                ),
            )
            updated_draft = cur.fetchone()
            if result.get("id"):
                enqueue_max_outbox(
                    cur,
                    employee,
                    draft.get("max_user_id") or "",
                    draft.get("max_chat_id") or "",
                    "max_invoice_confirmed",
                    "warehouse_invoice",
                    result.get("id"),
                    "Накладная принята на склад",
                    max_invoice_message_body(payload),
                    payload={
                        "draftToken": updated_draft.get("draft_token") or draft_token,
                        "warehouseInvoiceId": result.get("id"),
                        "supplierInvoiceId": result.get("supplierInvoiceId"),
                        "accountingStatus": result.get("accountingStatus") or "",
                        "projectName": payload.get("project") or "",
                        "location": payload.get("location") or "",
                    },
                    actions=max_invoice_open_actions(result.get("id")),
                    priority=4,
                )
            conn.commit()
            result.update({
                "draftToken": updated_draft.get("draft_token") or draft_token,
                "status": "confirmed",
                "alreadyConfirmed": already_confirmed,
                "accountingLink": accounting_link,
            })
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/max/warehouse-invoices/reject")
    def reject_max_warehouse_invoice(data: dict, _bot: dict = Depends(require_max_bot_token)):
        data = data or {}
        draft_token = _text(data.get("draftToken") or data.get("draft_token"), 120)
        if not draft_token:
            raise HTTPException(status_code=400, detail="Нужен draftToken MAX-черновика")
        reason = _text(data.get("reason") or data.get("rejectReason") or data.get("reject_reason"), 1000)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
                UPDATE max_invoice_drafts
                   SET status='rejected',
                       reject_reason=%s,
                       rejected_at=NOW(),
                       updated_at=NOW()
                 WHERE draft_token=%s
                   AND status='draft'
             RETURNING *
                """,
                (reason, draft_token),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Активный MAX-черновик накладной не найден")
            payload = _json_dict(row.get("payload_json"))
            enqueue_max_outbox(
                cur,
                {
                    "source": row.get("employee_source") or "",
                    "id": row.get("employee_id"),
                    "messengerAccountId": row.get("messenger_account_id"),
                },
                row.get("max_user_id") or "",
                row.get("max_chat_id") or "",
                "max_invoice_rejected",
                "max_invoice_draft",
                row.get("id"),
                "Накладная отклонена",
                reason or max_invoice_message_body(payload),
                payload={
                    "draftToken": row.get("draft_token"),
                    "reason": reason,
                    "projectName": row.get("project_name") or payload.get("project") or "",
                    "location": row.get("location") or payload.get("location") or "",
                },
                actions=[],
                priority=4,
            )
            conn.commit()
            return _public_max_invoice_draft(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/max/warehouse-invoices")
    def create_max_warehouse_invoice(data: dict, _bot: dict = Depends(require_max_bot_token)):
        context = build_max_invoice_context(data or {})
        result, _accounting_link = commit_max_invoice_payload(
            context["payload"],
            context["employee"],
            data or {},
            context["recognized"],
        )
        return result
