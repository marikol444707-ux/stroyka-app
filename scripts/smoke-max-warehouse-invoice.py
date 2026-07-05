#!/usr/bin/env python3
import datetime as dt
import hashlib
import hmac
import json
import os
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


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken")
    if not token:
        raise SystemExit(f"FAIL login {email}: authToken не получен")
    return token


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


def cleanup(invoice_id, material_name, project_name, account_id, supplier_name=""):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
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
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    material_name = f"CODEX QA MAX накладная {stamp}"
    supplier_name = f"CODEX QA MAX поставщик {stamp}"
    supplier_inn = "77" + stamp[-8:]
    invoice_id = None
    try:
        _, created = api_json(
            "POST",
            "/max/warehouse-invoices",
            data={
                "maxUserId": account["maxUserId"],
                "maxMessageId": f"max-smoke-{stamp}",
                "projectName": project_name,
                "photoUrl": "/uploads/smoke/max-invoice.jpg",
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
            },
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
            "/max/warehouse-invoices",
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
        cleanup(invoice_id, material_name, project_name, account.get("accountId"), supplier_name)


if __name__ == "__main__":
    main()
