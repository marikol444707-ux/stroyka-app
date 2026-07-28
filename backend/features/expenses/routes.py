"""Project expense routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 3):
GET /expenses and POST /expenses keep their URLs, finance role guard
and response fields.
"""

from fastapi import Depends


def register_expenses_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    finance_roles = tuple(deps.get("finance_roles") or ())

    @app.get("/expenses")
    def get_expenses(project: str = "", _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        if project:
            cur.execute("SELECT id,project,category,amount,note,date,added_by,own_expense_id,source,photo_url FROM expenses WHERE project=%s ORDER BY id DESC", (project,))
        else:
            cur.execute("SELECT id,project,category,amount,note,date,added_by,own_expense_id,source,photo_url FROM expenses ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"project":r[1],"category":r[2],"amount":float(r[3] or 0),"note":r[4] or "","date":str(r[5]) if r[5] else "","addedBy":r[6] or "","ownExpenseId":r[7],"source":r[8] or "","photoUrl":r[9] or ""} for r in rows]

    @app.post("/expenses")
    def create_expense(data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO expenses (project,category,amount,note,date,added_by,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (data.get("project",""),data.get("category","other"),data.get("amount",0),data.get("note",""),data.get("date") or None,data.get("addedBy",""),data.get("photoUrl") or data.get("photo_url") or ""))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
