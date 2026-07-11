import json
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _actor_for_company(company_actors, company_id):
    normalized_company_id = _positive_int(company_id)
    for actor in company_actors or []:
        actor_company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        if actor_company_id == normalized_company_id:
            return actor
    raise HTTPException(status_code=404, detail="Смета не найдена")


def _load_sections(value):
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def register_estimate_versions_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    estimate_visibility_filter = deps["estimate_visibility_filter"]
    resolve_estimate_parent = deps["resolve_estimate_parent"]
    project_document_roles = set(deps["project_document_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = tuple(deps["package_limit_roles"])
    active_only_roles = tuple(deps["active_only_roles"])
    customer_roles = tuple(deps["customer_roles"])
    package_optional_roles = tuple(deps["package_optional_roles"])
    worker_execution_roles = set(deps["worker_execution_roles"])
    worker_allowed_items_for_scopes = deps["worker_allowed_items_for_scopes"]
    sanitize_worker_sections = deps["sanitize_worker_sections"]
    sanitize_worker_total = deps["sanitize_worker_total"]

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
            normalized_role = str((actor or {}).get("role") or "").strip()
            if normalized_role not in project_document_roles:
                continue
            normalized_actor = dict(actor or {})
            normalized_actor["role"] = normalized_role
            company_actors.append(normalized_actor)
        visibility_sql, visibility_params = estimate_visibility_filter(
            company_actors,
            full_view_roles,
            package_limit_roles,
            active_only_roles,
            customer_roles,
            package_optional_roles,
            column_prefix="e",
        )
        return company_actors, visibility_sql, visibility_params

    def verify_parent(cur, company_actors, row):
        actor = _actor_for_company(company_actors, (row or {}).get("company_id"))
        estimate_id = _positive_int((row or {}).get("estimate_id") or (row or {}).get("id"))
        resolve_estimate_parent(
            cur,
            actor,
            estimate_id,
            allow_template=True,
            allow_unbound=True,
        )
        if actor.get("role") == "бухгалтер":
            raise HTTPException(
                status_code=403,
                detail="Бухгалтер видит закрывающие документы и акты, но не версии клиентской сметы",
            )
        return actor

    @app.get("/estimates/{id}/versions")
    def get_estimate_versions(
        id: int,
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
                f"""SELECT e.id,e.company_id,e.project_id,e.project_name,
                            COALESCE(NULLIF(e.work_package,''),'Основная') AS work_package,
                            COALESCE(e.is_template,FALSE) AS is_template
                       FROM estimates e
                      WHERE e.id=%s AND {visibility_sql}""",
                (id, *visibility_params),
            )
            estimate_row = cur.fetchone()
            if not estimate_row:
                raise HTTPException(status_code=404, detail="Смета не найдена")
            actor = verify_parent(cur, company_actors, estimate_row)
            cur.execute(
                """SELECT id,version_label,total,comment,created_by,created_at
                     FROM estimate_versions
                    WHERE estimate_id=%s
                    ORDER BY id DESC""",
                (id,),
            )
            return [
                {
                    "id": row.get("id"),
                    "versionLabel": row.get("version_label") or "",
                    "total": sanitize_worker_total(actor, row.get("total")),
                    "comment": row.get("comment") or "",
                    "createdBy": row.get("created_by") or "",
                    "createdAt": str(row.get("created_at") or ""),
                }
                for row in cur.fetchall()
            ]
        finally:
            cur.close()
            conn.close()

    @app.get("/estimate-version/{version_id}")
    def get_estimate_version_detail(
        version_id: int,
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
                f"""SELECT ev.id,ev.estimate_id,ev.version_label,ev.sections_json,ev.total,
                            ev.comment,ev.created_by,ev.created_at,e.project_name,
                            COALESCE(NULLIF(e.work_package,''),'Основная') AS work_package,
                            COALESCE(e.status,'') AS estimate_status,e.company_id
                       FROM estimate_versions ev
                       JOIN estimates e ON e.id=ev.estimate_id
                      WHERE ev.id=%s AND {visibility_sql}""",
                (version_id, *visibility_params),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="version not found")
            actor = verify_parent(cur, company_actors, row)
            sections = _load_sections(row.get("sections_json"))
            if actor.get("role") in worker_execution_roles:
                project_name = row.get("project_name") or ""
                work_package = row.get("work_package") or "Основная"
                allowed_by_scope = worker_allowed_items_for_scopes(
                    cur,
                    actor,
                    [(project_name, work_package)],
                )
                sections = sanitize_worker_sections(
                    sections,
                    allowed_by_scope.get((project_name, work_package)) or [],
                    estimate_id=row.get("estimate_id"),
                )
            return {
                "id": row.get("id"),
                "estimateId": row.get("estimate_id"),
                "versionLabel": row.get("version_label") or "",
                "sections": sections,
                "total": sanitize_worker_total(actor, row.get("total")),
                "comment": row.get("comment") or "",
                "createdBy": row.get("created_by") or "",
                "createdAt": str(row.get("created_at") or ""),
            }
        finally:
            cur.close()
            conn.close()
