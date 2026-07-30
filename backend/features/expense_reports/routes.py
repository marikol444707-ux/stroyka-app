"""Expense report routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 30):
the /expense-reports quartet keeps its URLs, finance role guard,
items JSON handling and idempotent soft-cancel.
"""

from fastapi import Depends, HTTPException


def register_expense_reports_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    finance_roles = tuple(deps.get("finance_roles") or ())
    require_project_access = deps["require_project_access"]

    @app.get("/expense-reports")
    def list_expense_reports(employee_id: int = None, project_name: str = None, current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cols = "id, employee_id, employee_name, project_name, report_type, purpose, total_amount, issued_amount, spent_amount, balance, items_json, photo_url, date_from, date_to, status, approved_by, approved_at, created_at"
        where, params = [], []
        if employee_id: where.append("employee_id=%s"); params.append(employee_id)
        if project_name: where.append("project_name=%s"); params.append(project_name)
        q = f"SELECT {cols} FROM expense_reports"
        if where: q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC"
        cur.execute(q, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        import json as j
        out = []
        for r in rows:
            try: items = j.loads(r[10]) if r[10] else []
            except: items = []
            out.append({"id":r[0],"employeeId":r[1],"employeeName":r[2] or "",
                 "projectName":r[3] or "","reportType":r[4] or "Авансовый отчёт",
                 "purpose":r[5] or "","totalAmount":float(r[6] or 0),"issuedAmount":float(r[7] or 0),
                 "spentAmount":float(r[8] or 0),"balance":float(r[9] or 0),"items":items,
                 "photoUrl":r[11] or "","dateFrom":str(r[12]) if r[12] else "",
                 "dateTo":str(r[13]) if r[13] else "","status":r[14] or "На утверждении",
                 "approvedBy":r[15] or "","approvedAt":str(r[16]) if r[16] else "",
                 "createdAt":str(r[17])})
        return out

    @app.post("/expense-reports")
    def create_expense_report(data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        import json as j
        conn = get_db()
        cur = conn.cursor()
        items = j.dumps(data.get("items") or [], ensure_ascii=False)
        cur.execute("""INSERT INTO expense_reports
                       (employee_id, employee_name, project_name, report_type, purpose,
                        total_amount, issued_amount, spent_amount, balance, items_json, photo_url,
                        date_from, date_to, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (data.get("employeeId"), data.get("employeeName",""), data.get("projectName",""),
                     data.get("reportType","Авансовый отчёт"), data.get("purpose",""),
                     float(data.get("totalAmount",0)), float(data.get("issuedAmount",0)),
                     float(data.get("spentAmount",0)), float(data.get("balance",0)),
                     items, data.get("photoUrl",""), data.get("dateFrom") or None,
                     data.get("dateTo") or None, data.get("status","На утверждении")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id": row[0], "ok": True}

    @app.put("/expense-reports/{id}")
    def update_expense_report(id: int, data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        fields_map = [('status','status'),('approvedBy','approved_by'),('approvedAt','approved_at'),
                      ('spentAmount','spent_amount'),('balance','balance'),('purpose','purpose')]
        sets, vals = [], []
        for js_key, db_col in fields_map:
            if js_key in data:
                sets.append(db_col + "=%s")
                v = data[js_key]
                if js_key == 'approvedAt' and not v: v = None
                vals.append(v)
        if not sets:
            cur.close(); conn.close(); return {"ok": True}
        vals.append(id)
        cur.execute("UPDATE expense_reports SET " + ", ".join(sets) + " WHERE id=%s", vals)
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}

    @app.delete("/expense-reports/{id}")
    def delete_expense_report(id: int, _current_user: dict = Depends(require_roles(*finance_roles))):
        from datetime import date
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT project_name, status, purpose FROM expense_reports WHERE id=%s FOR UPDATE", (id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Авансовый отчет не найден")
        project_name, status, purpose = row
        if project_name:
            require_project_access(_current_user, project_name)
        if (status or "") == "Аннулирован":
            conn.rollback()
            cur.close(); conn.close()
            return {"ok": True, "cancelled": True, "alreadyCancelled": True}
        actor_name = _current_user.get("name") or ""
        cancel_note = "Аннулировано без физического удаления " + date.today().isoformat()
        if actor_name:
            cancel_note += " (" + actor_name + ")"
        new_purpose = ((purpose or "") + "\n" + cancel_note).strip() if purpose else cancel_note
        cur.execute("""UPDATE expense_reports
                       SET status=%s, purpose=%s, approved_by=%s, approved_at=%s
                       WHERE id=%s""",
                    ("Аннулирован", new_purpose, actor_name, date.today(), id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "cancelled": True}
