import json
import re
from datetime import datetime
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _text(value, limit=500):
    return str(value or "").strip()[:limit]


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _number(value, default=0.0):
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return default


def material_key(value):
    normalized = _text(value, 1000).lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _normalize_unit(value):
    unit = _text(value, 50).lower().replace("²", "2").replace("³", "3")
    compact = re.sub(r"[.\s_-]+", " ", unit).strip()
    aliases = {
        "м": "м", "метр": "м", "метры": "м", "m": "м", "пог м": "м", "п м": "м", "погонный метр": "м",
        "шт": "шт", "шт.": "шт", "штук": "шт", "штука": "шт",
        "кг": "кг", "килограмм": "кг", "килограммы": "кг", "килограммов": "кг",
        "т": "т", "тн": "т", "тонна": "т", "тонны": "т", "тонн": "т",
        "м2": "м2", "м кв": "м2", "кв м": "м2", "квадратный метр": "м2", "квадратных метров": "м2",
        "м3": "м3", "м куб": "м3", "куб м": "м3", "кубический метр": "м3", "кубических метров": "м3",
        "л": "л", "литр": "л", "литры": "л", "литров": "л",
        "компл": "компл", "комплект": "компл", "комплекты": "компл",
    }
    return aliases.get(compact, unit)


def _document_unit_key(value):
    unit = _normalize_unit(value)
    match = re.match(r"^(уп(?:ак)?|пач(?:ка)?|кор(?:об(?:ка)?)?|бухт(?:а)?|бобин(?:а)?|палет(?:а)?|рулон|меш(?:ок)?|ящик|ведр(?:о)?|канистр(?:а)?|бочк(?:а)?|баллон|катушк(?:а)?)\.?\s*\d", unit)
    if not match:
        return unit
    aliases = {
        "уп": "уп", "упак": "уп", "пач": "пач", "пачка": "пач", "кор": "кор", "короб": "кор", "коробка": "кор",
        "бухт": "бухта", "бухта": "бухта", "бобин": "бобина", "бобина": "бобина", "палет": "палета", "палета": "палета", "рулон": "рулон",
        "меш": "меш", "мешок": "меш", "ящик": "ящик", "ведр": "ведро", "ведро": "ведро", "канистр": "канистра", "канистра": "канистра",
        "бочк": "бочка", "бочка": "бочка", "баллон": "баллон", "катушк": "катушка", "катушка": "катушка",
    }
    return aliases.get(match.group(1).rstrip("."), match.group(1).rstrip("."))


def is_packaging_unit(value):
    """Return true only for document units that explicitly describe a package."""
    unit = _normalize_unit(value)
    return bool(re.match(
        r"^(уп(?:ак)?|пач(?:ка)?|кор(?:об(?:ка)?)?|бухт(?:а)?|бобин(?:а)?|палет(?:а)?|рулон|меш(?:ок)?|ящик|ведр(?:о)?|канистр(?:а)?|бочк(?:а)?|баллон|катушк(?:а)?)\.?($|\s|\d)",
        unit,
    ))


def base_unit_kind(value):
    unit = _normalize_unit(value)
    return {
        "м": "длина",
        "кг": "масса",
        "т": "масса",
        "м2": "площадь",
        "м3": "объем",
        "л": "жидкость",
        "шт": "количество",
        "компл": "комплект",
    }.get(unit, "другая единица")


def build_packaging_correction_preview(item, rule):
    """Describe a historical conversion without changing invoice or stock data."""
    document_quantity = _number(item.get("documentQuantity", item.get("quantity")), 0)
    document_unit = _text(item.get("documentUnit") or item.get("unit") or "шт", 50) or "шт"
    stored_quantity = _number(item.get("quantity"), 0)
    stored_unit = _text(item.get("unit") or document_unit, 50) or document_unit
    base_quantity = round(document_quantity * _number(rule.get("contentQuantity"), 0), 6)
    return {
        "document": {"quantity": document_quantity, "unit": document_unit},
        "stored": {"quantity": stored_quantity, "unit": stored_unit},
        "proposed": {"quantity": base_quantity, "unit": rule.get("baseUnit") or ""},
        "rule": {
            "id": rule.get("id"),
            "contentQuantity": _number(rule.get("contentQuantity"), 0),
            "baseUnit": rule.get("baseUnit") or "",
        },
        "canApply": False,
        "status": "preview_only",
        "reason": (
            "Автоматическая корректировка отключена: сначала нужно проверить выдачи и расходы, "
            "которые могли быть сделаны после этого прихода."
        ),
    }


