import json
import re
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
    aliases = {"метр": "м", "метры": "м", "m": "м", "шт.": "шт", "штук": "шт", "тонна": "т", "тонн": "т"}
    return aliases.get(unit, unit)


def _document_unit_key(value):
    unit = _normalize_unit(value)
    match = re.match(r"^(уп(?:ак)?|пач(?:ка)?|кор(?:об(?:ка)?)?|бухт(?:а)?|бобин(?:а)?|палет(?:а)?|рулон)\.?\s*\d", unit)
    if not match:
        return unit
    aliases = {
        "уп": "уп", "упак": "уп", "пач": "пач", "пачка": "пач", "кор": "кор", "короб": "кор", "коробка": "кор",
        "бухт": "бухта", "бухта": "бухта", "бобин": "бобина", "бобина": "бобина", "палет": "палета", "палета": "палета", "рулон": "рулон",
    }
    return aliases.get(match.group(1).rstrip("."), match.group(1).rstrip("."))


def is_packaging_unit(value):
    """Return true only for document units that explicitly describe a package."""
    unit = _normalize_unit(value)
    return bool(re.match(
        r"^(уп(?:ак)?|пач(?:ка)?|кор(?:об(?:ка)?)?|бухт(?:а)?|бобин(?:а)?|палет(?:а)?|рулон)\.?($|\s|\d)",
        unit,
    ))


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


def _rule_row(row):
    return {
        "id": row.get("id"),
        "companyId": row.get("company_id"),
        "supplierId": row.get("supplier_id"),
        "materialName": row.get("material_name") or "",
        "materialKey": row.get("material_key") or "",
        "documentUnit": row.get("document_unit") or "",
        "baseUnit": row.get("base_unit") or "",
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
            ensure_packaging_schema(cur)
            cur.execute(
                """SELECT id,company_id,number,date,supplier_id,supplier_name,items,status
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
            return {
                "ok": True,
                "warehouseInvoiceId": invoice_id,
                "itemIndex": item_index,
                "invoice": {
                    "number": invoice.get("number") or "",
                    "date": str(invoice.get("date")) if invoice.get("date") else "",
                    "supplierName": invoice.get("supplier_name") or "",
                },
                "materialName": name,
                "preview": build_packaging_correction_preview(item, rule),
            }
        finally:
            cur.close(); conn.close()
