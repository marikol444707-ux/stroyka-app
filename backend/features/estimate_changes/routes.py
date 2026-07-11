import re
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _optional_id(data, key, label):
    value = (data or {}).get(key)
    if value in (None, ""):
        return None
    raw_value = str(value).strip() if not isinstance(value, bool) else ""
    if not re.fullmatch(r"[1-9][0-9]*", raw_value):
        raise HTTPException(status_code=400, detail=label + " должен быть положительным целым числом")
    return int(raw_value)


def _row_id(row):
    if isinstance(row, dict):
        return _positive_int(row.get("id"))
    if isinstance(row, (list, tuple)) and row:
        return _positive_int(row[0])
    return None


def _number(value):
    return float(value or 0)


def _assert_same_project(estimate, project, label):
    estimate_company_id = _positive_int((estimate or {}).get("companyId") or (estimate or {}).get("company_id"))
    estimate_project_id = _positive_int((estimate or {}).get("projectId") or (estimate or {}).get("project_id"))
    project_company_id = _positive_int((project or {}).get("companyId") or (project or {}).get("company_id"))
    project_id = _positive_int((project or {}).get("id"))
    if estimate_company_id != project_company_id or estimate_project_id != project_id:
        raise HTTPException(status_code=409, detail=label + " относится к другому объекту")