def _date_sort_key(value):
    raw = _text(value, 100)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y, %H:%M"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def build_packaging_dependency_check(*, storage_location, stored_unit, invoice_date, current_balance, history_rows, movement_rows):
    """Summarize only possible post-receipt dependencies; never prove a relation by name alone."""
    receipt_date = _date_sort_key(invoice_date)

    def is_after_receipt(value):
        row_date = _date_sort_key(value)
        return row_date is None or receipt_date is None or row_date >= receipt_date

    possible_history = [
        {
            "id": row.get("id"),
            "type": row.get("type") or "",
            "quantity": _number(row.get("quantity"), 0),
            "unit": row.get("unit") or stored_unit,
            "date": str(row.get("date") or ""),
            "issuedTo": row.get("issued_to") or "",
            "issuedBy": row.get("issued_by") or "",
        }
        for row in (history_rows or [])
        if not str(row.get("type") or "").strip().lower().startswith("приход") and is_after_receipt(row.get("date"))
    ]
    possible_movements = [
        {
            "id": row.get("id"),
            "fromLocation": row.get("from_location") or "",
            "toLocation": row.get("to_location") or "",
            "quantity": _number(row.get("quantity"), 0),
            "unit": row.get("unit") or stored_unit,
            "date": str(row.get("date") or ""),
        }
        for row in (movement_rows or [])
        if is_after_receipt(row.get("date"))
    ]
    count = len(possible_history) + len(possible_movements)
    return {
        "storageLocation": storage_location,
        "currentBalance": {"quantity": _number(current_balance, 0), "unit": stored_unit},
        "possibleHistoryRows": possible_history[:20],
        "possibleMovementRows": possible_movements[:20],
        "possibleDependencyCount": count,
        "requiresManualReconciliation": True,
        "reason": (
            "Найдены возможные движения после прихода; сначала сверяйте их вручную."
            if count else
            "Совпадающих движений не найдено, но старая история не содержит прямой связи со строкой накладной."
        ),
    }


def build_packaging_traceability_status(*, invoice_id, item_index, history_rows, movement_rows):
    """Classify evidence links without inferring a legacy chain from matching names."""
    def has_exact_source(row):
        return (
            _positive_int(row.get("source_invoice_id")) == invoice_id
            and row.get("source_invoice_line_index") == item_index
        )

    receipt_source_linked = any(
        str(row.get("type") or "").strip().lower().startswith("приход") and has_exact_source(row)
        for row in (history_rows or [])
    )
    if not receipt_source_linked:
        return {
            "state": "legacy_unlinked",
            "receiptSourceLinked": False,
            "untracedDependencyCount": None,
            "requiresManualReconciliation": True,
            "reason": "Старая строка: прямой источник в истории не сохранен. Автоматическая корректировка запрещена; нужна ручная сверка.",
        }

    untraced_history = [
        row for row in (history_rows or [])
        if not str(row.get("type") or "").strip().lower().startswith("приход") and not has_exact_source(row)
    ]
    untraced_movements = [row for row in (movement_rows or []) if not has_exact_source(row)]
    untraced_count = len(untraced_history) + len(untraced_movements)
    if untraced_count:
        return {
            "state": "linked_with_untraced_dependencies",
            "receiptSourceLinked": True,
            "untracedDependencyCount": untraced_count,
            "requiresManualReconciliation": True,
            "reason": "Приход связан со строкой накладной, но есть последующие движения без прямой ссылки на нее. Нужна ручная сверка.",
        }
    return {
        "state": "linked_complete",
        "receiptSourceLinked": True,
        "untracedDependencyCount": 0,
        "requiresManualReconciliation": True,
        "reason": "Цепочка нового прихода прослеживается, но изменение исторических остатков все равно отключено до отдельного решения по сверке.",
    }


