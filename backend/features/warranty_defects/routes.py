from fastapi import Depends


def register_warranty_defects_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    project_document_roles = tuple(deps["project_document_roles"])
    project_document_write_roles = tuple(deps["project_document_write_roles"])
    leadership_roles = tuple(deps["leadership_roles"])
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]
    visible_project_names = deps["visible_project_names"]
    user_project_names = deps["user_project_names"]

    @app.get("/warranty-defects")
    def list_warranty_defects(
        project_name: str = None,
        current_user: dict = Depends(require_roles(*project_document_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        cols = (
            "id, project_name, description, found_at, reported_by, reporter_phone, "
            "status, assigned_to, fix_notes, fixed_at, photo_url, severity, created_at"
        )
        if project_name:
            require_project_access(current_user, project_name)
            cur.execute(
                f"SELECT {cols} FROM warranty_defects WHERE project_name=%s ORDER BY id DESC",
                (project_name,),
            )
        elif visible_project_names(current_user) is not None:
            projects = user_project_names(current_user)
            if not projects:
                cur.close()
                conn.close()
                return []
            cur.execute(
                f"SELECT {cols} FROM warranty_defects WHERE project_name = ANY(%s) ORDER BY id DESC",
                (projects,),
            )
        else:
            cur.execute(f"SELECT {cols} FROM warranty_defects ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": row[0],
                "projectName": row[1] or "",
                "description": row[2] or "",
                "foundAt": str(row[3]) if row[3] else "",
                "reportedBy": row[4] or "",
                "reporterPhone": row[5] or "",
                "status": row[6] or "Открыт",
                "assignedTo": row[7] or "",
                "fixNotes": row[8] or "",
                "fixedAt": str(row[9]) if row[9] else "",
                "photoUrl": row[10] or "",
                "severity": row[11] or "",
                "createdAt": str(row[12]),
            }
            for row in rows
        ]

    @app.post("/warranty-defects")
    def create_warranty_defect(
        data: dict,
        current_user: dict = Depends(require_roles(*project_document_roles)),
    ):
        require_project_access(current_user, data.get("projectName", ""))
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO warranty_defects
               (project_name, description, found_at, reported_by, reporter_phone,
                status, assigned_to, photo_url, severity)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                data.get("projectName", ""),
                data.get("description", ""),
                data.get("foundAt") or None,
                data.get("reportedBy", ""),
                data.get("reporterPhone", ""),
                data.get("status", "Открыт"),
                data.get("assignedTo", ""),
                data.get("photoUrl", ""),
                data.get("severity", ""),
            ),
        )
        conn.commit()
        row = cur.fetchone()
        cur.close()
        conn.close()
        return {"id": row[0], "ok": True}

    @app.put("/warranty-defects/{id}")
    def update_warranty_defect(
        id: int,
        data: dict,
        current_user: dict = Depends(require_roles(*project_document_write_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "warranty_defects", id, current_user, "project_name")
        fields_map = [
            ("status", "status"),
            ("assignedTo", "assigned_to"),
            ("fixNotes", "fix_notes"),
            ("fixedAt", "fixed_at"),
            ("severity", "severity"),
            ("photoUrl", "photo_url"),
        ]
        sets, vals = [], []
        for js_key, db_col in fields_map:
            if js_key in data:
                sets.append(db_col + "=%s")
                value = data[js_key]
                if js_key == "fixedAt" and not value:
                    value = None
                vals.append(value)
        if not sets:
            cur.close()
            conn.close()
            return {"ok": True}
        vals.append(id)
        cur.execute("UPDATE warranty_defects SET " + ", ".join(sets) + " WHERE id=%s", vals)
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.delete("/warranty-defects/{id}")
    def delete_warranty_defect(
        id: int,
        current_user: dict = Depends(
            require_roles(*leadership_roles, "прораб", "главный_инженер")
        ),
    ):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "warranty_defects", id, current_user, "project_name")
        cur.execute("DELETE FROM warranty_defects WHERE id=%s", (id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}
