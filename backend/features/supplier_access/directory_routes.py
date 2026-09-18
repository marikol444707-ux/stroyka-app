"""Supplier directory routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 38):
the supplier directory family (list with relation metadata, dedup-
aware create, update, user linking, duplicate linking, reference-
guarded delete and the requisites update) joins the supplier_access
feature. Alias memory, duplicate groups and relation metadata stay
in main.py and are injected; the delete reference summary helpers
move along — the delete route was their only caller.
"""

import re
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from .company_directory import CompanySupplierDirectory, PUBLIC_FIELDS


# These mutations affect one global supplier identity across all customers.
PRIVATE_COMMERCIAL_FIELDS = ('category', 'rating', 'status', 'contractUrl', 'contractNumber', 'contractDate',
                             'contract_url', 'contract_number', 'contract_date', 'notes',
                             'sourceType', 'sourceDetail', 'source_type', 'source_detail',
                             'priceUrl', 'price_url', 'licenseUrl', 'license_url', 'paymentTerms', 'deliveryTerms')


def reject_global_commercial_fields(data):
    if any(data.get(key) not in (None, '') for key in PRIVATE_COMMERCIAL_FIELDS):
        raise HTTPException(422, 'Условия, договор и заметки сохраняются в каталоге выбранной компании')


SUPPLIER_IDENTITY_MANAGE_ROLES = ("system_owner", "platform_admin")


class SupplierModel(BaseModel):
    companyId: Optional[int] = None
    relationshipVersion: Optional[int] = None
    paymentTerms: str = ""
    deliveryTerms: str = ""
    name: str
    phone: str = ""
    email: str = ""
    specialization: str = ""
    category: str = ""
    rating: float = 5.0
    status: str = "Активный"
    inn: Optional[str] = ""
    kpp: Optional[str] = ""
    ogrn: Optional[str] = ""
    legalAddress: Optional[str] = ""
    actualAddress: Optional[str] = ""
    bank: Optional[str] = ""
    bik: Optional[str] = ""
    account: Optional[str] = ""
    korAccount: Optional[str] = ""
    directorName: Optional[str] = ""
    directorPosition: Optional[str] = ""
    contractUrl: Optional[str] = ""
    contractNumber: Optional[str] = ""
    contractDate: Optional[str] = ""
    licenseUrl: Optional[str] = ""
    priceUrl: Optional[str] = ""
    website: Optional[str] = ""
    notes: Optional[str] = ""
    sourceType: Optional[str] = ""
    sourceDetail: Optional[str] = ""


def _has_legal_supplier_identity(inn: str = "", ogrn: str = "") -> bool:
    """A new supplier card needs a stable legal identifier, not a display name."""
    inn_digits = re.sub(r"\D", "", str(inn or ""))
    ogrn_digits = re.sub(r"\D", "", str(ogrn or ""))
    return len(inn_digits) in (10, 12) or len(ogrn_digits) in (13, 15)


