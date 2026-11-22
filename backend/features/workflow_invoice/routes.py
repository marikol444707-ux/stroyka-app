"""Routes moved verbatim from backend/main.py."""

import hmac
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional

def register_workflow_invoice_module(app, deps):
    workflow_token = deps['workflow_token']
    _float_or_zero = deps['_float_or_zero']
    _norm_base_unit = deps['_norm_base_unit']
    _normalize_invoice_totals_payload = deps['_normalize_invoice_totals_payload']
    router = APIRouter()

    def require_workflow_token(x_workflow_token: Optional[str] = Header(default=None)) -> dict:
        token = workflow_token()
        if not token:
            raise HTTPException(status_code=503, detail="WORKFLOW_TOKEN не настроен")
        if not x_workflow_token or not hmac.compare_digest(x_workflow_token.encode("utf-8"), token.encode("utf-8")):
            raise HTTPException(status_code=403, detail="Недостаточно прав Workflow")
        return {"role": "workflow", "name": "Yandex Workflow"}

    @router.post("/workflow/invoice/preview")
    def workflow_invoice_preview(data: dict, _workflow: dict = Depends(require_workflow_token)):
        """Safe Workflow entrypoint: validate/preview invoice data without writing stock."""
        document = data.get("document") if isinstance(data.get("document"), dict) else {}
        totals = data.get("totals") if isinstance(data.get("totals"), dict) else {}

        photos = data.get("photos") or data.get("photoUrls") or data.get("images") or data.get("pages") or []
        if isinstance(photos, str):
            photos = [photos]
        if not isinstance(photos, list):
            photos = []
        photos = [str(photo).strip() for photo in photos if str(photo or "").strip()]

        items = data.get("items") or data.get("positions") or []
        if not isinstance(items, list):
            items = []

        project_name = (
            data.get("projectName")
            or data.get("project")
            or data.get("project_name")
            or ""
        )
        warehouse_target = (data.get("warehouseTarget") or data.get("target") or "object").strip() or "object"
        selected_action = (data.get("selectedAction") or data.get("action") or "receive_to_warehouse").strip()
        warnings = []
        status = "ok"

        if selected_action not in ("receive_to_warehouse", "warehouse_invoice", "stock_receipt"):
            status = "needs_review"
            warnings.append("Маршрут не похож на складскую накладную. Проверьте, что документ не ушел в мои траты.")
        if warehouse_target in ("object", "project") and not str(project_name).strip():
            status = "needs_review"
            warnings.append("Для прихода на объект нужно указать объект.")
        if not photos:
            status = "needs_review"
            warnings.append("Фото накладной не переданы. Workflow подключен, но распознавание не запускалось.")
        if len(photos) > 8:
            status = "needs_review"
            warnings.append("Передано больше 8 страниц. Сейчас безопасный лимит распознавания — 8 фото.")

        invoice_preview = _normalize_invoice_totals_payload({
            **data,
            "document": document,
            "totals": totals,
            "items": items,
        })
        total_base = invoice_preview.get("totalBase", 0)
        total_vat = invoice_preview.get("totalVat", 0)
        total_with_vat = invoice_preview.get("totalWithVat", 0)
        if total_with_vat and total_base and total_vat and abs((total_base + total_vat) - total_with_vat) > 2:
            status = "needs_review"
            warnings.append("Итог с НДС не сходится с суммой без НДС и НДС.")

        normalized_items = []
        for idx, raw_item in enumerate((invoice_preview.get("items") or [])[:300], start=1):
            if not isinstance(raw_item, dict):
                continue
            qty = _float_or_zero(raw_item.get("quantity") or raw_item.get("qty"))
            price = _float_or_zero(raw_item.get("price") or raw_item.get("priceWithVat") or raw_item.get("price_with_vat"))
            line_total = _float_or_zero(raw_item.get("lineTotalWithVat") or raw_item.get("lineTotal") or raw_item.get("total"))
            normalized_items.append({
                "row": idx,
                "name": str(raw_item.get("name") or raw_item.get("title") or "").strip(),
                "quantity": qty,
                "unit": _norm_base_unit(raw_item.get("unit") or "шт") or "шт",
                "price": price,
                "lineTotal": line_total or (qty * price if qty and price else 0),
                "page": raw_item.get("page") or raw_item.get("pageNumber") or None,
                "confidence": _float_or_zero(raw_item.get("confidence") or 0),
                "needsReview": bool(raw_item.get("needsReview") or raw_item.get("needs_review")),
            })
        vat_label = str(invoice_preview.get("vat") or data.get("vat") or document.get("vat") or "").strip()

        if len(items) > 300:
            status = "needs_review"
            warnings.append("В накладной больше 300 позиций. Вернули первые 300 для безопасного предпросмотра.")

        pages_detected = int(_float_or_zero(data.get("pagesDetected") or document.get("pagesDetected")) or len(photos))

        return {
            "ok": True,
            "status": status,
            "route": "warehouse_invoice",
            "document": {
                "type": "invoice_preview",
                "number": data.get("number") or data.get("invoiceNumber") or document.get("number") or document.get("invoiceNumber") or "",
                "date": data.get("date") or data.get("invoiceDate") or document.get("date") or document.get("invoiceDate") or "",
                "supplierName": data.get("supplierName") or data.get("supplier") or document.get("supplierName") or document.get("supplier") or "",
                "vat": vat_label,
                "pagesDetected": pages_detected,
            },
            "projectName": project_name,
            "warehouseTarget": warehouse_target,
            "selectedAction": selected_action,
            "items": normalized_items,
            "totals": {
                "totalBase": total_base,
                "totalVat": total_vat,
                "totalWithVat": total_with_vat,
            },
            "photos": photos,
            "warnings": warnings,
            "message": "Workflow подключен. Это предпросмотр без записи в склад и без создания трат.",
        }

    app.include_router(router)

