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
    projects = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
    legacy = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    if legacy:
        projects.add(legacy)
    return projects


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def register_ai_summary_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    project_document_roles = {str(role or "").strip() for role in deps["project_document_roles"]}
    full_view_roles = {str(role or "").strip() for role in deps["full_view_roles"]}

    def selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для сводки ИИ выберите одну конкретную компанию")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in project_document_roles
        ]
        if not actors:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет открыть сводку ИИ")
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Для сводки ИИ выберите одну конкретную компанию")
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания сводки ИИ не определена")
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def resolve_project(cur, actor, project_name, for_update=False):
        requested_name = str(project_name or "")
        if not requested_name.strip():
            raise HTTPException(status_code=400, detail="projectName required")
        lock_sql = " FOR UPDATE" if for_update else ""
        cur.execute(
            """SELECT id,company_id,name
                 FROM projects
                WHERE company_id=%s AND BTRIM(name)=BTRIM(%s)
                ORDER BY id""" + lock_sql,
            (actor["companyId"], requested_name),
        )
        rows = cur.fetchall() or []
        if not rows:
            raise HTTPException(status_code=404, detail="Объект не найден в выбранной компании")
        if len(rows) > 1:
            raise HTTPException(status_code=409, detail="В выбранной компании найдено несколько объектов с таким названием")
        row = rows[0]
        project = {
            "id": _positive_int(_row_value(row, "id", 0)),
            "companyId": _positive_int(_row_value(row, "company_id", 1)),
            "name": str(_row_value(row, "name", 2) or ""),
        }
        if not project["id"] or project["companyId"] != actor["companyId"] or not project["name"].strip():
            raise HTTPException(status_code=409, detail="Владелец объекта не определён")
        if str(actor.get("role") or "").strip() not in full_view_roles:
            if project["name"].strip() not in _assigned_projects(actor):
                raise HTTPException(status_code=403, detail="Нет доступа к объекту")
        return project

    @app.get("/project-ai-summary/{project_name}")
    def get_project_ai_summary(
        project_name: str,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
            project = resolve_project(cur, actor, project_name)
            cur.execute(
                """SELECT payload_hash,summary,updated_at
                     FROM project_ai_summary
                    WHERE company_id=%s AND project_id=%s""",
                (project["companyId"], project["id"]),
            )
            row = cur.fetchone()
            if not row:
                return {"exists": False}
            return {
                "exists": True,
                "payloadHash": _row_value(row, "payload_hash", 0),
                "summary": _row_value(row, "summary", 1) or "",
                "updatedAt": str(_row_value(row, "updated_at", 2)),
            }
        finally:
            cur.close()
            conn.close()

    @app.post("/project-ai-summary")
    def save_project_ai_summary(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        project_name = (data or {}).get("projectName", "")
        if not str(project_name or "").strip():
            raise HTTPException(status_code=400, detail="projectName required")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            project = resolve_project(cur, actor, project_name, for_update=True)
            cur.execute(
                """INSERT INTO project_ai_summary
                       (project_name,company_id,project_id,payload_hash,summary,updated_at)
                   VALUES (%s,%s,%s,%s,%s,NOW())
                   ON CONFLICT (company_id,project_id)
                       WHERE company_id IS NOT NULL AND project_id IS NOT NULL
                   DO UPDATE SET
                       project_name=EXCLUDED.project_name,
                       payload_hash=EXCLUDED.payload_hash,
                       summary=EXCLUDED.summary,
                       updated_at=NOW()""",
                (
                    project["name"],
                    project["companyId"],
                    project["id"],
                    (data or {}).get("payloadHash", ""),
                    (data or {}).get("summary", ""),
                ),
            )
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
