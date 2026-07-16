#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:10]
MATERIAL_NAME = f"CODEX QA основной склад без поставщика {RUN_ID}"


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


def api_json(method, path, *, token=None, data=None, headers=None, expected=200):
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    request = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=50) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {path}: backend returned non-JSON body: {text[:300]}") from exc


def totp_code(secret):
    normalized = re.sub(r"\s+", "", str(secret or "")).upper()
    normalized += "=" * (-len(normalized) % 8)
    key = base64.b32decode(normalized, casefold=True)
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
        secret = body.get("manualKey") or env_value("SMOKE_TOTP_SECRET")
        if not setup_token or not secret:
            raise SystemExit(f"FAIL login {email}: 2FA setup не вернул setupToken/manualKey")
        confirmed = api_json(
            "POST",
            "/login/2fa/setup-confirm",
            data={"setupToken": setup_token, "code": totp_code(secret)},
        )
        if confirmed.get("authToken"):
            return confirmed["authToken"]
        raise RuntimeError("authToken не получен после настройки 2FA")
    if body.get("twoFactorRequired"):
        code = env_value("SMOKE_2FA_CODE")
        if not code and env_value("SMOKE_TOTP_SECRET"):
            code = totp_code(env_value("SMOKE_TOTP_SECRET"))
        if not code:
            raise SystemExit("Нужно задать SMOKE_2FA_CODE или SMOKE_TOTP_SECRET")
        verified = api_json(
            "POST",
            "/login/2fa/verify",
            data={"challengeToken": body.get("challengeToken"), "code": code},
        )
        if verified.get("authToken"):
            return verified["authToken"]
    raise RuntimeError("authToken не получен")


def login(email, password):
    body = api_json("POST", "/login", data={"email": email, "password": password})
    return token_from_login_response(body, email)


def cleanup(invoice_id=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM warehouse_invoices WHERE CAST(items AS TEXT) LIKE %s",
            (f"%{MATERIAL_NAME}%",),
        )
        invoice_ids = {int(row[0]) for row in cur.fetchall()}
        if invoice_id:
            invoice_ids.add(int(invoice_id))
        supplier_invoice_ids = []
        if invoice_ids:
            invoice_id_list = sorted(invoice_ids)
            cur.execute(
                "SELECT id FROM supplier_invoices WHERE warehouse_invoice_id = ANY(%s) OR material_name=%s",
                (invoice_id_list, MATERIAL_NAME),
            )
            supplier_invoice_ids = [row[0] for row in cur.fetchall()]
            cur.execute("UPDATE warehouse_invoices SET supplier_invoice_id=NULL WHERE id = ANY(%s)", (invoice_id_list,))
            cur.execute("UPDATE supplier_invoices SET warehouse_invoice_id=NULL WHERE warehouse_invoice_id = ANY(%s)", (invoice_id_list,))
        cur.execute("DELETE FROM warehouse_history WHERE material=%s", (MATERIAL_NAME,))
        if invoice_ids:
            cur.execute("DELETE FROM warehouse_invoices WHERE id = ANY(%s)", (sorted(invoice_ids),))
        if supplier_invoice_ids:
            cur.execute("DELETE FROM supplier_invoices WHERE id = ANY(%s)", (supplier_invoice_ids,))
        cur.execute("DELETE FROM warehouse_main WHERE name=%s", (MATERIAL_NAME,))
        conn.commit()
        cur.close()
        print("cleanup: removed main-warehouse receipt smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = login(email, password)
    context = api_json("GET", "/users/company-context", token=token)
    requested_company_id = int(env_value("SMOKE_COMPANY_ID", "0") or 0)
    companies = [
        company for company in context.get("companies") or []
        if company.get("role") in {"директор", "зам_директора"}
    ]
    selected = next(
        (company for company in companies if int(company.get("companyId") or 0) == requested_company_id),
        companies[0] if companies and not requested_company_id else None,
    )
    if not selected:
        raise RuntimeError("У smoke-пользователя нет роли директора или заместителя в выбранной компании")
    company_id = int(selected["companyId"])
    headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    invoice_id = None
    try:
        created = api_json(
            "POST",
            "/warehouse-invoices",
            token=token,
            headers=headers,
            data={
                "companyId": company_id,
                "number": "",
                "date": time.strftime("%Y-%m-%d"),
                "location": "Основной склад",
                "project": "",
                "warehouseTarget": "main",
                "inventoryOnly": True,
                "syncSupplierInvoice": False,
                "selectedAction": "receive_stock_without_supplier",
                "sourceType": "manual_main_receipt",
                "acceptedBy": "CODEX QA",
                "vat": "Без НДС",
                "items": [{"name": MATERIAL_NAME, "quantity": 0.001, "unit": "шт", "price": 1}],
            },
        )
        invoice_id = int(created.get("id") or 0)
        if not invoice_id or created.get("accountingRequired") is not False:
            raise RuntimeError("Backend не подтвердил складской приход без бухгалтерской первички")
        if created.get("supplierInvoiceId"):
            raise RuntimeError("Для складского прихода без поставщика создан supplier invoice")
        if not str(created.get("number") or "").startswith("ПРИХОД-"):
            raise RuntimeError("Backend не присвоил внутренний номер складскому приходу")

        invoices = api_json("GET", "/warehouse-invoices", token=token, headers=headers)
        stored = next((row for row in invoices if int(row.get("id") or 0) == invoice_id), None)
        if not stored or stored.get("accountingRequired") is not False or stored.get("supplierName"):
            raise RuntimeError("Складской приход сохранён с неверной бухгалтерской политикой")

        supplier_invoices = api_json("GET", "/supplier-invoices", token=token, headers=headers)
        if any(int(row.get("warehouseInvoiceId") or 0) == invoice_id for row in supplier_invoices):
            raise RuntimeError("Складской приход без поставщика попал в supplier invoices")

        api_json(
            "PUT",
            f"/warehouse-invoices/{invoice_id}/accounting",
            token=token,
            headers=headers,
            data={"accountingStatus": "К оплате"},
            expected=409,
        )

        main_stock = api_json("GET", "/warehouse-main", token=token, headers=headers)
        if not any(row.get("name") == MATERIAL_NAME and float(row.get("quantity") or 0) >= 0.001 for row in main_stock):
            raise RuntimeError("Материал не появился на основном складе")
        history = api_json("GET", "/warehouse-history", token=token, headers=headers)
        if not any(row.get("material") == MATERIAL_NAME and row.get("type") == "приход" for row in history):
            raise RuntimeError("Приход не появился в истории склада")

        print(json.dumps({
            "ok": True,
            "companyId": company_id,
            "warehouseInvoiceId": invoice_id,
            "checked": [
                "director/deputy inventory-only receipt creates main warehouse stock",
                "internal receipt number is generated when document number is absent",
                "receipt is stored without supplier and accounting obligation",
                "supplier invoice is not created or listed",
                "accounting status mutation is blocked",
                "main warehouse history records the receipt",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(invoice_id)


if __name__ == "__main__":
    main()