def build_packaging_review_snapshot(*, invoice, item_index, material_name, preview, dependency_check, traceability_status):
    """Keep immutable evidence of a manual review without creating a stock operation."""
    return {
        "warehouseInvoiceId": invoice.get("id"),
        "invoiceNumber": invoice.get("number") or "",
        "invoiceDate": str(invoice.get("date") or ""),
        "supplierName": invoice.get("supplier_name") or "",
        "itemIndex": item_index,
        "materialName": material_name,
        "preview": preview,
        "dependencyCheck": dependency_check,
        "traceabilityStatus": traceability_status,
    }


REVIEW_DECISIONS = {"confirmed", "discrepancy", "document_required"}


def normalize_review_decision(value):
    decision = _text(value, 50).lower()
    return decision if decision in REVIEW_DECISIONS else None


def packaging_review_row(row):
    snapshot = row.get("snapshot") or {}
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except (TypeError, ValueError, json.JSONDecodeError):
            snapshot = {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    traceability = snapshot.get("traceabilityStatus") or {}
    return {
        "id": row.get("id"),
        "warehouseInvoiceId": row.get("warehouse_invoice_id"),
        "invoiceNumber": row.get("number") or snapshot.get("invoiceNumber") or "",
        "supplierName": row.get("supplier_name") or snapshot.get("supplierName") or "",
        "itemIndex": row.get("item_index"),
        "materialName": snapshot.get("materialName") or "",
        "packagingRuleId": row.get("packaging_rule_id"),
        "status": row.get("status") or "reviewed_no_stock_change",
        "decision": row.get("review_decision") or "legacy_unclassified",
        "reviewNote": row.get("review_note") or "",
        "reviewedBy": row.get("reviewed_by") or "",
        "reviewedAt": row.get("reviewed_at").isoformat() if row.get("reviewed_at") else "",
        "traceabilityState": traceability.get("state") or "unknown",
    }


def ensure_packaging_schema(cur):
    cur.execute(
        """CREATE TABLE IF NOT EXISTS material_packaging_rules (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            supplier_id INT,
            material_key TEXT NOT NULL,
            material_name TEXT NOT NULL,
            document_unit VARCHAR(50) NOT NULL,
            base_unit VARCHAR(50) NOT NULL,
            content_quantity NUMERIC(14,4) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'confirmed',
            note TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )"""
    )
    cur.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_material_packaging_rule_identity
            ON material_packaging_rules(company_id, COALESCE(supplier_id, 0), material_key, document_unit)
        """
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS material_packaging_reviews (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            warehouse_invoice_id INT NOT NULL,
            item_index INT NOT NULL,
            packaging_rule_id INT NOT NULL,
            status VARCHAR(40) NOT NULL DEFAULT 'reviewed_no_stock_change',
            review_note TEXT NOT NULL,
            snapshot JSONB NOT NULL,
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMP DEFAULT NOW()
        )"""
    )
    cur.execute(
        """ALTER TABLE material_packaging_reviews
               ADD COLUMN IF NOT EXISTS review_decision VARCHAR(40) NOT NULL DEFAULT 'legacy_unclassified'"""
    )
    cur.execute(
        """CREATE INDEX IF NOT EXISTS idx_material_packaging_reviews_invoice
            ON material_packaging_reviews(company_id, warehouse_invoice_id, item_index, reviewed_at DESC)
        """
    )


def _rule_row(row):
    base_unit = row.get("base_unit") or ""
    return {
        "id": row.get("id"),
        "companyId": row.get("company_id"),
        "supplierId": row.get("supplier_id"),
        "materialName": row.get("material_name") or "",
        "materialKey": row.get("material_key") or "",
        "documentUnit": row.get("document_unit") or "",
        "baseUnit": base_unit,
        "baseUnitKind": base_unit_kind(base_unit),
        "contentQuantity": float(row.get("content_quantity") or 0),
        "status": row.get("status") or "confirmed",
        "note": row.get("note") or "",
        "createdBy": row.get("created_by") or "",
        "createdAt": row.get("created_at").isoformat() if row.get("created_at") else "",
        "updatedAt": row.get("updated_at").isoformat() if row.get("updated_at") else "",
    }


