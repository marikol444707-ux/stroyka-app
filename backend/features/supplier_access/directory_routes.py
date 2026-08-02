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
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class SupplierModel(BaseModel):
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
    def get_suppliers(current_user: dict = Depends(get_current_user)):
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
        elif role in supply_roles or role in warehouse_roles or role in finance_roles:
            cur.execute("SELECT * FROM suppliers ORDER BY name")
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        relation_metadata = supplier_relation_metadata(cur, rows)
        payload = []
        for row in rows:
            supplier = dict(row)
            supplier.update(relation_metadata.get(int(supplier.get("id") or 0), {}))
            payload.append(supplier)
        cur.close()
        conn.close()
        return payload

    @app.post("/suppliers")
    def create_supplier(s: SupplierModel, _current_user: dict = Depends(require_roles(*warehouse_roles, "бухгалтер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        name = (s.name or "").strip()
        if not name:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Название поставщика обязательно")
        payload = s.dict()
        payload["name"] = name
        payload["sourceType"] = payload.get("sourceType") or "manual"
        payload["sourceDetail"] = payload.get("sourceDetail") or ("Добавил вручную: " + (_current_user.get("name") or _current_user.get("role") or ""))
        existing = supplier_find_match(cur, payload, allow_name_match=True)
        if existing:
            cur.execute("""
                UPDATE suppliers SET
                  phone=CASE WHEN COALESCE(phone,'')='' THEN %s ELSE phone END,
                  email=CASE WHEN COALESCE(email,'')='' THEN %s ELSE email END,
                  specialization=CASE WHEN COALESCE(specialization,'')='' THEN %s ELSE specialization END,
                  category=CASE WHEN COALESCE(category,'')='' THEN %s ELSE category END,
                  rating=COALESCE(rating,%s),
                  status=CASE WHEN COALESCE(status,'')='' THEN %s ELSE status END,
                  inn=CASE WHEN COALESCE(inn,'')='' THEN %s ELSE inn END,
                  kpp=CASE WHEN COALESCE(kpp,'')='' THEN %s ELSE kpp END,
                  ogrn=CASE WHEN COALESCE(ogrn,'')='' THEN %s ELSE ogrn END,
                  legal_address=CASE WHEN COALESCE(legal_address,'')='' THEN %s ELSE legal_address END,
                  actual_address=CASE WHEN COALESCE(actual_address,'')='' THEN %s ELSE actual_address END,
                  bank=CASE WHEN COALESCE(bank,'')='' THEN %s ELSE bank END,
                  bik=CASE WHEN COALESCE(bik,'')='' THEN %s ELSE bik END,
                  account=CASE WHEN COALESCE(account,'')='' THEN %s ELSE account END,
                  kor_account=CASE WHEN COALESCE(kor_account,'')='' THEN %s ELSE kor_account END,
                  director_name=CASE WHEN COALESCE(director_name,'')='' THEN %s ELSE director_name END,
                  director_position=CASE WHEN COALESCE(director_position,'')='' THEN %s ELSE director_position END,
                  contract_url=CASE WHEN COALESCE(contract_url,'')='' THEN %s ELSE contract_url END,
                  contract_number=CASE WHEN COALESCE(contract_number,'')='' THEN %s ELSE contract_number END,
                  contract_date=CASE WHEN contract_date IS NULL THEN %s ELSE contract_date END,
                  license_url=CASE WHEN COALESCE(license_url,'')='' THEN %s ELSE license_url END,
                  price_url=CASE WHEN COALESCE(price_url,'')='' THEN %s ELSE price_url END,
                  website=CASE WHEN COALESCE(website,'')='' THEN %s ELSE website END,
                  notes=CASE WHEN COALESCE(notes,'')='' THEN %s ELSE notes END,
                  source_type=CASE WHEN COALESCE(source_type,'')='' THEN %s ELSE source_type END,
                  source_detail=CASE WHEN COALESCE(source_detail,'')='' THEN %s ELSE source_detail END
                WHERE id=%s RETURNING *
            """, (
                s.phone, s.email, s.specialization, s.category, s.rating, s.status,
                s.inn, s.kpp, s.ogrn, s.legalAddress, s.actualAddress, s.bank, s.bik,
                s.account, s.korAccount, s.directorName, s.directorPosition,
                s.contractUrl, s.contractNumber, s.contractDate or None, s.licenseUrl,
                s.priceUrl, s.website, s.notes, payload["sourceType"], payload["sourceDetail"], existing["id"],
            ))
            row = cur.fetchone()
            remember_supplier_alias(cur, existing["id"], payload, source="manual_supplier")
            cur.close(); conn.close()
            return dict(row)
        if not _has_legal_supplier_identity(s.inn, s.ogrn):
            cur.close(); conn.close()
            raise HTTPException(
                status_code=422,
                detail="Для новой карточки поставщика укажите ИНН (10 или 12 цифр) либо ОГРН/ОГРНИП (13 или 15 цифр)",
            )
        cur.execute("""
            INSERT INTO suppliers (
                name,phone,email,specialization,category,rating,status,
                inn,kpp,ogrn,legal_address,actual_address,bank,bik,account,kor_account,
                director_name,director_position,contract_url,contract_number,contract_date,
                license_url,price_url,website,notes,source_type,source_detail
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s
            ) RETURNING *
        """, (
            name, s.phone, s.email, s.specialization, s.category, s.rating, s.status,
            s.inn, s.kpp, s.ogrn, s.legalAddress, s.actualAddress, s.bank, s.bik,
            s.account, s.korAccount, s.directorName, s.directorPosition,
            s.contractUrl, s.contractNumber, s.contractDate or None,
            s.licenseUrl, s.priceUrl, s.website, s.notes, payload["sourceType"], payload["sourceDetail"],
        ))
        row = cur.fetchone()
        supplier_id = row.get("id") if isinstance(row, dict) else row[0]
        remember_supplier_alias(cur, supplier_id, payload, source="manual_supplier")
        cur.close()
        conn.close()
        return dict(row)

    @app.put("/suppliers/{id}")
    def update_supplier(id: int, data: dict, _current_user: dict = Depends(require_roles(*warehouse_roles, "бухгалтер"))):
        data = data or {}
        def field(camel, snake=None, fallback=""):
            snake = snake or camel
            if camel in data:
                return data.get(camel) or ""
            if snake in data:
                return data.get(snake) or ""
            return fallback or ""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM suppliers WHERE id=%s", (id,))
        existing = cur.fetchone()
        if not existing:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Поставщик не найден")
        try:
            supplier_rating = float(data.get("rating") if "rating" in data and data.get("rating") not in (None, "") else (existing.get("rating") or 5.0))
        except (TypeError, ValueError):
            supplier_rating = float(existing.get("rating") or 5.0)
        cur.execute("""
            UPDATE suppliers SET
                name=%s,phone=%s,email=%s,specialization=%s,category=%s,rating=%s,status=%s,
                inn=%s,kpp=%s,ogrn=%s,legal_address=%s,actual_address=%s,bank=%s,bik=%s,
                account=%s,kor_account=%s,director_name=%s,director_position=%s,
                contract_url=%s,contract_number=%s,contract_date=%s,license_url=%s,
                price_url=%s,website=%s,notes=%s
                ,source_type=%s,source_detail=%s
            WHERE id=%s
        """, (
            field("name", fallback=existing.get("name")), field("phone", fallback=existing.get("phone")),
            field("email", fallback=existing.get("email")), field("specialization", fallback=existing.get("specialization")),
            field("category", fallback=existing.get("category")), supplier_rating,
            field("status", fallback=existing.get("status")),
            field("inn", fallback=existing.get("inn")), field("kpp", fallback=existing.get("kpp")),
            field("ogrn", fallback=existing.get("ogrn")), field("legalAddress", "legal_address", existing.get("legal_address")),
            field("actualAddress", "actual_address", existing.get("actual_address")),
            field("bank", fallback=existing.get("bank")), field("bik", fallback=existing.get("bik")),
            field("account", fallback=existing.get("account")), field("korAccount", "kor_account", existing.get("kor_account")),
            field("directorName", "director_name", existing.get("director_name")),
            field("directorPosition", "director_position", existing.get("director_position")),
            field("contractUrl", "contract_url", existing.get("contract_url")),
            field("contractNumber", "contract_number", existing.get("contract_number")),
            field("contractDate", "contract_date", existing.get("contract_date")) or None,
            field("licenseUrl", "license_url", existing.get("license_url")),
            field("priceUrl", "price_url", existing.get("price_url")),
            field("website", fallback=existing.get("website")),
            field("notes", fallback=existing.get("notes")),
            field("sourceType", "source_type", existing.get("source_type")),
            field("sourceDetail", "source_detail", existing.get("source_detail")),
            id,
        ))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.post("/suppliers/{id}/link-user")
    def link_supplier_user(id: int, data: dict, current_user: dict = Depends(require_roles(*leadership_roles))):
        data = data or {}
        raw_user_id = data.get("userId") or data.get("user_id")
        email = (str(data.get("email") or "").strip().lower())
        conn = get_db()
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
                (supplier_user_id, supplier_email, "Пользователь привязан директором: " + supplier_name, id),
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
    def link_supplier_duplicate(id: int, data: dict, current_user: dict = Depends(require_roles(*leadership_roles))):
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
    def delete_supplier(id: int, _current_user: dict = Depends(require_roles("директор", "зам_директора", "снабженец", "кладовщик"))):
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
        elif role not in ("директор", "зам_директора", "снабженец", "кладовщик", "бухгалтер"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        # Расширенный апдейт реквизитов: все поля опциональные
        cur.execute("""UPDATE suppliers SET
            inn=COALESCE(%s, inn), kpp=COALESCE(%s, kpp), ogrn=COALESCE(%s, ogrn),
            legal_address=COALESCE(%s, legal_address),
            actual_address=COALESCE(%s, actual_address),
            bank=COALESCE(%s, bank), bik=COALESCE(%s, bik),
            account=COALESCE(%s, account), kor_account=COALESCE(%s, kor_account),
            director_name=COALESCE(%s, director_name),
            director_position=COALESCE(%s, director_position),
            contract_url=COALESCE(%s, contract_url),
            contract_number=COALESCE(%s, contract_number),
            contract_date=COALESCE(%s, contract_date),
            license_url=COALESCE(%s, license_url),
            price_url=COALESCE(%s, price_url),
            website=COALESCE(%s, website),
            notes=COALESCE(%s, notes),
            phone=COALESCE(%s, phone), email=COALESCE(%s, email),
            category=COALESCE(%s, category), specialization=COALESCE(%s, specialization)
            WHERE id=%s""",
            (data.get("inn"), data.get("kpp"), data.get("ogrn"),
             data.get("legalAddress") or data.get("address"),
             data.get("actualAddress"),
             data.get("bank"), data.get("bik"),
             data.get("account"), data.get("korAccount"),
             data.get("directorName"), data.get("directorPosition"),
             data.get("contractUrl"), data.get("contractNumber"), data.get("contractDate") or None,
             data.get("licenseUrl"), data.get("priceUrl"),
             data.get("website"), data.get("notes"),
             data.get("phone"), data.get("email"),
             data.get("category"), data.get("specialization"),
             id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
