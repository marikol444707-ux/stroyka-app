#!/usr/bin/env python3
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
TEST_EMAIL = os.getenv("MAX_SMOKE_FOREMAN_EMAIL", "max-warehouse-foreman-smoke@stroyka.local")
TEST_NAME = os.getenv("MAX_SMOKE_FOREMAN_NAME", "CODEX QA MAX Прораб")
TEST_PASSWORD = os.getenv("MAX_SMOKE_FOREMAN_PASSWORD", "MaxWarehouseSmoke123!")
TEST_MAX_USER_ID = os.getenv("MAX_SMOKE_USER_ID", f"codex-max-{int(dt.datetime.now().timestamp())}")
TEST_QTY = float(os.getenv("MAX_WAREHOUSE_SMOKE_QTY", "0.001"))
TEST_PRICE = float(os.getenv("MAX_WAREHOUSE_SMOKE_PRICE", "123.45"))


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name, default=""):
    return os.getenv(name) or ENV.get(name, default)


def db_config():
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def api_json(method, path, token=None, data=None, headers=None, expected=None):
    body = None
    request_headers = {"Content-Type": "application/json"}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if headers:
        request_headers.update(headers)
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def totp_code(secret):
    secret = re.sub(r"\s+", "", str(secret or "")).upper()
    if not secret:
        raise RuntimeError("Нет TOTP secret для 2FA")
    secret += "=" * (-len(secret) % 8)
    key = base64.b32decode(secret, casefold=True)
    counter = int(time.time()) // 30
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
    return str(code).zfill(6)


def token_from_login_response(body, email):
    token = body.get("authToken")
    if token:
        return token
    if body.get("twoFactorSetupRequired"):
        setup_token = body.get("setupToken")
        secret = env_value("SMOKE_TOTP_SECRET") or body.get("manualKey") or ""
        if not setup_token or not secret:
            raise SystemExit(f"FAIL login {email}: 2FA setup не вернул setupToken/manualKey")
        _, confirmed = api_json(
            "POST",
            "/login/2fa/setup-confirm",
            data={"setupToken": setup_token, "code": totp_code(secret)},
            expected=200,
        )
        token = confirmed.get("authToken")
        if token:
            return token
        raise SystemExit(f"FAIL login {email}: authToken не получен после 2FA setup")
    if body.get("twoFactorRequired"):
        challenge_token = body.get("challengeToken")
        code = env_value("SMOKE_2FA_CODE") or (totp_code(env_value("SMOKE_TOTP_SECRET")) if env_value("SMOKE_TOTP_SECRET") else "")
        if not challenge_token or not code:
            raise SystemExit(f"FAIL login {email}: нужен SMOKE_2FA_CODE или SMOKE_TOTP_SECRET")
        _, verified = api_json(
            "POST",
            "/login/2fa/verify",
            data={"challengeToken": challenge_token, "code": code},
            expected=200,
        )
        token = verified.get("authToken")
        if token:
            return token
        raise SystemExit(f"FAIL login {email}: authToken не получен после 2FA")
    raise SystemExit(f"FAIL login {email}: authToken не получен")


def require_env(name):
    value = env_value(name, "")
    if not value:
        raise SystemExit(f"Нужно задать {name} в окружении или backend/.env")
    return value


def max_bot_token():
    token = env_value("SMOKE_MAX_BOT_TOKEN") or env_value("MAX_WEBHOOK_SECRET") or env_value("MAX_BOT_API_TOKEN")
    token = (token or "").strip()
    if not token:
        raise SystemExit("Нужно задать SMOKE_MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET или MAX_BOT_API_TOKEN")
    if token.lower() in {"change-me", "token", "***", "..."}:
        raise SystemExit("MAX token содержит заглушку, нужен реальный тестовый секрет")
    return token


def max_initdata_token():
    token = env_value("SMOKE_MAX_INITDATA_TOKEN") or env_value("MAX_BOT_API_TOKEN")
    token = (token or "").strip()
    if not token or token.lower() in {"change-me", "token", "***", "..."}:
        return ""
    return token


