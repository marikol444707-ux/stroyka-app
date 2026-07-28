"""Supplier invoice recognition template routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 9):
GET /supplier-invoice-templates and POST /supplier-invoice-templates/learn
keep their URLs, warehouse+accountant role guard and payloads. Shared
recognition helpers and log_audit stay in main.py and arrive through deps.
"""

import datetime as dt
import json

import psycopg2.extras
from fastapi import Depends, HTTPException


def register_supplier_invoice_templates_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    warehouse_roles = tuple(deps.get("warehouse_roles") or ())
    supplier_invoice_template_row = deps["supplier_invoice_template_row"]
    supplier_invoice_template_key = deps["supplier_invoice_template_key"]
    scan_invoice_supplier_name = deps["scan_invoice_supplier_name"]
    find_supplier_by_name_key = deps["find_supplier_by_name_key"]
    log_audit = deps["log_audit"]

    @app.get("/supplier-invoice-templates")
    def list_supplier_invoice_templates(current_user: dict = Depends(require_roles(*warehouse_roles, "бухгалтер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT *
                       FROM supplier_invoice_templates
                       WHERE active=TRUE
                       ORDER BY updated_at DESC, id DESC""")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [supplier_invoice_template_row(row) for row in rows]

    @app.post("/supplier-invoice-templates/learn")
    def learn_supplier_invoice_template(data: dict, current_user: dict = Depends(require_roles(*warehouse_roles, "бухгалтер"))):
        supplier_name = (
            data.get("supplierName")
            or data.get("supplier")
            or data.get("newSupplierName")
            or scan_invoice_supplier_name(data)
        )
        supplier_name = str(supplier_name or "").strip()
        if not supplier_name:
            raise HTTPException(status_code=400, detail="Укажите поставщика, чтобы сохранить правило распознавания")
        supplier_key = supplier_invoice_template_key(supplier_name)
        if not supplier_key:
            raise HTTPException(status_code=400, detail="Не удалось нормализовать название поставщика")
        document_type = str(data.get("documentType") or data.get("scanDocumentType") or "supplier_invoice").strip() or "supplier_invoice"
        items = data.get("items") if isinstance(data.get("items"), list) else []
        sample = {
            "number": data.get("number") or data.get("invoiceNumber") or "",
            "date": data.get("date") or "",
            "supplierName": supplier_name,
            "documentType": document_type,
            "vat": data.get("vat") or "",
            "totalBase": data.get("totalBase") or 0,
            "totalVat": data.get("totalVat") or 0,
            "totalWithVat": data.get("totalWithVat") or 0,
            "items": items[:60],
        }
        keywords = [supplier_name]
        recognition = data.get("recognition") if isinstance(data.get("recognition"), dict) else data.get("scanRecognition")
        if isinstance(recognition, dict):
            for value in (recognition.get("supplierName"), recognition.get("templateName")):
                if value and str(value) not in keywords:
                    keywords.append(str(value))
        for value in data.get("matchKeywords") or []:
            if value and str(value) not in keywords:
                keywords.append(str(value))
        column_map = {
            "source": "scan_preview_correction",
            "columns": {
                "name": "name",
                "quantity": "quantity",
                "unit": "unit",
                "price": "price",
                "lineTotal": "lineTotal",
            },
            "lastCorrectionAt": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        supplier_id = data.get("supplierId") or 0
        try:
            supplier_id = int(supplier_id or 0)
        except Exception:
            supplier_id = 0
        if not supplier_id:
            supplier = find_supplier_by_name_key(cur, supplier_name)
            if supplier:
                supplier_id = supplier["id"]
                supplier_name = supplier["name"] or supplier_name
        cur.execute("""SELECT *
                       FROM supplier_invoice_templates
                       WHERE active=TRUE AND supplier_key=%s AND COALESCE(document_type,'')=%s
                       ORDER BY id DESC LIMIT 1""", (supplier_key, document_type))
        row = cur.fetchone()
        if row:
            cur.execute("""UPDATE supplier_invoice_templates
                           SET supplier_id=%s,
                               supplier_name=%s,
                               template_name=%s,
                               match_keywords=%s,
                               column_map=%s,
                               sample_json=%s,
                               updated_by=%s,
                               updated_at=NOW()
                           WHERE id=%s
                           RETURNING *""", (
                supplier_id or None,
                supplier_name,
                data.get("templateName") or ("Счет/накладная " + supplier_name),
                json.dumps(keywords, ensure_ascii=False),
                json.dumps(column_map, ensure_ascii=False),
                json.dumps(sample, ensure_ascii=False),
                current_user.get("name", ""),
                row["id"],
            ))
        else:
            cur.execute("""INSERT INTO supplier_invoice_templates (
                               supplier_id, supplier_key, supplier_name, template_name, document_type,
                               match_keywords, column_map, sample_json, active, usage_count,
                               updated_by, updated_at, created_at
                           )
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE,0,%s,NOW(),NOW())
                           RETURNING *""", (
                supplier_id or None,
                supplier_key,
                supplier_name,
                data.get("templateName") or ("Счет/накладная " + supplier_name),
                document_type,
                json.dumps(keywords, ensure_ascii=False),
                json.dumps(column_map, ensure_ascii=False),
                json.dumps(sample, ensure_ascii=False),
                current_user.get("name", ""),
            ))
        saved = cur.fetchone()
        conn.commit()
        cur.close(); conn.close()
        template = supplier_invoice_template_row(saved)
        log_audit(
            user_name=current_user.get("name", ""),
            user_role=current_user.get("role", ""),
            action="learn",
            entity_type="supplier_invoice_template",
            entity_id=template["id"],
            description="Обновлен шаблон распознавания поставщика " + template["supplierName"],
            project_name=data.get("project") or data.get("projectName") or "",
        )
        return {
            "ok": True,
            "template": template,
            "recognition": {
                "method": "template",
                "label": "Распознано по шаблону поставщика",
                "templateId": template["id"],
                "templateName": template["templateName"],
                "supplierId": template["supplierId"],
                "supplierName": template["supplierName"],
                "confidence": 1,
                "warnings": [],
            }
        }
