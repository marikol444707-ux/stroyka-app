import json
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from .service import resolve_task_owner, task_owner_filter

try:
    from backend.features.ai_findings.service import resolve_project_owner
except ModuleNotFoundError:
    from features.ai_findings.service import resolve_project_owner


class AiTaskPayload(BaseModel):
    findingId: Optional[int] = None
    projectName: str = ""
    title: str = ""
    description: str = ""
    assignedRole: str = ""
    assignedTo: str = ""
    status: str = "Новое"
    dueDate: str = ""
    actionLabel: str = ""
    actionPayload: str = ""
    dedupeKey: str = ""


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _payload(data):
    if isinstance(data, dict):
        return dict(data)
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if hasattr(data, "dict"):
        return data.dict()
    return {}


def _json_values(value):
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item or "").strip()}
    if isinstance(value, str):
        try:
            return _json_values(json.loads(value))
        except Exception:
            return set()
    return set()


def _assigned_projects(actor):
    projects = _json_values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
    legacy = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    if legacy:
        projects.add(legacy)
    return projects


def _identity_values(actor):
    return [
        str(value).strip().lower()
        for value in (actor.get("name"), actor.get("email"), actor.get("id"))
        if str(value or "").strip()
    ]


def register_ai_tasks_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    read_roles = {str(role or "").strip() for role in deps["read_roles"]}
    write_roles = {str(role or "").strip() for role in deps["write_roles"]}
    update_roles = {str(role or "").strip() for role in deps.get("update_roles", deps["write_roles"])}
    full_view_roles = {str(role or "").strip() for role in deps["full_view_roles"]}
    platform_task_roles = {str(role or "").strip() for role in deps["platform_task_roles"]}
    task_select = deps["task_select"]
    insert_task = deps["insert_task"]
    close_duplicates = deps["close_duplicates"]
    dedupe_key = deps["dedupe_key"]
    system_project_name = deps["system_project_name"]

    def selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur, current_user, None, action_mode,
            x_company_id=x_company_id, x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для поручений выберите одну конкретную компанию")
        allowed_roles = read_roles if action_mode == "read" else (update_roles if action_mode == "update" else write_roles)
        actors = [
            dict(actor or {}) for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in allowed_roles
        ]
        if not actors:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет работать с поручениями")
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Для поручений выберите одну конкретную компанию")
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания поручения не определена")
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def require_actor_project(cur, actor, project_name, *, project_id=None, for_update=False):
        project = resolve_project_owner(
            cur, project_name, company_id=actor["companyId"], project_id=project_id, for_update=for_update,
        )
        if str(actor.get("role") or "").strip() not in full_view_roles:
            if project["name"].strip() not in _assigned_projects(actor):
                raise HTTPException(status_code=403, detail="Нет доступа к объекту")
        return project

    def assigned_project_ids(cur, actor):
        assigned = sorted(_assigned_projects(actor))
        if not assigned:
            return []
        cur.execute(
            "SELECT id,company_id,name FROM projects WHERE company_id=%s AND BTRIM(name)=ANY(%s) ORDER BY id",
            (actor["companyId"], assigned),
        )
        rows = cur.fetchall() or []
        by_name = {}
        for row in rows:
            name = str(row.get("name") or "").strip()
            by_name.setdefault(name, []).append(_positive_int(row.get("id")))
        if any(name not in by_name or len(by_name[name]) != 1 for name in assigned):
            raise HTTPException(status_code=409, detail="Назначение по названию объекта неоднозначно")
        return [by_name[name][0] for name in assigned]

    def append_assignment_scope(where, params, actor):
        identities = _identity_values(actor) or ["__no_identity__"]
        where.append(
            "(LOWER(COALESCE(assigned_to,''))=ANY(%s) "
            "OR (COALESCE(assigned_to,'')='' AND assigned_role=%s) "
            "OR LOWER(COALESCE(created_by,''))=ANY(%s))"
        )
        params.extend([identities, actor.get("role") or "", identities])

    def can_access_task(actor, task):
        if str(actor.get("role") or "").strip() in (full_view_roles | platform_task_roles):
            return True
        identities = set(_identity_values(actor))
        assigned_to = str(task.get("assigned_to") or "").strip().lower()
        assigned_role = str(task.get("assigned_role") or "").strip()
        created_by = str(task.get("created_by") or "").strip().lower()
        return bool(
            (assigned_to and assigned_to in identities)
            or (not assigned_to and assigned_role and assigned_role == str(actor.get("role") or "").strip())
            or (created_by and created_by in identities)
        )

    def task_owner_for_actor(cur, actor, task, *, for_update=False):
        if task.get("owner_scope") == "platform":
            if str(actor.get("role") or "").strip() not in platform_task_roles:
                raise HTTPException(status_code=404, detail="Поручение не найдено")
            return {"scope": "platform", "companyId": None, "projectId": None, "projectName": system_project_name}
        company_id = _positive_int(task.get("company_id"))
        project_id = _positive_int(task.get("project_id"))
        if company_id != actor["companyId"] or not project_id:
            raise HTTPException(status_code=404, detail="Поручение не найдено")
        project = require_actor_project(
            cur, actor, task.get("project_name") or "", project_id=project_id, for_update=for_update,
        )
        if not can_access_task(actor, task):
            raise HTTPException(status_code=403, detail="Поручение назначено другой роли или исполнителю")
        return {"scope": "company", "companyId": company_id, "projectId": project["id"], "projectName": project["name"]}

    @app.get("/ai-tasks")
    def list_ai_tasks(
        project_name: str = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            where, params = [], []
            if project_name == system_project_name:
                if str(current_user.get("role") or "").strip() not in platform_task_roles:
                    raise HTTPException(status_code=403, detail="Нет доступа к системным поручениям")
                where.append("owner_scope='platform' AND company_id IS NULL AND project_id IS NULL")
            else:
                actor = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
                role = str(actor.get("role") or "").strip()
            if project_name and project_name != system_project_name:
                project = require_actor_project(cur, actor, project_name)
                where.append("owner_scope='company' AND company_id=%s AND project_id=%s")
                params.extend([actor["companyId"], project["id"]])
                if role not in full_view_roles:
                    append_assignment_scope(where, params, actor)
            elif not project_name:
                company_where = "(owner_scope='company' AND company_id=%s"
                params.append(actor["companyId"])
                if role not in full_view_roles:
                    project_ids = assigned_project_ids(cur, actor)
                    if not project_ids:
                        return []
                    company_where += " AND project_id=ANY(%s)"
                    params.append(project_ids)
                company_where += ")"
                where.append(company_where)
                if role not in full_view_roles:
                    append_assignment_scope(where, params, actor)
            cur.execute(task_select + " WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC, id DESC", tuple(params))
            return [dict(row) for row in (cur.fetchall() or [])]
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-tasks")
    def create_ai_task(
        data: AiTaskPayload,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = _payload(data)
        project_name = str(payload.get("projectName") or "")
        if not project_name.strip():
            raise HTTPException(status_code=400, detail="projectName required")
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if project_name == system_project_name:
                if str(current_user.get("role") or "").strip() not in platform_task_roles:
                    raise HTTPException(status_code=403, detail="Нет доступа к системным поручениям")
                actor = dict(current_user)
                owner = resolve_task_owner(cur, payload, system_project_name=system_project_name)
            else:
                actor = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
                if payload.get("findingId"):
                    owner = resolve_task_owner(cur, payload, system_project_name=system_project_name)
                    if owner.get("companyId") != actor["companyId"]:
                        raise HTTPException(status_code=404, detail="Находка ИИ не найдена")
                    project = require_actor_project(cur, actor, owner["projectName"], project_id=owner["projectId"], for_update=True)
                else:
                    project = require_actor_project(cur, actor, project_name, for_update=True)
                    owner = resolve_task_owner(cur, payload, system_project_name=system_project_name, project_owner=project)
                payload["projectName"] = owner["projectName"]
            owner_sql, owner_params = task_owner_filter(owner)
            key = dedupe_key(payload)
            if key:
                payload["dedupeKey"] = key
                cur.execute(
                    task_select + " WHERE project_name=%s AND dedupe_key=%s "
                    "AND status NOT IN ('Закрыто','Отклонено') AND " + owner_sql +
                    " ORDER BY updated_at DESC, id DESC LIMIT 1",
                    (payload["projectName"], key, *owner_params),
                )
                existing = cur.fetchone()
                if existing:
                    close_duplicates(cur, payload["projectName"], key, existing["id"], actor.get("name") or "system", owner)
                    conn.commit()
                    return dict(existing)
            task_id = insert_task(cur, payload, actor, owner)
            cur.execute(task_select + " WHERE id=%s AND " + owner_sql, (task_id, *owner_params))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Поручение не сохранилось в выбранном контуре")
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/ai-tasks/{id}")
    def update_ai_task(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        patch = _payload(data)
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if str(current_user.get("role") or "").strip() in platform_task_roles:
                actor = dict(current_user)
                cur.execute(
                    "SELECT id,owner_scope,company_id,project_id,project_name,assigned_role,assigned_to,created_by "
                    "FROM ai_tasks WHERE id=%s AND owner_scope='platform' AND company_id IS NULL AND project_id IS NULL",
                    (id,),
                )
            else:
                actor = selected_actor(cur, current_user, "update", x_company_id, x_company_mode)
                cur.execute(
                    "SELECT id,owner_scope,company_id,project_id,project_name,assigned_role,assigned_to,created_by "
                    "FROM ai_tasks WHERE id=%s AND owner_scope='company' AND company_id=%s",
                    (id, actor["companyId"]),
                )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Поручение не найдено")
            owner = task_owner_for_actor(cur, actor, task, for_update=True)
            owner_sql, owner_params = task_owner_filter(owner)
            editable = {
                "title": "title", "description": "description", "assignedRole": "assigned_role",
                "assignedTo": "assigned_to", "status": "status", "dueDate": "due_date",
                "actionLabel": "action_label", "actionPayload": "action_payload",
            }
            sets, values = [], []
            for key, column in editable.items():
                if key in patch:
                    sets.append(column + ("=NULLIF(%s,'')::date" if key == "dueDate" else "=%s"))
                    values.append(patch[key] or "")
            if patch.get("status") in ("Принято к исполнению", "В работе"):
                sets.extend(["accepted_by=%s", "accepted_at=COALESCE(accepted_at,NOW())"])
                values.append(actor.get("name") or "")
            if patch.get("status") in ("Закрыто", "Отклонено", "Исправлено"):
                sets.extend(["closed_by=%s", "closed_at=NOW()"])
                values.append(actor.get("name") or "")
            if sets:
                cur.execute(
                    "UPDATE ai_tasks SET " + ", ".join(sets) + ", updated_at=NOW() WHERE " + owner_sql + " AND id=%s",
                    (*values, *owner_params, id),
                )
            cur.execute(task_select + " WHERE " + owner_sql + " AND id=%s", (*owner_params, id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Поручение не найдено")
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