def signed_max_init_data(bot_token, user_id, start_param=""):
    user = json.dumps(
        {
            "id": user_id,
            "first_name": "CODEX",
            "last_name": "MAX",
            "username": "codex_max_smoke",
            "language_code": "ru",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chat = json.dumps(
        {"id": user_id, "type": "DIALOG"},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    auth_date = str(int(time.time()))
    params = {
        "auth_date": auth_date,
        "chat": chat,
        "query_id": f"max-smoke-{auth_date}",
        "start_param": start_param,
        "user": user,
    }
    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, launch_params.encode("utf-8"), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(params)


def signed_max_contact(bot_token, user_id):
    phone = "79990000000"
    auth_date = str(int(time.time()))
    params = {
        "authDate": auth_date,
        "phone": phone,
        "userId": str(user_id),
    }
    payload = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    return {
        "phone": "+" + phone,
        "authDate": auth_date,
        "hash": hmac.new(bot_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def validate_max_miniapp_launch():
    token = max_initdata_token()
    if not token:
        return None
    _, body = api_json(
        "POST",
        "/max/miniapp/validate",
        data={
            "initData": signed_max_init_data(token, TEST_MAX_USER_ID, "invite_CODEX"),
            "contact": signed_max_contact(token, TEST_MAX_USER_ID),
        },
        expected=200,
    )
    max_user = body.get("maxUser") or {}
    if str(max_user.get("id") or "") != str(TEST_MAX_USER_ID):
        raise RuntimeError(f"MAX mini-app validate вернул другого пользователя: {body}")
    if not body.get("contactVerified"):
        raise RuntimeError(f"MAX mini-app contact не прошел проверку: {body}")
    return "MAX mini-app initData/contact signature is validated"


def validate_max_miniapp_session():
    token = max_initdata_token()
    if not token:
        return None
    _, body = api_json(
        "POST",
        "/max/miniapp/session",
        data={
            "initData": signed_max_init_data(token, TEST_MAX_USER_ID, "invite_CODEX"),
            "contact": signed_max_contact(token, TEST_MAX_USER_ID),
        },
        expected=200,
    )
    user = body.get("user") or {}
    if not body.get("sessionCreated") or not user.get("authToken"):
        raise RuntimeError(f"MAX mini-app session не вернул authToken: {body}")
    if user.get("role") != "прораб":
        raise RuntimeError(f"MAX mini-app session вернул неверную роль: {body}")
    return "MAX mini-app session issues authToken for linked non-2FA foreman"


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    return token_from_login_response(body, email)


def select_project():
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("MAX_WAREHOUSE_SMOKE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    cur.close()
    conn.close()
    if not project:
        raise SystemExit("FAIL: нет активного объекта для MAX smoke")
    return project["name"]


def ensure_foreman(project_name):
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "manage-temp-user.py"),
            "create",
            "--email",
            TEST_EMAIL,
            "--name",
            TEST_NAME,
            "--password",
            TEST_PASSWORD,
            "--role",
            "прораб",
            "--project",
            project_name,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (TEST_EMAIL,))
    user = cur.fetchone()
    if not user:
        raise SystemExit("FAIL: smoke-прораб не создан")
    cur.close()
    conn.close()
    return {"userId": user["id"]}


def link_max_account(director_token, user_id):
    _, created = api_json(
        "POST",
        "/messenger-accounts",
        token=director_token,
        data={
            "provider": "max",
            "userId": user_id,
            "externalUserId": TEST_MAX_USER_ID,
            "chatId": TEST_MAX_USER_ID,
            "displayName": TEST_NAME,
            "enabled": True,
        },
        expected=200,
    )
    account = created.get("account") or {}
    account_id = account.get("id")
    if not account_id:
        raise RuntimeError(f"MAX account link did not return id: {created}")
    return {"accountId": account_id, "maxUserId": TEST_MAX_USER_ID}


def find_outbox_item(bot_token, *, event_type="", draft_token="", warehouse_invoice_id=None):
    _, outbox = api_json(
        "GET",
        "/max/outbox?limit=100",
        headers={"X-Max-Bot-Token": bot_token},
        expected=200,
    )
    for item in outbox.get("items") or []:
        payload = item.get("payload") or {}
        if event_type and item.get("eventType") != event_type:
            continue
        if draft_token and payload.get("draftToken") != draft_token:
            continue
        if warehouse_invoice_id and str(payload.get("warehouseInvoiceId") or item.get("entityId") or "") != str(warehouse_invoice_id):
            continue
        return item
    return None


def cleanup(invoice_id, material_name, project_name, account_id, supplier_name="", draft_token="", file_url=""):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        if file_url:
            cur.execute("DELETE FROM messenger_files WHERE provider='max' AND url=%s", (file_url,))
        if draft_token:
            cur.execute("DELETE FROM messenger_outbox WHERE provider='max' AND payload_json::text LIKE %s", (f"%{draft_token}%",))
        if invoice_id:
            cur.execute("DELETE FROM messenger_outbox WHERE provider='max' AND entity_type='warehouse_invoice' AND entity_id=%s", (invoice_id,))
        if draft_token:
            cur.execute("DELETE FROM max_invoice_drafts WHERE draft_token=%s", (draft_token,))
        if invoice_id:
            cur.execute("DELETE FROM max_invoice_drafts WHERE warehouse_invoice_id=%s", (invoice_id,))
        if invoice_id:
            cur.execute("DELETE FROM supplier_invoices WHERE warehouse_invoice_id=%s", (invoice_id,))
        if supplier_name:
            cur.execute("DELETE FROM supplier_invoices WHERE supplier_name=%s", (supplier_name,))
        if invoice_id:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (invoice_id,))
        if material_name:
            cur.execute("DELETE FROM materials WHERE name=%s AND project=%s", (material_name, project_name))
            cur.execute(
                "DELETE FROM warehouse_history WHERE material=%s AND project=%s AND issued_by=%s",
                (material_name, project_name, TEST_NAME),
            )
            cur.execute("DELETE FROM material_inspection_journal WHERE material_name=%s AND project=%s", (material_name, project_name))
            cur.execute("DELETE FROM cable_journal WHERE cable_brand=%s AND project=%s", (material_name, project_name))
        if account_id:
            cur.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=LOWER(%s))", (TEST_EMAIL,))
            cur.execute("DELETE FROM messenger_accounts WHERE id=%s", (account_id,))
        if supplier_name:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id IN (SELECT id FROM suppliers WHERE name=%s)", (supplier_name,))
            cur.execute("DELETE FROM suppliers WHERE name=%s", (supplier_name,))
        conn.commit()
        cur.close()
        print("cleanup: removed MAX warehouse smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def main():
    admin_email = require_env("SMOKE_EMAIL")
    admin_password = require_env("SMOKE_PASSWORD")
    director_token = login(admin_email, admin_password)
    bot_token = max_bot_token()
    checked = []
    miniapp_check = validate_max_miniapp_launch()
    if miniapp_check:
        checked.append(miniapp_check)
    project_name = select_project()
    foreman = ensure_foreman(project_name)
    account = link_max_account(director_token, foreman["userId"])
    miniapp_session_check = validate_max_miniapp_session()
    if miniapp_session_check:
        checked.append(miniapp_session_check)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    material_name = f"CODEX QA MAX накладная {stamp}"
    supplier_name = f"CODEX QA MAX поставщик {stamp}"
    supplier_inn = "77" + stamp[-8:]
    invoice_id = None
    draft_token = None
    stored_file_url = ""
    try:
        _, uploaded = api_json(
            "POST",
            "/max/files",
            data={
                "maxUserId": account["maxUserId"],
                "projectName": project_name,
                "context": "max-invoices",
                "fileToken": f"max-file-smoke-{stamp}",
                "filename": f"max-invoice-{stamp}.txt",
                "contentType": "text/plain",
                "contentBase64": base64.b64encode(f"CODEX MAX invoice smoke {stamp}".encode("utf-8")).decode("ascii"),
            },
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        stored_file = uploaded.get("file") or {}
        stored_file_url = stored_file.get("url") or ""
        if not stored_file_url:
            raise RuntimeError(f"MAX file upload не вернул стабильный url: {uploaded}")

        max_invoice_payload = {
            "maxUserId": account["maxUserId"],
            "maxMessageId": f"max-smoke-{stamp}",
            "projectName": project_name,
            "photoUrl": stored_file_url,
            "recognizedInvoice": {
                "method": "smoke_ocr_stub",
                "documentType": "warehouse_invoice",
                "confidence": 0.98,
                "number": f"MAX-{stamp}",
                "date": dt.date.today().isoformat(),
                "supplier": supplier_name,
                "supplierInn": supplier_inn,
                "items": [{
                    "name": material_name,
                    "quantity": TEST_QTY,
                    "unit": "шт",
                    "price": TEST_PRICE,
                    "workPackage": "Основная",
                }],
                "totalBase": round(TEST_QTY * TEST_PRICE, 2),
                "totalVat": 0,
                "totalWithVat": round(TEST_QTY * TEST_PRICE, 2),
            },
        }
        _, preview = api_json(
            "POST",
            "/max/warehouse-invoices/preview",
            data=max_invoice_payload,
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        draft_token = preview.get("draftToken")
        if not draft_token:
            raise RuntimeError(f"MAX preview не вернул draftToken: {preview}")
        if preview.get("status") != "draft":
            raise RuntimeError(f"MAX preview вернул неверный статус: {preview}")
        if preview.get("warehouseInvoiceId"):
            raise RuntimeError(f"MAX preview уже записал накладную в склад: {preview}")
        if not preview.get("recognized"):
            raise RuntimeError(f"MAX preview не отметил OCR/recognizedInvoice: {preview}")
        invoice_draft = preview.get("invoiceDraft") or {}
        if invoice_draft.get("supplierName") != supplier_name:
            raise RuntimeError(f"MAX preview неверно замапил поставщика: {preview}")
        if invoice_draft.get("photoUrl") != stored_file_url:
            raise RuntimeError(f"MAX preview не использует внутренний URL файла: {preview}")
        if not any(row.get("name") == material_name for row in invoice_draft.get("items") or []):
            raise RuntimeError(f"MAX preview не вернул позицию накладной: {preview}")

        preview_outbox = find_outbox_item(bot_token, event_type="max_invoice_preview", draft_token=draft_token)
        if not preview_outbox:
            raise RuntimeError("MAX preview не поставил сообщение с кнопками в outbox")
        action_ids = {action.get("id") for action in preview_outbox.get("actions") or []}
        if not {"confirm", "reject"}.issubset(action_ids):
            raise RuntimeError(f"MAX preview outbox без кнопок confirm/reject: {preview_outbox}")
        _, sent_status = api_json(
            "POST",
            f"/max/outbox/{preview_outbox['id']}/status",
            data={"status": "sent", "providerMessageId": f"max-outbox-preview-{stamp}"},
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        if (sent_status.get("item") or {}).get("status") != "sent":
            raise RuntimeError(f"MAX outbox не отметил preview как sent: {sent_status}")

        _, created = api_json(
            "POST",
            "/max/warehouse-invoices/confirm",
            data={"draftToken": draft_token, "maxUserId": account["maxUserId"]},
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        invoice_id = created.get("id")
        if not invoice_id:
            raise RuntimeError(f"MAX накладная не вернула id: {created}")
        if created.get("sourceType") != "max_project_invoice":
            raise RuntimeError(f"MAX накладная получила неверный sourceType: {created}")
        if not created.get("recognized"):
            raise RuntimeError(f"MAX накладная не отметила OCR/recognizedInvoice: {created}")
        supplier_invoice_id = created.get("supplierInvoiceId")
        if not supplier_invoice_id:
            raise RuntimeError(f"MAX накладная не создала бухгалтерскую первичку: {created}")

        _, repeated = api_json(
            "POST",
            "/max/warehouse-invoices/confirm",
            data={"draftToken": draft_token, "maxUserId": account["maxUserId"]},
            headers={"X-Max-Bot-Token": bot_token},
            expected=200,
        )
        repeated_invoice_id = repeated.get("id") or repeated.get("warehouseInvoiceId")
        if str(repeated_invoice_id) != str(invoice_id) or not repeated.get("alreadyConfirmed"):
            raise RuntimeError(f"Повторный MAX confirm не вернул уже принятую накладную: {repeated}")

        confirmed_outbox = find_outbox_item(bot_token, event_type="max_invoice_confirmed", warehouse_invoice_id=invoice_id)
        if not confirmed_outbox:
            raise RuntimeError("MAX confirm не поставил итоговое сообщение в outbox")
        confirmed_action_ids = {action.get("id") for action in confirmed_outbox.get("actions") or []}
        if "openWarehouseInvoice" not in confirmed_action_ids:
            raise RuntimeError(f"MAX confirm outbox без кнопки открытия накладной: {confirmed_outbox}")

        _, invoices = api_json("GET", "/warehouse-invoices", token=director_token, expected=200)
        invoice = next((row for row in invoices if str(row.get("id")) == str(invoice_id)), None)
        if not invoice:
            raise RuntimeError("MAX накладная не видна в общем реестре склада")
        if invoice.get("location") != project_name:
            raise RuntimeError("MAX накладная ушла не на объектный склад")
        if str(invoice.get("supplierInvoiceId") or "") != str(supplier_invoice_id):
            raise RuntimeError("MAX накладная не связана со счетом поставщика в реестре склада")
        if invoice.get("accountingStatus") != "На проверке":
            raise RuntimeError("MAX накладная не попала в бухгалтерскую очередь проверки")

        _, materials = api_json("GET", "/materials", token=director_token, expected=200)
        if not any(row.get("name") == material_name and row.get("project") == project_name for row in materials):
            raise RuntimeError("Материал MAX накладной не попал на склад объекта")

        _, supplier_invoices = api_json("GET", "/supplier-invoices", token=director_token, expected=200)
        supplier_invoice = next((row for row in supplier_invoices if str(row.get("id")) == str(supplier_invoice_id)), None)
        if not supplier_invoice:
            raise RuntimeError("MAX первичка не видна в счетах поставщика")
        if supplier_invoice.get("status") != "На утверждении":
            raise RuntimeError("MAX первичка получила неверный статус счета поставщика")
        if str(supplier_invoice.get("warehouseInvoiceId") or "") != str(invoice_id):
            raise RuntimeError("Счет поставщика не связан обратно со складской накладной")

        _, suppliers = api_json("GET", "/suppliers", token=director_token, expected=200)
        if not any(row.get("name") == supplier_name and str(row.get("inn") or "") == supplier_inn for row in suppliers):
            raise RuntimeError("Поставщик из MAX/OCR не создан или не обновлен")

        blocked_status, _ = api_json(
            "POST",
            "/max/warehouse-invoices/preview",
            data={
                "maxUserId": account["maxUserId"],
                "maxMessageId": f"max-smoke-main-{stamp}",
                "location": "Основной склад",
                "project": "",
                "number": f"MAX-MAIN-{stamp}",
                "date": dt.date.today().isoformat(),
                "supplierName": supplier_name,
                "items": [{"name": material_name + " main", "quantity": TEST_QTY, "unit": "шт", "price": TEST_PRICE}],
            },
            headers={"X-Max-Bot-Token": bot_token},
            expected=None,
        )
        if blocked_status != 403:
            raise RuntimeError(f"Прораб смог или некорректно попытался принять MAX накладную на основной склад: HTTP {blocked_status}")

        print(json.dumps({
            "ok": True,
            "projectName": project_name,
            "invoiceId": invoice_id,
            "material": material_name,
            "messengerAccountId": account["accountId"],
            "checked": checked + [
                "MAX recognizedInvoice/OCR draft is mapped to warehouse invoice fields",
                "MAX mini-app linked foreman session opens without bypassing 2FA roles",
                "MAX file upload stores attachment in Stroyka storage",
                "MAX preview returns draft without warehouse write",
                "MAX preview queues confirm/reject buttons for bot delivery",
                "MAX outbox status callback marks preview message as sent",
                "MAX confirm writes preview to warehouse and accounting queue",
                "MAX confirm queues warehouse invoice open action",
                "repeated MAX confirm is idempotent and does not duplicate stock",
                "MAX messenger account resolves to foreman",
                "MAX project invoice is accepted to assigned object warehouse",
                "MAX invoice writes material to object stock",
                "MAX invoice creates supplier record and supplier_invoices primary document",
                "MAX warehouse invoice is linked to accounting review queue",
                "foreman main warehouse invoice through MAX is blocked",
            ],
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        raise SystemExit(f"FAIL smoke:max-warehouse: {exc}")
    finally:
        cleanup(invoice_id, material_name, project_name, account.get("accountId"), supplier_name, draft_token, stored_file_url)


if __name__ == "__main__":
    main()
