"""Accountable payment and expense routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 6):
GET/POST /accountable-payments and GET/POST /accountable-expenses
keep their URLs, finance role guard and payload fields. The only
change: an unreachable duplicate return after `return {"ok":True}`
in create_accountable_expense was dropped (it referenced an
undefined name and could never execute).
"""

from fastapi import Depends


def register_accountable_payments_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    finance_roles = tuple(deps.get("finance_roles") or ())

    @app.get("/accountable-payments")
    def get_accountable_payments(project_name: str = "", _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        if project_name:
            cur.execute("SELECT id,project_name,given_to,amount,payment_method,purpose,date,added_by,status,spent_amount FROM accountable_payments WHERE project_name=%s ORDER BY id DESC", (project_name,))
        else:
            cur.execute("SELECT id,project_name,given_to,amount,payment_method,purpose,date,added_by,status,spent_amount FROM accountable_payments ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectName":r[1],"givenTo":r[2],"amount":float(r[3] or 0),"paymentMethod":r[4] or "Наличные","purpose":r[5] or "","date":str(r[6]) if r[6] else "","addedBy":r[7] or "","status":r[8] or "Открыт","spentAmount":float(r[9] or 0)} for r in rows]

    @app.post("/accountable-payments")
    def create_accountable_payment(data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO accountable_payments (project_name,given_to,given_to_id,amount,payment_method,purpose,date,added_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("projectName",""),data.get("givenTo",""),data.get("givenToId"),data.get("amount",0),data.get("paymentMethod","Наличные"),data.get("purpose",""),data.get("date") or None,data.get("addedBy","")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.get("/accountable-expenses")
    def get_accountable_expenses(payment_id: int = 0, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        if payment_id:
            cur.execute("SELECT id,payment_id,project_name,description,amount,photo_url,date,added_by FROM accountable_expenses WHERE payment_id=%s ORDER BY id DESC", (payment_id,))
        else:
            cur.execute("SELECT id,payment_id,project_name,description,amount,photo_url,date,added_by FROM accountable_expenses ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"paymentId":r[1],"projectName":r[2],"description":r[3],"amount":float(r[4] or 0),"photoUrl":r[5] or "","date":str(r[6]) if r[6] else "","addedBy":r[7] or ""} for r in rows]

    @app.post("/accountable-expenses")
    def create_accountable_expense(data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO accountable_expenses (payment_id,project_name,description,amount,photo_url,date,added_by) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("paymentId"),data.get("projectName",""),data.get("description",""),data.get("amount",0),data.get("photoUrl",""),data.get("date") or None,data.get("addedBy","")))
        # Обновляем spent_amount
        cur.execute("UPDATE accountable_payments SET spent_amount=spent_amount+%s WHERE id=%s", (data.get("amount",0),data.get("paymentId")))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
