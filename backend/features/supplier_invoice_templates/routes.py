"""Company-owned OCR templates; learning never grants supplier access."""

import datetime as dt
import json

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from .scope import resolve_scan_company


def register_supplier_invoice_templates_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    warehouse_roles = tuple(deps.get("warehouse_roles") or ())
    supplier_invoice_template_row = deps["supplier_invoice_template_row"]
    supplier_invoice_template_key = deps["supplier_invoice_template_key"]
    scan_invoice_supplier_name = deps["scan_invoice_supplier_name"]
    resolve_context = deps["resolve_work_company_context"]
    log_audit = deps["log_audit"]

    def owner(cur, user, data, company, mode):
        return resolve_scan_company(cur, user, resolve_context, (*warehouse_roles, "бухгалтер"),
                                    company_id=(data or {}).get("companyId"),
                                    x_company_id=company, x_company_mode=mode)

    @app.get("/supplier-invoice-templates")
    def list_supplier_invoice_templates(x_company_id: str = Header(default=None, alias="X-Company-Id"), x_company_mode: str = Header(default=None, alias="X-Company-Mode"), current_user: dict = Depends(require_roles(*warehouse_roles, "бухгалтер"))):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                company_id = owner(cur, current_user, None, x_company_id, x_company_mode)
                cur.execute("""SELECT * FROM supplier_invoice_templates
                               WHERE active=TRUE AND company_id=%s
                               ORDER BY updated_at DESC, id DESC""", (company_id,))
                rows = cur.fetchall()
        finally:
            conn.close()
        return [supplier_invoice_template_row(row) for row in rows]

    @app.post("/supplier-invoice-templates/learn")
    def learn_supplier_invoice_template(data: dict, x_company_id: str = Header(default=None, alias="X-Company-Id"), x_company_mode: str = Header(default=None, alias="X-Company-Mode"), current_user: dict = Depends(require_roles(*warehouse_roles, "бухгалтер"))):
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
            "lastCorrectionAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        }
        try:
            supplier_id = int(str(data.get("supplierId") or 0))
            if supplier_id < 0 or isinstance(data.get("supplierId"), bool):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(400, "Некорректный идентификатор поставщика")
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                company_id = owner(cur, current_user, data, x_company_id, x_company_mode)
                if supplier_id:
                    cur.execute("SELECT 1 FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s FOR KEY SHARE", (company_id, supplier_id))
                    if not cur.fetchone():
                        raise HTTPException(403, "Поставщик недоступен в выбранной компании")
                # Serialize simultaneous learns of the same company/key without duplicates.
                cur.execute("""INSERT INTO supplier_invoice_templates (
                     company_id,supplier_id,supplier_key,supplier_name,template_name,document_type,
                     match_keywords,column_map,sample_json,updated_by)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     ON CONFLICT (company_id,supplier_key,(COALESCE(document_type,''))) WHERE active=TRUE
                     DO UPDATE SET supplier_id=EXCLUDED.supplier_id,supplier_name=EXCLUDED.supplier_name,
                       template_name=EXCLUDED.template_name,match_keywords=EXCLUDED.match_keywords,
                       column_map=EXCLUDED.column_map,sample_json=EXCLUDED.sample_json,
                       updated_by=EXCLUDED.updated_by,updated_at=NOW()
                     RETURNING *""", (
                         company_id, supplier_id or None, supplier_key, supplier_name,
                         data.get("templateName") or ("Счет/накладная " + supplier_name), document_type,
                         json.dumps(keywords, ensure_ascii=False),json.dumps(column_map, ensure_ascii=False),
                         json.dumps(sample, ensure_ascii=False),current_user.get("name", "")))
                saved = cur.fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        template = supplier_invoice_template_row(saved)
        log_audit(
            user_name=current_user.get("name", ""),
            user_role=current_user.get("role", ""),
            action="learn",
            owner_scope="company", company_id=company_id,
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
