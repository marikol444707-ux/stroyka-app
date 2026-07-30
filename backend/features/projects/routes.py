"""Project card routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 36):
the /projects quartet keeps its URLs, company-scoped visibility,
budget/warranty hiding for workers, the archive/close prohibition
outside the director procedure and the disabled delete. The model
moved here — sole user; the project-access helper factory and the
public-fields SELECT fragment are injected.
"""

from typing import List, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel


class ProjectModel(BaseModel):
    name: str
    client: str = ""
    status: str = "Планирование"
    budget: float = 0
    deadline: str = ""
    progress: int = 0
    tasks: List[str] = []
    pricelistId: Optional[int] = None
    floors: int = 1
    liters: str = ""


def register_projects_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    leadership_roles = tuple(deps.get("leadership_roles") or ())
    project_card_write_roles = tuple(deps.get("project_card_write_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    project_public_select = deps["project_public_select"]
    project_access_helpers = deps["project_access_helpers"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    require_project_access = deps["require_project_access"]
    log_audit = deps["log_audit"]

    @app.get("/projects")
    def get_projects(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        project_visibility_filter, _, _ = project_access_helpers()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        company_context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        company_actors = effective_company_actors(current_user, company_context)
        visibility_sql, visibility_params = project_visibility_filter(
            company_actors,
            ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
        )
        cur.execute(
            f"""SELECT p.id,p.company_id as "companyId",p.name,p.client,p.status,p.budget,p.deadline,p.progress,p.tasks,
                       p.pricelist_id as "pricelistId",p.floors,p.liters,
                       p.warranty_start_date as "warrantyStartDate",p.warranty_end_date as "warrantyEndDate",
                       p.warranty_contact as "warrantyContact",COALESCE(p.archived,false) as archived,
                       p.archived_at as "archivedAt",{project_public_select}
                  FROM projects p
                 WHERE {visibility_sql}
                 ORDER BY p.id""",
            visibility_params,
        )
        rows = cur.fetchall()
        cur.close(); conn.close()
        actors_by_company = {
            int(actor.get("companyId") or actor.get("company_id")): actor
            for actor in company_actors
            if actor.get("companyId") or actor.get("company_id")
        }
        out = []
        for r in rows:
            d = dict(r)
            row_actor = actors_by_company.get(int(d.get("companyId") or 0), current_user)
            if row_actor.get("role") in worker_execution_roles:
                d["budget"] = 0
                d["pricelistId"] = None
                d["warrantyStartDate"] = ""
                d["warrantyEndDate"] = ""
                d["warrantyContact"] = ""
            out.append(d)
        return out

    @app.post("/projects")
    def create_project(
        p: ProjectModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        _, _, require_project_write_actor = project_access_helpers()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
            project_card_write_roles,
        )
        company_id = int(actor.get("companyId") or actor.get("company_id"))
        cur.execute(f"""INSERT INTO projects (company_id,name,client,status,budget,deadline,progress,tasks,pricelist_id,floors,liters)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                         RETURNING id,company_id as "companyId",name,client,status,budget,deadline,progress,tasks,
                                   pricelist_id as "pricelistId",floors,liters,COALESCE(archived,false) as archived,
                                   archived_at as "archivedAt",{project_public_select}""",
                    (company_id,p.name,p.client,p.status,p.budget,p.deadline,p.progress,p.tasks,p.pricelistId,p.floors,p.liters))
        row = cur.fetchone()
        conn.commit()
        cur.close(); conn.close()
        log_audit(user_name=actor.get("name",""), user_role=actor.get("role",""),
                  action="create", entity_type="project", entity_id=row["id"], description="Создан объект", project_name=row["name"])
        return dict(row)

    @app.put("/projects/{id}")
    def update_project(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        _, require_project_row_company, require_project_write_actor = project_access_helpers()
        archived_value = data.pop("archived", None) if "archived" in data else None
        archived_at_value = data.pop("archivedAt", None) if "archivedAt" in data else None
        archived_at_snake = data.pop("archived_at", None) if "archived_at" in data else None
        if archived_value not in (None, False, 0, "", "false", "False") or archived_at_value not in (None, False, "") or archived_at_snake not in (None, False, ""):
            raise HTTPException(status_code=403, detail="Архивация объекта отключена. Объект может закрыть только директор отдельной процедурой закрытия.")
        if str(data.get("status") or "").strip().lower() in ("завершён", "завершен", "архив", "закрыт", "закрытый"):
            raise HTTPException(status_code=403, detail="Закрытие или архив объекта отключены в обычном редактировании. Объект закрывается только отдельной процедурой директора.")
        fields_map = [
            ('name','name'),('client','client'),('status','status'),('budget','budget'),
            ('deadline','deadline'),('progress','progress'),('tasks','tasks'),
            ('pricelistId','pricelist_id'),('floors','floors'),('liters','liters'),
            ('warrantyStartDate','warranty_start_date'),
            ('warrantyEndDate','warranty_end_date'),
            ('warrantyContact','warranty_contact'),
        ]
        sets, vals = [], []
        for js_key, db_col in fields_map:
            if js_key in data:
                sets.append(db_col + "=%s")
                v = data[js_key]
                if db_col in ('warranty_start_date','warranty_end_date','deadline','archived_at') and not v:
                    v = None
                vals.append(v)
        if not sets:
            return {"ok": True}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT company_id,name FROM projects WHERE id=%s", (id,))
        project_row = cur.fetchone()
        if not project_row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Объект не найден")
        project_company_id = project_row.get("company_id")
        company_context = resolve_work_company_context(
            cur,
            current_user,
            project_company_id,
            "update",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        actor = require_project_write_actor(
            effective_company_actors(current_user, company_context),
            project_card_write_roles,
        )
        require_project_row_company(actor, project_company_id)
        require_project_access(actor, project_row.get("name") or "")
        vals.extend([id, project_company_id])
        cur.execute("UPDATE projects SET " + ", ".join(sets) + " WHERE id=%s AND company_id=%s", vals)
        cur.execute("SELECT id,company_id as \"companyId\",name,COALESCE(archived,false) as archived FROM projects WHERE id=%s AND company_id=%s", (id, project_company_id))
        row = cur.fetchone()
        conn.commit()
        cur.close(); conn.close()
        if row:
            action = "archive" if "archived" in data and data.get("archived") else ("restore" if "archived" in data else "update")
            log_audit(user_name=actor.get("name",""), user_role=actor.get("role",""),
                      action=action, entity_type="project", entity_id=id, description="Обновлён объект", project_name=row["name"])
        return {"ok": True}

    @app.delete("/projects/{id}")
    def delete_project(id: int, current_user: dict = Depends(require_roles(*leadership_roles))):
        raise HTTPException(status_code=405, detail="Удаление и архивирование объекта отключены. Объект может закрыть только директор отдельной процедурой закрытия.")