def register_estimate_changes_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    require_project_write_actor = deps["require_project_write_actor"]
    resolve_project_parent = deps["resolve_project_parent"]
    require_project_parent_access = deps["require_project_parent_access"]
    resolve_estimate_parent = deps["resolve_estimate_parent"]
    has_package_access = deps["has_package_access"]
    visibility_filter = deps["visibility_filter"]
    project_document_roles = {str(role or "").strip() for role in deps["project_document_roles"]}
    journal_write_roles = tuple(deps["journal_write_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = set(deps["package_limit_roles"])
    package_unrestricted_roles = tuple(deps["package_unrestricted_roles"])
    customer_roles = tuple(deps["customer_roles"])
    customer_statuses = tuple(deps["customer_statuses"])
    worker_execution_roles = set(deps["worker_execution_roles"])

    def read_scope(cur, current_user, x_company_id, x_company_mode):
        company_context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        company_actors = []
        for actor in effective_company_actors(current_user, company_context):
            company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
            role = str((actor or {}).get("role") or "").strip()
            if not company_id or role not in project_document_roles:
                continue
            normalized_actor = dict(actor or {})
            normalized_actor["companyId"] = company_id
            normalized_actor["company_id"] = company_id
            normalized_actor["role"] = role
            company_actors.append(normalized_actor)
        visibility_sql, visibility_params = visibility_filter(
            company_actors,
            project_document_roles,
            full_view_roles,
            package_limit_roles,
            package_unrestricted_roles,
            customer_roles,
            customer_statuses,
            project_prefix="p",
            change_prefix="uw",
        )
        return company_actors, visibility_sql, visibility_params

    @app.get("/unexpected-works")
    def get_unexpected_works(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_actors, visibility_sql, visibility_params = read_scope(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
            )
            cur.execute(
                f"""SELECT uw.id,uw.project_name,uw.description,uw.unit,uw.quantity,uw.price,
                            uw.total,uw.added_by,uw.added_by_role,uw.status,uw.approved_by,
                            uw.approved_at,uw.notes,uw.photo_url,uw.change_type,uw.estimate_id,
                            uw.section_name,uw.estimate_item_name,uw.base_quantity,
                            uw.new_required_quantity,uw.delta_quantity,uw.included_in_estimate_id,
                            uw.reason,uw.company_id
                       FROM unexpected_works uw
                       JOIN projects p ON p.id=uw.project_id AND p.company_id=uw.company_id
                      WHERE {visibility_sql}
                      ORDER BY uw.id DESC""",
                tuple(visibility_params),
            )
            actors_by_company = {
                _positive_int(actor.get("companyId") or actor.get("company_id")): actor
                for actor in company_actors
            }
            result = []
            for row in cur.fetchall() or []:
                actor = actors_by_company.get(_positive_int(row.get("company_id")))
                if not actor:
                    continue
                hide_money = actor.get("role") in worker_execution_roles
                result.append({
                    "id": row.get("id"),
                    "projectName": row.get("project_name"),
                    "description": row.get("description"),
                    "unit": row.get("unit"),
                    "quantity": _number(row.get("quantity")),
                    "price": 0 if hide_money else _number(row.get("price")),
                    "total": 0 if hide_money else _number(row.get("total")),
                    "addedBy": row.get("added_by"),
                    "addedByRole": row.get("added_by_role"),
                    "status": row.get("status"),
                    "approvedBy": row.get("approved_by"),
                    "approvedAt": row.get("approved_at"),
                    "notes": row.get("notes"),
                    "photoUrl": row.get("photo_url"),
                    "changeType": row.get("change_type") or "Работа вне сметы",
                    "estimateId": row.get("estimate_id"),
                    "sectionName": row.get("section_name") or "",
                    "estimateItemName": row.get("estimate_item_name") or "",
                    "baseQuantity": _number(row.get("base_quantity")),
                    "newRequiredQuantity": _number(row.get("new_required_quantity")),
                    "deltaQuantity": _number(row.get("delta_quantity")),
                    "includedInEstimateId": row.get("included_in_estimate_id"),
                    "reason": row.get("reason") or "",
                })
            return result
        finally:
            cur.close()
            conn.close()

    @app.post("/unexpected-works")
    def create_unexpected_work(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = data or {}
        project_name = str(payload.get("projectName") or "").strip()
        project_id_claim = _optional_id(payload, "projectId", "projectId")
        estimate_id = _optional_id(payload, "estimateId", "estimateId")
        included_estimate_id = _optional_id(
            payload,
            "includedInEstimateId",
            "includedInEstimateId",
        )
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = resolve_work_company_context(
                cur,
                current_user,
                None,
                "create",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            actor = require_project_write_actor(
                effective_company_actors(current_user, company_context),
                journal_write_roles,
            )
            project = resolve_project_parent(
                cur,
                actor,
                project_id=project_id_claim,
                project_name=project_name,
            )
            require_project_parent_access(cur, actor, project, full_view_roles)

            company_id = _positive_int(project.get("companyId") or project.get("company_id"))
            project_id = _positive_int(project.get("id"))
            canonical_project_name = str(project.get("name") or "").strip()
            if not company_id or not project_id or not canonical_project_name:
                raise HTTPException(status_code=409, detail="Объект не имеет точного владельца")

            if estimate_id:
                estimate = resolve_estimate_parent(cur, actor, estimate_id)
                _assert_same_project(estimate, project, "Смета")
            if included_estimate_id:
                included_estimate = resolve_estimate_parent(cur, actor, included_estimate_id)
                _assert_same_project(included_estimate, project, "Смета включения")

            role = str(actor.get("role") or "").strip()
            section_name = str(
                payload.get("sectionName") or payload.get("workPackage") or "Основная"
            ).strip() or "Основная"
            if role in package_limit_roles and not has_package_access(actor, section_name):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ: " + section_name)

            price = float(payload.get("price", 0) or 0)
            total = float(payload.get("total", 0) or 0)
            status = payload.get("status", "Ожидает согласования")
            added_by = payload.get("addedBy", "") or actor.get("name", "")
            added_by_role = payload.get("addedByRole", "") or role
            if role in worker_execution_roles:
                price = 0
                total = 0
                status = "Ожидает согласования"
                added_by = actor.get("name", "")
                added_by_role = role

            cur.execute(
                """INSERT INTO unexpected_works
                       (project_name,project_id,company_id,description,unit,quantity,price,total,
                        added_by,added_by_role,status,notes,photo_url,change_type,estimate_id,
                        section_name,estimate_item_name,base_quantity,new_required_quantity,
                        delta_quantity,included_in_estimate_id,reason)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                (
                    canonical_project_name,
                    project_id,
                    company_id,
                    payload.get("description", ""),
                    payload.get("unit", "шт"),
                    float(payload.get("quantity", 0)),
                    price,
                    total,
                    added_by,
                    added_by_role,
                    status,
                    payload.get("notes", ""),
                    payload.get("photoUrl", ""),
                    payload.get("changeType") or "Работа вне сметы",
                    estimate_id,
                    section_name,
                    payload.get("estimateItemName", ""),
                    float(payload.get("baseQuantity") or 0),
                    float(payload.get("newRequiredQuantity") or 0),
                    float(payload.get("deltaQuantity") or 0),
                    included_estimate_id,
                    payload.get("reason", ""),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {"id": _row_id(row), "ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
