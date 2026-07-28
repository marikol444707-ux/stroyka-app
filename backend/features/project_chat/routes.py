"""Project chat routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 7):
GET /project-chat/{project_name} and POST /project-chat keep their
URLs, project access checks and payload fields. The access helper
require_project_access stays in main.py and arrives through deps.
"""

from fastapi import Depends


def register_project_chat_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_project_access = deps["require_project_access"]

    @app.get("/project-chat/{project_name}")
    def get_project_chat(project_name: str, current_user: dict = Depends(get_current_user)):
        require_project_access(current_user, project_name)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id,project_name,author_id,author_name,author_role,text,photo_url,created_at FROM project_chat WHERE project_name=%s ORDER BY created_at ASC LIMIT 200",(project_name,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectName":r[1],"authorId":r[2],"authorName":r[3],"authorRole":r[4],"text":r[5],"photoUrl":r[6],"createdAt":str(r[7])} for r in rows]

    @app.post("/project-chat")
    def create_project_chat(data: dict, current_user: dict = Depends(get_current_user)):
        project_name = data.get("projectName", "")
        require_project_access(current_user, project_name)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO project_chat (project_name,author_id,author_name,author_role,text,photo_url) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (project_name,current_user.get("id"),current_user.get("name",""),current_user.get("role",""),data.get("text",""),data.get("photoUrl","")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}
