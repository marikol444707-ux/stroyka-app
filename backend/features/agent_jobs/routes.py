from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from .query_service import AgentJobQueryError, get_agent_job, list_agent_jobs


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def register_agent_jobs_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    read_roles = {str(role or "").strip() for role in deps["read_roles"]}

    def selected_actor(cur, current_user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(
                status_code=409,
                detail="Для очереди агента выберите одну конкретную компанию",
            )
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in read_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет смотреть очередь агента",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для очереди агента выберите одну конкретную компанию",
            )
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания очереди агента не определена")
        actor["companyId"] = company_id
        return actor

    @app.get("/agent-jobs")
    def list_jobs_route(
        status: str = "",
        project_id: Optional[int] = None,
        before_id: Optional[int] = None,
        limit: int = 25,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, x_company_id, x_company_mode)
            try:
                return list_agent_jobs(
                    cur,
                    company_id=actor["companyId"],
                    status=status,
                    project_id=project_id,
                    before_id=before_id,
                    limit=limit,
                )
            except AgentJobQueryError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            cur.close()
            conn.close()

    @app.get("/agent-jobs/{id}")
    def get_job_route(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, x_company_id, x_company_mode)
            try:
                job = get_agent_job(cur, company_id=actor["companyId"], job_id=id)
            except AgentJobQueryError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if job is None:
                raise HTTPException(
                    status_code=404,
                    detail="Задача агента не найдена в выбранной компании",
                )
            return job
        finally:
            cur.close()
            conn.close()
