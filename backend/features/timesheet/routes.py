"""Company-scoped timesheet routes.

GET /timesheet/{staff_id}, POST /timesheet and GET /timesheet keep their
URLs. Days are visible only through a verified staff row in the selected
company scope. all_companies reads stay inside the caller's companies, and
a change requires one concrete company.
"""

from collections.abc import Mapping
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

try:
    from backend.features.company_context.service import company_id_scope_filter
except ModuleNotFoundError:
    from features.company_context.service import company_id_scope_filter


class TimesheetModel(BaseModel):
    staffId: int
    day: str


def register_timesheet_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    log_audit = deps["log_audit"]
    view_roles = {
        str(role).strip()
        for role in (deps.get("staff_view_roles") or ())
        if str(role or "").strip()
    }
    toggle_roles = {
        str(role).strip()
        for role in (deps.get("staff_manage_roles") or ())
        if str(role or "").strip()
    }
    toggle_roles.update({"прораб", "главный_инженер"})

    def _positive_int(value):
        return value if type(value) is int and value > 0 else None

    def _row_value(row, key, index):
        if isinstance(row, Mapping):
            return row.get(key)
        if isinstance(row, (list, tuple)) and len(row) > index:
            return row[index]
        return None

    def _allowed_company_ids(actors, allowed_roles):
        return {
            company_id
            for actor in actors or []
            for company_id in [
                _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
            ]
            if company_id and str((actor or {}).get("role") or "").strip() in allowed_roles
        }

    def read_scope(cur, user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        actors = effective_company_actors(user, context)
        allowed = _allowed_company_ids(actors, view_roles)
        mode = (context or {}).get("mode")
        if mode == "company":
            company_id = _positive_int(
                (context or {}).get("companyId") or (context or {}).get("company_id")
            )
            if not company_id or company_id not in allowed:
                raise HTTPException(
                    status_code=403,
                    detail="Роль в выбранной компании не позволяет смотреть табель",
                )
            return {**context, "companyIds": [company_id]}
        if mode == "all_companies":
            context_ids = {
                company_id
                for value in (context or {}).get("companyIds") or []
                for company_id in [_positive_int(value)]
                if company_id
            }
            visible = sorted(allowed & context_ids)
            if not visible:
                raise HTTPException(
                    status_code=403,
                    detail="Роль в выбранных компаниях не позволяет смотреть табель",
                )
            return {**context, "companyIds": visible}
        raise HTTPException(status_code=403, detail="Контекст компаний для табеля не определён")

    def write_actor(cur, user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            user,
            None,
            "write",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if (context or {}).get("mode") != "company":
            raise HTTPException(
                status_code=409,
                detail="Для изменения табеля выберите одну конкретную компанию",
            )
        company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания табеля не определена")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(user, context)
            if _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
            == company_id
            and str((actor or {}).get("role") or "").strip() in toggle_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет менять табель",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для изменения табеля выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def verified_staff(cur, company_id, staff_id):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="Некорректный id сотрудника")
        cur.execute(
            """SELECT id, name, COALESCE(project, '') AS project
                 FROM public.staff
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE
                FOR SHARE""",
            (staff_id, company_id),
        )
        row = cur.fetchone()
        resolved_id = _positive_int(_row_value(row, "id", 0))
        if resolved_id is None:
            raise HTTPException(
                status_code=404,
                detail="Сотрудник не найден в выбранной компании",
            )
        return {
            "id": resolved_id,
            "name": str(_row_value(row, "name", 1) or ""),
            "project": str(_row_value(row, "project", 2) or ""),
        }

    def staff_in_scope(cur, staff_id, scope_sql, scope_params):
        cur.execute(
            """SELECT s.id
                 FROM public.staff s
                WHERE s.id=%s
                  AND s.company_scope_verified IS TRUE"""
            + scope_sql,
            (staff_id, *scope_params),
        )
        return _positive_int(_row_value(cur.fetchone(), "id", 0)) is not None

    @app.get("/timesheet/{staff_id}")
    def get_timesheet(
        staff_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if _positive_int(staff_id) is None:
                raise HTTPException(status_code=400, detail="Некорректный id сотрудника")
            context = read_scope(cur, current_user, x_company_id, x_company_mode)
            scope_sql, scope_params = company_id_scope_filter(context, "s.company_id")
            cur.execute(
                """SELECT t.day
                     FROM public.timesheet t
                     JOIN public.staff s ON s.id = t.staff_id
                    WHERE t.staff_id=%s
                      AND s.company_scope_verified IS TRUE"""
                + scope_sql
                + " ORDER BY t.day",
                (staff_id, *scope_params),
            )
            rows = list(cur.fetchall() or [])
            if not rows and not staff_in_scope(cur, staff_id, scope_sql, scope_params):
                raise HTTPException(
                    status_code=404,
                    detail="Сотрудник не найден в выбранной компании",
                )
            return {"days": [_row_value(row, "day", 0) for row in rows]}
        finally:
            cur.close()
            conn.close()

    @app.post("/timesheet")
    def toggle_timesheet(
        data: TimesheetModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = write_actor(cur, current_user, x_company_id, x_company_mode)
            staff = verified_staff(cur, actor["companyId"], data.staffId)
            cur.execute(
                """SELECT t.id
                     FROM public.timesheet t
                     JOIN public.staff s ON s.id = t.staff_id
                    WHERE t.staff_id=%s AND t.day=%s
                      AND s.company_id=%s
                      AND s.company_scope_verified IS TRUE
                    FOR UPDATE OF t""",
                (staff["id"], data.day, actor["companyId"]),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """DELETE FROM public.timesheet t
                        USING public.staff s
                        WHERE t.staff_id = s.id
                          AND t.staff_id=%s AND t.day=%s
                          AND s.company_id=%s
                          AND s.company_scope_verified IS TRUE""",
                    (staff["id"], data.day, actor["companyId"]),
                )
                if cur.rowcount < 1:
                    raise HTTPException(status_code=409, detail="Табель сотрудника изменился")
                action = "timesheet_remove"
            else:
                cur.execute(
                    """INSERT INTO public.timesheet (staff_id, day)
                       SELECT s.id, %s
                         FROM public.staff s
                        WHERE s.id=%s AND s.company_id=%s
                          AND s.company_scope_verified IS TRUE""",
                    (data.day, staff["id"], actor["companyId"]),
                )
                if cur.rowcount != 1:
                    raise HTTPException(status_code=409, detail="Табель сотрудника изменился")
                action = "timesheet_add"
            conn.commit()
            log_audit(
                str(actor.get("name") or current_user.get("name") or ""),
                str(actor.get("role") or ""),
                action,
                "timesheet",
                staff["id"],
                ("Табель: " + (staff["name"] or str(staff["id"])) + ", день " + str(data.day))[:250],
                staff["project"] or "",
                company_id=actor["companyId"],
                owner_scope="company",
            )
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/timesheet")
    def get_timesheet_all(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context = read_scope(cur, current_user, x_company_id, x_company_mode)
            scope_sql, scope_params = company_id_scope_filter(context, "s.company_id")
            cur.execute(
                """SELECT t.staff_id, t.day
                     FROM public.timesheet t
                     JOIN public.staff s ON s.id = t.staff_id
                    WHERE s.company_scope_verified IS TRUE"""
                + scope_sql
                + " ORDER BY t.staff_id, t.day",
                tuple(scope_params),
            )
            return [
                {
                    "staffId": _row_value(row, "staff_id", 0),
                    "day": _row_value(row, "day", 1),
                }
                for row in (cur.fetchall() or [])
            ]
        finally:
            cur.close()
            conn.close()
