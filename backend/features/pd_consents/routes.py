"""Personal data consent routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 13):
GET /pd-consents, POST /pd-consents and DELETE /pd-consents/{user_id}
keep their URLs, role guards and self-signing rule. PdConsentModel
moved here — this was its only user.
"""

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel


class PdConsentModel(BaseModel):
    userId: int
    signedAt: str = ""
    scanUrl: str = ""
    uploadedBy: str = ""


from backend.features.master_profiles.access import authorized_profile_users, require_profile_user

def register_pd_consents_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    staff_manage_roles = tuple(deps.get("staff_manage_roles") or ())
    columns = 'id,user_id as "userId",signed_at as "signedAt",scan_url as "scanUrl",uploaded_by as "uploadedBy"'

    @app.get("/pd-consents")
    def get_pd_consents(_current_user: dict = Depends(get_current_user),
                        x_company_id: str = Header(default=None, alias="X-Company-Id"),
                        x_company_mode: str = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                allowed = authorized_profile_users(cur, _current_user, deps, manager_roles=staff_manage_roles,
                    company_id=x_company_id, company_mode=x_company_mode)
                cur.execute("SELECT " + columns + " FROM pd_consents WHERE user_id=ANY(%s)", (list(allowed),))
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @app.post("/pd-consents")
    def create_pd_consent(p: PdConsentModel, _current_user: dict = Depends(get_current_user),
                          x_company_id: str = Header(default=None, alias="X-Company-Id"),
                          x_company_mode: str = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                allowed = authorized_profile_users(cur, _current_user, deps, manager_roles=staff_manage_roles,
                    company_id=x_company_id, company_mode=x_company_mode, write=True)
                require_profile_user(allowed, p.userId)
                cur.execute("""
                    INSERT INTO pd_consents (user_id,signed_at,scan_url,uploaded_by)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        signed_at=EXCLUDED.signed_at,scan_url=EXCLUDED.scan_url,uploaded_by=EXCLUDED.uploaded_by
                    RETURNING """ + columns, (p.userId,p.signedAt,p.scanUrl,p.uploadedBy))
                return dict(cur.fetchone())
        finally:
            conn.close()

    @app.delete("/pd-consents/{user_id}")
    def delete_pd_consent(user_id: int, _current_user: dict = Depends(get_current_user),
                          x_company_id: str = Header(default=None, alias="X-Company-Id"),
                          x_company_mode: str = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                allowed = authorized_profile_users(cur, _current_user, deps, manager_roles=staff_manage_roles,
                    company_id=x_company_id, company_mode=x_company_mode, write=True, allow_self=False)
                require_profile_user(allowed, user_id)
                cur.execute("DELETE FROM pd_consents WHERE user_id=%s", (user_id,))
            return {"ok": True}
        finally:
            conn.close()