def register_supplier_directory_module(app, deps):
    company_directory = CompanySupplierDirectory(deps)
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    supply_roles = tuple(deps.get("supply_roles") or ())
    warehouse_roles = tuple(deps.get("warehouse_roles") or ())
    finance_roles = tuple(deps.get("finance_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    leadership_roles = tuple(deps.get("leadership_roles") or ())
    current_supplier_ids = deps["current_supplier_ids"]
    supplier_relation_metadata = deps["supplier_relation_metadata"]
    supplier_find_match = deps["supplier_find_match"]
    remember_supplier_alias = deps["remember_supplier_alias"]
    remember_supplier_duplicate_alias = deps["remember_supplier_duplicate_alias"]
    supplier_related_ids = deps["supplier_related_ids"]
    row_get = deps["row_get"]
    log_audit = deps["log_audit"]

    @app.get("/suppliers")
    def get_suppliers(current_user: dict = Depends(get_current_user),
                      x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                      x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        role = current_user.get('role')
        if role not in ('поставщик', *SUPPLIER_IDENTITY_MANAGE_ROLES, *worker_execution_roles):
            return company_directory.list(current_user, (x_company_id, x_company_mode))
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        role = current_user.get("role")
        if role == "поставщик":
            supplier_ids = current_supplier_ids(cur, current_user)
            if supplier_ids:
                cur.execute("SELECT * FROM suppliers WHERE id = ANY(%s) ORDER BY name", (supplier_ids,))
            else:
                cur.close(); conn.close()
                return []
        elif role in worker_execution_roles:
            cur.close(); conn.close()
            return []
        elif role in SUPPLIER_IDENTITY_MANAGE_ROLES:
            cur.execute("SELECT * FROM suppliers ORDER BY name")
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        relation_metadata = supplier_relation_metadata(cur, rows) if role in SUPPLIER_IDENTITY_MANAGE_ROLES else {}
        payload = []
        for row in rows:
            supplier = {key: row.get(key) for key in (*PUBLIC_FIELDS.values(), 'id', 'user_id', 'phone', 'email', 'specialization')}
            supplier.update(relation_metadata.get(int(supplier.get("id") or 0), {}))
            payload.append(supplier)
        cur.close()
        conn.close()
        return payload

    @app.post("/suppliers")
    def create_supplier(s: SupplierModel, _current_user: dict = Depends(get_current_user),
                        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        if _current_user.get('role') not in SUPPLIER_IDENTITY_MANAGE_ROLES:
            return company_directory.create(s.model_dump(), _current_user, (x_company_id, x_company_mode))
        raise HTTPException(403, 'Добавление в каталог требует рабочей роли в выбранной компании')

    @app.put("/suppliers/{id}")
    def update_supplier(id: int, data: dict, _current_user: dict = Depends(get_current_user),
                        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        if _current_user.get('role') not in SUPPLIER_IDENTITY_MANAGE_ROLES:
            return company_directory.update(id, data or {}, _current_user, (x_company_id, x_company_mode))
        return update_supplier_requisites(id, data or {}, _current_user)

    @app.post("/suppliers/{id}/link-user")
    def link_supplier_user(id: int, data: dict, current_user: dict = Depends(require_roles(*SUPPLIER_IDENTITY_MANAGE_ROLES))):
        data = data or {}
        raw_user_id = data.get("userId") or data.get("user_id")
        email = (str(data.get("email") or "").strip().lower())
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM suppliers WHERE id=%s LIMIT 1", (id,))
            supplier = cur.fetchone()
            if not supplier:
                raise HTTPException(status_code=404, detail="Поставщик не найден")

            if raw_user_id:
                cur.execute(
                    "SELECT id,name,email,role FROM users WHERE id=%s LIMIT 1",
                    (int(raw_user_id),),
                )
            elif email:
                cur.execute(
                    """
                    SELECT id,name,email,role
                      FROM users
                     WHERE LOWER(email)=LOWER(%s)
                       AND COALESCE(active, TRUE)=TRUE
                     ORDER BY id
                     LIMIT 1
                    """,
                    (email,),
                )
            else:
                raise HTTPException(status_code=400, detail="Выберите пользователя или укажите email поставщика")

            supplier_user = cur.fetchone()
            if not supplier_user:
                raise HTTPException(status_code=404, detail="Пользователь поставщика не найден")
            if (supplier_user.get("role") or "") != "поставщик":
                raise HTTPException(status_code=400, detail="К поставщику можно привязать только пользователя с ролью поставщик")

            supplier_user_id = int(supplier_user.get("id"))
            supplier_email = supplier_user.get("email") or email
            supplier_name = supplier_user.get("name") or supplier_email or ""

            # Один пользователь должен иметь один явный вход в свою карточку. Дубли подтягиваются
            # через ИНН/ОГРН/email/name/aliases, но старый неверный user_id не должен перехватывать кабинет.
            cur.execute("UPDATE suppliers SET user_id=NULL WHERE user_id=%s AND id<>%s", (supplier_user_id, id))
            cur.execute(
                """
                UPDATE suppliers
                   SET user_id=%s,
                       email=CASE WHEN COALESCE(email,'')='' THEN %s ELSE email END,
                       status=CASE WHEN COALESCE(status,'')='' THEN 'Активный' ELSE status END,
                       registered_at=COALESCE(registered_at, NOW()),
                       source_type=CASE WHEN COALESCE(source_type,'')='' THEN 'linked_account' ELSE source_type END,
                       source_detail=CASE WHEN COALESCE(source_detail,'')='' THEN %s ELSE source_detail END
                 WHERE id=%s
                 RETURNING *
                """,
                (supplier_user_id, supplier_email, "Пользователь привязан администратором платформы: " + supplier_name, id),
            )
            row = cur.fetchone()
            remember_supplier_alias(cur, id, {
                "name": supplier.get("name") or "",
                "email": supplier_email,
                "companyName": supplier.get("name") or "",
            }, source="manual_supplier_user_link")
            remember_supplier_alias(cur, id, {
                "name": supplier_name,
                "email": supplier_email,
            }, source="manual_supplier_user_link")
            conn.commit()
            log_audit(
                user_name=current_user.get("name", ""),
                user_role=current_user.get("role", ""),
                action="supplier_link_user",
                entity_type="supplier",
                entity_id=id,
                description=("Привязан пользователь поставщика: " + supplier_name + " <" + supplier_email + ">")[:250],
            )
            return dict(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.post("/suppliers/{id}/link-duplicate")
    def link_supplier_duplicate(id: int, data: dict, current_user: dict = Depends(require_roles(*SUPPLIER_IDENTITY_MANAGE_ROLES))):
        data = data or {}
        try:
            duplicate_id = int(data.get("duplicateSupplierId") or data.get("duplicate_supplier_id") or data.get("supplierId") or 0)
        except (TypeError, ValueError):
            duplicate_id = 0
        if duplicate_id <= 0:
            raise HTTPException(status_code=400, detail="Выберите карточку-дубль поставщика")
        if int(id) == duplicate_id:
            raise HTTPException(status_code=400, detail="Нельзя связать карточку саму с собой")
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM suppliers WHERE id=%s FOR UPDATE", (id,))
            canonical = cur.fetchone()
            cur.execute("SELECT * FROM suppliers WHERE id=%s FOR UPDATE", (duplicate_id,))
            duplicate = cur.fetchone()
            if not canonical:
                raise HTTPException(status_code=404, detail="Основная карточка поставщика не найдена")
            if not duplicate:
                raise HTTPException(status_code=404, detail="Карточка-дубль поставщика не найдена")

            remember_supplier_duplicate_alias(cur, id, duplicate_id, duplicate)
            remember_supplier_duplicate_alias(cur, duplicate_id, id, canonical)
            conn.commit()
            related_ids = supplier_related_ids(cur, id)
            log_audit(
                current_user.get("name", ""),
                current_user.get("role", ""),
                "supplier_link_duplicate",
                "supplier",
                id,
                ("Связан дубль поставщика #" + str(duplicate_id) + " с " + str(canonical.get("name") or ""))[:250],
            )
            return {
                "ok": True,
                "supplierId": id,
                "duplicateSupplierId": duplicate_id,
                "relatedSupplierIds": related_ids,
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        finally:
            cur.close()
            conn.close()

    def _db_column_exists(cur, table_name: str, column_name: str) -> bool:
        cur.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema='public'
               AND table_name=%s
               AND column_name=%s
             LIMIT 1
            """,
            (table_name, column_name),
        )
        return bool(cur.fetchone())

    def _supplier_delete_reference_summary(cur, supplier_id: int) -> list[dict]:
        supplier_id = int(supplier_id or 0)
        references = []
        direct_refs = [
            ("warehouse_invoices", "supplier_id", "складские накладные"),
            ("supplier_invoices", "supplier_id", "счета/первичка поставщика"),
            ("supplier_offers", "supplier_id", "КП поставщика"),
            ("supply_deliveries", "supplier_id", "поставки"),
            ("supply_claims", "supplier_id", "претензии"),
            ("supply_history", "supplier_id", "история снабжения"),
            ("supplier_catalog", "supplier_id", "каталог поставщика"),
            ("supplier_documents", "supplier_id", "документы поставщика"),
            ("supplier_subscriptions", "supplier_id", "подписки поставщика"),
            ("supplier_invoice_templates", "supplier_id", "шаблоны распознавания"),
            ("company_supplier_links", "supplier_id", "связи с компаниями"),
            ("invite_codes", "supplier_id", "инвайты поставщика"),
            ("supply_request_recipients", "supplier_id", "получатели КП"),
            ("supply_request_recipients", "target_supplier_id", "целевые получатели КП"),
        ]
        for table_name, column_name, label in direct_refs:
            if not _db_column_exists(cur, table_name, column_name):
                continue
            cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name}=%s", (supplier_id,))
            count = int(row_get(cur.fetchone(), "count", 0, 0) or 0)
            if count:
                references.append({"table": table_name, "column": column_name, "label": label, "count": count})

        if _db_column_exists(cur, "supply_requests", "selected_suppliers"):
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM supply_requests
                 WHERE selected_suppliers IS NOT NULL
                   AND selected_suppliers && ARRAY[%s]::int[]
                """,
                (supplier_id,),
            )
            count = int(row_get(cur.fetchone(), "count", 0, 0) or 0)
            if count:
                references.append({"table": "supply_requests", "column": "selected_suppliers", "label": "выбранные поставщики заявок", "count": count})

        if _db_column_exists(cur, "supply_request_recipients", "supplier_group_ids"):
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM supply_request_recipients
                 WHERE supplier_group_ids IS NOT NULL
                   AND supplier_group_ids && ARRAY[%s]::int[]
                """,
                (supplier_id,),
            )
            count = int(row_get(cur.fetchone(), "count", 0, 0) or 0)
            if count:
                references.append({"table": "supply_request_recipients", "column": "supplier_group_ids", "label": "группы дублей получателей КП", "count": count})
        return references

    @app.delete("/suppliers/{id}")
    def delete_supplier(id: int, _current_user: dict = Depends(require_roles(*SUPPLIER_IDENTITY_MANAGE_ROLES))):
        conn = get_db()
        cur = conn.cursor()
        conn.autocommit = False
        try:
            cur.execute("SELECT id FROM suppliers WHERE id=%s FOR UPDATE", (id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Поставщик не найден")
            references = _supplier_delete_reference_summary(cur, id)
            if references:
                total = sum(ref["count"] for ref in references)
                detail = (
                    "Поставщика нельзя удалить физически: есть связанные документы (" + str(total) + "). "
                    "Используйте привязку кабинета или объединение дублей, чтобы накладные, КП и счета не потеряли связь."
                )
                raise HTTPException(status_code=409, detail=detail)
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (id,))
            cur.execute("DELETE FROM suppliers WHERE id=%s", (id,))
            conn.commit()
            return {"ok": True, "deleted": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        finally:
            cur.close()
            conn.close()

    @app.put("/suppliers/{id}/requisites")
    def update_supplier_requisites(id: int, data: dict, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        role = current_user.get("role")
        if role == "поставщик":
            supplier_ids = current_supplier_ids(cur, current_user)
            if id not in supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к этому поставщику")
        elif role not in SUPPLIER_IDENTITY_MANAGE_ROLES:
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        try:
            reject_global_commercial_fields(data)
            fields = {**PUBLIC_FIELDS, 'phone': 'phone', 'email': 'email', 'specialization': 'specialization'}
            if 'address' in data and 'legalAddress' not in data:
                data = {**data, 'legalAddress': data['address']}
            values = [(column, str(data[key] or '').strip()) for key, column in fields.items() if key in data]
            if not values:
                raise HTTPException(422, 'Нет реквизитов для обновления')
            if any(len(value) > 500 for _, value in values):
                raise HTTPException(422, 'Реквизиты слишком длинные')
            cur.execute('UPDATE suppliers SET ' + ','.join(column + '=%s' for column, _ in values) + ' WHERE id=%s',
                        [value for _, value in values] + [id])
            conn.commit()
            return {'ok': True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
