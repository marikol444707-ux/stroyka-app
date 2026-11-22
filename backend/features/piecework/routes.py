"""Selected-company access for piecework accruals."""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from ..record_company_scope import read_context, resolve_project_owner, row_value, selected_actor


class PieceworkModel(BaseModel):
    staffId: str
    description: str
    unit: str = "м2"
    quantity: float
    pricePerUnit: float
    total: float
    project: str = ""
    date: str = ""
    comment: str = ""
    photoUrl: str = ""
    workJournalId: Optional[int] = None


_LEADERSHIP = {"директор", "зам_директора", "главный_инженер", "бухгалтер"}
_COLUMNS = (
    'id,staff_id as "staffId",description,unit,quantity,price_per_unit as "pricePerUnit",'
    'total,project,date,comment,photo_url as "photoUrl",work_journal_id as "workJournalId",'
    'company_id as "companyId",project_id as "projectId"'
)
_ACTIVE = """NOT EXISTS (
        SELECT 1 FROM work_journal wj
        WHERE wj.id = piecework.work_journal_id
          AND COALESCE(wj.status,'') = 'Отклонено'
    ) AND NOT EXISTS (
        SELECT 1 FROM work_journal w JOIN brigade_contract_items i ON i.id=w.contract_item_id
        JOIN brigade_contracts c ON c.id=i.contract_id
        WHERE w.id=piecework.work_journal_id AND c.settlement_version=2
    )"""


def register_piecework_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    get_current_user = deps["get_current_user"]
    resolve = deps["resolve_work_company_context"]
    actors_for = deps["effective_company_actors"]
    scope_filter = deps["company_id_scope_filter"]
    all_company_data = deps["can_see_all_company_data"]
    user_projects = deps["user_project_names"]
    project_access = deps["require_project_access"]
    require_journal = deps["require_work_journal_actor_access"]
    lock_settlement = deps["lock_legacy_work_settlement"]
    require_legacy_work = deps["require_legacy_work"]
    journal_roles = tuple(deps.get("journal_write_roles") or ())
    worker_roles = tuple(deps.get("worker_execution_roles") or ())

    @app.get("/piecework")
    def get_piecework(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, actor, all_leadership = read_context(
                resolve, actors_for, cur, current_user, x_company_id, x_company_mode, _LEADERSHIP
            )
            if not actor and not all_leadership:
                return []
            actor = actor or current_user
            company_sql, company_params = scope_filter(context, "company_id")
            where = [_ACTIVE]
            params = []
            role = actor.get("role")
            if role in worker_roles and not all_leadership:
                where.append("""(staff_id=%s OR EXISTS (
                              SELECT 1 FROM work_journal wj
                              WHERE wj.id = piecework.work_journal_id
                                AND wj.company_id=piecework.company_id
                                AND (COALESCE(wj.master_id,0)=%s OR (COALESCE(wj.master_id,0)=0 AND LOWER(TRIM(COALESCE(wj.master_name,'')))=LOWER(TRIM(%s))))
                          ))""")
                params.extend([str(actor.get("id")), actor.get("id"), actor.get("name") or ""])
            elif not all_leadership and not all_company_data(actor):
                allowed = user_projects(actor)
                if not allowed:
                    where.append("staff_id=%s")
                    params.append(str(actor.get("id")))
                else:
                    where.append("(owner_scope='company' OR project = ANY(%s) OR staff_id=%s)")
                    params.extend([allowed, str(actor.get("id"))])
            params.extend(company_params)
            cur.execute(
                f"SELECT {_COLUMNS} FROM piecework WHERE " + " AND ".join(where) + company_sql + " ORDER BY id DESC",
                tuple(params),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post("/piecework")
    def create_piecework(
        p: PieceworkModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*journal_roles)),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "create", x_company_id, x_company_mode, journal_roles
            )
            if actor.get("role") in worker_roles:
                raise HTTPException(status_code=403, detail="Сдельное начисление создаётся только после проверки ЖПР прорабом/руководителем")
            project_access(actor, p.project)
            if not p.workJournalId:
                raise HTTPException(status_code=400, detail="Ручные сдельные начисления отключены. Закрывайте работу через ЖПР: подтверждённая запись сама формирует сумму исполнителя и акт бухгалтерии.")
            require_journal(cur, p.workJournalId, actor)
            lock_settlement(cur)
            require_legacy_work(cur, [p.workJournalId])
            cur.execute(
                "SELECT id FROM piecework WHERE work_journal_id=%s AND company_id=%s LIMIT 1",
                (p.workJournalId, company_id),
            )
            existing = cur.fetchone()
            if existing:
                conn.commit()
                conn.close()
                return dict(existing)
            cur.execute(
                """SELECT master_id, master_name, project, description, unit, quantity,
                          execution_price_per_unit, execution_total, date
                   FROM work_journal
                   WHERE id=%s AND company_id=%s AND COALESCE(status,'')='Подтверждено'""",
                (p.workJournalId, company_id),
            )
            work_row = cur.fetchone()
            if not work_row:
                raise HTTPException(status_code=400, detail="Сдельное начисление можно создать только по подтверждённой записи ЖПР")
            project = work_row.get("project") or p.project
            scope, project_id = resolve_project_owner(cur, project, company_id)
            cur.execute(
                "INSERT INTO piecework (staff_id,description,unit,quantity,price_per_unit,total,project,date,comment,photo_url,work_journal_id,owner_scope,company_id,project_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (str(work_row.get("master_id") or p.staffId or ""), work_row.get("description") or p.description,
                 work_row.get("unit") or p.unit, float(work_row.get("quantity") or 0),
                 float(work_row.get("execution_price_per_unit") or 0),
                 float(work_row.get("execution_total") or 0), project, str(work_row.get("date") or p.date or ""),
                 p.comment, p.photoUrl, p.workJournalId, scope, company_id, project_id),
            )
            row = cur.fetchone()
            conn.commit()
            conn.close()
            return dict(row)
        finally:
            if not conn.closed:
                conn.rollback()
                conn.close()

    @app.delete("/piecework/{id}")
    def delete_piecework(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles("директор")),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "delete", x_company_id, x_company_mode, ("директор",)
            )
            cur.execute(
                "SELECT work_journal_id, project FROM piecework WHERE id=%s AND company_id=%s FOR UPDATE",
                (id, company_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сдельное начисление не найдено в выбранной компании")
            if not all_company_data(actor):
                project_access(actor, row_value(row, "project", 1, "") or "")
            lock_settlement(cur)
            journal_id = row_value(row, "work_journal_id", 0)
            if journal_id:
                require_legacy_work(cur, [journal_id])
            cur.execute("DELETE FROM piecework WHERE id=%s AND company_id=%s", (id, company_id))
            conn.commit()
            conn.close()
            return {"ok": True}
        finally:
            if not conn.closed:
                conn.rollback()
                conn.close()
