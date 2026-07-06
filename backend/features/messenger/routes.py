import base64
import binascii
import datetime as dt
import hashlib
import json
import hmac
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
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


def _num_value(value) -> float:
    try:
        return float(str(value if value is not None else 0).replace(" ", "").replace(",", "."))
    except Exception:
        return 0.0


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


def _public_messenger_file(row: dict) -> dict:
    row = row or {}
    return {
        "id": row.get("id"),
        "provider": row.get("provider") or "",
        "messengerAccountId": row.get("messenger_account_id"),
        "externalUserId": row.get("external_user_id") or "",
        "chatId": row.get("chat_id") or "",
        "fileToken": row.get("file_token") or "",
        "sourceId": row.get("source_id") or "",
        "projectName": row.get("project_name") or "",
        "context": row.get("context") or "",
        "filename": row.get("original_filename") or "",
        "contentType": row.get("content_type") or "",
        "sizeBytes": int(row.get("size_bytes") or 0),
        "url": row.get("url") or "",
        "storage": row.get("storage") or "",
        "storageKey": row.get("storage_key") or "",
        "entityType": row.get("entity_type") or "",
        "entityId": row.get("entity_id"),
        "metadata": _json_dict(row.get("metadata_json")),
        "createdAt": _iso_value(row.get("created_at")),
        "updatedAt": _iso_value(row.get("updated_at")),
    }


def _public_messenger_channel(row: dict) -> dict:
    row = row or {}
    return {
        "id": row.get("id"),
        "provider": row.get("provider") or "",
        "chatId": row.get("chat_id") or "",
        "title": row.get("title") or "",
        "channelType": row.get("channel_type") or "",
        "projectName": row.get("project_name") or "",
        "sourceLabel": row.get("source_label") or "",
        "campaignCode": row.get("campaign_code") or "",
        "defaultStage": row.get("default_stage") or "Новый",
        "enabled": bool(row.get("enabled", True)),
        "metadata": _json_dict(row.get("metadata_json")),
        "createdAt": _iso_value(row.get("created_at")),
        "updatedAt": _iso_value(row.get("updated_at")),
    }


def _decode_file_base64(value: str) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Нужен contentBase64 для MAX-файла")
    if "," in raw and raw.split(",", 1)[0].lower().endswith(";base64"):
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="MAX-файл передан невалидным base64")


