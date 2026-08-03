#!/usr/bin/env python3
"""Verify that an invoice-selected movement consumes its exact new receipt lot."""
import importlib.util
import json
import sys
import time
import uuid
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SMOKE = ROOT / "scripts" / "smoke-main-warehouse-receipt.py"
SPEC = importlib.util.spec_from_file_location("smoke_main_warehouse_receipt", RECEIPT_SMOKE)
RECEIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECEIPT)

RUN_ID = uuid.uuid4().hex[:10]
PROJECT_NAME = f"CODEX QA партия перемещение {RUN_ID}"
MATERIAL_NAME = f"CODEX QA партия материал {RUN_ID}"
QUANTITY = 0.001


def estimate_sections():
    return [{
        "name": "CODEX QA",
        "items": [{
            "type": "material",
            "name": MATERIAL_NAME,
            "unit": "шт",
            "quantity": 1,
            "price": 1,
        }],
    }]


def select_company(token):
    context = RECEIPT.api_json("GET", "/users/company-context", token=token)
    requested_company_id = int(RECEIPT.env_value("SMOKE_COMPANY_ID", "0") or 0)
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
    return int(selected["companyId"])


def setup_project_and_estimate(company_id):
    conn = psycopg2.connect(**RECEIPT.db_config())
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO projects
                (company_id,name,client,status,budget,deadline,progress,tasks,pricelist_id,floors,liters)
               VALUES (%s,%s,%s,%s,0,NULL,0,ARRAY[]::TEXT[],NULL,1,'')
               RETURNING id""",
            (company_id, PROJECT_NAME, "CODEX QA", "В работе"),
        )
        project_id = int(cur.fetchone()[0])
        cur.execute(
            """INSERT INTO estimates
                (company_id,project_id,project_name,name,version,sections_json,smeta_type,work_package,status)
               VALUES (%s,%s,%s,%s,'1.0',%s,'Материалы','Основная','Активная')
               RETURNING id""",
            (company_id, project_id, PROJECT_NAME, "CODEX QA смета партии", json.dumps(estimate_sections(), ensure_ascii=False)),
        )
        estimate_id = int(cur.fetchone()[0])
        conn.commit()
        return project_id, estimate_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup(*, company_id=None, project_id=None, estimate_id=None, invoice_id=None, movement_id=None):
    conn = None
    try:
        conn = psycopg2.connect(**RECEIPT.db_config())
        cur = conn.cursor()
        if invoice_id:
            cur.execute(
                """DELETE FROM warehouse_lot_movements
                    WHERE lot_id IN (
                        SELECT id FROM warehouse_receipt_lots WHERE warehouse_invoice_id=%s
                    )""",
                (invoice_id,),
            )
        if movement_id:
            cur.execute("DELETE FROM warehouse_history WHERE source_type='warehouse_movement' AND source_id=%s", (movement_id,))
            cur.execute("DELETE FROM warehouse_movements WHERE id=%s", (movement_id,))
        if invoice_id:
            cur.execute("DELETE FROM warehouse_history WHERE source_invoice_id=%s", (invoice_id,))
            cur.execute("DELETE FROM material_inspection_journal WHERE invoice_id=%s", (invoice_id,))
            cur.execute("DELETE FROM cable_journal WHERE invoice_id=%s", (invoice_id,))
            cur.execute("DELETE FROM warehouse_receipt_lots WHERE warehouse_invoice_id=%s", (invoice_id,))
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (invoice_id,))
        if company_id:
            cur.execute("DELETE FROM warehouse_main WHERE company_id=%s AND name=%s", (company_id, MATERIAL_NAME))
            cur.execute("DELETE FROM materials WHERE company_id=%s AND project=%s AND name=%s", (company_id, PROJECT_NAME, MATERIAL_NAME))
        if estimate_id:
            cur.execute("DELETE FROM estimates WHERE id=%s", (estimate_id,))
        if project_id:
            cur.execute("DELETE FROM projects WHERE id=%s", (project_id,))
        conn.commit()
        cur.close()
        print("cleanup: removed receipt-lot movement smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def main():
    email = RECEIPT.env_value("SMOKE_EMAIL")
    password = RECEIPT.env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = RECEIPT.login(email, password)
    company_id = select_company(token)
    headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    project_id = estimate_id = invoice_id = movement_id = None
    try:
        project_id, estimate_id = setup_project_and_estimate(company_id)
        created = RECEIPT.api_json(
            "POST",
            "/warehouse-invoices",
            token=token,
            headers=headers,
            data={
                "companyId": company_id,
                "number": f"CODEX-LOT-{RUN_ID}",
                "date": time.strftime("%Y-%m-%d"),
                "location": PROJECT_NAME,
                "project": PROJECT_NAME,
                "warehouseTarget": "object",
                "sourceType": "manual_project_invoice",
                "acceptedBy": "CODEX QA",
                "vat": "Без НДС",
                "items": [{"name": MATERIAL_NAME, "quantity": QUANTITY, "unit": "шт", "price": 1, "workPackage": "Основная"}],
            },
        )
        invoice_id = int(created.get("id") or 0)
        if not invoice_id:
            raise RuntimeError("Тестовая объектная накладная не создана")
        conn = psycopg2.connect(**RECEIPT.db_config())
        cur = conn.cursor()
        cur.execute("SELECT items FROM warehouse_invoices WHERE id=%s AND company_id=%s", (invoice_id, company_id))
        invoice_row = cur.fetchone()
        cur.close(); conn.close()
        # PostgreSQL installations may expose this column as TEXT or JSON/JSONB.
        # psycopg2 deserializes JSON values to Python lists, so do not parse them
        # a second time and accidentally turn a valid source line into an empty list.
        invoice_items = RECEIPT._json_list_or_empty((invoice_row or [""])[0])
        source_line_index = next(
            (
                index for index, item in enumerate(invoice_items)
                if isinstance(item, dict) and (item.get("name") or item.get("materialName") or item.get("title"))
            ),
            None,
        )
        if source_line_index is None:
            raise RuntimeError(
                "Созданная накладная не сохранила точную тестовую строку материала: "
                + json.dumps(
                    {
                        "invoiceId": invoice_id,
                        "storedItems": invoice_items,
                        "receiptResult": {
                            "stockRowsAdded": created.get("stockRowsAdded"),
                            "historyAdded": created.get("historyAdded"),
                            "receiptLotsAdded": created.get("receiptLotsAdded"),
                        },
                    },
                    ensure_ascii=False,
                )
            )
        source_item = invoice_items[source_line_index]
        source_material_name = str(
            source_item.get("name") or source_item.get("materialName") or source_item.get("title") or ""
        ).strip()
        source_unit = str(source_item.get("unit") or "шт").strip() or "шт"

        movement = RECEIPT.api_json(
            "POST",
            "/warehouse-movements",
            token=token,
            headers=headers,
            data={
                "materialName": source_material_name,
                "fromLocation": PROJECT_NAME,
                "toLocation": "Основной склад",
                "quantity": QUANTITY,
                "unit": source_unit,
                "workPackage": "Основная",
                "date": time.strftime("%Y-%m-%d"),
                "createdBy": "CODEX QA",
                "notes": "Проверка точного списания партии",
                "invoiceId": invoice_id,
                "invoiceLineIndex": source_line_index,
            },
        )
        movement_id = int(movement.get("id") or 0)
        if (
            not movement_id
            or int(movement.get("sourceInvoiceId") or 0) != invoice_id
            or movement.get("sourceInvoiceLineIndex") is None
            or int(movement["sourceInvoiceLineIndex"]) != source_line_index
        ):
            raise RuntimeError("Перемещение не сохранило точную ссылку на строку накладной")

        conn = psycopg2.connect(**RECEIPT.db_config())
        cur = conn.cursor()
        cur.execute(
            """SELECT id,available_quantity FROM warehouse_receipt_lots
                 WHERE company_id=%s AND warehouse_invoice_id=%s AND invoice_line_index=%s""",
            (company_id, invoice_id, source_line_index),
        )
        lot = cur.fetchone()
        if not lot or abs(float(lot[1])) > 1e-9:
            raise RuntimeError("Перемещение не списало остаток точной партии")
        cur.execute(
            """SELECT quantity,unit,warehouse_movement_id
                 FROM warehouse_lot_movements
                WHERE lot_id=%s AND operation_type='warehouse_movement_out'""",
            (lot[0],),
        )
        lot_movement = cur.fetchone()
        cur.close(); conn.close()
        if (
            not lot_movement
            or abs(float(lot_movement[0]) - QUANTITY) > 1e-9
            or lot_movement[1] != source_unit
            or int(lot_movement[2] or 0) != movement_id
        ):
            raise RuntimeError("Не создана точная неизменяемая проводка партии")

        print(json.dumps({
            "ok": True,
            "companyId": company_id,
            "projectId": project_id,
            "warehouseInvoiceId": invoice_id,
            "warehouseMovementId": movement_id,
            "checked": [
                "new project receipt creates one exact lot",
                "invoice-selected project-to-main movement consumes that lot",
                "movement preserves exact invoice-line source",
                "lot balance and immutable lot movement match the warehouse movement",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(
            company_id=company_id,
            project_id=project_id,
            estimate_id=estimate_id,
            invoice_id=invoice_id,
            movement_id=movement_id,
        )


if __name__ == "__main__":
    main()