def normalize_invoice_packaging_items(cur, items, *, company_id, supplier_id=None):
    """Apply only confirmed rules. Raw document values stay on every converted item."""
    ensure_packaging_schema(cur)
    raw_items = [dict(item) for item in (items or []) if isinstance(item, dict)]
    if not raw_items:
        return []
    cur.execute(
        """SELECT * FROM material_packaging_rules
             WHERE company_id=%s AND status='confirmed'
               AND (supplier_id IS NULL OR supplier_id=%s)
             ORDER BY CASE WHEN supplier_id=%s THEN 0 ELSE 1 END, id DESC""",
        (company_id, supplier_id, supplier_id),
    )
    rules = [_rule_row(row) for row in cur.fetchall() or []]
    lookup = {}
    for rule in rules:
        lookup.setdefault((rule["materialKey"], _normalize_unit(rule["documentUnit"])), rule)

    normalized = []
    for raw in raw_items:
        item = dict(raw)
        name = _text(item.get("name"), 1000)
        document_unit = _text(item.get("unit") or "шт", 50) or "шт"
        document_unit_key = _document_unit_key(document_unit)
        quantity = _number(item.get("quantity"), 0)
        rule = lookup.get((material_key(name), document_unit_key))
        if not rule or quantity <= 0:
            # Preserve the received stock in its document unit. A package cannot
            # silently close an estimate need expressed in meters, kilograms, etc.
            if quantity > 0 and is_packaging_unit(document_unit):
                document_price = _number(item.get("price"), 0)
                item.update({
                    "documentQuantity": quantity,
                    "documentUnit": document_unit,
                    "documentPrice": document_price,
                    "conversionStatus": "needs_review",
                    "conversionSource": "packaging_rule_missing",
                    "conversionReviewReason": "Не найдено подтвержденное правило содержимого упаковки",
                })
            normalized.append(item)
            continue
        base_quantity = round(quantity * rule["contentQuantity"], 6)
        document_price = _number(item.get("price"), 0)
        item.update({
            "documentQuantity": quantity,
            "documentUnit": document_unit,
            "documentPrice": document_price,
            "quantity": base_quantity,
            "unit": rule["baseUnit"],
            "price": round(document_price / rule["contentQuantity"], 6) if document_price else 0,
            "baseQuantity": base_quantity,
            "baseUnit": rule["baseUnit"],
            "packageContentQuantity": rule["contentQuantity"],
            "packageContentUnit": rule["baseUnit"],
            "conversionStatus": "confirmed",
            "conversionSource": "packaging_rule",
            "packagingRuleId": rule["id"],
        })
        normalized.append(item)
    return normalized


