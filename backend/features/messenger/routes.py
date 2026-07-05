import datetime as dt
import hashlib
import json
import hmac
import time
import urllib.parse
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

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

    @app.post("/max/warehouse-invoices")
    def create_max_warehouse_invoice(data: dict, _bot: dict = Depends(require_max_bot_token)):
        data = data or {}
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

        result = create_warehouse_invoice_record(payload, employee)
        accounting_link = None
        if _bool_value(data.get("syncAccounting"), True) and sync_supplier_invoice_from_warehouse:
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
            "projectName": target_project,
            "location": payload["location"],
            "sourceType": payload["sourceType"],
            "recognized": bool(recognized),
            "recognition": payload.get("recognition") or {},
            "accountingLink": accounting_link,
        })
        return result
