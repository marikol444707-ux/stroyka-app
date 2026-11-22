"""Project chat is limited to the selected company's project."""
from typing import Optional

from fastapi import Depends, Header, HTTPException


def register_project_chat_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_project_access = deps["require_project_access"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    resolve_project_parent = deps["resolve_project_parent"]

    def owner(cur, user, project_name, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur, user, None, "read",
            x_company_id=x_company_id, x_company_mode=x_company_mode,
        )
        actors = [actor for actor in effective_company_actors(user, context) or [] if actor]
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Для чата объекта выберите одну компанию")
        actor = actors[0]
        require_project_access(actor, project_name)
        project = resolve_project_parent(cur, actor, project_name=project_name)
        return actor, project

    @app.get("/project-chat/{project_name}")
    def get_project_chat(
        project_name: str,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            _actor, project = owner(cur, current_user, project_name, x_company_id, x_company_mode)
            cur.execute(
                "SELECT id,project_name,author_id,author_name,author_role,text,photo_url,created_at "
                "FROM project_chat WHERE project_name=%s AND company_id=%s "
                "ORDER BY created_at ASC LIMIT 200",
                (project["name"], project["companyId"]),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        return [{"id": r[0], "projectName": r[1], "authorId": r[2], "authorName": r[3],
                 "authorRole": r[4], "text": r[5], "photoUrl": r[6], "createdAt": str(r[7])} for r in rows]

    @app.post("/project-chat")
    def create_project_chat(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        project_name = data.get("projectName", "")
        conn = get_db()
        cur = conn.cursor()
        try:
            _actor, project = owner(cur, current_user, project_name, x_company_id, x_company_mode)
            cur.execute(
                "INSERT INTO project_chat (project_name,company_id,author_id,author_name,author_role,text,photo_url) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (project["name"], project["companyId"], current_user.get("id"), current_user.get("name", ""),
                 current_user.get("role", ""), data.get("text", ""), data.get("photoUrl", "")),
            )
            conn.commit()
            row = cur.fetchone()
        finally:
            cur.close()
            conn.close()
        return {"id": row[0], "ok": True, "companyId": project["companyId"]}
