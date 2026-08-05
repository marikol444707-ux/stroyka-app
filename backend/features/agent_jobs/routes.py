from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from ..director_daily_brief.query_service import (
    DirectorDailyBriefQueryError,
    get_latest_director_daily_brief,
)
from .cancellation_service import (
    AgentJobCancellationError,
    cancel_queued_agent_job,
    cancellation_reason_label,
)
from .query_service import AgentJobQueryError, get_agent_job, list_agent_jobs, public_agent_job


class AgentJobCancelPayload(BaseModel):
    reasonCode: str = "user_request"


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
    cancel_roles = {str(role or "").strip() for role in deps["cancel_roles"]}
    insert_audit_event = deps["insert_audit_event"]

    def selected_actor(
        cur,
        current_user,
        x_company_id,
        x_company_mode,
        *,
        action_mode,
        allowed_roles,
    ):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
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
            if str((actor or {}).get("role") or "").strip() in allowed_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Роль в выбранной компании не позволяет управлять очередью агента"
                    if action_mode != "read"
                    else "Роль в выбранной компании не позволяет смотреть очередь агента"
                ),
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
            actor = selected_actor(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
                action_mode="read",
                allowed_roles=read_roles,
            )
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

    @app.get("/agent-jobs/director-daily-brief/latest")
    def latest_director_daily_brief_route(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
                action_mode="read",
                allowed_roles=read_roles,
            )
            try:
                return get_latest_director_daily_brief(
                    cur,
                    company_id=actor["companyId"],
                )
            except DirectorDailyBriefQueryError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="Последняя сводка недоступна: требуется повторное формирование",
                ) from exc
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
            actor = selected_actor(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
                action_mode="read",
                allowed_roles=read_roles,
            )
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

    @app.post("/agent-jobs/{id}/cancel")
    def cancel_job_route(
        id: int,
        data: Optional[AgentJobCancelPayload] = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
                action_mode="update",
                allowed_roles=cancel_roles,
            )
            actor_user_id = _positive_int(actor.get("id") or current_user.get("id"))
            if not actor_user_id:
                raise HTTPException(status_code=409, detail="Автор отмены задачи не определён")
            reason_code = data.reasonCode if data is not None else "user_request"
            try:
                outcome = cancel_queued_agent_job(
                    cur,
                    company_id=actor["companyId"],
                    job_id=id,
                    reason_code=reason_code,
                )
            except AgentJobCancellationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            if outcome["state"] == "not_found":
                raise HTTPException(
                    status_code=404,
                    detail="Задача агента не найдена в выбранной компании",
                )
            if outcome["state"] == "conflict":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Можно отменить только ожидающую задачу агента; "
                        f"текущий статус: {outcome['currentStatus'] or 'unknown'}"
                    ),
                )

            job = outcome["job"]
            audit = insert_audit_event(
                cur,
                user_id=actor_user_id,
                user_name=actor.get("name") or current_user.get("name") or "",
                user_role=actor.get("role") or "",
                action="cancel",
                entity_type="agent_job",
                entity_id=job.get("id"),
                description=(
                    f"Отменена ожидающая задача агента {job.get('job_type') or ''}: "
                    f"{cancellation_reason_label(outcome['reasonCode'])}"
                ),
                owner_scope="company",
                company_id=actor["companyId"],
                project_id=job.get("project_id"),
            )
            owner = dict((audit or {}).get("owner") or {})
            if (
                not _positive_int((audit or {}).get("id"))
                or owner.get("scope") != "company"
                or _positive_int(owner.get("companyId")) != actor["companyId"]
                or _positive_int(owner.get("projectId"))
                != _positive_int(job.get("project_id"))
            ):
                raise RuntimeError("agent job cancellation audit owner mismatch")
            conn.commit()
            return {
                "cancelled": True,
                "reasonCode": outcome["reasonCode"],
                "job": public_agent_job(job),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
