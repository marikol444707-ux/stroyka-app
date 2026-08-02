#!/usr/bin/env python3
"""Verify a packaging review records evidence without changing the receipt stock."""
import json
import importlib.util
import time
import uuid
from pathlib import Path

import psycopg2

BASE_SMOKE_PATH = Path(__file__).with_name("smoke-main-warehouse-receipt.py")
BASE_SMOKE_SPEC = importlib.util.spec_from_file_location("main_warehouse_receipt_smoke", BASE_SMOKE_PATH)
BASE_SMOKE = importlib.util.module_from_spec(BASE_SMOKE_SPEC)
BASE_SMOKE_SPEC.loader.exec_module(BASE_SMOKE)
api_json = BASE_SMOKE.api_json
db_config = BASE_SMOKE.db_config
env_value = BASE_SMOKE.env_value
login = BASE_SMOKE.login


RUN_ID = uuid.uuid4().hex[:10]
MATERIAL_NAME = f"CODEX QA packaging review {RUN_ID}"


def cleanup(invoice_id=None, rule_id=None):
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
        if invoice_ids:
            cur.execute(
                "DELETE FROM material_packaging_reviews WHERE warehouse_invoice_id = ANY(%s)",
                (sorted(invoice_ids),),
            )
            cur.execute("DELETE FROM warehouse_history WHERE material=%s", (MATERIAL_NAME,))
            cur.execute("DELETE FROM warehouse_invoices WHERE id = ANY(%s)", (sorted(invoice_ids),))
        cur.execute("DELETE FROM warehouse_main WHERE name=%s", (MATERIAL_NAME,))
        if rule_id:
            cur.execute("DELETE FROM material_packaging_rules WHERE id=%s", (int(rule_id),))
        else:
            cur.execute("DELETE FROM material_packaging_rules WHERE material_name=%s", (MATERIAL_NAME,))
        conn.commit()
        cur.close()
        print("cleanup: removed material packaging review smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}")
    finally:
        if conn:
            conn.close()


def select_company(token):
    context = api_json("GET", "/users/company-context", token=token)
    requested_company_id = int(env_value("SMOKE_COMPANY_ID", "0") or 0)
    candidates = [
        row for row in context.get("companies") or []
        if row.get("role") in {"директор", "зам_директора"}
    ]
    selected = next(
        (row for row in candidates if int(row.get("companyId") or 0) == requested_company_id),
        candidates[0] if candidates and not requested_company_id else None,
    )
    if not selected:
        raise RuntimeError("У smoke-пользователя нет роли директора или заместителя в выбранной компании")
    return int(selected["companyId"])


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = login(email, password)
    company_id = select_company(token)
    headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    invoice_id = None
    rule_id = None
    try:
        invoice = api_json(
            "POST", "/warehouse-invoices", token=token, headers=headers,
            data={
                "companyId": company_id, "number": "", "date": time.strftime("%Y-%m-%d"),
                "location": "Основной склад", "project": "", "warehouseTarget": "main",
                "inventoryOnly": True, "syncSupplierInvoice": False,
                "selectedAction": "receive_stock_without_supplier", "sourceType": "manual_main_receipt",
                "acceptedBy": "CODEX QA", "vat": "Без НДС",
                "items": [{"name": MATERIAL_NAME, "quantity": 2, "unit": "бухта", "price": 100}],
            },
        )
        invoice_id = int(invoice.get("id") or 0)
        if not invoice_id:
            raise RuntimeError("Не создана тестовая накладная")

        created_rule = api_json(
            "POST", "/material-packaging-rules", token=token, headers=headers,
            data={"materialName": MATERIAL_NAME, "documentUnit": "бухта", "contentQuantity": 100, "baseUnit": "м", "note": "CODEX QA smoke"},
        )
        rule_id = int(created_rule.get("id") or 0)
        if not rule_id:
            raise RuntimeError("Не создано тестовое правило упаковки")

        preview = api_json(
            "POST", "/material-packaging-corrections/preview", token=token, headers=headers,
            data={"warehouseInvoiceId": invoice_id, "itemIndex": 0},
        )
        if preview.get("preview", {}).get("canApply") is not False:
            raise RuntimeError("Предпросмотр упаковки разрешил изменение остатка")

        before_stock = api_json("GET", "/warehouse-main", token=token, headers=headers)
        before_quantity = next((float(row.get("quantity") or 0) for row in before_stock if row.get("name") == MATERIAL_NAME), None)
        review = api_json(
            "POST", "/material-packaging-corrections/reviews", token=token, headers=headers,
            data={
                "warehouseInvoiceId": invoice_id, "itemIndex": 0,
                "reviewDecision": "document_required",
                "reviewNote": "CODEX QA: ожидается первичный документ поставщика.",
            },
        )
        if review.get("review", {}).get("decision") != "document_required":
            raise RuntimeError("Решение ручной сверки не сохранено")

        after_stock = api_json("GET", "/warehouse-main", token=token, headers=headers)
        after_quantity = next((float(row.get("quantity") or 0) for row in after_stock if row.get("name") == MATERIAL_NAME), None)
        if before_quantity != after_quantity:
            raise RuntimeError("Ручная сверка изменила складской остаток")
        invoices = api_json("GET", "/warehouse-invoices", token=token, headers=headers)
        stored = next((row for row in invoices if int(row.get("id") or 0) == invoice_id), None)
        item = (stored or {}).get("items", [{}])[0]
        if item.get("quantity") != 2 or item.get("unit") != "бухта":
            raise RuntimeError("Ручная сверка изменила строку накладной")
        reviews = api_json("GET", "/material-packaging-reviews?limit=100", token=token, headers=headers)
        saved = next((row for row in reviews if int(row.get("warehouseInvoiceId") or 0) == invoice_id and row.get("itemIndex") == 0), None)
        if not saved or saved.get("decision") != "document_required":
            raise RuntimeError("Ручная сверка не найдена в реестре")

        print(json.dumps({
            "ok": True, "companyId": company_id, "warehouseInvoiceId": invoice_id, "reviewId": review.get("review", {}).get("id"),
            "checked": [
                "unknown package stays in document unit", "confirmed rule enables only preview",
                "director/deputy records explicit manual decision", "review registry returns exact decision",
                "manual review does not change stock", "manual review does not rewrite invoice item",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(invoice_id, rule_id)


if __name__ == "__main__":
    main()
