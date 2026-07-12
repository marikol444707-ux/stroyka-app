import json
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from .service import resolve_project_owner, validate_linked_entity_owner


class AiFindingPayload(BaseModel):
    projectName: str = ""
    findingType: str = "manual"
    category: str = "Общее"
    severity: str = "Проверить"
    title: str = ""
    description: str = ""
    source: str = "manual"
    linkedEntityType: str = ""
    linkedEntityId: str = ""
    suggestedAction: str = ""
    assignedRole: str = ""
    assignedTo: str = ""
    status: str = "Новое"
    dedupeKey: str = ""


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _values(value):
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item or "").strip()}
    if isinstance(value, str):
        try:
            return _values(json.loads(value))
        except Exception:
            return set()
    return set()


def _assigned_projects(actor):
    result = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
    legacy = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    if legacy:
        result.add(legacy)
    return result


def _payload(data):
    if isinstance(data, dict):
        return dict(data)
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if hasattr(data, "dict"):
        return data.dict()
    return {}


def register_ai_findings_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    read_roles = {str(role or "").strip() for role in deps["read_roles"]}
    write_roles = {str(role or "").strip() for role in deps["write_roles"]}
    update_roles = {str(role or "").strip() for role in deps.get("update_roles", deps["write_roles"])}
    full_view_roles = {str(role or "").strip() for role in deps["full_view_roles"]}
    finding_select = deps["finding_select"]
    upsert_finding = deps["upsert_finding"]

    def selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur, current_user, None, action_mode,
            x_company_id=x_company_id, x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для находок ИИ выберите одну конкретную компанию")
        allowed_roles = read_roles if action_mode == "read" else (update_roles if action_mode == "update" else write_roles)
        actors = [
            dict(actor or {}) for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in allowed_roles
        ]
        if not actors:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет работать с находками ИИ")
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Для находок ИИ выберите одну конкретную компанию")
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания находки ИИ не определена")
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def require_project_access(cur, actor, project):
        if str(actor.get("role") or "").strip() in full_view_roles:
            return project
        assigned = _assigned_projects(actor)
        if project["name"].strip() not in assigned:
            raise HTTPException(status_code=403, detail="Нет доступа к объекту")
        cur.execute(
            "SELECT id FROM projects WHERE company_id=%s AND BTRIM(name)=BTRIM(%s) ORDER BY id",
            (actor["companyId"], project["name"]),
        )
        ids = [_positive_int((row.get("id") if isinstance(row, dict) else row[0])) for row in (cur.fetchall() or [])]
        if ids != [project["id"]]:
            raise HTTPException(status_code=409, detail="Назначение по названию объекта неоднозначно")
        actor["assignedProjects"] = sorted(assigned | {project["name"].strip(), project["name"]})
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
            name = str((row.get("name") if isinstance(row, dict) else row[2]) or "").strip()
            by_name.setdefault(name, []).append(_positive_int(row.get("id") if isinstance(row, dict) else row[0]))
        if any(len(ids) != 1 for ids in by_name.values()) or any(name not in by_name for name in assigned):
            raise HTTPException(status_code=409, detail="Назначение по названию объекта неоднозначно")
        return [by_name[name][0] for name in assigned]

    @app.get("/ai-findings")
    def list_ai_findings(
        project_name: str = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
            params = [actor["companyId"]]
            where = " WHERE company_id=%s"
            if project_name:
                project = resolve_project_owner(cur, project_name, company_id=actor["companyId"])
                require_project_access(cur, actor, project)
                where += " AND project_id=%s"
                params.append(project["id"])
            elif str(actor.get("role") or "").strip() not in full_view_roles:
                project_ids = assigned_project_ids(cur, actor)
                if not project_ids:
                    return []
                where += " AND project_id = ANY(%s)"
                params.append(project_ids)
            cur.execute(finding_select + where + " ORDER BY updated_at DESC, id DESC", tuple(params))
            return [dict(row) for row in (cur.fetchall() or [])]
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-findings")
    def create_ai_finding(
        data: AiFindingPayload,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = _payload(data)
        if not str(payload.get("projectName") or "").strip():
            raise HTTPException(status_code=400, detail="projectName required")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            project = resolve_project_owner(cur, payload["projectName"], company_id=actor["companyId"], for_update=True)
            require_project_access(cur, actor, project)
            validate_linked_entity_owner(cur, project, payload.get("linkedEntityType"), payload.get("linkedEntityId"))
            finding_id = upsert_finding(cur, payload, actor, project)
            cur.execute(finding_select + " WHERE id=%s AND company_id=%s AND project_id=%s", (finding_id, project["companyId"], project["id"]))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Находка ИИ не сохранилась в выбранном объекте")
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/ai-findings/{id}")
    def update_ai_finding(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        patch = _payload(data)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "update", x_company_id, x_company_mode)
            cur.execute(
                "SELECT id,company_id,project_id,project_name,linked_entity_type,linked_entity_id "
                "FROM ai_findings WHERE id=%s AND company_id=%s",
                (id, actor["companyId"]),
            )
            finding = cur.fetchone()
            if not finding:
                raise HTTPException(status_code=404, detail="Находка ИИ не найдена")
            project = resolve_project_owner(
                cur, finding.get("project_name") or "", company_id=actor["companyId"],
                project_id=finding.get("project_id"), for_update=True,
            )
            require_project_access(cur, actor, project)
            cur.execute(
                "SELECT id,company_id,project_id,project_name,linked_entity_type,linked_entity_id "
                "FROM ai_findings WHERE id=%s AND company_id=%s AND project_id=%s FOR UPDATE",
                (id, project["companyId"], project["id"]),
            )
            finding = cur.fetchone()
            if not finding:
                raise HTTPException(status_code=404, detail="Находка ИИ не найдена")
            linked_type = patch.get("linkedEntityType", finding.get("linked_entity_type") or "")
            linked_id = patch.get("linkedEntityId", finding.get("linked_entity_id") or "")
            validate_linked_entity_owner(cur, project, linked_type, linked_id)
            editable = {
                "findingType": "finding_type", "category": "category", "severity": "severity",
                "title": "title", "description": "description", "source": "source",
                "linkedEntityType": "linked_entity_type", "linkedEntityId": "linked_entity_id",
                "suggestedAction": "suggested_action", "assignedRole": "assigned_role",
                "assignedTo": "assigned_to", "status": "status", "dedupeKey": "dedupe_key",
            }
            sets, values = [], []
            for key, column in editable.items():
                if key in patch:
                    sets.append(column + "=%s")
                    values.append(patch[key])
            if sets:
                values.extend([id, project["companyId"], project["id"]])
                cur.execute(
                    "UPDATE ai_findings SET " + ", ".join(sets) + ", updated_at=NOW() "
                    "WHERE id=%s AND company_id=%s AND project_id=%s",
                    tuple(values),
                )
                if patch.get("status") in ("Закрыто", "Отклонено"):
                    cur.execute(
                        "UPDATE ai_tasks SET status=%s,closed_by=%s,closed_at=NOW(),updated_at=NOW() "
                        "WHERE finding_id=%s AND status NOT IN ('Закрыто','Отклонено')",
                        (patch["status"], actor.get("name") or "", id),
                    )
            cur.execute(finding_select + " WHERE id=%s AND company_id=%s AND project_id=%s", (id, project["companyId"], project["id"]))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Находка ИИ не найдена")
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
