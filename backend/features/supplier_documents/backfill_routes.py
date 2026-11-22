"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import psycopg2

def register_supplier_document_maintenance_module(app, deps):
    CLIENT_ACCOUNT_ROLES = deps['CLIENT_ACCOUNT_ROLES']
    FINANCE_ROLES = deps['FINANCE_ROLES']
    PLATFORM_STAFF_ROLES = deps['PLATFORM_STAFF_ROLES']
    _ensure_invoice_document_link_columns = deps['_ensure_invoice_document_link_columns']
    _ensure_warehouse_invoice_accounting_columns = deps['_ensure_warehouse_invoice_accounting_columns']
    _float_or_zero = deps['_float_or_zero']
    _payment_ledger_available = deps['_payment_ledger_available']
    _pick_supplier_invoice_canonical = deps['_pick_supplier_invoice_canonical']
    _positive_int_or_none = deps['_positive_int_or_none']
    _require_unmanaged_payment_document = deps['_require_unmanaged_payment_document']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    _supplier_backfill_preview_review_state = deps['_supplier_backfill_preview_review_state']
    _supplier_invoice_duplicate_group_safety = deps['_supplier_invoice_duplicate_group_safety']
    _supplier_invoice_duplicate_summary = deps['_supplier_invoice_duplicate_summary']
    _sync_supplier_invoice_from_warehouse = deps['_sync_supplier_invoice_from_warehouse']
    assert_rows_company_scope = deps['assert_rows_company_scope']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    require_project_access = deps['require_project_access']
    require_roles = deps['require_roles']
    resolve_resource_company_actor = deps['resolve_resource_company_actor']
    router = APIRouter()

    @router.post("/supplier-documents/backfill")
    def backfill_supplier_documents(data: dict = None, _current_user: dict = Depends(require_roles(*FINANCE_ROLES))):
        """Сверяет старые складские накладные с первичкой поставщиков без повторного склада/оплат."""
        data = data or {}
        apply_changes = bool(data.get("apply") or data.get("commit"))
        target_ids = []
        raw_ids = data.get("warehouseInvoiceIds") or data.get("warehouse_invoice_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]
        raw_single_id = data.get("warehouseInvoiceId") or data.get("warehouse_invoice_id")
        if raw_single_id:
            raw_ids.append(raw_single_id)
        for raw_id in raw_ids:
            value = _positive_int_or_none(raw_id)
            if value and value not in target_ids:
                target_ids.append(value)
        try:
            limit = int(data.get("limit") or 200)
        except Exception:
            limit = 200
        limit = max(1, min(limit, 500))
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _ensure_invoice_document_link_columns(cur)
        _ensure_warehouse_invoice_accounting_columns(cur)
        conn.commit()
        where = [
            "COALESCE(status,'Принята') <> 'Аннулирована'",
            "supplier_invoice_id IS NULL",
            "(supplier_id IS NOT NULL OR COALESCE(supplier_name,'') <> '')",
        ]
        params = []
        if target_ids:
            where.append("id = ANY(%s)")
            params.append(target_ids)
            limit = min(limit, max(len(target_ids), 1))
        params.append(limit)
        cur.execute(
            f"""
            SELECT id, number, date, supplier_id, supplier_name, location, project,
                   total_with_vat, total_base, supplier_invoice_id
              FROM warehouse_invoices
             WHERE {" AND ".join(where)}
             ORDER BY id
             LIMIT %s
            """,
            tuple(params),
        )
        candidates = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()

        checked = []
        linked = 0
        errors = []
        for row in candidates:
            item = {
                "warehouseInvoiceId": row.get("id"),
                "number": row.get("number") or "",
                "date": str(row.get("date")) if row.get("date") else "",
                "supplierId": row.get("supplier_id"),
                "supplierName": row.get("supplier_name") or "",
                "projectName": row.get("project") or row.get("location") or "",
                "amount": float(row.get("total_with_vat") or row.get("total_base") or 0),
                "action": "preview" if not apply_changes else "sync",
            }
            preview_review = _supplier_backfill_preview_review_state(row)
            item.update({
                "needsReview": preview_review.get("needsReview"),
                "reviewReason": preview_review.get("reviewReason") or "",
                "accountingStatus": preview_review.get("accountingStatus") or "На проверке",
            })
            if not apply_changes:
                checked.append(item)
                continue
            try:
                result = _sync_supplier_invoice_from_warehouse(
                    row.get("id"),
                    {"reviewUncertainSupplierMatch": True},
                    _current_user,
                )
                item.update({
                    "supplierInvoiceId": result.get("id"),
                    "supplierId": result.get("supplierId"),
                    "supplierName": result.get("supplierName") or item["supplierName"],
                    "accountingStatus": result.get("accountingStatus") or "На проверке",
                    "needsReview": bool(result.get("needsReview")),
                    "reviewReason": result.get("reviewReason") or "",
                    "ok": True,
                })
                linked += 1
            except Exception as exc:
                item["ok"] = False
                item["error"] = getattr(exc, "detail", str(exc)) or "Не удалось связать документ"
                errors.append(item)
            checked.append(item)
        return {
            "ok": True,
            "dryRun": not apply_changes,
            "checked": len(checked),
            "linked": linked,
            "errors": errors,
            "items": checked,
        }

    @router.post("/supplier-documents/dedupe")
    def dedupe_supplier_accounting_documents(
        data: dict = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        """Находит и безопасно схлопывает старые дубли бухгалтерской первички без удаления склада/оплат."""
        data = data or {}
        apply_changes = bool(data.get("apply") or data.get("commit"))
        force_review = bool(data.get("force") or data.get("forceReview"))
        project_filter = str(data.get("projectName") or data.get("project_name") or "").strip()
        raw_ids = data.get("supplierInvoiceIds", data.get("supplier_invoice_ids", []))
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]
        else:
            raw_ids = list(raw_ids)
        raw_single_id = data.get("supplierInvoiceId", data.get("supplier_invoice_id"))
        if raw_single_id is not None:
            raw_ids.append(raw_single_id)
        target_ids = []
        for raw_id in raw_ids:
            if not (type(raw_id) is int or (isinstance(raw_id, str) and raw_id.isdecimal())):
                raise HTTPException(422, "Некорректный идентификатор счёта")
            value = int(raw_id)
            if not 0 < value <= 2147483647:
                raise HTTPException(422, "Некорректный идентификатор счёта")
            if value not in target_ids:
                target_ids.append(value)
        try:
            limit = int(data.get("limit") or 50)
        except Exception:
            limit = 50
        limit = max(1, min(limit, 200))

        conn = get_db()
        cur = None
        try:
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            context = _resolve_work_company_context(cur, _current_user, None, "write",
                x_company_id=x_company_id, x_company_mode=x_company_mode)
            if (context.get("mode") != "company" or context.get("source") != "membership"
                    or not context.get("active") or not context.get("companyActive")
                    or not context.get("membershipId") or context.get("role") not in FINANCE_ROLES):
                raise HTTPException(403, "Для сверки документов требуется финансовая роль в выбранной компании")
            company_id = context["companyId"]
            membership_id = context["membershipId"]
            cur.execute("SHOW transaction_isolation")
            if cur.fetchone()["transaction_isolation"] != "read committed":
                raise HTTPException(409, "Сверка документов требует новой транзакции")
            ledger_present = _payment_ledger_available(cur)
            if not ledger_present:
                # Legacy writers prepare schema before taking the company lock.
                # Keep the same order; all business changes still share this txn.
                _ensure_invoice_document_link_columns(cur)
                _ensure_warehouse_invoice_accounting_columns(cur)
            # Collection discovery has no document root. Use the payment engine's
            # company lock BEFORE membership/document row locks. With 0017, no DDL.
            cur.execute("SELECT pg_advisory_xact_lock(%s,%s)", (1735289201, company_id))
            cur.execute("SELECT * FROM users WHERE id=%s AND active=TRUE FOR SHARE", (_current_user["id"],))
            fresh_user = cur.fetchone()
            if not fresh_user:
                raise HTTPException(403, "Пользователь отключён")
            _current_user = dict(fresh_user)
            cur.execute("SELECT id FROM companies WHERE id=%s FOR SHARE", (company_id,))
            cur.fetchone()
            cur.execute("SELECT id FROM user_company_roles WHERE id=%s AND user_id=%s AND company_id=%s FOR SHARE",
                        (membership_id, _current_user["id"], company_id))
            if not cur.fetchone():
                raise HTTPException(403, "Членство больше не действует")
            context, actor = resolve_resource_company_actor(cur, _current_user, company_id, "update",
                claimed_company_id=data.get("companyId", data.get("company_id")),
                x_company_id=x_company_id, x_company_mode=x_company_mode, allowed_roles=FINANCE_ROLES,
                platform_staff_roles=PLATFORM_STAFF_ROLES, client_account_roles=CLIENT_ACCOUNT_ROLES)
            if (context.get("source") != "membership" or context.get("membershipId") != membership_id
                    or not context.get("active") or not context.get("companyActive")):
                raise HTTPException(403, "Членство больше не действует")
            _current_user = actor
            if target_ids:
                cur.execute("SELECT id,company_id FROM supplier_invoices WHERE id=ANY(%s)", (target_ids,))
                seeds = cur.fetchall()
                if len(seeds) != len(target_ids):
                    raise HTTPException(404, "Счёт не найден")
                assert_rows_company_scope(seeds, company_id, "Выбранные счета")
            where = [
                "company_id=%s",
                "COALESCE(status,'') <> 'Аннулирован'",
                "COALESCE(invoice_number,'') <> ''",
            ]
            params = [company_id]
            if project_filter:
                require_project_access(_current_user, project_filter)
                where.append("COALESCE(project_name,'')=%s")
                params.append(project_filter)
            if target_ids:
                seed_where = where + ["id = ANY(%s)"]
                seed_params = params + [target_ids]
                cur.execute(
                    f"""
                    SELECT DISTINCT company_id,
                           COALESCE(invoice_number,'') AS invoice_number,
                           COALESCE(invoice_date::text,'') AS invoice_date_key,
                           COALESCE(project_name,'') AS project_name,
                           ROUND(COALESCE(amount,0)::numeric, 2) AS amount_key,
                           COUNT(*) OVER () AS total_count,
                           MAX(id) OVER () AS latest_id
                      FROM supplier_invoices
                     WHERE {" AND ".join(seed_where)}
                     ORDER BY latest_id DESC
                     LIMIT %s
                    """,
                    tuple(seed_params + [limit]),
                )
            else:
                cur.execute(
                    f"""
                    SELECT company_id,
                           COALESCE(invoice_number,'') AS invoice_number,
                           COALESCE(invoice_date::text,'') AS invoice_date_key,
                           COALESCE(project_name,'') AS project_name,
                           ROUND(COALESCE(amount,0)::numeric, 2) AS amount_key,
                           COUNT(*) AS total_count,
                           MAX(id) AS latest_id
                      FROM supplier_invoices
                     WHERE {" AND ".join(where)}
                     GROUP BY company_id, COALESCE(invoice_number,''),
                              COALESCE(invoice_date::text,''), COALESCE(project_name,''),
                              ROUND(COALESCE(amount,0)::numeric, 2)
                    HAVING COUNT(*) > 1
                     ORDER BY MAX(id) DESC
                     LIMIT %s
                    """,
                    tuple(params + [limit]),
                )
            keys = [dict(row) for row in cur.fetchall() or []]
            groups = []
            plans = []
            applied_groups = 0
            annulled_rows = 0
            linked_warehouse_rows = 0
            for key in keys:
                project_name = key.get("project_name") or ""
                if project_name:
                    require_project_access(_current_user, project_name)
                cur.execute(
                    """
                    SELECT id, company_id, supplier_id, supplier_name, project_name,
                           invoice_number, invoice_date, amount, paid_amount, status,
                           warehouse_invoice_id, offer_id, request_id, file_url, photo_url,
                           payment_terms, material_name, work_package, description, paid_note
                      FROM supplier_invoices
                     WHERE COALESCE(status,'') <> 'Аннулирован'
                       AND company_id=%s
                       AND COALESCE(invoice_number,'')=%s
                       AND COALESCE(invoice_date::text,'')=%s
                       AND COALESCE(project_name,'')=%s
                       AND ROUND(COALESCE(amount,0)::numeric, 2)=%s
                     ORDER BY id FOR UPDATE
                    """,
                    (
                        company_id,
                        key.get("invoice_number") or "",
                        key.get("invoice_date_key") or "",
                        project_name,
                        key.get("amount_key") or 0,
                    ),
                )
                rows = [dict(row) for row in cur.fetchall() or []]
                if len(rows) < 2:
                    continue
                canonical = _pick_supplier_invoice_canonical(rows)
                safety = _supplier_invoice_duplicate_group_safety(cur, rows)
                needs_manual_review = not bool(safety.get("safe"))
                canonical_id = canonical.get("id") if canonical else None
                duplicate_rows = [row for row in rows if int(row.get("id") or 0) != int(canonical_id or 0)]
                group = {
                    "companyId": company_id,
                    "invoiceNumber": key.get("invoice_number") or "",
                    "invoiceDate": key.get("invoice_date_key") or "",
                    "projectName": project_name,
                    "amount": _float_or_zero(key.get("amount_key")),
                    "canonicalId": canonical_id,
                    "duplicateIds": [row.get("id") for row in duplicate_rows],
                    "needsManualReview": needs_manual_review,
                    "reviewReason": safety.get("reason") or "",
                    "applied": False,
                    "rows": [_supplier_invoice_duplicate_summary(row) for row in rows],
                }
                if apply_changes and canonical_id and (safety.get("safe") or force_review):
                    row_ids = [row["id"] for row in rows]
                    forward_ids = sorted({row["warehouse_invoice_id"] for row in rows if row.get("warehouse_invoice_id")})
                    cur.execute("""SELECT id,company_id,supplier_invoice_id FROM warehouse_invoices
                        WHERE id=ANY(%s::int[]) OR supplier_invoice_id=ANY(%s::int[]) ORDER BY id""",
                        (forward_ids, row_ids))
                    warehouses = cur.fetchall()
                    assert_rows_company_scope(warehouses, company_id, "Связанные накладные")
                    warehouse_ids = [row["id"] for row in warehouses]
                    if not set(forward_ids).issubset(warehouse_ids):
                        raise HTTPException(409, "Связанная накладная не найдена")
                    cur.execute("""SELECT id,company_id,supplier_invoice_id FROM warehouse_invoices
                        WHERE company_id=%s AND id=ANY(%s::int[]) ORDER BY id FOR UPDATE""",
                        (company_id, warehouse_ids))
                    warehouses = cur.fetchall()
                    if [row["id"] for row in warehouses] != warehouse_ids:
                        raise HTTPException(409, "Принадлежность накладных изменилась. Повторите запрос")
                    # Reverse warehouses may themselves have other forward/reverse
                    # invoice neighbours. Check them even when 0017 is absent.
                    neighbor_ids = [row["supplier_invoice_id"] for row in warehouses if row.get("supplier_invoice_id")]
                    cur.execute("""SELECT id,company_id FROM supplier_invoices
                        WHERE id=ANY(%s::int[]) OR warehouse_invoice_id=ANY(%s::int[])""",
                        (neighbor_ids, warehouse_ids))
                    assert_rows_company_scope(cur.fetchall(), company_id, "Связанные счета")
                    if ledger_present:
                        for row_id in row_ids:
                            _require_unmanaged_payment_document(cur, 'invoice', row_id)
                        for warehouse_id in warehouse_ids:
                            _require_unmanaged_payment_document(cur, 'warehouse', warehouse_id)
                    plans.append((canonical, duplicate_rows, group))
                groups.append(group)
            # Preflight the entire batch before any document changes. A conflict in
            # any group (including forceReview) aborts this single transaction.
            for canonical, duplicate_rows, group in plans:
                canonical_id = canonical["id"]
                canonical_warehouse_id = _positive_int_or_none(canonical.get("warehouse_invoice_id"))
                actor_note = "Схлопнуто как дубль бухгалтерской первички в счет #" + str(canonical_id)
                for duplicate in duplicate_rows:
                    duplicate_id = int(duplicate.get("id") or 0)
                    if not duplicate_id:
                        continue
                    duplicate_warehouse_id = _positive_int_or_none(duplicate.get("warehouse_invoice_id"))
                    cur.execute(
                        """
                        UPDATE supplier_invoices
                           SET supplier_id=COALESCE(supplier_id,%s),
                               supplier_name=COALESCE(NULLIF(supplier_name,''),%s),
                               offer_id=COALESCE(offer_id,%s),
                               request_id=COALESCE(request_id,%s),
                               warehouse_invoice_id=COALESCE(warehouse_invoice_id,%s),
                               file_url=COALESCE(NULLIF(file_url,''),%s),
                               photo_url=COALESCE(NULLIF(photo_url,''),%s),
                               payment_terms=COALESCE(NULLIF(payment_terms,''),%s),
                               material_name=COALESCE(NULLIF(material_name,''),%s),
                               work_package=COALESCE(NULLIF(work_package,''),%s)
                         WHERE id=%s AND company_id=%s
                        """,
                        (
                            duplicate.get("supplier_id"),
                            duplicate.get("supplier_name") or "",
                            duplicate.get("offer_id"),
                            duplicate.get("request_id"),
                            duplicate_warehouse_id,
                            duplicate.get("file_url") or "",
                            duplicate.get("photo_url") or "",
                            duplicate.get("payment_terms") or "",
                            duplicate.get("material_name") or "",
                            duplicate.get("work_package") or "",
                            canonical_id,
                            company_id,
                        ),
                    )
                    if duplicate_warehouse_id:
                        cur.execute(
                            "UPDATE warehouse_invoices SET supplier_invoice_id=%s WHERE id=%s AND company_id=%s AND COALESCE(status,'') <> 'Аннулирована'",
                            (canonical_id, duplicate_warehouse_id, company_id),
                        )
                        linked_warehouse_rows += cur.rowcount
                        if not canonical_warehouse_id:
                            cur.execute("UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s AND company_id=%s", (duplicate_warehouse_id, canonical_id, company_id))
                            canonical_warehouse_id = duplicate_warehouse_id
                    cur.execute(
                        "UPDATE warehouse_invoices SET supplier_invoice_id=%s WHERE supplier_invoice_id=%s AND company_id=%s AND COALESCE(status,'') <> 'Аннулирована'",
                        (canonical_id, duplicate_id, company_id),
                    )
                    linked_warehouse_rows += cur.rowcount
                    cur.execute(
                        """
                        UPDATE supplier_invoices
                           SET status='Аннулирован',
                               paid_note=COALESCE(NULLIF(paid_note,''),'') ||
                                   CASE WHEN COALESCE(paid_note,'')<>'' THEN E'\n' ELSE '' END || %s
                         WHERE id=%s AND company_id=%s
                           AND COALESCE(status,'') <> 'Аннулирован'
                           AND COALESCE(paid_amount,0)=0
                        """,
                        (actor_note, duplicate_id, company_id),
                    )
                    annulled_rows += cur.rowcount
                group["applied"] = True
                applied_groups += 1
            if apply_changes:
                conn.commit()
            else:
                conn.rollback()
            return {
                "ok": True,
                "dryRun": not apply_changes,
                "checkedGroups": len(groups),
                "appliedGroups": applied_groups,
                "annulledRows": annulled_rows,
                "linkedWarehouseRows": linked_warehouse_rows,
                "groups": groups,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            conn.close()

    app.include_router(router)

