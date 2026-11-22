"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import psycopg2

def register_brigade_contracts_module(app, deps):
    CONTRACT_ROLES = deps['CONTRACT_ROLES']
    LEADERSHIP_ROLES = deps['LEADERSHIP_ROLES']
    PACKAGE_LIMIT_ROLES = deps['PACKAGE_LIMIT_ROLES']
    PROJECT_SCOPED_ACCESS_ROLES = deps['PROJECT_SCOPED_ACCESS_ROLES']
    WORK_PACKAGE_REQUIRED_ACCESS_ROLES = deps['WORK_PACKAGE_REQUIRED_ACCESS_ROLES']
    _brigade_contract_read_scope = deps['_brigade_contract_read_scope']
    _positive_int_or_none = deps['_positive_int_or_none']
    _resolve_brigade_contract_actor = deps['_resolve_brigade_contract_actor']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    _row_get = deps['_row_get']
    effective_company_actors = deps['effective_company_actors']
    find_existing_brigade_contract_id = deps['find_existing_brigade_contract_id']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    grant_brigade_contractor_scope = deps['grant_brigade_contractor_scope']
    has_package_access = deps['has_package_access']
    insert_pricelist_contract_item = deps['insert_pricelist_contract_item']
    recalc_brigade_contract_total = deps['recalc_brigade_contract_total']
    require_brigade_write_actor = deps['require_brigade_write_actor']
    require_project_access = deps['require_project_access']
    resolve_brigade_contractor_user = deps['resolve_brigade_contractor_user']
    user_package_names = deps['user_package_names']
    router = APIRouter()

    @router.get("/brigade-contracts")
    def get_brigade_contracts(
        project_name: str = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        try:
            visibility_sql, params, actors = _brigade_contract_read_scope(
                conn,
                _current_user,
                CONTRACT_ROLES,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            if visibility_sql == "FALSE":
                return []
            where = [visibility_sql]
            if project_name:
                where.append("bc.project_name=%s")
                params.append(project_name)
            base = (
                "SELECT bc.id,bc.project_id,bc.project_name,bc.brigade_name,bc.contractor_type,bc.contractor_id,"
                "bc.total_amount,bc.status,bc.signed_at,bc.notes,bc.created_at,bc.pricelist_id,COALESCE(bc.work_package,''),"
                "COALESCE((SELECT SUM(COALESCE(bci.quantity,0)*COALESCE(bci.price_brigade,0)) FROM brigade_contract_items bci WHERE bci.contract_id=bc.id),0) AS plan_amount,"
                "COALESCE((SELECT SUM(CASE WHEN COALESCE(bci.quantity,0)>0 THEN GREATEST(0, LEAST(COALESCE(bci.done_quantity,0), COALESCE(bci.quantity,0))) * COALESCE(bci.price_brigade,0) ELSE 0 END) FROM brigade_contract_items bci WHERE bci.contract_id=bc.id),0) AS done_amount,"
                "COALESCE((SELECT SUM(bp.amount) FROM brigade_payments bp WHERE bp.contract_id=bc.id AND bp.company_id=bc.company_id AND bp.amount IS NOT NULL AND bp.amount NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)),0) AS paid_amount,"
                "bc.act_scan_url,bc.company_id,bc.settlement_version,COALESCE(bc.contract_scan_url,''),"
                "bc.party_snapshot_json FROM brigade_contracts bc WHERE "
            )
            cur = conn.cursor()
            try:
                cur.execute(base + " AND ".join(where) + " ORDER BY bc.id DESC", tuple(params))
                rows = cur.fetchall()
                actor_by_company = {
                    _positive_int_or_none(actor.get("companyId") or actor.get("company_id")): actor
                    for actor in actors
                    if _positive_int_or_none(actor.get("companyId") or actor.get("company_id"))
                }
                scoped_groups = {}
                package_scoped_contract_ids = set()
                for row in rows:
                    actor = actor_by_company.get(_positive_int_or_none(row[17])) or {}
                    if (actor.get("role") or "") not in PACKAGE_LIMIT_ROLES:
                        continue
                    packages = user_package_names(actor)
                    if not packages:
                        continue
                    scoped_groups.setdefault(tuple(packages), []).append(row[0])
                    package_scoped_contract_ids.add(row[0])
                from backend.features.brigade_access.settlement_summary import read_settlement_summaries
                settlement_summaries = read_settlement_summaries(cur, [
                    (row[0], row[17]) for row in rows
                    if row[18] == 2 and row[0] not in package_scoped_contract_ids
                ])
                scoped_item_amounts = {}
                for packages, contract_ids in scoped_groups.items():
                    cur.execute("""SELECT contract_id,
                                          COALESCE(SUM(COALESCE(quantity,0)*COALESCE(price_brigade,0)),0),
                                          COALESCE(SUM(CASE WHEN COALESCE(quantity,0)>0 THEN GREATEST(0, LEAST(COALESCE(done_quantity,0), COALESCE(quantity,0))) * COALESCE(price_brigade,0) ELSE 0 END),0)
                                   FROM brigade_contract_items
                                   WHERE contract_id = ANY(%s)
                                     AND COALESCE(NULLIF(work_package,''),'Основная') = ANY(%s)
                                   GROUP BY contract_id""", (contract_ids, list(packages)))
                    for amount_row in cur.fetchall():
                        scoped_item_amounts[amount_row[0]] = {
                            "plan": float(amount_row[1] or 0),
                            "done": float(amount_row[2] or 0),
                        }
            finally:
                cur.close()
            result = []
            for row in rows:
                plan_amount = float(row[13] or 0)
                done_amount = float(row[14] or 0)
                package_scoped = row[0] in package_scoped_contract_ids
                if package_scoped:
                    scoped_amounts = scoped_item_amounts.get(row[0]) or {"plan": 0, "done": 0}
                    plan_amount = scoped_amounts["plan"]
                    done_amount = scoped_amounts["done"]
                total_amount = plan_amount if package_scoped else float((plan_amount if plan_amount > 0 else row[6]) or 0)
                result.append({
                    "id": row[0], "projectId": row[1], "projectName": row[2],
                    "brigadeName": row[3], "contractorType": row[4], "contractorId": row[5],
                    "totalAmount": total_amount, "status": row[7],
                    "signedAt": str(row[8]) if row[8] else "", "notes": row[9] or "",
                    "createdAt": str(row[10]), "pricelistId": row[11],
                    "planAmount": plan_amount, "doneAmount": done_amount,
                    "paidAmount": float(row[15] or 0), "workPackage": row[12] or "",
                    "actScanUrl": row[16] or "", "companyId": row[17],
                    "settlementVersion": _row_get(row, "settlement_version", 18, 1),
                    "settlementSummary": settlement_summaries.get((row[0], row[17])),
                    "contractScanUrl": _row_get(row, "contract_scan_url", 19, "") or "",
                    "partySnapshot": _row_get(row, "party_snapshot_json", 20),
                })
            return result
        finally:
            conn.close()

    @router.post("/brigade-contracts")
    def create_brigade_contract(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        access_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            try:
                from backend.features.project_access.service import resolve_project_parent
            except ModuleNotFoundError:
                from features.project_access.service import resolve_project_parent
            claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
            company_context = _resolve_work_company_context(
                access_cur,
                _current_user,
                claimed_company_id,
                "write",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            actor = require_brigade_write_actor(
                effective_company_actors(_current_user, company_context),
                LEADERSHIP_ROLES,
            )
            company_id = int(actor["companyId"])
            project = resolve_project_parent(
                access_cur,
                actor,
                project_id=data.get("projectId") or data.get("project_id"),
                project_name=data.get("projectName") or data.get("project_name") or "",
                for_update=True,
            )
            require_project_access(actor, project["name"])
            pricelist_id = data.get("pricelistId") or None
            work_package = (data.get("workPackage") or data.get("work_package") or "Основная").strip() or "Основная"
            contractor_user_id = resolve_brigade_contractor_user(
                cur,
                company_id,
                data.get("contractorId"),
                data.get("brigadeName", ""),
                **({'contractor_ref': data['contractorRef'], 'project_id': project['id'],
                    'work_package': work_package} if 'contractorRef' in data else {}),
            )
            reference = data.get('contractorRef') or {}
            manual_command = None
            if reference.get('type') == 'manual':
                if not str(data.get('brigadeName') or '').strip():
                    raise HTTPException(400, 'Укажите название бригады без аккаунта')
                try:
                    from backend.features.contractor_identity.manual import command_evidence, find_manual_retry, record_manual_origin
                except ModuleNotFoundError:
                    from features.contractor_identity.manual import command_evidence, find_manual_retry, record_manual_origin
                manual_command = command_evidence(reference, company_id=company_id, project_id=project['id'],
                    actor_id=actor['id'], command='create_contract', payload=data)
                existing_id = find_manual_retry(cur, company_id, project['id'], work_package, *manual_command)
            else:
                selected_contract_id = int(reference['id']) if reference.get('type') == 'contract' else None
                existing_id = selected_contract_id or find_existing_brigade_contract_id(
                    cur, company_id, project["id"], work_package,
                    contractor_user_id, data.get("brigadeName", ""),
                )
            if existing_id:
                conn.rollback()
                return {
                    "id": existing_id,
                    "ok": True,
                    "reused": True,
                    "itemsLoaded": 0,
                    "companyId": company_id,
                    "projectId": project["id"],
                    "contractorId": contractor_user_id,
                    "manualRequestId": manual_command[0] if manual_command else None,
                }
            cur.execute(
                """INSERT INTO brigade_contracts
                       (company_id,project_id,project_name,work_package,brigade_name,contractor_type,
                        contractor_id,total_amount,status,notes,pricelist_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    company_id, project["id"], project["name"], work_package,
                    data.get("brigadeName", ""), data.get("contractorType", "Бригада"),
                    contractor_user_id or None, data.get("totalAmount", 0),
                    "Черновик", data.get("notes", ""), pricelist_id,
                ),
            )
            row = cur.fetchone()
            new_id = _row_get(row, "id", 0)
            if manual_command:
                record_manual_origin(cur, new_id, company_id, project['id'], *manual_command, actor['id'])
            grant_brigade_contractor_scope(
                cur,
                company_id,
                contractor_user_id,
                project["name"],
                work_package,
                project_scoped_roles=PROJECT_SCOPED_ACCESS_ROLES,
                package_required_roles=WORK_PACKAGE_REQUIRED_ACCESS_ROLES,
            )

            inserted = 0
            if pricelist_id:
                pl_id_int = int(pricelist_id)
                cur.execute("SELECT coefficient FROM pricelists WHERE id=%s", (pl_id_int,))
                cr = cur.fetchone()
                coef = float(cr[0] or 1.0) if cr else 1.0
                cur.execute("SELECT name, unit, price, category FROM pricelist_items WHERE pricelist_id=%s AND (item_type IS NULL OR item_type='work')", (pl_id_int,))
                for it in cur.fetchall():
                    insert_pricelist_contract_item(
                        cur,
                        contract_id=new_id,
                        work_package=work_package,
                        name=it[0],
                        unit=it[1],
                        price=it[2],
                        category=it[3],
                        coefficient=coef,
                    )
                    inserted += 1
                recalc_brigade_contract_total(cur, new_id)
            conn.commit()
            return {
                "id": new_id,
                "ok": True,
                "itemsLoaded": inserted,
                "companyId": company_id,
                "projectId": project["id"],
                "contractorId": contractor_user_id,
                "manualRequestId": manual_command[0] if manual_command else None,
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            access_cur.close()
            cur.close()
            conn.close()

    @router.post("/brigade-contracts/{contract_id}/load-from-pricelist")
    def load_brigade_items_from_pricelist(
        contract_id: int,
        with_materials: bool = False,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            contract, actor, project = _resolve_brigade_contract_actor(
                cur,
                _current_user,
                contract_id,
                LEADERSHIP_ROLES,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            if not has_package_access(actor, contract["workPackage"]):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ договора")
            cur.execute("SELECT pricelist_id FROM brigade_contracts WHERE id=%s AND company_id=%s", (contract["id"], contract["companyId"]))
            r = cur.fetchone()
            if not r or not _row_get(r, "pricelist_id", 0):
                raise HTTPException(status_code=400, detail="К наряду не привязан прайс-лист")
            pl_id = int(_row_get(r, "pricelist_id", 0))

            cur.execute("SELECT coefficient FROM pricelists WHERE id=%s", (pl_id,))
            cr = cur.fetchone()
            coef = float(_row_get(cr, "coefficient", 0, 1.0) or 1.0) if cr else 1.0

            cur.execute("SELECT description FROM brigade_contract_items WHERE contract_id=%s", (contract["id"],))
            existing_names = {_row_get(row, "description", 0) for row in cur.fetchall()}
            if with_materials:
                cur.execute("SELECT name, unit, price, category, item_type FROM pricelist_items WHERE pricelist_id=%s", (pl_id,))
            else:
                cur.execute("SELECT name, unit, price, category, item_type FROM pricelist_items WHERE pricelist_id=%s AND (item_type IS NULL OR item_type='work')", (pl_id,))
            rows = cur.fetchall()
            inserted = 0
            for item in rows:
                item_name = _row_get(item, "name", 0)
                if item_name in existing_names:
                    continue
                insert_pricelist_contract_item(
                    cur,
                    contract_id=contract["id"],
                    work_package=contract["workPackage"],
                    name=item_name,
                    unit=_row_get(item, "unit", 1, "шт"),
                    price=_row_get(item, "price", 2, 0),
                    category=_row_get(item, "category", 3, ""),
                    coefficient=coef,
                )
                inserted += 1
            recalc_brigade_contract_total(cur, contract["id"])
            conn.commit()
            return {"ok": True, "itemsLoaded": inserted, "matchedFromEstimate": 0, "companyId": contract["companyId"], "projectId": project["id"]}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @router.put("/brigade-contracts/{id}")
    def update_brigade_contract(
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
            claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
            contract, _actor, _project = _resolve_brigade_contract_actor(
                cur,
                _current_user,
                id,
                LEADERSHIP_ROLES,
                claimed_company_id=claimed_company_id,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            company_id = int(contract["companyId"])
            if data.get("status") == "Подписан" and contract.get("status") != "Подписан":
                raise HTTPException(
                    status_code=409,
                    detail="Сначала загрузите подписанный оригинал и нажмите «Сохранить договор»",
                )
            work_package = (data.get("workPackage") or data.get("work_package") or "").strip()
            cur.execute(
                """UPDATE brigade_contracts
                      SET brigade_name=%s,contractor_type=%s,total_amount=%s,status=%s,signed_at=%s,
                          notes=%s,pricelist_id=%s,work_package=COALESCE(NULLIF(%s,''),work_package),
                          act_scan_url=COALESCE(%s,act_scan_url)
                    WHERE id=%s AND company_id=%s
                    RETURNING id""",
                (
                    data.get("brigadeName", ""), data.get("contractorType", "Бригада"),
                    data.get("totalAmount", 0), data.get("status", "Черновик"),
                    data.get("signedAt") or None, data.get("notes", ""),
                    data.get("pricelistId") or None, work_package, data.get("actScanUrl"),
                    contract["id"], company_id,
                ),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=409, detail="Компания договора изменилась во время обновления")
            conn.commit()
            return {"ok": True, "companyId": company_id}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @router.delete("/brigade-contracts/{id}")
    def delete_brigade_contract(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            contract, _actor, _project = _resolve_brigade_contract_actor(
                cur,
                _current_user,
                id,
                (*LEADERSHIP_ROLES, "бухгалтер"),
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            company_id = int(contract["companyId"])
            if contract.get("partySnapshot") is not None:
                raise HTTPException(status_code=409, detail="Подписанный договор хранится в истории и не удаляется")
            try:
                from backend.features.brigade_access.archive_policy import require_empty_signed_duplicate
            except ModuleNotFoundError:
                from features.brigade_access.archive_policy import require_empty_signed_duplicate
            require_empty_signed_duplicate(cur, contract)
            cur.execute(
                """UPDATE brigade_contracts
                      SET status='Аннулирован'
                    WHERE id=%s AND company_id=%s
                    RETURNING id""",
                (contract["id"], company_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=409, detail="Компания договора изменилась во время аннулирования")
            conn.commit()
            return {"ok": True, "companyId": company_id}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    app.include_router(router)

