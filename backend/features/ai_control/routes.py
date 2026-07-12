from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _row_value(row, key, index=0):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _project_name(data):
    payload = dict(data or {})
    return str(payload.get("projectName") or payload.get("project_name") or payload.get("project") or "").strip()


def register_ai_control_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    get_ai_control_runner = deps.get("get_ai_control_runner") or get_current_user
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    resolve_project_owner = deps["resolve_project_owner"]
    require_project_access = deps["require_project_access"]
    run_project_ai_control = deps["run_project_ai_control"]
    generate_roles = {str(role or "").strip() for role in deps["generate_roles"]}
    run_roles = {str(role or "").strip() for role in deps["run_roles"]}
    run_all_roles = {str(role or "").strip() for role in deps.get("run_all_roles", ())}
    system_actor_for_project = deps.get("system_actor_for_project") or (lambda project: {
        "id": None,
        "name": "ИИ-контроль",
        "role": "директор",
        "companyId": project["companyId"],
        "company_id": project["companyId"],
    })

    def assert_name_only_sources_are_unambiguous(cur, project):
        cur.execute(
            "SELECT COUNT(DISTINCT company_id) AS company_count,COUNT(*) AS project_count "
            "FROM projects WHERE BTRIM(name)=BTRIM(%s)",
            (project["name"],),
        )
        duplicate_row = cur.fetchone() or {}
        company_count = int(_row_value(duplicate_row, "company_count", 0) or 0)
        project_count = int(_row_value(duplicate_row, "project_count", 1) or 0)
        if company_count != 1 or project_count != 1:
            raise HTTPException(
                status_code=409,
                detail=(
                    "ИИ-контроль временно недоступен: объект с одинаковым названием есть в нескольких "
                    "компаниях. Сначала завершите перенос источников ИИ на project_id."
                ),
            )

    def selected_project(cur, current_user, project_name, allowed_roles, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "write",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для запуска ИИ-контроля выберите одну компанию")
        actors = [
            dict(item or {})
            for item in effective_company_actors(current_user, context)
            if str((item or {}).get("role") or "").strip() in allowed_roles
        ]
        if not actors:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет запускать ИИ-контроль")
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Компания запуска ИИ-контроля не определена")
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания запуска ИИ-контроля не определена")
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        project = resolve_project_owner(cur, project_name, company_id=company_id, for_update=True)
        require_project_access(actor, project["name"])

        # Several AI source tables are still name-only. Fail closed until their project IDs are migrated.
        assert_name_only_sources_are_unambiguous(cur, project)
        return actor, project

    def execute_single(data, current_user, allowed_roles, x_company_id, x_company_mode):
        payload = dict(data or {})
        project_name = _project_name(payload)
        if not project_name:
            raise HTTPException(status_code=400, detail="projectName required")
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, project = selected_project(
                cur, current_user, project_name, allowed_roles, x_company_id, x_company_mode,
            )
            result = run_project_ai_control(
                cur,
                project["name"],
                actor,
                payload.get("reason") or "manual",
                project_owner=project,
            )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-findings/generate")
    def generate_ai_findings(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        return execute_single(data, current_user, generate_roles, x_company_id, x_company_mode)

    @app.post("/ai-control/run")
    def run_ai_control(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        return execute_single(data, current_user, run_roles, x_company_id, x_company_mode)

    @app.post("/ai-control/run-all")
    def run_all_ai_control(
        data: dict = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_ai_control_runner),
    ):
        payload = dict(data or {})
        is_system = bool(current_user.get("aiControlSystem"))
        list_conn = get_db()
        list_cur = list_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if is_system:
                actor = None
                list_cur.execute(
                    "SELECT id,company_id,name FROM projects "
                    "WHERE COALESCE(archived,FALSE)=FALSE "
                    "AND COALESCE(status,'') NOT IN ('Завершён','Завершен','Архив') ORDER BY company_id,id"
                )
            else:
                context = resolve_work_company_context(
                    list_cur,
                    current_user,
                    None,
                    "write",
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                )
                if context.get("mode") == "all_companies":
                    raise HTTPException(status_code=409, detail="Для запуска ИИ-контроля выберите одну компанию")
                actors = [
                    dict(item or {})
                    for item in effective_company_actors(current_user, context)
                    if str((item or {}).get("role") or "").strip() in run_all_roles
                ]
                if not actors:
                    raise HTTPException(
                        status_code=403,
                        detail="Роль в выбранной компании не позволяет запускать ИИ-контроль по всем объектам",
                    )
                if len(actors) != 1:
                    raise HTTPException(status_code=409, detail="Для запуска ИИ-контроля выберите одну компанию")
                actor = actors[0]
                company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
                if not company_id:
                    raise HTTPException(status_code=409, detail="Компания запуска ИИ-контроля не определена")
                list_cur.execute(
                    "SELECT id,company_id,name FROM projects WHERE company_id=%s "
                    "AND COALESCE(archived,FALSE)=FALSE "
                    "AND COALESCE(status,'') NOT IN ('Завершён','Завершен','Архив') ORDER BY id",
                    (company_id,),
                )
            projects = [dict(row) for row in (list_cur.fetchall() or [])]
        finally:
            list_cur.close()
            list_conn.close()

        results = []
        for project_row in projects:
            conn = get_db()
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                project = resolve_project_owner(
                    cur,
                    project_row.get("name") or "",
                    company_id=project_row.get("company_id"),
                    project_id=project_row.get("id"),
                    for_update=True,
                )
                assert_name_only_sources_are_unambiguous(cur, project)
                project_actor = system_actor_for_project(project) if is_system else actor
                require_project_access(project_actor, project["name"])
                result = run_project_ai_control(
                    cur,
                    project["name"],
                    project_actor,
                    payload.get("reason") or "nightly",
                    project_owner=project,
                )
                conn.commit()
                results.append(result)
            except Exception as exc:
                conn.rollback()
                results.append({
                    "ok": False,
                    "projectName": project_row.get("name") or "",
                    "companyId": project_row.get("company_id"),
                    "projectId": project_row.get("id"),
                    "detail": str(getattr(exc, "detail", None) or exc),
                })
            finally:
                cur.close()
                conn.close()
        return {
            "ok": True,
            "projects": len(projects),
            "results": results,
            "created": sum(int(item.get("created") or 0) for item in results if item.get("ok")),
            "updated": sum(int(item.get("updated") or 0) for item in results if item.get("ok")),
            "tasksCreated": sum(int(item.get("tasksCreated") or 0) for item in results if item.get("ok")),
            "tasksUpdated": sum(int(item.get("tasksUpdated") or 0) for item in results if item.get("ok")),
            "closed": sum(int(item.get("closed") or 0) for item in results if item.get("ok")),
        }
