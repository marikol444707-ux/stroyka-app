import json
import re
from typing import Optional

from fastapi import Depends, Header, HTTPException

from .service import reconciliation_visibility_filter


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _required_id(data, camel_key, snake_key):
    value = (data or {}).get(camel_key, (data or {}).get(snake_key))
    raw = str(value).strip() if not isinstance(value, bool) else ""
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise HTTPException(status_code=400, detail=camel_key + " должен быть положительным целым числом")
    return int(raw)


def _row_id(row):
    if isinstance(row, dict):
        return _positive_int(row.get("id"))
    if isinstance(row, (list, tuple)) and row:
        return _positive_int(row[0])
    return None


def register_estimate_reconciliations_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    require_project_write_actor = deps["require_project_write_actor"]
    resolve_project_parent = deps["resolve_project_parent"]
    require_project_parent_access = deps["require_project_parent_access"]
    resolve_estimate_parent = deps["resolve_estimate_parent"]
    has_package_access = deps["has_package_access"]
    normalize_sections = deps["normalize_sections"]
    sections_total = deps["sections_total"]
    build_diff = deps["build_diff"]
    add_change_items = deps["add_change_items"]
    item_payload = deps["item_payload"]
    reconciliation_payload = deps["reconciliation_payload"]
    safe_float = deps["safe_float"]
    log_audit = deps["log_audit"]
    document_roles = tuple(deps["document_roles"])
    estimate_write_roles = tuple(deps["estimate_write_roles"])
    approval_roles = set(deps["approval_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = set(deps["package_limit_roles"])
    package_unrestricted_roles = tuple(deps["package_unrestricted_roles"])
    customer_roles = tuple(deps["customer_roles"])

    owner_join = """JOIN estimates b ON b.id=r.base_estimate_id
                    JOIN estimates n ON n.id=r.next_estimate_id
                    JOIN projects p ON p.id=b.project_id AND p.company_id=b.company_id"""
    owner_match = """b.company_id=n.company_id AND b.project_id=n.project_id
                      AND b.project_id IS NOT NULL
                      AND COALESCE(NULLIF(b.work_package,''),'Основная')=
                          COALESCE(NULLIF(n.work_package,''),'Основная')
                      AND COALESCE(b.smeta_type,'Заказчик')=COALESCE(n.smeta_type,'Заказчик')"""

    def read_scope(cur, current_user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        actors = effective_company_actors(current_user, context)
        return reconciliation_visibility_filter(
            actors,
            document_roles,
            full_view_roles,
            package_limit_roles,
            package_unrestricted_roles,
            customer_roles,
        )

    def write_actor(cur, current_user, x_company_id, x_company_mode, action_mode="update"):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        return require_project_write_actor(
            effective_company_actors(current_user, context),
            estimate_write_roles,
        )

    def select_with_counts(where_sql):
        return f"""SELECT r.id,p.name AS project_name,r.work_package,r.smeta_type,
                           r.base_estimate_id,r.next_estimate_id,
                           r.base_estimate_name,r.next_estimate_name,r.base_version,r.next_version,
                           r.base_total,r.next_total,r.impact,r.changed_count,r.added_count,r.removed_count,
                           r.status,r.notes,r.created_by,r.approved_by,r.approved_at,r.created_at,r.updated_at,
                           COUNT(i.id) AS item_count,
                           COALESCE(SUM(CASE
                             WHEN COALESCE(i.decision,'') ILIKE 'Проверить%%'
                               OR COALESCE(i.decision,'')='На проверке' THEN 1 ELSE 0 END),0) AS review_count
                      FROM estimate_reconciliations r
                      {owner_join}
                      LEFT JOIN estimate_reconciliation_items i ON i.reconciliation_id=r.id
                     WHERE {owner_match} AND ({where_sql})
                     GROUP BY r.id,p.name
                     ORDER BY r.id DESC"""

    def assert_package_access(actor, work_package):
        role = str((actor or {}).get("role") or "").strip()
        if role in package_limit_roles and role not in set(package_unrestricted_roles):
            if not has_package_access(actor, work_package):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету сверки")

    def verify_estimate_pair(cur, actor, base_id, next_id, *, for_update):
        base_parent = resolve_estimate_parent(cur, actor, base_id, for_update=for_update)
        next_parent = resolve_estimate_parent(cur, actor, next_id, for_update=for_update)
        owner = (
            _positive_int(base_parent.get("companyId")),
            _positive_int(base_parent.get("projectId")),
        )
        if owner != (
            _positive_int(next_parent.get("companyId")),
            _positive_int(next_parent.get("projectId")),
        ):
            raise HTTPException(status_code=409, detail="Сметы относятся к разным компаниям или объектам")
        project = resolve_project_parent(
            cur,
            actor,
            project_id=owner[1],
            project_name=base_parent.get("projectName"),
            for_update=for_update,
        )
        require_project_parent_access(cur, actor, project, full_view_roles)
        if str(base_parent.get("workPackage") or "Основная") != str(next_parent.get("workPackage") or "Основная"):
            raise HTTPException(status_code=409, detail="Сметы относятся к разным пакетам работ")
        assert_package_access(actor, base_parent.get("workPackage") or "Основная")
        return base_parent, next_parent, project

    def load_source(cur, actor, estimate_id, *, for_update=True):
        parent = resolve_estimate_parent(cur, actor, estimate_id, for_update=for_update)
        lock_sql = " FOR UPDATE" if for_update else ""
        cur.execute(
            """SELECT id,project_id,project_name,name,version,sections_json,
                      COALESCE(smeta_type,'Заказчик'),
                      COALESCE(NULLIF(work_package,''),'Основная'),
                      COALESCE(status,'Черновик'),created_at,company_id
                 FROM estimates
                WHERE id=%s AND company_id=%s AND project_id=%s""" + lock_sql,
            (parent["id"], parent["companyId"], parent["projectId"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Смета изменилась во время проверки владельца")
        raw_sections = row[5]
        try:
            sections = raw_sections if isinstance(raw_sections, list) else json.loads(raw_sections or "[]")
        except Exception:
            sections = []
        sections, _warnings = normalize_sections(sections)
        return row, sections, sections_total(sections)

    def mutation_parent(cur, actor, reconciliation_id):
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        cur.execute(
            f"""SELECT r.id,r.base_estimate_id,r.next_estimate_id,r.project_name,
                       COALESCE(NULLIF(r.work_package,''),'Основная'),r.status
                  FROM estimate_reconciliations r
                  {owner_join}
                 WHERE r.id=%s AND p.company_id=%s AND {owner_match}
                 FOR UPDATE OF r,b,n,p""",
            (reconciliation_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Сверка смет не найдена в выбранной компании")
        base_parent, next_parent, project = verify_estimate_pair(
            cur,
            actor,
            row[1],
            row[2],
            for_update=True,
        )
        if (
            _positive_int(base_parent.get("projectId")) != _positive_int(project.get("id"))
            or _positive_int(next_parent.get("projectId")) != _positive_int(project.get("id"))
        ):
            raise HTTPException(status_code=409, detail="Владелец сверки изменился")
        assert_package_access(actor, row[4] or "Основная")
        return row, project

    @app.get("/estimate-reconciliations")
    def list_reconciliations(
        project_name: str = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            visibility_sql, params = read_scope(cur, current_user, x_company_id, x_company_mode)
            filters = [visibility_sql]
            if project_name:
                filters.append("p.name=%s")
                params.append(project_name)
            cur.execute(select_with_counts(" AND ".join(filters)), tuple(params))
            return [reconciliation_payload(row) for row in (cur.fetchall() or [])]
        finally:
            cur.close()
            conn.close()

    @app.get("/estimate-reconciliations/{id}")
    def get_reconciliation(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            visibility_sql, params = read_scope(cur, current_user, x_company_id, x_company_mode)
            cur.execute(select_with_counts("r.id=%s AND " + visibility_sql), (id, *params))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сверка смет не найдена")
            cur.execute(
                """SELECT id,reconciliation_id,item_type,section_name,item_name,unit,
                          base_quantity,next_quantity,base_unit_price,next_unit_price,
                          base_total,next_total,impact,decision,confidence,notes,
                          old_row_json,new_row_json,unexpected_work_id,created_at
                     FROM estimate_reconciliation_items
                    WHERE reconciliation_id=%s
                    ORDER BY CASE item_type
                               WHEN 'changed' THEN 1 WHEN 'added' THEN 2
                               WHEN 'removed' THEN 3 WHEN 'estimate_change' THEN 4 ELSE 5
                             END,ABS(COALESCE(impact,0)) DESC,id""",
                (id,),
            )
            return reconciliation_payload(row, [item_payload(item) for item in (cur.fetchall() or [])])
        finally:
            cur.close()
            conn.close()

    @app.post("/estimate-reconciliations")
    def create_reconciliation(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        base_id = _required_id(data, "baseEstimateId", "base_estimate_id")
        next_id = _required_id(data, "nextEstimateId", "next_estimate_id")
        if base_id == next_id:
            raise HTTPException(status_code=400, detail="Нужно выбрать две разные сметы")
        conn = get_db()
        cur = conn.cursor()
        try:
            actor = write_actor(cur, current_user, x_company_id, x_company_mode, action_mode="create")
            base_parent, next_parent, project = verify_estimate_pair(
                cur,
                actor,
                base_id,
                next_id,
                for_update=True,
            )
            base, base_sections, base_total = load_source(cur, actor, base_id)
            next_est, next_sections, next_total = load_source(cur, actor, next_id)
            if (base[6] or "Заказчик") != (next_est[6] or "Заказчик"):
                raise HTTPException(status_code=400, detail="Сравнивать можно сметы одного типа")
            if (base[7] or "Основная") != (next_est[7] or "Основная"):
                raise HTTPException(status_code=400, detail="Сравнивать можно сметы одного пакета работ")
            status = str((data or {}).get("status") or "Черновик")
            if status not in ("Черновик", "На проверке", "Утверждена", "Отклонена"):
                status = "Черновик"
            if status == "Утверждена" and str(actor.get("role") or "") not in approval_roles:
                raise HTTPException(status_code=403, detail="Утвердить сверку может руководитель, главный инженер или сметчик")
            diff = build_diff(base_id, base_sections, base_total, next_id, next_sections, next_total)
            project_name = str(project.get("name") or next_parent.get("projectName") or "")
            cur.execute(
                """INSERT INTO estimate_reconciliations
                   (project_name,work_package,smeta_type,base_estimate_id,next_estimate_id,
                    base_estimate_name,next_estimate_name,base_version,next_version,
                    base_total,next_total,impact,changed_count,added_count,removed_count,
                    status,notes,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id,created_at""",
                (
                    project_name,
                    next_est[7] or "Основная",
                    next_est[6] or "Заказчик",
                    base_id,
                    next_id,
                    base[3] or "",
                    next_est[3] or "",
                    base[4] or "",
                    next_est[4] or "",
                    diff["baseTotal"],
                    diff["nextTotal"],
                    diff["impact"],
                    len(diff["changed"]),
                    len(diff["added"]),
                    len(diff["removed"]),
                    status,
                    (data or {}).get("notes") or "",
                    actor.get("name") or "",
                ),
            )
            created = cur.fetchone()
            reconciliation_id = _row_id(created)
            created_at = created[1] if created and len(created) > 1 else None
            if not reconciliation_id:
                raise HTTPException(status_code=409, detail="Сверка смет не создана")

            def insert_item(item_type, row, base_row=None, next_row=None):
                old_row = (base_row or row) if item_type == "removed" else base_row
                new_row = (next_row or row) if item_type == "added" else next_row
                source = next_row or row or base_row or {}
                cur.execute(
                    """INSERT INTO estimate_reconciliation_items
                       (reconciliation_id,item_type,section_name,item_name,unit,
                        base_quantity,next_quantity,base_unit_price,next_unit_price,
                        base_total,next_total,impact,decision,confidence,old_row_json,new_row_json)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        reconciliation_id,
                        item_type,
                        source.get("section") or "",
                        source.get("name") or "",
                        source.get("unit") or "",
                        safe_float((base_row or {}).get("qty")),
                        safe_float((next_row or {}).get("qty")),
                        safe_float((base_row or {}).get("unitPrice")),
                        safe_float((next_row or {}).get("unitPrice")),
                        safe_float((base_row or {}).get("sum")),
                        safe_float((next_row or {}).get("sum")),
                        safe_float(row.get("impact")),
                        {
                            "changed": "Проверить изменение объёма/цены",
                            "added": "Проверить новую позицию",
                            "removed": "Проверить исключённую позицию",
                        }.get(item_type, "На проверке"),
                        1,
                        json.dumps(old_row or {}, ensure_ascii=False),
                        json.dumps(new_row or {}, ensure_ascii=False),
                    ),
                )

            for row in diff["changed"]:
                insert_item("changed", row, row.get("base"), row.get("next"))
            for row in diff["added"]:
                insert_item("added", row, None, row)
            for row in diff["removed"]:
                insert_item("removed", row, row, None)
            add_change_items(
                cur,
                reconciliation_id,
                base_parent["companyId"],
                base_parent["projectId"],
                next_est[7] or "Основная",
                base_id,
                next_id,
                diff,
            )
            cur.execute(
                """INSERT INTO project_documents
                   (project_name,side,doc_type,number,doc_date,counterparty,sign_status,
                    scan_url,amount,notes,uploaded_by)
                   VALUES (%s,%s,%s,%s,CURRENT_DATE,%s,%s,%s,%s,%s,%s)""",
                (
                    project_name,
                    "customer",
                    "Сверка смет",
                    "СС-" + str(reconciliation_id),
                    "",
                    "Подписан" if status == "Утверждена" else status,
                    "",
                    diff["impact"],
                    "Автоматически создана по сверке смет #"
                    + str(reconciliation_id)
                    + ": "
                    + (base[3] or "")
                    + " -> "
                    + (next_est[3] or ""),
                    actor.get("name") or "",
                ),
            )
            conn.commit()
            return {"ok": True, "id": reconciliation_id, "createdAt": str(created_at) if created_at else ""}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/estimate-reconciliations/{id}")
    def update_reconciliation(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        status = (data or {}).get("status")
        if status and status not in ("Черновик", "На проверке", "Утверждена", "Отклонена"):
            raise HTTPException(status_code=400, detail="Недопустимый статус сверки")
        conn = get_db()
        cur = conn.cursor()
        audit_payload = None
        try:
            actor = write_actor(cur, current_user, x_company_id, x_company_mode)
            row, project = mutation_parent(cur, actor, id)
            if status == "Утверждена" and str(actor.get("role") or "") not in approval_roles:
                raise HTTPException(status_code=403, detail="Утвердить сверку может руководитель, главный инженер или сметчик")
            updates = ["updated_at=NOW()"]
            params = []
            if status:
                updates.append("status=%s")
                params.append(status)
                if status == "Утверждена":
                    updates.extend(["approved_by=%s", "approved_at=CURRENT_DATE"])
                    params.append(actor.get("name") or "")
            if "notes" in (data or {}):
                updates.append("notes=%s")
                params.append((data or {}).get("notes") or "")
            params.extend([id, row[1], row[2]])
            cur.execute(
                "UPDATE estimate_reconciliations SET "
                + ",".join(updates)
                + " WHERE id=%s AND base_estimate_id=%s AND next_estimate_id=%s RETURNING id",
                tuple(params),
            )
            if not _row_id(cur.fetchone()):
                raise HTTPException(status_code=409, detail="Сверка изменилась во время проверки владельца")
            if status:
                doc_status = "Подписан" if status == "Утверждена" else status
                cur.execute(
                    """UPDATE project_documents SET sign_status=%s
                        WHERE project_name=%s AND doc_type='Сверка смет' AND number=%s""",
                    (doc_status, project.get("name") or "", "СС-" + str(id)),
                )
                if status != (row[5] or ""):
                    audit_payload = {
                        "user_name": actor.get("name") or "",
                        "user_role": actor.get("role") or "",
                        "action": "status_change",
                        "entity_type": "estimate_reconciliation",
                        "entity_id": id,
                        "description": "Статус сверки смет: " + (row[5] or "—") + " -> " + status,
                        "project_name": project.get("name") or "",
                    }
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        if audit_payload:
            log_audit(**audit_payload)
        return {"ok": True}

    @app.put("/estimate-reconciliation-items/{id}")
    def update_reconciliation_item(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            actor = write_actor(cur, current_user, x_company_id, x_company_mode)
            cur.execute(
                "SELECT id,reconciliation_id FROM estimate_reconciliation_items WHERE id=%s FOR UPDATE",
                (id,),
            )
            item_row = cur.fetchone()
            if not item_row:
                raise HTTPException(status_code=404, detail="Строка сверки не найдена")
            reconciliation_id = _positive_int(item_row[1])
            mutation_parent(cur, actor, reconciliation_id)
            updates = []
            params = []
            if "decision" in (data or {}):
                updates.append("decision=%s")
                params.append((data or {}).get("decision") or "На проверке")
            if "notes" in (data or {}):
                updates.append("notes=%s")
                params.append((data or {}).get("notes") or "")
            if updates:
                params.extend([id, reconciliation_id])
                cur.execute(
                    "UPDATE estimate_reconciliation_items SET "
                    + ",".join(updates)
                    + " WHERE id=%s AND reconciliation_id=%s RETURNING id",
                    tuple(params),
                )
                if not _row_id(cur.fetchone()):
                    raise HTTPException(status_code=409, detail="Строка сверки изменилась во время проверки")
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
