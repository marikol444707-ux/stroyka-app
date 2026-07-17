import psycopg2.extras
from fastapi import Depends

from .models import TimesheetModel


def register_timesheet_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    staff_view_roles = tuple(deps["staff_view_roles"])
    staff_manage_roles = tuple(deps["staff_manage_roles"])
    log_audit = deps["log_audit"]

    @app.get("/timesheet/{staff_id}")
    def get_timesheet(
        staff_id: int,
        _current_user: dict = Depends(require_roles(*staff_view_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT day FROM timesheet WHERE staff_id=%s", (staff_id,))
        rows = cur.fetchall()
        conn.close()
        return {"days": [row["day"] for row in rows]}

    @app.post("/timesheet")
    def toggle_timesheet(
        data: TimesheetModel,
        _current_user: dict = Depends(
            require_roles(*staff_manage_roles, "прораб", "главный_инженер")
        ),
    ):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM timesheet WHERE staff_id=%s AND day=%s",
            (data.staffId, data.day),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "DELETE FROM timesheet WHERE staff_id=%s AND day=%s",
                (data.staffId, data.day),
            )
            action = "timesheet_remove"
        else:
            cur.execute(
                "INSERT INTO timesheet (staff_id,day) VALUES (%s,%s)",
                (data.staffId, data.day),
            )
            action = "timesheet_add"
        cur.execute(
            "SELECT name, COALESCE(project,'') FROM staff WHERE id=%s",
            (data.staffId,),
        )
        staff_row = cur.fetchone()
        conn.commit()
        log_audit(
            _current_user.get("name", ""),
            _current_user.get("role", ""),
            action,
            "timesheet",
            data.staffId,
            (
                "Табель: "
                + str(staff_row[0] if staff_row else data.staffId)
                + ", день "
                + str(data.day)
            )[:250],
            (staff_row[1] if staff_row else "") or "",
        )
        conn.close()
        return {"ok": True}

    @app.get("/timesheet")
    def get_timesheet_all(
        _current_user: dict = Depends(require_roles(*staff_view_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT staff_id, day FROM timesheet")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"staffId": row[0], "day": row[1]} for row in rows]