def _max_file_items(data: dict) -> list:
    data = data or {}
    source = data.get("data") if isinstance(data.get("data"), dict) else {}
    raw_items = data.get("files") or data.get("attachments") or source.get("files") or source.get("attachments") or []
    single = data.get("file") or source.get("file")
    if single:
        raw_items = [single] + (raw_items if isinstance(raw_items, list) else [])
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        raw_items = []
    items = []
    for item in raw_items:
        if isinstance(item, dict):
            items.append(item)
    return items[:8]


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
    save_upload_bytes = deps.get("save_upload_bytes")
    warehouse_roles = deps["warehouse_roles"]
    leadership_roles = deps.get("leadership_roles") or ()
    main_warehouse_write_roles = deps.get("main_warehouse_write_roles") or ()
    app_public_url = (deps.get("app_public_url") or "https://stroyka26.pro").rstrip("/")
    max_bot_api_base = (deps.get("max_bot_api_base") or "https://platform-api2.max.ru").rstrip("/")
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
        x_max_bot_api_secret: Optional[str] = Header(default=None),
    ):
        expected_tokens = [token for token in (max_webhook_secret, max_bot_api_token) if token]
        if not expected_tokens:
            raise HTTPException(status_code=503, detail="MAX_BOT_API_TOKEN или MAX_WEBHOOK_SECRET не настроен")
        candidates = [
            _header_token(authorization or ""),
            _text(x_max_bot_token, 500),
            _text(x_max_webhook_secret, 500),
            _text(x_max_bot_api_secret, 500),
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

    def find_existing_max_file(cur, file_token: str, source_id: str):
        if not file_token and not source_id:
            return None
        cur.execute(
            """
            SELECT *
              FROM messenger_files
             WHERE provider='max'
               AND ((%s<>'' AND file_token=%s)
                 OR (%s<>'' AND source_id=%s))
             ORDER BY id DESC
             LIMIT 1
            """,
            (file_token, file_token, source_id, source_id),
        )
        return cur.fetchone()

    def persist_max_file_item(item: dict, employee: dict, max_user_id: str, max_chat_id: str,
                              project_name: str, context: str = "max-invoices",
                              entity_type: str = "", entity_id: int = None) -> dict:
        if not save_upload_bytes:
            raise HTTPException(status_code=503, detail="Storage helper для MAX-файлов не настроен")
        item = item if isinstance(item, dict) else {}
        file_token = _text(item.get("fileToken") or item.get("file_token") or item.get("token"), 255)
        source_id = _text(
            item.get("sourceId")
            or item.get("source_id")
            or item.get("maxFileId")
            or item.get("max_file_id")
            or file_token,
            255,
        )

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            existing = find_existing_max_file(cur, file_token, source_id)
            if existing:
                return _public_messenger_file(existing)

            content_b64 = (
                item.get("contentBase64")
                or item.get("content_base64")
                or item.get("base64")
                or item.get("dataUrl")
                or item.get("data_url")
                or item.get("content")
            )
            content = _decode_file_base64(content_b64)
            filename = _text(
                item.get("filename")
                or item.get("fileName")
                or item.get("file_name")
                or item.get("name")
                or "max-file",
                255,
            )
            content_type = _text(item.get("contentType") or item.get("content_type") or item.get("mimeType"), 120)
            saved = save_upload_bytes(content, filename, project_name, context, content_type)
            user_id = employee.get("id") if employee.get("source") == "users" else None
            staff_id = employee.get("id") if employee.get("source") == "staff" else None
            metadata = {
                key: value
                for key, value in item.items()
                if key not in {"contentBase64", "content_base64", "base64", "dataUrl", "data_url", "content"}
            }
            cur.execute(
                """
                INSERT INTO messenger_files
                    (provider,messenger_account_id,user_id,staff_id,external_user_id,chat_id,
                     file_token,source_id,project_name,context,original_filename,content_type,size_bytes,
                     url,storage,storage_key,entity_type,entity_id,metadata_json)
                VALUES
                    ('max',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                RETURNING *
                """,
                (
                    employee.get("messengerAccountId"),
                    user_id,
                    staff_id,
                    max_user_id or "",
                    max_chat_id or max_user_id or "",
                    file_token or None,
                    source_id or None,
                    project_name or "",
                    context or "max-invoices",
                    filename,
                    saved.get("contentType") or content_type,
                    len(content),
                    saved.get("url") or "",
                    saved.get("storage") or "",
                    saved.get("key") or "",
                    entity_type or "",
                    entity_id,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return _public_messenger_file(row)
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            existing = find_existing_max_file(cur, file_token, source_id)
            if existing:
                return _public_messenger_file(existing)
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def persist_max_files_from_payload(data: dict, employee: dict, max_user_id: str, max_chat_id: str,
                                       project_name: str, context: str = "max-invoices") -> list:
        files = _max_file_items(data)
        stored = []
        for item in files:
            if not any(
                item.get(key)
                for key in ("contentBase64", "content_base64", "base64", "dataUrl", "data_url", "content")
            ):
                continue
            stored.append(persist_max_file_item(item, employee, max_user_id, max_chat_id, project_name, context))
        if not stored:
            return []
        urls = [item.get("url") for item in stored if item.get("url")]
        if not urls:
            return stored
        source = data.get("data") if isinstance(data.get("data"), dict) else None
        current_photos = data.get("photos") or data.get("photoUrls") or []
        if isinstance(current_photos, str):
            current_photos = _json_list(current_photos)
        if not isinstance(current_photos, list):
            current_photos = []
        next_photos = []
        for url in [*current_photos, *urls]:
            if url and url not in next_photos:
                next_photos.append(url)
        data["photos"] = next_photos
        data["photoUrls"] = next_photos
        data["photoUrl"] = data.get("photoUrl") or (next_photos[0] if next_photos else "")
        if source is not None:
            source["photos"] = next_photos
            source["photoUrls"] = next_photos
            source["photoUrl"] = source.get("photoUrl") or data["photoUrl"]
        return stored

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
        stored_files = persist_max_files_from_payload(data, employee, max_user_id, max_chat_id, target_project or location, "max-invoices")

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
            "storedFiles": stored_files,
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

    def max_api_request(method: str, path: str, data: dict = None, query: dict = None, timeout: int = 30) -> dict:
        if not max_bot_api_token:
            raise HTTPException(status_code=503, detail="MAX_BOT_API_TOKEN не настроен")
        method = str(method or "GET").upper()
        path = "/" + str(path or "").lstrip("/")
        clean_query = {
            key: value
            for key, value in (query or {}).items()
            if value not in (None, "")
        }
        url = max_bot_api_base + path
        if clean_query:
            url += "?" + urllib.parse.urlencode(clean_query)
        body = json.dumps(data or {}, ensure_ascii=False).encode("utf-8") if data is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": max_bot_api_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            status = exc.code if 400 <= int(exc.code or 0) < 600 else 502
            raise HTTPException(status_code=status, detail=f"MAX API {method} {path}: {text[:900] or exc.reason}")
        except urllib.error.URLError as exc:
            raise HTTPException(status_code=502, detail=f"MAX API недоступен: {exc.reason}")
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    def max_action_button(action: dict) -> dict:
        action = action if isinstance(action, dict) else {}
        label = _text(action.get("label") or action.get("text") or action.get("title") or "Открыть", 80)
        action_id = _text(action.get("id") or action.get("actionId") or action.get("action_id"), 80)
        kind = _text(action.get("kind") or action.get("type"), 80)
        url = _text(action.get("url") or action.get("href"), 1000)
        if not url and kind in ("open_app", "link"):
            path = _text(action.get("path") or action.get("route") or "/app", 1000)
            if path.startswith("http://") or path.startswith("https://"):
                url = path
            else:
                if not path.startswith("/"):
                    path = "/" + path
                url = app_public_url + path
            entity_type = _text(action.get("entityType") or action.get("entity_type"), 120)
            entity_id = action.get("entityId") or action.get("entity_id")
            if entity_type and entity_id:
                separator = "&" if "?" in url else "?"
                url += separator + urllib.parse.urlencode({"entity": entity_type, "id": entity_id})
        if url:
            return {"type": "link", "text": label, "url": url}

        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        callback_payload = {
            **payload,
            "actionId": action_id or _text(payload.get("actionId") or payload.get("action_id"), 80),
            "endpoint": _text(action.get("endpoint") or payload.get("endpoint"), 255),
            "method": _text(action.get("method") or payload.get("method") or "POST", 20),
        }
        callback_payload = {key: value for key, value in callback_payload.items() if value not in (None, "")}
        return {
            "type": "callback",
            "text": label,
            "payload": json.dumps(callback_payload, ensure_ascii=False, separators=(",", ":"))[:1000],
        }

    def max_message_payload_from_outbox(row: dict) -> dict:
        row = row or {}
        title = _text(row.get("title"), 500)
        body = _text(row.get("body"), 3500)
        text = "\n\n".join(item for item in (title, body) if item).strip() or "Уведомление Stroyka"
        message = {"text": text[:4000], "notify": True}
        buttons = []
        for action in _json_array(row.get("actions_json"))[:6]:
            button = max_action_button(action)
            if button:
                buttons.append(button)
        if buttons:
            message["attachments"] = [{
                "type": "inline_keyboard",
                "payload": {"buttons": [buttons]},
            }]
        return message

    def max_provider_message_id(response: dict) -> str:
        response = response if isinstance(response, dict) else {}
        sources = [response]
        if isinstance(response.get("message"), dict):
            sources.append(response["message"])
        if isinstance(response.get("result"), dict):
            sources.append(response["result"])
        for source in sources:
            for key in ("message_id", "messageId", "id", "mid"):
                value = source.get(key)
                if value not in (None, ""):
                    return str(value)
        return ""

    def send_max_outbox_row(row: dict) -> tuple[dict, str, dict]:
        row = row or {}
        chat_id = _text(row.get("chat_id"), 120)
        user_id = _text(row.get("external_user_id"), 120)
        if not chat_id and not user_id:
            raise HTTPException(status_code=400, detail="У MAX outbox нет chat_id или external_user_id")
        query = {"chat_id": chat_id} if chat_id else {"user_id": user_id}
        payload = max_message_payload_from_outbox(row)
        response = max_api_request("POST", "/messages", data=payload, query=query)
        return response, max_provider_message_id(response), payload

    def max_update_list(data) -> list:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        data = data if isinstance(data, dict) else {}
        if isinstance(data.get("updates"), list):
            return [item for item in data["updates"] if isinstance(item, dict)]
        if isinstance(data.get("update"), dict):
            return [data["update"]]
        return [data] if data else []

    def max_nested_dict(data: dict, *keys: str) -> dict:
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, dict):
                return value
        return {}

    def max_user_name(user: dict) -> str:
        user = user if isinstance(user, dict) else {}
        return " ".join(
            item
            for item in (
                _text(user.get("first_name") or user.get("firstName"), 80),
                _text(user.get("last_name") or user.get("lastName"), 80),
            )
            if item
        ) or _text(user.get("username") or user.get("name"), 120)

    def max_update_chat_id(update: dict) -> str:
        message = max_nested_dict(update, "message")
        recipient = max_nested_dict(message, "recipient")
        callback = max_nested_dict(update, "callback")
        callback_message = max_nested_dict(callback, "message")
        callback_recipient = max_nested_dict(callback_message, "recipient")
        chat = max_nested_dict(update, "chat")
        return _payload_value(
            update,
            "chat_id",
            "chatId",
            "conversation_id",
            "conversationId",
        ) or _payload_value(
            message,
            "chat_id",
            "chatId",
        ) or _payload_value(
            recipient,
            "chat_id",
            "chatId",
        ) or _payload_value(
            callback,
            "chat_id",
            "chatId",
        ) or _payload_value(
            callback_recipient,
            "chat_id",
            "chatId",
        ) or _payload_value(
            chat,
            "id",
            "chat_id",
            "chatId",
        )

    def max_update_user(update: dict) -> dict:
        message = max_nested_dict(update, "message")
        callback = max_nested_dict(update, "callback")
        return (
            max_nested_dict(update, "user")
            or max_nested_dict(message, "sender", "user")
            or max_nested_dict(callback, "user")
        )

    def max_update_user_id(update: dict) -> str:
        user = max_update_user(update)
        message = max_nested_dict(update, "message")
        sender = max_nested_dict(message, "sender")
        callback = max_nested_dict(update, "callback")
        return _payload_value(
            user,
            "user_id",
            "userId",
            "id",
        ) or _payload_value(
            sender,
            "user_id",
            "userId",
            "id",
        ) or _payload_value(
            callback,
            "user_id",
            "userId",
        )

    def max_update_message_text(update: dict) -> str:
        message = max_nested_dict(update, "message")
        body = max_nested_dict(message, "body")
        return _text(
            body.get("text")
            or message.get("text")
            or update.get("text")
            or update.get("message_text")
            or update.get("messageText"),
            4000,
        )

    def max_update_source_id(update: dict) -> str:
        message = max_nested_dict(update, "message")
        callback = max_nested_dict(update, "callback")
        return _payload_value(
            message,
            "mid",
            "id",
            "message_id",
            "messageId",
        ) or _payload_value(
            callback,
            "message_id",
            "messageId",
            "id",
        ) or _payload_value(update, "message_id", "messageId", "mid", "id")

    def max_callback_payload(update: dict) -> dict:
        callback = max_nested_dict(update, "callback")
        raw_payload = (
            callback.get("payload")
            or callback.get("data")
            or update.get("payload")
            or update.get("callback_payload")
        )
        if isinstance(raw_payload, dict):
            return raw_payload
        if isinstance(raw_payload, str) and raw_payload.strip():
            try:
                parsed = json.loads(raw_payload)
                return parsed if isinstance(parsed, dict) else {"value": raw_payload}
            except Exception:
                return {"value": raw_payload}
        return {}

    def upsert_max_channel_from_update(cur, update: dict, chat_id: str) -> dict:
        update_type = _text(update.get("update_type") or update.get("updateType"), 80)
        is_channel = bool(update.get("is_channel") or update.get("isChannel"))
        channel_type = "internal"
        chat = max_nested_dict(update, "chat")
        title = _text(
            update.get("title")
            or update.get("chat_title")
            or update.get("chatTitle")
            or chat.get("title")
            or chat.get("name")
            or ("MAX внутренний канал " + chat_id if is_channel else "MAX внутренний диалог " + chat_id),
            255,
        )
        metadata = {
            "linkedByWebhook": True,
            "lastUpdateType": update_type,
            "isChannel": is_channel,
            "lastUserId": max_update_user_id(update),
            "lastUserName": max_user_name(max_update_user(update)),
        }
        cur.execute(
            """
            INSERT INTO messenger_channels
                (provider,chat_id,title,channel_type,source_label,default_stage,enabled,metadata_json)
            VALUES
                ('max',%s,%s,%s,%s,'Новый',TRUE,%s::jsonb)
            ON CONFLICT (provider, chat_id) DO UPDATE SET
                title=COALESCE(NULLIF(EXCLUDED.title,''), messenger_channels.title),
                source_label=COALESCE(NULLIF(messenger_channels.source_label,''), EXCLUDED.source_label),
                metadata_json=COALESCE(messenger_channels.metadata_json,'{}'::jsonb) || EXCLUDED.metadata_json,
                enabled=COALESCE(messenger_channels.enabled, TRUE),
                updated_at=NOW()
            RETURNING *
            """,
            (
                chat_id,
                title,
                channel_type,
                "MAX внутренний бот",
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        return cur.fetchone()

    def handle_max_webhook_update(update: dict) -> dict:
        update = update if isinstance(update, dict) else {}
        update_type = _text(update.get("update_type") or update.get("updateType"), 80)
        chat_id = max_update_chat_id(update)
        user_id = max_update_user_id(update)
        source_id = max_update_source_id(update)
        if update_type in ("bot_added", "bot_started", "chat_title_changed") and chat_id:
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                channel = upsert_max_channel_from_update(cur, update, chat_id)
                conn.commit()
                return {"ok": True, "action": "channel_linked", "updateType": update_type, "channel": _public_messenger_channel(channel)}
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()

        if update_type == "message_created" and chat_id:
            text = max_update_message_text(update)
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                channel = find_messenger_channel(cur, "max", chat_id)
            finally:
                cur.close()
                conn.close()
            if channel and bool(channel.get("enabled", True)) and (channel.get("channel_type") or "") == "marketing":
                lead_result = create_max_marketing_lead(
                    {
                        "maxChatId": chat_id,
                        "maxUserId": user_id,
                        "name": max_user_name(max_update_user(update)),
                        "username": _text(max_update_user(update).get("username"), 120),
                        "message": text,
                        "sourceId": source_id,
                        "maxUser": max_update_user(update),
                        "data": update,
                    },
                    _bot={"role": "max_bot", "name": "MAX Bot"},
                )
                return {"ok": True, "action": "marketing_lead_created", "updateType": update_type, "lead": lead_result.get("lead")}
            return {"ok": True, "action": "message_ignored", "updateType": update_type, "reason": "not_marketing_channel", "chatId": chat_id}

        if update_type == "message_callback":
            payload = max_callback_payload(update)
            action_id = _text(payload.get("actionId") or payload.get("action_id") or payload.get("id") or payload.get("value"), 80)
            endpoint = _text(payload.get("endpoint"), 255)
            draft_token = _text(payload.get("draftToken") or payload.get("draft_token"), 120)
            actor = {"maxUserId": user_id, "maxChatId": chat_id, "draftToken": draft_token}
            if action_id == "confirm" or endpoint.endswith("/max/warehouse-invoices/confirm"):
                if not draft_token:
                    return {"ok": True, "action": "callback_ignored", "updateType": update_type, "reason": "missing_draft_token"}
                result = confirm_max_warehouse_invoice(actor, _bot={"role": "max_bot", "name": "MAX Bot"})
                return {"ok": True, "action": "invoice_confirmed", "updateType": update_type, "result": result}
            if action_id == "reject" or endpoint.endswith("/max/warehouse-invoices/reject"):
                if not draft_token:
                    return {"ok": True, "action": "callback_ignored", "updateType": update_type, "reason": "missing_draft_token"}
                result = reject_max_warehouse_invoice(actor, _bot={"role": "max_bot", "name": "MAX Bot"})
                return {"ok": True, "action": "invoice_rejected", "updateType": update_type, "result": result}
            return {"ok": True, "action": "callback_ignored", "updateType": update_type, "payload": payload}

        return {"ok": True, "action": "ignored", "updateType": update_type or "unknown", "chatId": chat_id}

    def append_file_urls_to_payload(payload: dict, files: list) -> dict:
        payload = dict(payload or {})
        urls = [item.get("url") for item in files or [] if item.get("url")]
        if not urls:
            return payload
        current = payload.get("photos") or payload.get("photoUrls") or []
        if isinstance(current, str):
            current = _json_list(current)
        if not isinstance(current, list):
            current = []
        photos = []
        for url in [*current, *urls]:
            if url and url not in photos:
                photos.append(url)
        payload["photos"] = photos
        payload["photoUrls"] = photos
        payload["photoUrl"] = payload.get("photoUrl") or (photos[0] if photos else "")
        payload["maxFiles"] = [
            {
                "id": item.get("id"),
                "url": item.get("url"),
                "fileToken": item.get("fileToken") or "",
                "filename": item.get("filename") or "",
            }
            for item in files or []
        ]
        return payload

    channel_types = {
        "marketing",
        "object",
        "supply",
        "accounting",
        "director",
        "alerts",
        "internal",
    }

    def normalize_channel_payload(data: dict, existing: dict = None) -> dict:
        data = data or {}
        existing = existing or {}
        provider = _text(data.get("provider") or existing.get("provider") or "max", 40).lower()
        if provider not in ("max", "telegram"):
            raise HTTPException(status_code=400, detail="Поддерживаются только provider=max или provider=telegram")
        chat_id = _text(
            data.get("chatId")
            or data.get("chat_id")
            or data.get("maxChatId")
            or data.get("telegramChatId")
            or existing.get("chat_id"),
            120,
        )
        if not chat_id:
            raise HTTPException(status_code=400, detail="Нужен chatId канала")
        channel_type = _text(data.get("channelType") or data.get("channel_type") or existing.get("channel_type") or "marketing", 80)
        if channel_type not in channel_types:
            raise HTTPException(status_code=400, detail="Недопустимый тип канала")
        return {
            "provider": provider,
            "chatId": chat_id,
            "title": _text(data.get("title") if "title" in data else existing.get("title"), 255),
            "channelType": channel_type,
            "projectName": _text(
                data.get("projectName") if "projectName" in data else data.get("project_name") if "project_name" in data else existing.get("project_name"),
                500,
            ),
            "sourceLabel": _text(
                data.get("sourceLabel") if "sourceLabel" in data else data.get("source_label") if "source_label" in data else existing.get("source_label"),
                255,
            ),
            "campaignCode": _text(
                data.get("campaignCode") if "campaignCode" in data else data.get("campaign_code") if "campaign_code" in data else existing.get("campaign_code"),
                120,
            ),
            "defaultStage": _text(
                data.get("defaultStage") if "defaultStage" in data else data.get("default_stage") if "default_stage" in data else existing.get("default_stage") or "Новый",
                80,
            ) or "Новый",
            "enabled": _bool_value(data.get("enabled"), bool(existing.get("enabled", True))),
            "metadata": _json_dict(
                data.get("metadata")
                if "metadata" in data
                else data.get("metadata_json")
                if "metadata_json" in data
                else existing.get("metadata_json")
            ),
        }

    def fetch_channel(cur, channel_id: int):
        cur.execute("SELECT * FROM messenger_channels WHERE id=%s", (channel_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Канал мессенджера не найден")
        return row

    def find_messenger_channel(cur, provider: str, chat_id: str):
        cur.execute(
            """
            SELECT *
              FROM messenger_channels
             WHERE provider=%s AND chat_id=%s
             LIMIT 1
            """,
            (_text(provider, 40).lower(), _text(chat_id, 120)),
        )
        return cur.fetchone()

    def max_marketing_lead_payload(data: dict) -> dict:
        data = data or {}
        source = data.get("data") if isinstance(data.get("data"), dict) else {}
        merged = dict(source)
        merged.update({key: value for key, value in data.items() if key != "data"})
        return merged

    def max_lead_source(channel: dict, data: dict) -> str:
        campaign = _text(data.get("campaignCode") or data.get("campaign_code") or channel.get("campaign_code"), 120)
        label = _text(
            data.get("source")
            or data.get("sourceLabel")
            or channel.get("source_label")
            or channel.get("title")
            or campaign
            or channel.get("chat_id")
            or "MAX",
            220,
        )
        source = "MAX: " + label
        if campaign and campaign not in source:
            source += " / " + campaign
        return source[:255]

    def max_lead_notes(channel: dict, data: dict) -> str:
        max_user = data.get("maxUser") if isinstance(data.get("maxUser"), dict) else data.get("user") if isinstance(data.get("user"), dict) else {}
        utm = data.get("utm") if isinstance(data.get("utm"), dict) else {}
        lines = []
        message = _text(data.get("message") or data.get("text") or data.get("comment") or data.get("caption"), 2000)
        if message:
            lines.append("Сообщение MAX: " + message)
        lines.append("MAX канал: " + (channel.get("title") or channel.get("chat_id") or "не указан"))
        lines.append("MAX chatId: " + (channel.get("chat_id") or ""))
        campaign = _text(data.get("campaignCode") or data.get("campaign_code") or channel.get("campaign_code"), 120)
        if campaign:
            lines.append("Кампания: " + campaign)
        max_user_id = _payload_value(data, "maxUserId", "max_user_id", "userId", "user_id", "fromUserId", "senderId")
        username = _text(data.get("username") or max_user.get("username"), 120)
        if max_user_id or username:
            lines.append("MAX пользователь: " + " ".join(item for item in (max_user_id, username) if item))
        source_id = _payload_value(data, "sourceId", "source_id", "maxMessageId", "messageId", "mid")
        if source_id:
            lines.append("MAX сообщение: " + source_id)
        if utm:
            lines.append("UTM: " + json.dumps(utm, ensure_ascii=False, sort_keys=True))
        extra_notes = _text(data.get("notes"), 1200)
        if extra_notes:
            lines.append(extra_notes)
        return "\n".join(lines)[:4000]

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

    @app.get("/messenger-channels")
    def list_messenger_channels(
        provider: str = Query(default="max"),
        channel_type: str = Query(default=""),
        current_user: dict = Depends(require_roles(*leadership_roles, "менеджер_crm")),
    ):
        provider = _text(provider or "max", 40).lower()
        channel_type = _text(channel_type, 80)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if channel_type:
                cur.execute(
                    """
                    SELECT *
                      FROM messenger_channels
                     WHERE provider=%s AND channel_type=%s
                     ORDER BY enabled DESC, id DESC
                     LIMIT 500
                    """,
                    (provider, channel_type),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                      FROM messenger_channels
                     WHERE provider=%s
                     ORDER BY enabled DESC, channel_type, id DESC
                     LIMIT 500
                    """,
                    (provider,),
                )
            return {"ok": True, "items": [_public_messenger_channel(row) for row in cur.fetchall()]}
        finally:
            cur.close()
            conn.close()

    @app.post("/messenger-channels")
    def upsert_messenger_channel(data: dict, current_user: dict = Depends(require_roles(*leadership_roles, "менеджер_crm"))):
        payload = normalize_channel_payload(data or {})
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
                INSERT INTO messenger_channels
                    (provider,chat_id,title,channel_type,project_name,source_label,campaign_code,default_stage,enabled,metadata_json)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (provider, chat_id) DO UPDATE SET
                    title=EXCLUDED.title,
                    channel_type=EXCLUDED.channel_type,
                    project_name=EXCLUDED.project_name,
                    source_label=EXCLUDED.source_label,
                    campaign_code=EXCLUDED.campaign_code,
                    default_stage=EXCLUDED.default_stage,
                    enabled=EXCLUDED.enabled,
                    metadata_json=EXCLUDED.metadata_json,
                    updated_at=NOW()
                RETURNING *
                """,
                (
                    payload["provider"],
                    payload["chatId"],
                    payload["title"],
                    payload["channelType"],
                    payload["projectName"],
                    payload["sourceLabel"],
                    payload["campaignCode"],
                    payload["defaultStage"],
                    payload["enabled"],
                    json.dumps(payload["metadata"], ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {"ok": True, "channel": _public_messenger_channel(row)}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.patch("/messenger-channels/{channel_id}")
    def update_messenger_channel(channel_id: int, data: dict, current_user: dict = Depends(require_roles(*leadership_roles, "менеджер_crm"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            existing = fetch_channel(cur, channel_id)
            payload = normalize_channel_payload(data or {}, existing)
            cur.execute(
                """
                UPDATE messenger_channels
                   SET provider=%s,
                       chat_id=%s,
                       title=%s,
                       channel_type=%s,
                       project_name=%s,
                       source_label=%s,
                       campaign_code=%s,
                       default_stage=%s,
                       enabled=%s,
                       metadata_json=%s::jsonb,
                       updated_at=NOW()
                 WHERE id=%s
             RETURNING *
                """,
                (
                    payload["provider"],
                    payload["chatId"],
                    payload["title"],
                    payload["channelType"],
                    payload["projectName"],
                    payload["sourceLabel"],
                    payload["campaignCode"],
                    payload["defaultStage"],
                    payload["enabled"],
                    json.dumps(payload["metadata"], ensure_ascii=False),
                    channel_id,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {"ok": True, "channel": _public_messenger_channel(row)}
        except Exception:
            conn.rollback()
            raise
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

    @app.post("/max/marketing-leads")
    def create_max_marketing_lead(data: dict, _bot: dict = Depends(require_max_bot_token)):
        lead_data = max_marketing_lead_payload(data or {})
        chat_id = _payload_value(
            lead_data,
            "maxChatId",
            "max_chat_id",
            "chatId",
            "chat_id",
            "channelId",
            "channel_id",
        )
        if not chat_id:
            raise HTTPException(status_code=400, detail="Нужен maxChatId/chatId маркетингового MAX-канала")

        contact = lead_data.get("contact") if isinstance(lead_data.get("contact"), dict) else {}
        max_user = (
            lead_data.get("maxUser")
            if isinstance(lead_data.get("maxUser"), dict)
            else lead_data.get("user")
            if isinstance(lead_data.get("user"), dict)
            else {}
        )
        name = _text(
            lead_data.get("name")
            or lead_data.get("fullName")
            or lead_data.get("contactName")
            or contact.get("name")
            or " ".join(
                item
                for item in (
                    _text(contact.get("firstName") or max_user.get("first_name"), 80),
                    _text(contact.get("lastName") or max_user.get("last_name"), 80),
                )
                if item
            )
            or lead_data.get("username")
            or max_user.get("username")
            or "Лид из MAX",
            255,
        )
        phone = _text(lead_data.get("phone") or lead_data.get("phoneNumber") or contact.get("phone"), 80)
        email = _text(lead_data.get("email") or contact.get("email"), 255)
        budget = _num_value(lead_data.get("budget") or lead_data.get("amount"))
        lead_type = _text(lead_data.get("leadType") or lead_data.get("lead_type") or "Клиент", 80)
        review_status = _text(lead_data.get("reviewStatus") or lead_data.get("review_status") or "Новая", 80)

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            channel = find_messenger_channel(cur, "max", chat_id)
            if not channel:
                raise HTTPException(status_code=404, detail="MAX-канал не привязан как маркетинговый источник")
            if not bool(channel.get("enabled", True)):
                raise HTTPException(status_code=403, detail="MAX-канал отключен")
            if (channel.get("channel_type") or "") != "marketing":
                raise HTTPException(status_code=409, detail="Этот MAX-канал не является маркетинговым")

            source = max_lead_source(channel, lead_data)
            stage = _text(lead_data.get("stage") or channel.get("default_stage") or "Новый", 80) or "Новый"
            notes = max_lead_notes(channel, lead_data)
            created_at = dt.datetime.utcnow().strftime("%Y-%m-%d")
            cur.execute(
                """
                INSERT INTO crm_leads
                    (name,phone,email,source,budget,notes,stage,created_by,created_at,
                     lead_type,review_status)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id,name,phone,email,source,budget,notes,stage,
                          created_by,created_at,project_id,photo_url,
                          COALESCE(lead_type,'Клиент') AS lead_type,
                          COALESCE(review_status,'Новая') AS review_status
                """,
                (
                    name,
                    phone,
                    email,
                    source,
                    budget,
                    notes,
                    stage,
                    "MAX",
                    created_at,
                    lead_type,
                    review_status,
                ),
            )
            lead = cur.fetchone()
            conn.commit()
            return {
                "ok": True,
                "lead": {
                    "id": lead.get("id"),
                    "name": lead.get("name") or "",
                    "phone": lead.get("phone") or "",
                    "email": lead.get("email") or "",
                    "source": lead.get("source") or "",
                    "budget": float(lead.get("budget") or 0),
                    "notes": lead.get("notes") or "",
                    "stage": lead.get("stage") or "Новый",
                    "createdBy": lead.get("created_by") or "",
                    "createdAt": lead.get("created_at") or "",
                    "projectId": lead.get("project_id"),
                    "photoUrl": lead.get("photo_url") or "",
                    "leadType": lead.get("lead_type") or "Клиент",
                    "reviewStatus": lead.get("review_status") or "Новая",
                },
                "channel": _public_messenger_channel(channel),
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

    @app.get("/max/bot/status")
    def get_max_bot_status(
        include_subscriptions: bool = Query(default=False),
        _bot: dict = Depends(require_max_bot_token),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
                SELECT COALESCE(channel_type,'') AS channel_type, COUNT(*) AS count
                  FROM messenger_channels
                 WHERE provider='max'
                 GROUP BY COALESCE(channel_type,'')
                 ORDER BY channel_type
                """
            )
            channel_summary = {
                row.get("channel_type") or "unknown": int(row.get("count") or 0)
                for row in cur.fetchall()
            }
            cur.execute(
                """
                SELECT *
                  FROM messenger_channels
                 WHERE provider='max'
                 ORDER BY updated_at DESC, id DESC
                 LIMIT 50
                """
            )
            channels = [_public_messenger_channel(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT COALESCE(status,'') AS status, COUNT(*) AS count
                  FROM messenger_outbox
                 WHERE provider='max'
                 GROUP BY COALESCE(status,'')
                 ORDER BY status
                """
            )
            outbox_summary = {
                row.get("status") or "unknown": int(row.get("count") or 0)
                for row in cur.fetchall()
            }
            cur.execute(
                """
                SELECT COUNT(*) AS count
                  FROM messenger_accounts
                 WHERE provider='max' AND COALESCE(enabled,TRUE)=TRUE
                """
            )
            accounts_row = cur.fetchone() or {}
            response = {
                "ok": True,
                "bot": {
                    "provider": "max",
                    "webhookConfigured": bool(max_webhook_secret),
                    "apiTokenConfigured": bool(max_bot_api_token),
                    "apiBase": max_bot_api_base,
                },
                "channelSummary": channel_summary,
                "channels": channels,
                "outboxSummary": outbox_summary,
                "activeMessengerAccountLinks": int(accounts_row.get("count") or 0),
            }
            if include_subscriptions:
                try:
                    response["subscriptions"] = max_api_request("GET", "/subscriptions")
                except HTTPException as exc:
                    response["subscriptionsError"] = exc.detail
            return response
        finally:
            cur.close()
            conn.close()

    @app.post("/max/outbox/dispatch")
    def dispatch_max_outbox(
        limit: int = Query(default=20, ge=1, le=100),
        dry_run: bool = Query(default=False),
        _bot: dict = Depends(require_max_bot_token),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sent = []
        failed = []
        planned = []
        try:
            cur.execute(
                """
                SELECT *
                  FROM messenger_outbox
                 WHERE provider='max'
                   AND status='queued'
                   AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
                 ORDER BY priority ASC, id ASC
                 LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            for row in rows:
                payload = max_message_payload_from_outbox(row)
                target = {
                    "chatId": row.get("chat_id") or "",
                    "userId": row.get("external_user_id") or "",
                }
                if dry_run:
                    planned.append({
                        "id": row.get("id"),
                        "eventType": row.get("event_type") or "",
                        "target": target,
                        "message": payload,
                    })
                    continue
                try:
                    response, provider_message_id, _payload = send_max_outbox_row(row)
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
                        (provider_message_id, row.get("id")),
                    )
                    updated = cur.fetchone()
                    sent.append({
                        "id": row.get("id"),
                        "providerMessageId": provider_message_id,
                        "response": response,
                        "item": _public_messenger_outbox_item(updated),
                    })
                except Exception as exc:
                    detail = getattr(exc, "detail", str(exc)) or "MAX delivery failed"
                    cur.execute(
                        """
                        UPDATE messenger_outbox
                           SET status='failed',
                               attempts=COALESCE(attempts,0)+1,
                               last_error=%s,
                               failed_at=NOW(),
                               next_attempt_at=NOW() + INTERVAL '5 minutes',
                               updated_at=NOW()
                         WHERE provider='max' AND id=%s
                     RETURNING *
                        """,
                        (_text(detail, 1000), row.get("id")),
                    )
                    updated = cur.fetchone()
                    failed.append({
                        "id": row.get("id"),
                        "error": _text(detail, 1000),
                        "item": _public_messenger_outbox_item(updated),
                    })
            if not dry_run:
                conn.commit()
            return {"ok": True, "dryRun": dry_run, "planned": planned, "sent": sent, "failed": failed}
        except Exception:
            conn.rollback()
            raise
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

    @app.get("/max/webhook/subscriptions")
    def list_max_webhook_subscriptions(_bot: dict = Depends(require_max_bot_token)):
        result = max_api_request("GET", "/subscriptions")
        return {"ok": True, "result": result}

    @app.post("/max/webhook/subscribe")
    def subscribe_max_webhook(data: Optional[dict] = None, _bot: dict = Depends(require_max_bot_token)):
        data = data or {}
        url = _text(data.get("url") or data.get("webhookUrl") or data.get("webhook_url"), 1000)
        if not url:
            url = app_public_url + "/max/webhook"
        if not url.startswith("https://"):
            raise HTTPException(status_code=400, detail="MAX webhook должен быть HTTPS URL")
        update_types = data.get("updateTypes") or data.get("update_types") or [
            "bot_added",
            "bot_started",
            "chat_title_changed",
            "message_created",
            "message_callback",
        ]
        if not isinstance(update_types, list):
            update_types = []
        body = {
            "url": url,
            "update_types": [_text(item, 80) for item in update_types if _text(item, 80)],
        }
        if max_webhook_secret:
            body["secret"] = max_webhook_secret
        result = max_api_request("POST", "/subscriptions", data=body)
        return {"ok": True, "subscription": body, "result": result}

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

    @app.post("/max/files")
    def upload_max_file(data: dict, _bot: dict = Depends(require_max_bot_token)):
        data = data or {}
        max_user_id, max_chat_id = _max_actor_from_data(data)
        employee = resolve_max_employee(max_user_id, max_chat_id)
        project_name = _text(data.get("projectName") or data.get("project") or data.get("location"), 255)
        if project_name == "Основной склад" and main_warehouse_write_roles and employee.get("role") not in main_warehouse_write_roles:
            raise HTTPException(status_code=403, detail="Прораб через MAX принимает файлы накладных только на закрепленный объектный склад")
        if project_name and project_name != "Основной склад" and not _employee_has_project_access(employee, project_name, deps):
            raise HTTPException(status_code=403, detail="У сотрудника нет доступа к объекту")
        context = _text(data.get("context") or "max-invoices", 120)
        draft_token = _text(data.get("draftToken") or data.get("draft_token"), 120)

        items = _max_file_items(data)
        if not items and any(
            data.get(key)
            for key in ("contentBase64", "content_base64", "base64", "dataUrl", "data_url", "content")
        ):
            items = [data]
        if not items:
            raise HTTPException(status_code=400, detail="Нужен MAX-файл в files[] или contentBase64")

        saved_files = [
            persist_max_file_item(item, employee, max_user_id, max_chat_id, project_name, context)
            for item in items
        ]
        draft = None
        if draft_token:
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute("SELECT * FROM max_invoice_drafts WHERE draft_token=%s FOR UPDATE", (draft_token,))
                draft_row = cur.fetchone()
                if not draft_row:
                    raise HTTPException(status_code=404, detail="MAX-черновик накладной не найден")
                if (
                    draft_row.get("messenger_account_id")
                    and employee.get("messengerAccountId")
                    and draft_row.get("messenger_account_id") != employee.get("messengerAccountId")
                ):
                    raise HTTPException(status_code=403, detail="MAX-черновик создан другим сотрудником")
                payload = append_file_urls_to_payload(_json_dict(draft_row.get("payload_json")), saved_files)
                cur.execute(
                    """
                    UPDATE max_invoice_drafts
                       SET payload_json=%s::jsonb,
                           updated_at=NOW()
                     WHERE id=%s
                 RETURNING *
                    """,
                    (json.dumps(payload, ensure_ascii=False), draft_row["id"]),
                )
                draft_row = cur.fetchone()
                for item in saved_files:
                    cur.execute(
                        """
                        UPDATE messenger_files
                           SET entity_type='max_invoice_draft',
                               entity_id=%s,
                               updated_at=NOW()
                         WHERE id=%s
                        """,
                        (draft_row["id"], item.get("id")),
                    )
                conn.commit()
                draft_row["employee_name"] = employee.get("name") or ""
                draft_row["employee_role"] = employee.get("role") or ""
                draft = _public_max_invoice_draft(draft_row, payload=payload)
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()
        return {"ok": True, "files": saved_files, "file": saved_files[0] if saved_files else None, "draft": draft}

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

    @app.post("/max/webhook")
    def max_webhook(data: dict, _bot: dict = Depends(require_max_bot_token)):
        updates = max_update_list(data)
        results = []
        for update in updates:
            results.append(handle_max_webhook_update(update))
        return {"ok": True, "count": len(results), "results": results}
