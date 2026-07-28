"""Personal data consent routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 13):
GET /pd-consents, POST /pd-consents and DELETE /pd-consents/{user_id}
keep their URLs, role guards and self-signing rule. PdConsentModel
moved here — this was its only user.
"""

import psycopg2.extras
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class PdConsentModel(BaseModel):
    userId: int
    signedAt: str = ""
    scanUrl: str = ""
    uploadedBy: str = ""


def register_pd_consents_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    staff_manage_roles = tuple(deps.get("staff_manage_roles") or ())

    @app.get("/pd-consents")
    def get_pd_consents(_current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id,user_id as \"userId\",signed_at as \"signedAt\",scan_url as \"scanUrl\",uploaded_by as \"uploadedBy\" FROM pd_consents")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/pd-consents")
    def create_pd_consent(p: PdConsentModel, _current_user: dict = Depends(get_current_user)):
        if _current_user.get("role") not in staff_manage_roles and int(p.userId) != int(_current_user.get("id") or 0):
            raise HTTPException(status_code=403, detail="Можно подписать только своё согласие")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO pd_consents (user_id,signed_at,scan_url,uploaded_by)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
                signed_at=EXCLUDED.signed_at,scan_url=EXCLUDED.scan_url,uploaded_by=EXCLUDED.uploaded_by
            RETURNING id,user_id as "userId",signed_at as "signedAt",scan_url as "scanUrl",uploaded_by as "uploadedBy"
        """, (p.userId,p.signedAt,p.scanUrl,p.uploadedBy))
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.delete("/pd-consents/{user_id}")
    def delete_pd_consent(user_id: int, _current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM pd_consents WHERE user_id=%s", (user_id,))
        conn.close()
        return {"ok": True}
