"""Supplier offer routes (KP).

Extracted verbatim from backend/main.py (Task 13.1, slice 44):
the six supplier-offer routes (list, history, create, update,
create-invoice, ship). Shared helpers stay in main.py and are
injected under their original names; visibility filters and company
scope come from the supplier_access and company_context features.
The model moved here — sole user.
"""

import datetime as dt
import hashlib
import math
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

try:
    from backend.features.supplier_access.service import (
        supplier_offer_visibility_filter,
    )
    from backend.features.company_context.service import (
        assert_rows_company_scope,
        company_id_scope_filter,
        resolve_resource_company_actor,
    )
except ModuleNotFoundError:
    from features.supplier_access.service import (
        supplier_offer_visibility_filter,
    )
    from features.company_context.service import (
        assert_rows_company_scope,
        company_id_scope_filter,
        resolve_resource_company_actor,
    )


class SupplierOfferModel(BaseModel):
    requestId: int
    supplierId: int
    pricePerUnit: float
    totalPrice: float
    deliveryDays: int = 0
    notes: str = ""



def register_supplier_offers_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    SUPPLY_ROLES = deps["SUPPLY_ROLES"]
    SUPPLY_INTERNAL_ROLES = deps["SUPPLY_INTERNAL_ROLES"]
    LEADERSHIP_ROLES = deps["LEADERSHIP_ROLES"]
    WORKER_EXECUTION_ROLES = deps["WORKER_EXECUTION_ROLES"]
    PACKAGE_LIMIT_ROLES = deps["PACKAGE_LIMIT_ROLES"]
    PLATFORM_STAFF_ROLES = deps["PLATFORM_STAFF_ROLES"]
    CLIENT_ACCOUNT_ROLES = deps["CLIENT_ACCOUNT_ROLES"]
    OFFERS_SELECT = deps["OFFERS_SELECT"]
    DELIVERY_SELECT = deps["DELIVERY_SELECT"]
    supplier_group_scope_ids = deps["supplier_group_scope_ids"]
    _require_supplier_offer_visibility = deps["_require_supplier_offer_visibility"]
    _log_supplier_offer_event = deps["_log_supplier_offer_event"]
    _ensure_supplier_offer_events_table = deps["_ensure_supplier_offer_events_table"]
    _ensure_supply_request_recipients_table = deps["_ensure_supply_request_recipients_table"]
    _ensure_supply_runtime_columns = deps["_ensure_supply_runtime_columns"]
    _find_existing_supplier_invoice_duplicate = deps["_find_existing_supplier_invoice_duplicate"]
    _find_supply_request_recipient = deps["_find_supply_request_recipient"]
    _float_or_zero = deps["_float_or_zero"]
    _json_list_or_empty = deps["_json_list_or_empty"]
    _norm_base_unit = deps["_norm_base_unit"]
    _norm_key_text = deps["_norm_key_text"]
    _normalize_supplier_ids = deps["_normalize_supplier_ids"]
    _positive_int_or_none = deps["_positive_int_or_none"]
    _resolve_work_company_context = deps["_resolve_work_company_context"]
    _supply_work_package = deps["_supply_work_package"]
    current_supplier_ids = deps["current_supplier_ids"]
    has_package_access = deps["has_package_access"]
    package_access_filter = deps["package_access_filter"]
    require_project_or_warehouse_access = deps["require_project_or_warehouse_access"]
    user_project_names = deps["user_project_names"]


    @app.get("/supplier-offers")
    def get_supplier_offers(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        role = current_user.get("role")
        if role in SUPPLY_INTERNAL_ROLES:
            try:
                company_context = _resolve_work_company_context(
                    cur,
                    current_user,
                    None,
                    "read",
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                )
                company_filter_sql, company_filter_params = company_id_scope_filter(company_context)
            except Exception:
                cur.close(); conn.close()
                raise
            if role == "прораб":
                projects = user_project_names(current_user)
                if not projects:
                    cur.close(); conn.close()
                    return []
                package_sql, package_params = package_access_filter(current_user)
                cur.execute(
                    OFFERS_SELECT
                    + " WHERE request_id IN (SELECT id FROM supply_requests WHERE project = ANY(%s)"
                    + package_sql
                    + ")"
                    + company_filter_sql
                    + " ORDER BY id DESC",
                    [projects] + package_params + company_filter_params,
                )
            else:
                cur.execute(
                    OFFERS_SELECT + " WHERE TRUE" + company_filter_sql + " ORDER BY id DESC",
                    company_filter_params,
                )
        elif role == "поставщик":
            _ensure_supply_request_recipients_table(cur)
            supplier_ids = current_supplier_ids(cur, current_user)
            visibility_sql, visibility_params = supplier_offer_visibility_filter(
                supplier_ids,
                current_user.get("id"),
            )
            cur.execute(
                OFFERS_SELECT + " WHERE TRUE" + visibility_sql + " ORDER BY id DESC",
                visibility_params,
            )
        elif role in WORKER_EXECUTION_ROLES:
            cur.close(); conn.close()
            return []
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.get("/supplier-offers/{id}/history")
    def get_supplier_offer_history(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _ensure_supplier_offer_events_table(cur)
        cur.execute("""
            SELECT o.id, o.supplier_id, o.company_id, o.request_id,
                   r.company_id AS request_company_id, r.project
              FROM supplier_offers o
              LEFT JOIN supply_requests r ON r.id=o.request_id
             WHERE o.id=%s
        """, (id,))
        offer = cur.fetchone()
        if not offer:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="КП не найдено")
        role = current_user.get("role")
        if role == "поставщик":
            try:
                _require_supplier_offer_visibility(cur, id, current_user, "Нет доступа к истории КП")
            except Exception:
                cur.close(); conn.close()
                raise
        elif role in SUPPLY_INTERNAL_ROLES:
            try:
                company_context, effective_user = resolve_resource_company_actor(
                    cur,
                    current_user,
                    offer.get("company_id"),
                    "read",
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                    allowed_roles=SUPPLY_INTERNAL_ROLES,
                    forbidden_detail="Роль в выбранной компании не позволяет смотреть историю КП",
                    platform_staff_roles=PLATFORM_STAFF_ROLES,
                    client_account_roles=CLIENT_ACCOUNT_ROLES,
                )
                company_id = int(company_context.get("companyId"))
                assert_rows_company_scope(
                    [{"company_id": offer.get("request_company_id")}],
                    company_id,
                    "Заявка КП",
                )
                if offer.get("project"):
                    require_project_or_warehouse_access(effective_user, offer.get("project") or "")
            except Exception:
                cur.close(); conn.close()
                raise
        else:
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        cur.execute("""
            SELECT id, offer_id as "offerId", event_type as "eventType",
                   status_from as "statusFrom", status_to as "statusTo",
                   actor_name as "actorName", actor_role as "actorRole",
                   payload_json as "payloadJson", created_at as "createdAt"
              FROM supplier_offer_events
             WHERE offer_id=%s
             ORDER BY id
        """, (id,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows

    @app.post("/supplier-offers")
    def create_supplier_offer(
        o: SupplierOfferModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*SUPPLY_ROLES)),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _ensure_supply_request_recipients_table(cur)
            cur.execute(
                """
                SELECT id, project, selected_suppliers, status, company_id
                  FROM supply_requests
                 WHERE id=%s
                 FOR UPDATE
                """,
                (o.requestId,),
            )
            req = cur.fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="Заявка не найдена")
            if (req.get("status") or "Новая") not in ("Утверждена", "КП запрошены"):
                raise HTTPException(status_code=400, detail="КП можно создать только после утверждения заявки директором")

            company_id = int(req.get("company_id") or 0)
            if company_id <= 0:
                raise HTTPException(status_code=409, detail="Заявка не привязана к компании")
            role = _current_user.get("role") or ""
            actor_user = _current_user
            supplier_user_id = None
            if role == "поставщик":
                supplier_scope_ids = current_supplier_ids(cur, _current_user)
                supplier_user_id = _current_user.get("id")
            else:
                company_context, actor_user = resolve_resource_company_actor(
                    cur,
                    _current_user,
                    company_id,
                    "update",
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                    allowed_roles=SUPPLY_INTERNAL_ROLES,
                    forbidden_detail="Роль в выбранной компании не позволяет создавать КП",
                    platform_staff_roles=PLATFORM_STAFF_ROLES,
                    client_account_roles=CLIENT_ACCOUNT_ROLES,
                )
                company_id = int(company_context.get("companyId"))
                supplier_scope_ids = supplier_group_scope_ids(cur, [o.supplierId])
                if req.get("project"):
                    require_project_or_warehouse_access(actor_user, req.get("project") or "")
            if not supplier_scope_ids and not supplier_user_id:
                raise HTTPException(status_code=403, detail="Поставщик не найден")

            cur.execute(
                "SELECT company_id FROM supply_request_recipients WHERE request_id=%s FOR UPDATE",
                (o.requestId,),
            )
            recipient_company_rows = cur.fetchall()
            assert_rows_company_scope(recipient_company_rows, company_id, "Получатели КП")
            cur.execute(
                "SELECT company_id FROM supplier_offers WHERE request_id=%s FOR UPDATE",
                (o.requestId,),
            )
            assert_rows_company_scope(cur.fetchall(), company_id, "Коммерческие предложения заявки")

            recipient = _find_supply_request_recipient(
                cur,
                o.requestId,
                company_id,
                supplier_scope_ids,
                supplier_user_id,
            )
            selected_supplier_ids = _normalize_supplier_ids(req.get("selected_suppliers") or [])
            if recipient:
                supplier_id = int(recipient.get("target_supplier_id") or recipient.get("supplier_id") or 0)
                recipient_scope_ids = _normalize_supplier_ids(recipient.get("supplier_group_ids") or [])
                supplier_scope_ids = sorted(set(supplier_scope_ids + recipient_scope_ids + [supplier_id]))
            else:
                if recipient_company_rows:
                    raise HTTPException(status_code=403, detail="Поставщик не является получателем этой заявки")
                legacy_matches = [sid for sid in supplier_scope_ids if sid in selected_supplier_ids]
                if not legacy_matches:
                    raise HTTPException(status_code=403, detail="Поставщик не выбран в заявке")
                supplier_id = int(legacy_matches[0])
            if supplier_id <= 0:
                raise HTTPException(status_code=403, detail="Поставщик для КП не определен")

            cur.execute(
                """
                SELECT id, status
                  FROM supplier_offers
                 WHERE request_id=%s
                   AND company_id=%s
                   AND supplier_id = ANY(%s::int[])
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (o.requestId, company_id, supplier_scope_ids),
            )
            existing_offer = cur.fetchone()
            if existing_offer:
                existing_status = (existing_offer.get("status") or "").strip()
                if existing_status not in ("", "Ожидает", "Ожидает ответа"):
                    raise HTTPException(status_code=409, detail="КП уже существует. Измените существующее предложение вместо создания дубля")
                offer_id = int(existing_offer.get("id"))
                cur.execute(
                    """
                    UPDATE supplier_offers
                       SET supplier_id=%s,
                           price_per_unit=%s,
                           total_price=%s,
                           delivery_days=%s,
                           notes=%s
                     WHERE id=%s
                       AND company_id=%s
                    """,
                    (supplier_id, o.pricePerUnit, o.totalPrice, o.deliveryDays, o.notes, offer_id, company_id),
                )
                _log_supplier_offer_event(
                    cur,
                    offer_id,
                    "draft_updated",
                    existing_status or "Ожидает",
                    existing_status or "Ожидает",
                    actor_user,
                    {
                        "action": "draft_updated",
                        "pricePerUnit": o.pricePerUnit,
                        "totalPrice": o.totalPrice,
                        "deliveryDays": o.deliveryDays,
                    },
                )
            else:
                cur.execute(
                    """
                    INSERT INTO supplier_offers
                        (request_id, supplier_id, company_id, price_per_unit, total_price, delivery_days, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (o.requestId, supplier_id, company_id, o.pricePerUnit, o.totalPrice, o.deliveryDays, o.notes),
                )
                offer_id = int(cur.fetchone()["id"])
                _log_supplier_offer_event(cur, offer_id, "created", "", "Ожидает", actor_user, {"action": "created"})
            cur.execute(OFFERS_SELECT + " WHERE id=%s AND company_id=%s", (offer_id, company_id))
            row = cur.fetchone()
            conn.commit()
            return dict(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        finally:
            cur.close()
            conn.close()

    @app.put("/supplier-offers/{id}")
    def update_supplier_offer(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*SUPPLY_ROLES)),
    ):
        from datetime import datetime
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        action = data.get('action')
        cur.execute("""
            SELECT o.id, o.supplier_id, o.request_id, o.company_id,
                   o.status, o.delivery_status, r.company_id AS request_company_id, r.project
            FROM supplier_offers o
            LEFT JOIN supply_requests r ON r.id=o.request_id
            WHERE o.id=%s
        """, (id,))
        offer_access = cur.fetchone()
        if not offer_access:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="КП не найдено")
        role = _current_user.get("role")
        actor_user = _current_user
        if role == "поставщик":
            try:
                _require_supplier_offer_visibility(cur, id, _current_user)
            except Exception:
                cur.close(); conn.close()
                raise
            if action not in ('respond', 'withdraw'):
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Поставщик может только ответить на своё КП или отозвать его")
        else:
            try:
                company_context, actor_user = resolve_resource_company_actor(
                    cur,
                    _current_user,
                    offer_access.get("company_id"),
                    "update",
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                    allowed_roles=SUPPLY_INTERNAL_ROLES,
                    forbidden_detail="Роль в выбранной компании не позволяет изменять КП",
                    platform_staff_roles=PLATFORM_STAFF_ROLES,
                    client_account_roles=CLIENT_ACCOUNT_ROLES,
                )
                role = actor_user.get("role") or ""
                if offer_access.get("project"):
                    require_project_or_warehouse_access(actor_user, offer_access.get("project") or "")
            except Exception:
                cur.close(); conn.close()
                raise

        company_id = int(offer_access.get("company_id") or 0)
        try:
            assert_rows_company_scope(
                [{"company_id": offer_access.get("request_company_id")}],
                company_id,
                "Заявка КП",
            )
            _ensure_supply_request_recipients_table(cur)
            cur.execute(
                "SELECT company_id FROM supplier_offers WHERE request_id=%s FOR UPDATE",
                (offer_access.get("request_id"),),
            )
            assert_rows_company_scope(cur.fetchall(), company_id, "Коммерческие предложения заявки")
            cur.execute(
                "SELECT company_id FROM supply_request_recipients WHERE request_id=%s FOR UPDATE",
                (offer_access.get("request_id"),),
            )
            assert_rows_company_scope(cur.fetchall(), company_id, "Получатели КП")
        except Exception:
            cur.close(); conn.close()
            raise

        def _offer_line_key(item):
            return (
                _norm_key_text((item or {}).get("materialName") or (item or {}).get("name") or ""),
                _norm_base_unit((item or {}).get("unit") or ""),
                _supply_work_package((item or {}).get("workPackage") or (item or {}).get("work_package") or ""),
            )

        def _require_valid_supplier_offer_for_approval():
            cur.execute("""SELECT o.status, o.total_price, o.price_per_unit, o.items_kp_json,
                                  r.items_json, r.quantity
                           FROM supplier_offers o
                           LEFT JOIN supply_requests r ON r.id=o.request_id
                           WHERE o.id=%s""", (id,))
            guard = cur.fetchone()
            if not guard:
                raise HTTPException(status_code=404, detail="КП не найдено")
            if (guard.get("status") or "") != "Получено":
                raise HTTPException(status_code=400, detail="Нельзя утвердить КП, пока поставщик не прислал цены")
            request_items = _json_list_or_empty(guard.get("items_json"))
            kp_items = _json_list_or_empty(guard.get("items_kp_json"))
            total_price = _float_or_zero(guard.get("total_price"))
            price_per_unit = _float_or_zero(guard.get("price_per_unit"))
            if request_items:
                if not kp_items:
                    raise HTTPException(status_code=400, detail="В КП нет постатейных цен по материалам заявки")
                request_by_key = {}
                for req_item in request_items:
                    if not isinstance(req_item, dict):
                        continue
                    request_by_key[_offer_line_key(req_item)] = req_item
                priced_keys = set()
                kp_total = 0.0
                for kp_item in kp_items:
                    if not isinstance(kp_item, dict):
                        continue
                    key = _offer_line_key(kp_item)
                    req_item = request_by_key.get(key)
                    if not req_item:
                        continue
                    kp_qty = _float_or_zero(kp_item.get("quantity"))
                    req_qty = _float_or_zero(req_item.get("quantity"))
                    price = _float_or_zero(kp_item.get("pricePerUnit"))
                    line_total = _float_or_zero(kp_item.get("totalPrice"))
                    if price <= 0 or line_total <= 0:
                        continue
                    if abs(kp_qty - req_qty) > 0.000001:
                        raise HTTPException(
                            status_code=400,
                            detail="Количество в КП не совпадает с заявкой: " + str(req_item.get("materialName") or req_item.get("name") or "позиция")
                        )
                    expected_line_total = round(price * req_qty, 2)
                    if abs(line_total - expected_line_total) > 0.05:
                        raise HTTPException(
                            status_code=400,
                            detail="Сумма строки КП не сходится с ценой и количеством: " + str(req_item.get("materialName") or req_item.get("name") or "позиция")
                        )
                    kp_total += line_total
                    priced_keys.add(key)
                missing = []
                for req_item in request_items:
                    if not isinstance(req_item, dict):
                        continue
                    if _offer_line_key(req_item) not in priced_keys:
                        missing.append(req_item.get("materialName") or req_item.get("name") or "позиция")
                if missing:
                    raise HTTPException(status_code=400, detail="В КП нет цены по позициям: " + ", ".join(missing[:5]))
                if abs(total_price - round(kp_total, 2)) > 0.05:
                    raise HTTPException(status_code=400, detail="Итог КП не совпадает с суммой строк заявки")
            else:
                request_qty = _float_or_zero(guard.get("quantity"))
                if request_qty > 0 and price_per_unit <= 0:
                    raise HTTPException(status_code=400, detail="В КП не указана цена за единицу")
            if total_price <= 0:
                raise HTTPException(status_code=400, detail="Нельзя утвердить КП с нулевой суммой")

        if action == 'respond':
            # Поставщик отвечает на КП: цена, срок, условия, НДС, PDF, комментарий
            import json as _json
            current_status = offer_access.get("status") or ""
            items_kp = data.get('itemsKp') or []
            # Если пришёл массив постатейного КП — считаем итог автоматически
            items_kp_json = None
            if items_kp and isinstance(items_kp, list):
                # Нормализация: каждый item должен иметь pricePerUnit и quantity
                normalized = []
                calc_total = 0.0
                for it in items_kp:
                    if not isinstance(it, dict): continue
                    p = float(it.get('pricePerUnit') or 0)
                    q = float(it.get('quantity') or 0)
                    line_total = p * q
                    normalized.append({
                        'materialName': it.get('materialName',''),
                        'quantity': q,
                        'unit': it.get('unit','шт'),
                        'workPackage': (it.get('workPackage') or it.get('work_package') or '').strip(),
                        'pricePerUnit': p,
                        'totalPrice': line_total,
                        'deliveryDays': int(it.get('deliveryDays') or 0) if it.get('deliveryDays') else None,
                        'notes': it.get('notes','')
                    })
                    calc_total += line_total
                items_kp_json = _json.dumps(normalized, ensure_ascii=False)
                # Для совместимости: pricePerUnit = средневзвешенная, totalPrice = сумма
                total = float(data.get('totalPrice') or calc_total)
                ppu = float(data.get('pricePerUnit') or (calc_total / max(1, len(normalized))))
            else:
                # Старый путь — одна цена за единицу
                ppu = float(data.get('pricePerUnit') or 0)
                qty_for_total = float(data.get('quantity') or 0)
                total = float(data.get('totalPrice') or (ppu * qty_for_total))
                cur.execute("""SELECT items_json, material_name, quantity, unit, COALESCE(work_package,'Основная') AS work_package
                               FROM supply_requests WHERE id=%s""", (offer_access.get("request_id"),))
                req_line = cur.fetchone()
                req_items = _json_list_or_empty(req_line.get("items_json") if req_line else None)
                if not req_items and req_line:
                    req_items = [{
                        "materialName": req_line.get("material_name") or "",
                        "quantity": req_line.get("quantity") or qty_for_total,
                        "unit": req_line.get("unit") or "",
                        "workPackage": req_line.get("work_package") or "Основная",
                    }]
                if len(req_items) == 1:
                    req_item = req_items[0]
                    req_qty = _float_or_zero(req_item.get("quantity") or qty_for_total)
                    items_kp_json = _json.dumps([{
                        "materialName": req_item.get("materialName") or req_item.get("name") or "",
                        "quantity": req_qty,
                        "unit": req_item.get("unit") or "",
                        "workPackage": (req_item.get("workPackage") or req_item.get("work_package") or (req_line.get("work_package") if req_line else "") or "Основная").strip(),
                        "pricePerUnit": ppu,
                        "totalPrice": round(ppu * req_qty, 2),
                        "deliveryDays": int(data.get("deliveryDays") or 0) if data.get("deliveryDays") else None,
                        "notes": data.get("supplierMessage") or "",
                    }], ensure_ascii=False)
            cur.execute(
                "UPDATE supplier_offers SET status=%s, price_per_unit=%s, total_price=%s, delivery_days=%s, "
                "payment_terms=%s, vat_included=%s, pdf_url=%s, valid_until=%s, supplier_message=%s, "
                "items_kp_json=COALESCE(%s, items_kp_json), responded_at=%s WHERE id=%s",
                ('Получено', ppu, total, int(data.get('deliveryDays') or 0),
                 data.get('paymentTerms') or 'Постоплата',
                 bool(data.get('vatIncluded', True)),
                 data.get('pdfUrl') or None,
                 data.get('validUntil') or None,
                 data.get('supplierMessage') or '',
                 items_kp_json,
                 datetime.now(), id))
            _ensure_supply_request_recipients_table(cur)
            cur.execute("""
                UPDATE supply_request_recipients
                   SET status=%s, responded_at=NOW()
                 WHERE request_id=%s
                   AND company_id=%s
                   AND (
                        target_supplier_id=%s
                     OR supplier_id=%s
                     OR COALESCE(supplier_group_ids, '{}'::int[]) && %s::int[]
                   )
            """, (
                "КП получено",
                offer_access.get("request_id"),
                company_id,
                offer_access.get("supplier_id"),
                offer_access.get("supplier_id"),
                [offer_access.get("supplier_id")],
            ))
            _log_supplier_offer_event(cur, id, "responded", current_status, "Получено", actor_user, data)
        elif action == 'select':
            # Директор выбрал это КП
            if role not in LEADERSHIP_ROLES:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Утвердить КП может только директор или замдиректора")
            try:
                _require_valid_supplier_offer_for_approval()
            except HTTPException:
                cur.close(); conn.close()
                raise
            cur.execute("UPDATE supplier_offers SET status=%s WHERE id=%s", ('Утверждено', id))
            _ensure_supply_request_recipients_table(cur)
            cur.execute("""
                UPDATE supply_request_recipients
                   SET status=%s
                 WHERE request_id=%s
                   AND company_id=%s
                   AND (
                        target_supplier_id=%s
                     OR supplier_id=%s
                     OR COALESCE(supplier_group_ids, '{}'::int[]) && %s::int[]
                   )
            """, (
                "КП выбрано",
                offer_access.get("request_id"),
                company_id,
                offer_access.get("supplier_id"),
                offer_access.get("supplier_id"),
                [offer_access.get("supplier_id")],
            ))
            _log_supplier_offer_event(cur, id, "selected", offer_access.get("status") or "", "Утверждено", actor_user, data)
            # Остальные КП по этой заявке — отклонены
            cur.execute("SELECT request_id FROM supplier_offers WHERE id=%s", (id,))
            r = cur.fetchone()
            if r and r['request_id']:
                cur.execute("UPDATE supplier_offers SET status=%s WHERE request_id=%s AND company_id=%s AND id<>%s AND status<>%s",
                    ('Отклонено', r['request_id'], company_id, id, 'Отклонено'))
                cur.execute("""
                    UPDATE supply_request_recipients
                       SET status=%s
                     WHERE request_id=%s
                       AND company_id=%s
                       AND status NOT IN (%s)
                """, ("КП отклонено", r['request_id'], company_id, "КП выбрано"))
        elif action == 'withdraw':
            current_status = offer_access.get("status") or ""
            if current_status == "Утверждено":
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Выигранное КП нельзя отозвать. Сначала отмените счёт/поставку через снабжение.")
            if current_status in ("Отозвано", "Отклонено"):
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="КП уже закрыто")
            cur.execute("SELECT id FROM supplier_invoices WHERE offer_id=%s LIMIT 1", (id,))
            has_invoice = cur.fetchone()
            cur.execute("SELECT id FROM supply_deliveries WHERE offer_id=%s LIMIT 1", (id,))
            has_delivery = cur.fetchone()
            if has_invoice or has_delivery or offer_access.get("delivery_status"):
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="КП уже связано со счётом или поставкой, отзыв заблокирован")
            cur.execute("UPDATE supplier_offers SET status=%s WHERE id=%s", ('Отозвано', id))
            _ensure_supply_request_recipients_table(cur)
            cur.execute("""
                UPDATE supply_request_recipients
                   SET status=%s
                 WHERE request_id=%s
                   AND company_id=%s
                   AND (
                        target_supplier_id=%s
                     OR supplier_id=%s
                     OR COALESCE(supplier_group_ids, '{}'::int[]) && %s::int[]
                   )
            """, (
                "КП отозвано",
                offer_access.get("request_id"),
                company_id,
                offer_access.get("supplier_id"),
                offer_access.get("supplier_id"),
                [offer_access.get("supplier_id")],
            ))
            _log_supplier_offer_event(cur, id, "withdrawn", current_status, "Отозвано", actor_user, data)
        elif action == 'reject':
            cur.execute("UPDATE supplier_offers SET status=%s WHERE id=%s", ('Отклонено', id))
            _ensure_supply_request_recipients_table(cur)
            cur.execute("""
                UPDATE supply_request_recipients
                   SET status=%s
                 WHERE request_id=%s
                   AND company_id=%s
                   AND (
                        target_supplier_id=%s
                     OR supplier_id=%s
                     OR COALESCE(supplier_group_ids, '{}'::int[]) && %s::int[]
                   )
            """, (
                "КП отклонено",
                offer_access.get("request_id"),
                company_id,
                offer_access.get("supplier_id"),
                offer_access.get("supplier_id"),
                [offer_access.get("supplier_id")],
            ))
            _log_supplier_offer_event(cur, id, "rejected", offer_access.get("status") or "", "Отклонено", actor_user, data)
        else:
            if 'status' in data:
                new_status = str(data.get('status') or '').strip()
                if new_status in ("Утверждено", "Выбрано", "Принято") and role not in LEADERSHIP_ROLES:
                    cur.close(); conn.close()
                    raise HTTPException(status_code=403, detail="Утвердить КП может только директор или замдиректора")
                if new_status in ("Утверждено", "Выбрано", "Принято"):
                    try:
                        _require_valid_supplier_offer_for_approval()
                    except HTTPException:
                        cur.close(); conn.close()
                        raise
                cur.execute("UPDATE supplier_offers SET status=%s WHERE id=%s", (data['status'], id))
                if new_status in ("Утверждено", "Выбрано", "Принято"):
                    cur.execute("SELECT request_id FROM supplier_offers WHERE id=%s", (id,))
                    r = cur.fetchone()
                    if r and r['request_id']:
                        cur.execute("UPDATE supplier_offers SET status=%s WHERE request_id=%s AND company_id=%s AND id<>%s AND status<>%s",
                            ('Отклонено', r['request_id'], company_id, id, 'Отклонено'))
                _log_supplier_offer_event(cur, id, "status_changed", offer_access.get("status") or "", data.get('status'), actor_user, data)
            if 'deliveryStatus' in data:
                cur.execute("UPDATE supplier_offers SET delivery_status=%s WHERE id=%s", (data['deliveryStatus'], id))
                _log_supplier_offer_event(cur, id, "delivery_status_changed", offer_access.get("delivery_status") or "", data.get('deliveryStatus'), actor_user, data)
        cur.execute(OFFERS_SELECT + " WHERE id=%s", (id,))
        row = cur.fetchone()
        conn.commit()
        conn.close()
        return dict(row) if row else {"ok": True}

    @app.post("/supplier-offers/{id}/create-invoice")
    def create_invoice_from_offer(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        """Поставщик выставляет счёт по выигранному КП.
           Автоматически создаёт supplier_invoice."""
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _ensure_supply_runtime_columns(cur)
        conn.commit()
        cur.execute(
            "SELECT o.id, o.supplier_id, o.request_id, o.total_price, o.payment_terms, o.vat_included, "
            "o.company_id, r.company_id AS request_company_id, "
            "s.name as supplier_name, r.project as project_name, r.material_name, "
            "COALESCE(r.work_package,'') AS work_package, r.items_json "
            "FROM supplier_offers o "
            "LEFT JOIN suppliers s ON s.id=o.supplier_id "
            "JOIN supply_requests r ON r.id=o.request_id "
            "WHERE o.id=%s AND o.status=%s FOR UPDATE OF o, r",
            (id, 'Утверждено'))
        offer = cur.fetchone()
        if not offer:
            cur.close(); conn.close()
            return {"error": "Утверждённое КП не найдено"}
        company_id = int(offer.get("company_id") or 0)
        claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
        try:
            assert_rows_company_scope(
                [{"company_id": offer.get("request_company_id")}],
                company_id,
                "Заявка утверждённого КП",
            )
            if claimed_company_id not in (None, ""):
                claimed_id = _positive_int_or_none(claimed_company_id)
                if not claimed_id:
                    raise HTTPException(status_code=400, detail="companyId должен быть положительным целым числом")
                assert_rows_company_scope(
                    [{"company_id": claimed_id}],
                    company_id,
                    "companyId счёта",
                )
            _ensure_supply_request_recipients_table(cur)
            cur.execute("SELECT company_id FROM supplier_offers WHERE request_id=%s FOR UPDATE", (offer.get("request_id"),))
            assert_rows_company_scope(cur.fetchall(), company_id, "Коммерческие предложения заявки")
            cur.execute("SELECT company_id FROM supply_request_recipients WHERE request_id=%s FOR UPDATE", (offer.get("request_id"),))
            assert_rows_company_scope(cur.fetchall(), company_id, "Получатели КП")

            actor_user = _current_user
            if _current_user.get("role") == "поставщик":
                _require_supplier_offer_visibility(cur, id, _current_user, "Нет доступа к КП для выставления счёта")
            else:
                _company_context, actor_user = resolve_resource_company_actor(
                    cur,
                    _current_user,
                    company_id,
                    "create",
                    claimed_company_id=claimed_company_id,
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                    allowed_roles=SUPPLY_INTERNAL_ROLES,
                    forbidden_detail="Роль в выбранной компании не позволяет создавать счёт по КП",
                    platform_staff_roles=PLATFORM_STAFF_ROLES,
                    client_account_roles=CLIENT_ACCOUNT_ROLES,
                )
                require_project_or_warehouse_access(actor_user, offer['project_name'] or "")
                if actor_user.get("role") in PACKAGE_LIMIT_ROLES and not has_package_access(actor_user, offer.get("work_package") or "Основная"):
                    raise HTTPException(status_code=403, detail="Нет доступа к пакету КП")
        except Exception:
            conn.rollback()
            cur.close(); conn.close()
            raise
        invoice_number = str(data.get('invoiceNumber') or '').strip()
        if not invoice_number:
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Укажите номер счёта")
        if len(invoice_number) > 100:
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Номер счёта слишком длинный")
        invoice_date = str(data.get('invoiceDate') or '').strip() or None
        if invoice_date:
            try:
                dt.date.fromisoformat(invoice_date)
            except ValueError:
                conn.rollback()
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Дата счёта должна быть в формате ГГГГ-ММ-ДД")
        try:
            raw_amount = data.get('amount')
            amount = float(raw_amount if raw_amount not in (None, "") else (offer['total_price'] or 0))
            vat_amount = float(data.get('vatAmount') or 0)
        except (TypeError, ValueError):
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Сумма счёта и НДС должны быть числами")
        if not math.isfinite(amount) or amount <= 0:
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Сумма счёта должна быть больше нуля")
        if not math.isfinite(vat_amount) or vat_amount < 0 or vat_amount > amount:
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Сумма НДС должна быть от нуля до суммы счёта")
        offer_total = _float_or_zero(offer.get('total_price'))
        if offer_total > 0 and amount > offer_total + max(1.0, offer_total * 0.02):
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail=f"Сумма счёта не может быть выше утверждённого КП: {round(offer_total, 2)} ₽")
        file_url = data.get('fileUrl') or data.get('photoUrl') or ''
        description = data.get('description') or ('Материал: '+(offer['material_name'] or ''))
        supplier_scope_ids = supplier_group_scope_ids(cur, [offer.get("supplier_id")])
        invoice_lock_key = "|".join((
            str(company_id),
            ",".join(str(value) for value in sorted(supplier_scope_ids)),
            invoice_number.casefold(),
            invoice_date or "",
            str(offer.get("project_name") or "").casefold(),
        ))
        invoice_lock_id = int.from_bytes(
            hashlib.sha256(invoice_lock_key.encode("utf-8")).digest()[:8],
            "big",
            signed=True,
        )
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (invoice_lock_id,))
        cur.execute("""SELECT id, status, company_id FROM supplier_invoices
                       WHERE offer_id=%s
                       ORDER BY id DESC FOR UPDATE""", (id,))
        invoice_rows = cur.fetchall()
        try:
            assert_rows_company_scope(invoice_rows, company_id, "Счета утверждённого КП")
        except Exception:
            conn.rollback()
            cur.close(); conn.close()
            raise
        existing_invoice = next(
            (row for row in invoice_rows if (row.get("status") or "") != "Аннулирован"),
            None,
        )
        if existing_invoice:
            existing_id = existing_invoice.get('id') if isinstance(existing_invoice, dict) else existing_invoice[0]
            conn.commit()
            cur.close(); conn.close()
            return {"ok": True, "id": existing_id, "alreadyExists": True}
        item_packages = {
            (it.get("workPackage") or it.get("work_package") or offer.get("work_package") or "").strip()
            for it in _json_list_or_empty(offer.get("items_json")) if isinstance(it, dict)
        }
        item_packages = {p for p in item_packages if p}
        invoice_package = data.get('workPackage') or (next(iter(item_packages)) if len(item_packages) == 1 else (offer.get("work_package") or ""))
        duplicate_invoice = _find_existing_supplier_invoice_duplicate(
            cur,
            company_id=company_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            project_name=offer['project_name'],
            supplier_id=offer['supplier_id'],
            supplier_name=offer['supplier_name'],
            amount=amount,
            request_id=offer['request_id'],
            offer_id=offer['id'],
        )
        if duplicate_invoice:
            existing_id = int(duplicate_invoice.get("id") or 0)
            cur.execute(
                """
                SELECT id, company_id, supplier_id, offer_id, request_id
                  FROM supplier_invoices
                 WHERE id=%s
                 FOR UPDATE
                """,
                (existing_id,),
            )
            duplicate_scope = cur.fetchone()
            try:
                assert_rows_company_scope([duplicate_scope], company_id, "Найденный дубликат счёта")
            except Exception:
                conn.rollback()
                cur.close(); conn.close()
                raise
            if int((duplicate_scope or {}).get("supplier_id") or 0) not in supplier_scope_ids:
                conn.rollback()
                cur.close(); conn.close()
                raise HTTPException(status_code=409, detail="Счёт с такими реквизитами относится к другому поставщику")
            linked_offer_id = int((duplicate_scope or {}).get("offer_id") or 0)
            linked_request_id = int((duplicate_scope or {}).get("request_id") or 0)
            if linked_offer_id and linked_offer_id != int(offer.get("id") or 0):
                conn.rollback()
                cur.close(); conn.close()
                raise HTTPException(status_code=409, detail="Счёт уже связан с другим КП")
            if linked_request_id and linked_request_id != int(offer.get("request_id") or 0):
                conn.rollback()
                cur.close(); conn.close()
                raise HTTPException(status_code=409, detail="Счёт уже связан с другой заявкой")
            cur.execute(
                """
                UPDATE supplier_invoices
                   SET offer_id=COALESCE(offer_id,%s),
                       request_id=COALESCE(request_id,%s),
                       supplier_id=COALESCE(supplier_id,%s),
                       supplier_name=COALESCE(NULLIF(supplier_name,''),%s),
                       payment_terms=COALESCE(NULLIF(payment_terms,''),%s),
                       material_name=COALESCE(NULLIF(material_name,''),%s),
                       work_package=COALESCE(NULLIF(work_package,''),%s),
                       description=COALESCE(NULLIF(description,''),%s),
                       file_url=COALESCE(NULLIF(file_url,''),%s)
                 WHERE id=%s AND company_id=%s
                """,
                (
                    offer['id'],
                    offer['request_id'],
                    offer['supplier_id'],
                    offer['supplier_name'],
                    offer['payment_terms'],
                    offer['material_name'],
                    invoice_package,
                    description,
                    file_url,
                    existing_id,
                    company_id,
                ),
            )
            if cur.rowcount != 1:
                conn.rollback()
                cur.close(); conn.close()
                raise HTTPException(status_code=409, detail="Компания счёта изменилась во время создания")
            _log_supplier_offer_event(
                cur,
                id,
                "invoice_linked",
                "Утверждено",
                "Утверждено",
                actor_user,
                {
                    "action": "invoice_linked",
                    "invoiceId": existing_id,
                    "invoiceNumber": invoice_number,
                    "amount": amount,
                    "vatAmount": vat_amount,
                    "duplicateDocument": True,
                },
            )
            conn.commit()
            cur.close(); conn.close()
            return {"ok": True, "id": existing_id, "alreadyExists": True, "duplicateDocument": True}
        cur.execute(
            "INSERT INTO supplier_invoices "
            "(company_id, supplier_id, supplier_name, project_name, invoice_number, invoice_date, "
            "amount, vat_amount, description, file_url, status, offer_id, request_id, "
            "payment_terms, material_name, work_package) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (company_id, offer['supplier_id'], offer['supplier_name'], offer['project_name'],
             invoice_number, invoice_date, amount, vat_amount, description, file_url,
             'На утверждении', offer['id'], offer['request_id'],
             offer['payment_terms'], offer['material_name'], invoice_package))
        new_id = cur.fetchone()['id']
        _log_supplier_offer_event(
            cur,
            id,
            "invoice_created",
            "Утверждено",
            "Утверждено",
            actor_user,
            {
                "action": "invoice_created",
                "invoiceId": new_id,
                "invoiceNumber": invoice_number,
                "amount": amount,
                "vatAmount": vat_amount,
            },
        )
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": new_id}

    @app.post("/supplier-offers/{id}/ship")
    def ship_supplier_offer(id: int, data: dict, _current_user: dict = Depends(require_roles(*SUPPLY_ROLES))):
        from datetime import datetime
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _ensure_supply_runtime_columns(cur)
        conn.commit()
        cur.execute("""
            SELECT o.id, o.request_id, o.supplier_id, o.price_per_unit, o.total_price,
                   o.payment_terms, o.items_kp_json, COALESCE(o.company_id, r.company_id, 1) as company_id,
                   s.name as supplier_name,
                   r.project, COALESCE(r.work_package,'') as work_package,
                   r.material_name, r.quantity, r.unit, r.items_json
            FROM supplier_offers o
            LEFT JOIN suppliers s ON s.id=o.supplier_id
            LEFT JOIN supply_requests r ON r.id=o.request_id
            WHERE o.id=%s AND o.status=%s
        """, (id, 'Утверждено'))
        offer = cur.fetchone()
        if not offer:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Утверждённое КП не найдено")
        role = _current_user.get("role")
        if role == "поставщик":
            supplier_ids = current_supplier_ids(cur, _current_user)
            if offer.get('supplier_id') not in supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к КП")
        else:
            if role not in SUPPLY_INTERNAL_ROLES:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Недостаточно прав для отгрузки")
            if offer.get('project'):
                require_project_or_warehouse_access(_current_user, offer.get('project') or "")
        cur.execute("SELECT id, status, paid_amount, amount FROM supplier_invoices WHERE offer_id=%s ORDER BY id DESC LIMIT 1", (id,))
        inv = cur.fetchone()
        terms = (offer.get('payment_terms') or '').lower()
        need_payment = ('предоплат' in terms) or ('50/50' in terms) or ('50' in terms and 'постоплат' not in terms)
        if need_payment:
            paid = _float_or_zero(inv['paid_amount']) if inv else 0
            amount = _float_or_zero(inv['amount']) if inv else _float_or_zero(offer['total_price'])
            required = amount if '100' in terms or 'предоплат' in terms else amount * 0.5
            if not inv:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Сначала поставщик должен выставить счёт, а бухгалтерия — оплатить по условиям КП")
            if paid + 0.01 < required:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail=f"По условиям «{offer.get('payment_terms') or ''}» перед отгрузкой нужно оплатить минимум {round(required, 2)} ₽. Сейчас оплачено {round(paid, 2)} ₽")
        def _line_key(item):
            if not isinstance(item, dict):
                return ("", "", "")
            return (
                str(item.get("materialName") or item.get("name") or "").strip().lower(),
                str(item.get("unit") or "").strip().lower(),
                _supply_work_package(item.get("workPackage") or item.get("work_package")).lower(),
            )

        request_items = []
        for item in _json_list_or_empty(offer.get("items_json")):
            if not isinstance(item, dict):
                continue
            name = (item.get("materialName") or item.get("name") or "").strip()
            qty = _float_or_zero(item.get("quantity"))
            if name and qty > 0:
                request_items.append({
                    "materialName": name,
                    "quantity": qty,
                    "unit": item.get("unit") or offer.get("unit") or "шт",
                    "workPackage": _supply_work_package(item.get("workPackage") or item.get("work_package") or offer.get("work_package")),
                })
        if not request_items:
            request_items = [{
                "materialName": offer.get("material_name") or "",
                "quantity": _float_or_zero(offer.get("quantity")),
                "unit": offer.get("unit") or "шт",
                "workPackage": _supply_work_package(offer.get("work_package")),
            }]

        kp_by_key = {}
        for item in _json_list_or_empty(offer.get("items_kp_json")):
            if isinstance(item, dict):
                kp_by_key[_line_key(item)] = item

        shipped_by_key = {}
        for item in _json_list_or_empty(data.get("shippedItems")):
            if isinstance(item, dict):
                shipped_by_key[_line_key(item)] = _float_or_zero(item.get("shippedQuantity") or item.get("quantity"))

        has_item_kp = bool(kp_by_key)
        fallback_total = _float_or_zero(offer.get("total_price"))
        fallback_line_total = fallback_total / len(request_items) if request_items and fallback_total > 0 else 0

        cur.execute("SELECT id, status FROM supply_deliveries WHERE offer_id=%s", (id,))
        existing_rows = cur.fetchall()
        if any((r.get('status') if isinstance(r, dict) else r[1]) in ('Принято', 'Проблема') for r in existing_rows):
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Поставка уже принята. Повторная отгрузка запрещена — создайте новую заявку/КП для допоставки.")
        if existing_rows:
            cur.execute("DELETE FROM supply_deliveries WHERE offer_id=%s", (id,))

        delivery_ids = []
        single_request = len(request_items) == 1
        for item in request_items:
            key = _line_key(item)
            kp = kp_by_key.get(key) or {}
            planned_qty = _float_or_zero(item.get("quantity"))
            shipped_qty = shipped_by_key.get(key)
            if shipped_qty is None:
                shipped_qty = _float_or_zero(data.get('shippedQuantity')) if single_request and data.get('shippedQuantity') not in (None, "") else planned_qty
            if shipped_qty <= 0:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Количество к отгрузке должно быть больше нуля")
            if planned_qty > 0 and shipped_qty > planned_qty + 0.000001:
                cur.close(); conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Нельзя отгрузить больше заявки: {item.get('materialName') or ''} — заявлено {planned_qty:g}, отгружается {shipped_qty:g}",
                )
            price_per_unit = _float_or_zero(kp.get("pricePerUnit")) if has_item_kp else 0
            line_total = _float_or_zero(kp.get("totalPrice")) if has_item_kp else 0
            if line_total <= 0 and price_per_unit > 0:
                line_total = round(price_per_unit * planned_qty, 2)
            if line_total <= 0:
                line_total = fallback_line_total if not single_request else fallback_total
            if price_per_unit <= 0 and planned_qty > 0 and line_total > 0:
                price_per_unit = round(line_total / planned_qty, 6)
            shipped_line_total = round(price_per_unit * shipped_qty, 2) if price_per_unit > 0 else line_total
            vals = (
                offer.get('company_id') or 1,
                offer['request_id'], offer['supplier_id'], offer['supplier_name'] or '',
                offer['project'] or '', _supply_work_package(item.get("workPackage") or offer.get('work_package')),
                item.get("materialName") or '',
                planned_qty, shipped_qty, item.get("unit") or offer.get("unit") or '',
                price_per_unit, shipped_line_total,
                data.get('waybillNumber') or '', data.get('waybillDate') or None,
                data.get('vehicleNumber') or '', data.get('driverName') or '',
                data.get('documentUrl') or '', data.get('photoUrl') or '', datetime.now()
            )
            cur.execute("""INSERT INTO supply_deliveries
                           (offer_id, company_id, request_id, supplier_id, supplier_name, project,
                            work_package, material_name, planned_quantity, shipped_quantity, unit,
                            price_per_unit, total_price, waybill_number, waybill_date,
                            vehicle_number, driver_name, document_url, photo_url, shipped_at, status)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id""",
                        (id,) + vals + ('В пути',))
            delivery_ids.append(cur.fetchone()['id'])
        cur.execute("UPDATE supplier_offers SET delivery_status=%s WHERE id=%s", ('В пути', id))
        cur.execute("UPDATE supply_requests SET status=%s WHERE id=%s", ('В пути', offer['request_id']))
        cur.execute(DELIVERY_SELECT + " WHERE d.offer_id=%s ORDER BY d.id", (id,))
        rows = [dict(r) for r in cur.fetchall()]
        row = rows[0] if rows else None
        conn.commit()
        cur.close(); conn.close()
        if len(rows) == 1:
            return row
        return {"ok": True, "count": len(rows), "deliveries": rows}
