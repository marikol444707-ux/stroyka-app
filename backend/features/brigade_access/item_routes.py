"""Brigade contract item routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 34):
the five /brigade-contract-items routes keep their URLs,
company-scoped visibility, package matching rules, done-quantity
clamping, price hiding for workers and contract total recalculation.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException


_CLIENT_LINEAGE_FIELDS = (
    "sourceType",
    "source_type",
    "sourceEstimateVersionId",
    "source_estimate_version_id",
    "sourceSectionIndex",
    "source_section_index",
    "sourceItemIndex",
    "source_item_index",
    "sourceItemKey",
    "source_item_key",
)


def _reject_client_lineage(data, *, reject_compatibility_key=False):
    fields = _CLIENT_LINEAGE_FIELDS
    if reject_compatibility_key:
        fields = (*fields, "estimateItemKey", "estimate_item_key")
    supplied = [
        field
        for field in fields
        if field in data and data.get(field) not in (None, "")
    ]
    if supplied:
        raise HTTPException(
            status_code=400,
            detail="Источник позиции назначается сервером и не принимается из запроса",
        )


def register_brigade_contract_items_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    contract_roles = tuple(deps.get("contract_roles") or ())
    leadership_roles = tuple(deps.get("leadership_roles") or ())
    finance_roles = tuple(deps.get("finance_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    brigade_contract_read_scope = deps["brigade_contract_read_scope"]
    resolve_brigade_contract_actor = deps["resolve_brigade_contract_actor"]
    positive_int_or_none = deps["positive_int_or_none"]
    has_package_access = deps["has_package_access"]
    row_get = deps["row_get"]
    recalc_brigade_contract_total = deps["recalc_brigade_contract_total"]

    @app.get("/brigade-contract-items-all")
    def list_all_brigade_contract_items(
        project_name: str = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        """Все позиции нарядов сразу — для подсчёта прогресса по бюджету."""
        conn = get_db()
        try:
            visibility_sql, params, actors = brigade_contract_read_scope(
                conn,
                _current_user,
                contract_roles,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                item_alias="bci",
            )
            if visibility_sql == "FALSE":
                return []
            where = [visibility_sql]
            if project_name:
                where.append("bc.project_name=%s")
                params.append(project_name)
            cur = conn.cursor()
            try:
                cur.execute("""SELECT bci.id,bci.contract_id,bci.description,bci.unit,bci.quantity,
                                      bci.price_smeta,bci.price_brigade,bci.done_quantity,bci.estimate_section,
                                      COALESCE(bci.work_package,''),COALESCE(bci.estimate_item_key,''),
                                      bc.project_name,bc.company_id
                               FROM brigade_contract_items bci
                               JOIN brigade_contracts bc ON bc.id=bci.contract_id
                               WHERE """ + " AND ".join(where) + " ORDER BY bci.id DESC", tuple(params))
                rows = cur.fetchall()
            finally:
                cur.close()
            actor_by_company = {
                positive_int_or_none(actor.get("companyId") or actor.get("company_id")): actor
                for actor in actors
                if positive_int_or_none(actor.get("companyId") or actor.get("company_id"))
            }
            result = []
            for row in rows:
                actor = actor_by_company.get(positive_int_or_none(row[12])) or {}
                hide_customer_money = (actor.get("role") or "") in worker_execution_roles
                quantity = float(row[4] or 0)
                done_quantity = float(row[7] or 0)
                result.append({
                    "id": row[0], "contractId": row[1], "name": row[2] or "", "unit": row[3] or "",
                    "quantity": quantity, "priceSmeta": 0 if hide_customer_money else float(row[5] or 0),
                    "priceBrigade": float(row[6] or 0),
                    "doneQuantity": max(0, min(done_quantity, quantity)) if quantity > 0 else 0,
                    "rawDoneQuantity": done_quantity,
                    "hasInvalidDoneQuantity": (quantity <= 0 and done_quantity > 0)
                        or done_quantity < 0 or (quantity > 0 and done_quantity > quantity),
                    "estimateSection": row[8] or "", "workPackage": row[9] or "",
                    "estimateItemKey": row[10] or "", "projectName": row[11] or "",
                    "companyId": row[12],
                })
            return result
        finally:
            conn.close()

    @app.get("/brigade-contract-items/{contract_id}")
    def get_brigade_contract_items(
        contract_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        try:
            visibility_sql, visibility_params, actors = brigade_contract_read_scope(
                conn,
                _current_user,
                contract_roles,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                item_alias="bci",
            )
            if visibility_sql == "FALSE":
                return []
            cur = conn.cursor()
            try:
                cur.execute("""SELECT bci.id,bci.contract_id,bci.estimate_section,bci.description,bci.unit,
                                      bci.quantity,bci.price_smeta,bci.price_brigade,bci.done_quantity,
                                      COALESCE(bci.work_package,''),COALESCE(bci.estimate_item_key,''),
                                      bc.company_id
                               FROM brigade_contract_items bci
                               JOIN brigade_contracts bc ON bc.id=bci.contract_id
                               WHERE bci.contract_id=%s AND """ + visibility_sql + " ORDER BY bci.id",
                            tuple([contract_id] + visibility_params))
                rows = cur.fetchall()
            finally:
                cur.close()
            actor_by_company = {
                positive_int_or_none(actor.get("companyId") or actor.get("company_id")): actor
                for actor in actors
                if positive_int_or_none(actor.get("companyId") or actor.get("company_id"))
            }

            def _status(quantity, done):
                try:
                    quantity = float(quantity or 0)
                    done = float(done or 0)
                except Exception:
                    return "Не начато"
                if done < 0:
                    return "Ошибка объёма"
                if quantity <= 0 and done > 0:
                    return "Нет плана"
                if quantity > 0 and done > quantity:
                    return "Сверх плана"
                if quantity > 0 and done >= quantity:
                    return "Выполнено"
                if done > 0:
                    return "В работе"
                return "Не начато"

            result = []
            for row in rows:
                actor = actor_by_company.get(positive_int_or_none(row[11])) or {}
                hide_customer_money = (actor.get("role") or "") in worker_execution_roles
                quantity = float(row[5] or 0)
                done_quantity = float(row[8] or 0)
                result.append({
                    "id": row[0], "contractId": row[1], "estimateSection": row[2],
                    "name": row[3], "unit": row[4], "quantity": quantity,
                    "priceSmeta": 0 if hide_customer_money else float(row[6] or 0),
                    "priceBrigade": float(row[7] or 0),
                    "doneQuantity": max(0, min(done_quantity, quantity)) if quantity > 0 else 0,
                    "rawDoneQuantity": done_quantity,
                    "hasInvalidDoneQuantity": (quantity <= 0 and done_quantity > 0)
                        or done_quantity < 0 or (quantity > 0 and done_quantity > quantity),
                    "workPackage": row[9] or "", "estimateItemKey": row[10] or "",
                    "status": _status(quantity, done_quantity), "companyId": row[11],
                })
            return result
        finally:
            conn.close()

    @app.post("/brigade-contract-items")
    def create_brigade_contract_item(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            _reject_client_lineage(data, reject_compatibility_key=True)
            contract, actor, project = resolve_brigade_contract_actor(
                cur,
                _current_user,
                data.get("contractId"),
                leadership_roles,
                claimed_company_id=data.get("companyId") if "companyId" in data else data.get("company_id"),
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            work_package = (data.get("workPackage") or data.get("work_package") or contract["workPackage"]).strip() or "Основная"
            if work_package != contract["workPackage"]:
                raise HTTPException(status_code=400, detail="Пакет позиции должен совпадать с пакетом договора")
            if not has_package_access(actor, work_package):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ")
            cur.execute(
                """INSERT INTO brigade_contract_items
                     (contract_id,estimate_section,description,work_package,estimate_item_key,
                      unit,quantity,price_smeta,price_brigade,done_quantity,
                      source_type,source_estimate_version_id,source_section_index,
                      source_item_index,source_item_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    contract["id"], data.get("estimateSection", ""),
                    data.get("name", "") or data.get("description", ""), work_package, "",
                    data.get("unit", ""), data.get("quantity", 0), data.get("priceSmeta", 0),
                    data.get("priceBrigade", 0), data.get("doneQuantity", 0),
                    "manual", None, None, None, None,
                ),
            )
            row = cur.fetchone()
            recalc_brigade_contract_total(cur, contract["id"])
            conn.commit()
            return {"id": row_get(row, "id", 0), "ok": True, "companyId": contract["companyId"], "projectId": project["id"]}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/brigade-contract-items/{id}")
    def update_brigade_contract_item(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            _reject_client_lineage(data)
            cur.execute("SELECT contract_id,COALESCE(NULLIF(work_package,''),'Основная') FROM brigade_contract_items WHERE id=%s FOR UPDATE", (id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Запись не найдена")
            contract_id = row_get(item, "contract_id", 0)
            contract, actor, project = resolve_brigade_contract_actor(
                cur,
                _current_user,
                contract_id,
                leadership_roles,
                claimed_company_id=data.get("companyId") if "companyId" in data else data.get("company_id"),
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            new_work_package = (data.get("workPackage") or data.get("work_package") or row_get(item, "work_package", 1) or contract["workPackage"]).strip() or "Основная"
            if new_work_package != contract["workPackage"]:
                raise HTTPException(status_code=400, detail="Пакет позиции должен совпадать с пакетом договора")
            if not has_package_access(actor, new_work_package):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ")
            quantity = float(data.get("quantity", 0) or 0)
            done_quantity = float(data.get("doneQuantity", 0) or 0)
            done_quantity = max(0, min(done_quantity, quantity)) if quantity > 0 else 0
            cur.execute(
                """UPDATE brigade_contract_items
                   SET quantity=%s,price_brigade=%s,price_smeta=%s,done_quantity=%s,work_package=%s
                   WHERE id=%s AND contract_id=%s RETURNING contract_id""",
                (
                    quantity, data.get("priceBrigade", 0), data.get("priceSmeta", 0),
                    done_quantity, new_work_package, id, contract["id"],
                ),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Позиция договора изменилась. Обновите страницу")
            recalc_brigade_contract_total(cur, contract["id"])
            conn.commit()
            return {"ok": True, "companyId": contract["companyId"], "projectId": project["id"]}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/brigade-contract-items/{id}")
    def delete_brigade_contract_item(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute("SELECT contract_id,COALESCE(NULLIF(work_package,''),'Основная') FROM brigade_contract_items WHERE id=%s FOR UPDATE", (id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Запись не найдена")
            contract, actor, project = resolve_brigade_contract_actor(
                cur,
                _current_user,
                row_get(item, "contract_id", 0),
                (*finance_roles, "прораб", "главный_инженер", "сметчик"),
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            item_package = row_get(item, "work_package", 1) or contract["workPackage"]
            if not has_package_access(actor, item_package):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ")
            cur.execute("DELETE FROM brigade_contract_items WHERE id=%s AND contract_id=%s RETURNING contract_id", (id, contract["id"]))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Позиция договора изменилась. Обновите страницу")
            recalc_brigade_contract_total(cur, contract["id"])
            conn.commit()
            return {"ok": True, "companyId": contract["companyId"], "projectId": project["id"]}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
