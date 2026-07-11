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
    journal_write_roles = tuple(deps["journal_write_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = set(deps["package_limit_roles"])
    worker_execution_roles = set(deps["worker_execution_roles"])

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
