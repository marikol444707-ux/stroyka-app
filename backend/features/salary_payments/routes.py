"""Salary payment routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 11):
GET/POST /salary-payments and DELETE /salary-payments/{id} keep their
URLs, finance role guard and payload fields.
"""

from fastapi import Depends


def register_salary_payments_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    finance_roles = tuple(deps.get("finance_roles") or ())

    @app.get("/salary-payments")
    def get_salary_payments(_current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id,staff_id,staff_name,month,amount,paid_by,paid_date,note,created_at FROM salary_payments ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"staffId":r[1],"staffName":r[2] or "","month":r[3] or "","amount":float(r[4] or 0),"paidBy":r[5] or "","paidDate":r[6] or "","note":r[7] or "","createdAt":str(r[8])} for r in rows]

    @app.post("/salary-payments")
    def create_salary_payment(data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO salary_payments (staff_id,staff_name,month,amount,paid_by,paid_date,note) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("staffId"), data.get("staffName",""), data.get("month",""), data.get("amount") or 0, data.get("paidBy",""), data.get("paidDate") or "", data.get("note","")))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": new_id}

    @app.delete("/salary-payments/{id}")
    def delete_salary_payment(id: int, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM salary_payments WHERE id=%s",(id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