def register_material_packaging_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    log_audit = deps["log_audit"]
    read_roles = {str(role or "").strip() for role in deps["read_roles"]}
    write_roles = {str(role or "").strip() for role in deps["write_roles"]}
    correction_roles = {"директор", "зам_директора"}

    def selected_actor(cur, current_user, mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(cur, current_user, None, mode, x_company_id=x_company_id, x_company_mode=x_company_mode)
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для правил упаковок выберите одну компанию")
        actors = [dict(actor or {}) for actor in effective_company_actors(current_user, context)]
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Компания правила упаковки не определена")
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания правила упаковки не определена")
        role = _text(actor.get("role"), 100)
        if mode == "read" and role not in read_roles:
            raise HTTPException(status_code=403, detail="Роль не позволяет смотреть правила упаковок")
        if mode != "read" and role not in write_roles:
            raise HTTPException(status_code=403, detail="Роль не позволяет менять правила упаковок")
        return actor, company_id

    def correction_context(cur, company_id, invoice_id, item_index):
        ensure_packaging_schema(cur)
        cur.execute(
            """SELECT id,company_id,number,date,supplier_id,supplier_name,items,status,project,location
                 FROM warehouse_invoices
                WHERE id=%s AND company_id=%s AND COALESCE(status,'Принята') <> 'Аннулирована'""",
            (invoice_id, company_id),
        )
        invoice = cur.fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Накладная не найдена в выбранной компании")
        try:
            items = json.loads(invoice.get("items") or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            items = []
        if not isinstance(items, list) or item_index >= len(items) or not isinstance(items[item_index], dict):
            raise HTTPException(status_code=404, detail="Строка накладной не найдена")
        item = dict(items[item_index])
        if item.get("conversionStatus") == "confirmed":
            raise HTTPException(status_code=409, detail="Эта строка уже была переведена по подтвержденному правилу")
        name = _text(item.get("name"), 1000)
        document_unit = _document_unit_key(item.get("documentUnit") or item.get("unit") or "шт")
        if not name or not is_packaging_unit(item.get("documentUnit") or item.get("unit")):
            raise HTTPException(status_code=409, detail="Строка не является упаковкой для пересчета")
        cur.execute(
            """SELECT * FROM material_packaging_rules
                 WHERE company_id=%s AND status='confirmed'
                   AND (supplier_id IS NULL OR supplier_id=%s)
                 ORDER BY CASE WHEN supplier_id=%s THEN 0 ELSE 1 END, id DESC""",
            (company_id, invoice.get("supplier_id"), invoice.get("supplier_id")),
        )
        rules = [_rule_row(row) for row in cur.fetchall() or []]
        rule = next((row for row in rules if row["materialKey"] == material_key(name) and _normalize_unit(row["documentUnit"]) == document_unit), None)
        if not rule:
            raise HTTPException(status_code=409, detail="Для этой строки пока нет подтвержденного правила упаковки")
        stored_unit = _text(item.get("unit") or item.get("documentUnit") or "шт", 50) or "шт"
        storage_location = invoice.get("project") or invoice.get("location") or "Основной склад"
        cur.execute(
            """SELECT id,type,quantity,unit,date,issued_to,issued_by,source_invoice_id,source_invoice_line_index
                 FROM warehouse_history
                WHERE company_id=%s AND project=%s
                  AND LOWER(TRIM(material))=LOWER(TRIM(%s))
                  AND LOWER(TRIM(COALESCE(unit,'')))=LOWER(TRIM(%s))
                ORDER BY id DESC""",
            (company_id, storage_location, name, stored_unit),
        )
        history_rows = [dict(row) for row in cur.fetchall() or []]
        cur.execute(
            """SELECT id,from_location,to_location,quantity,unit,date,source_invoice_id,source_invoice_line_index
                 FROM warehouse_movements
                WHERE company_id=%s
                  AND (from_location=%s OR to_location=%s)
                  AND LOWER(TRIM(material_name))=LOWER(TRIM(%s))
                  AND LOWER(TRIM(COALESCE(unit,'')))=LOWER(TRIM(%s))
                ORDER BY id DESC""",
            (company_id, storage_location, storage_location, name, stored_unit),
        )
        movement_rows = [dict(row) for row in cur.fetchall() or []]
        if storage_location == "Основной склад":
            cur.execute(
                """SELECT COALESCE(SUM(quantity),0) AS quantity FROM warehouse_main
                     WHERE company_id=%s AND LOWER(TRIM(name))=LOWER(TRIM(%s))
                       AND LOWER(TRIM(COALESCE(unit,'')))=LOWER(TRIM(%s))""",
                (company_id, name, stored_unit),
            )
        else:
            cur.execute(
                """SELECT COALESCE(SUM(quantity),0) AS quantity FROM materials
                     WHERE company_id=%s AND project=%s AND LOWER(TRIM(name))=LOWER(TRIM(%s))
                       AND LOWER(TRIM(COALESCE(unit,'')))=LOWER(TRIM(%s))""",
                (company_id, storage_location, name, stored_unit),
            )
        current_balance_row = cur.fetchone() or {}
        dependency_check = build_packaging_dependency_check(
            storage_location=storage_location,
            stored_unit=stored_unit,
            invoice_date=invoice.get("date"),
            current_balance=current_balance_row.get("quantity"),
            history_rows=history_rows,
            movement_rows=movement_rows,
        )
        preview = build_packaging_correction_preview(item, rule)
        traceability_status = build_packaging_traceability_status(
            invoice_id=invoice_id,
            item_index=item_index,
            history_rows=history_rows,
            movement_rows=movement_rows,
        )
        return {
            "invoice": invoice, "item": item, "materialName": name, "rule": rule,
            "preview": preview, "dependencyCheck": dependency_check,
            "traceabilityStatus": traceability_status,
        }

    @app.get("/material-packaging-rules")
    def list_material_packaging_rules(
        supplier_id: Optional[int] = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _actor, company_id = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
            ensure_packaging_schema(cur); conn.commit()
            where, params = ["company_id=%s"], [company_id]
            if supplier_id:
                where.append("supplier_id=%s"); params.append(supplier_id)
            cur.execute("SELECT * FROM material_packaging_rules WHERE " + " AND ".join(where) + " ORDER BY material_name,id", tuple(params))
            return [_rule_row(row) for row in cur.fetchall() or []]
        finally:
            cur.close(); conn.close()

    @app.get("/material-packaging-reviews")
    def list_material_packaging_reviews(
        limit: int = 30,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, company_id = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
            if _text(actor.get("role"), 100) not in correction_roles:
                raise HTTPException(status_code=403, detail="Реестр ручных сверок упаковок доступен директору или заместителю")
            ensure_packaging_schema(cur); conn.commit()
            cur.execute(
                """SELECT r.*,wi.number,wi.supplier_name
                     FROM material_packaging_reviews r
                     LEFT JOIN warehouse_invoices wi ON wi.id=r.warehouse_invoice_id AND wi.company_id=r.company_id
                    WHERE r.company_id=%s
                    ORDER BY r.reviewed_at DESC,r.id DESC
                    LIMIT %s""",
                (company_id, min(max(int(limit or 30), 1), 100)),
            )
            return [packaging_review_row(row) for row in cur.fetchall() or []]
        finally:
            cur.close(); conn.close()

    @app.post("/material-packaging-rules")
    def create_material_packaging_rule(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        material_name = _text(data.get("materialName") or data.get("material_name"), 1000)
        document_unit = _document_unit_key(data.get("documentUnit") or data.get("document_unit"))
        base_unit = _normalize_unit(data.get("baseUnit") or data.get("base_unit"))
        content_quantity = _number(data.get("contentQuantity") or data.get("content_quantity"), 0)
        if not material_name or not document_unit or not base_unit or content_quantity <= 0:
            raise HTTPException(status_code=400, detail="Укажите материал, единицу упаковки, базовую единицу и содержимое упаковки")
        supplier_id = _positive_int(data.get("supplierId") or data.get("supplier_id"))
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, company_id = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            ensure_packaging_schema(cur)
            key = material_key(material_name)
            cur.execute(
                """SELECT id FROM material_packaging_rules
                     WHERE company_id=%s AND COALESCE(supplier_id,0)=COALESCE(%s,0)
                       AND material_key=%s AND document_unit=%s FOR UPDATE""",
                (company_id, supplier_id, key, document_unit),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE material_packaging_rules
                         SET base_unit=%s,content_quantity=%s,material_name=%s,note=%s,updated_at=NOW()
                       WHERE id=%s RETURNING *""",
                    (base_unit, content_quantity, material_name, _text(data.get("note"), 2000), existing["id"]),
                )
            else:
                cur.execute(
                    """INSERT INTO material_packaging_rules
                        (company_id,supplier_id,material_key,material_name,document_unit,base_unit,content_quantity,status,note,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,'confirmed',%s,%s) RETURNING *""",
                    (company_id, supplier_id, key, material_name, document_unit, base_unit, content_quantity,
                     _text(data.get("note"), 2000), _text(actor.get("name") or actor.get("email"), 255)),
                )
            row = cur.fetchone(); conn.commit()
            return _rule_row(row)
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.post("/material-packaging-corrections/preview")
    def preview_material_packaging_correction(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        invoice_id = _positive_int((data or {}).get("warehouseInvoiceId") or (data or {}).get("warehouse_invoice_id"))
        try:
            item_index = int((data or {}).get("itemIndex") if (data or {}).get("itemIndex") is not None else (data or {}).get("item_index"))
        except (TypeError, ValueError):
            item_index = -1
        if not invoice_id or item_index < 0:
            raise HTTPException(status_code=400, detail="Укажите накладную и строку для предпросмотра")
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, company_id = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            if _text(actor.get("role"), 100) not in correction_roles:
                raise HTTPException(status_code=403, detail="Предпросмотр корректировки старого прихода доступен директору или заместителю")
            context = correction_context(cur, company_id, invoice_id, item_index)
            invoice = context["invoice"]
            return {
                "ok": True,
                "warehouseInvoiceId": invoice_id,
                "itemIndex": item_index,
                "invoice": {
                    "number": invoice.get("number") or "",
                    "date": str(invoice.get("date")) if invoice.get("date") else "",
                    "supplierName": invoice.get("supplier_name") or "",
                },
                "materialName": context["materialName"],
                "preview": context["preview"],
                "dependencyCheck": context["dependencyCheck"],
                "traceabilityStatus": context["traceabilityStatus"],
            }
        finally:
            cur.close(); conn.close()

    @app.post("/material-packaging-corrections/reviews")
    def confirm_material_packaging_review(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        invoice_id = _positive_int((data or {}).get("warehouseInvoiceId") or (data or {}).get("warehouse_invoice_id"))
        try:
            item_index = int((data or {}).get("itemIndex") if (data or {}).get("itemIndex") is not None else (data or {}).get("item_index"))
        except (TypeError, ValueError):
            item_index = -1
        review_note = _text((data or {}).get("reviewNote") or (data or {}).get("review_note"), 2000)
        review_decision = normalize_review_decision((data or {}).get("reviewDecision") or (data or {}).get("review_decision"))
        if not invoice_id or item_index < 0:
            raise HTTPException(status_code=400, detail="Укажите накладную и строку для сверки")
        if len(review_note) < 8:
            raise HTTPException(status_code=400, detail="Опишите результат ручной сверки не менее чем в 8 символах")
        if not review_decision:
            raise HTTPException(status_code=400, detail="Выберите результат ручной сверки")
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, company_id = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            if _text(actor.get("role"), 100) not in correction_roles:
                raise HTTPException(status_code=403, detail="Фиксировать сверку старого прихода может директор или заместитель")
            context = correction_context(cur, company_id, invoice_id, item_index)
            snapshot = build_packaging_review_snapshot(
                invoice=context["invoice"], item_index=item_index, material_name=context["materialName"],
                preview=context["preview"], dependency_check=context["dependencyCheck"],
                traceability_status=context["traceabilityStatus"],
            )
            snapshot["reviewDecision"] = review_decision
            cur.execute(
                """INSERT INTO material_packaging_reviews
                    (company_id,warehouse_invoice_id,item_index,packaging_rule_id,review_decision,review_note,snapshot,reviewed_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id,reviewed_at""",
                (company_id, invoice_id, item_index, context["rule"]["id"], review_decision,
                 review_note, json.dumps(snapshot, ensure_ascii=False), _text(actor.get("name") or actor.get("email"), 255)),
            )
            review = cur.fetchone(); conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()
        log_audit(
            user_name=_text(actor.get("name") or actor.get("email"), 255), user_role=_text(actor.get("role"), 100),
            action="review", entity_type="material_packaging_review", entity_id=review.get("id"),
            description="Зафиксирована ручная сверка упаковки без изменения остатка", project_name=context["invoice"].get("project") or "",
            company_id=company_id,
        )
        return {
            "ok": True,
            "review": {"id": review.get("id"), "status": "reviewed_no_stock_change", "decision": review_decision, "reviewedAt": review.get("reviewed_at").isoformat() if review.get("reviewed_at") else ""},
            "message": "Сверка зафиксирована. Остатки, накладная и история движений не изменены.",
            "preview": context["preview"], "dependencyCheck": context["dependencyCheck"],
            "traceabilityStatus": context["traceabilityStatus"],
        }
