"""Personal data consent routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 13):
GET /pd-consents, POST /pd-consents and DELETE /pd-consents/{user_id}
keep their URLs, role guards and self-signing rule. PdConsentModel
moved here — this was its only user.
"""

import psycopg2.extras
from fastapi import Depends, HTTPException, Request
from ..legacy_project_records.user_scope import selected_actors, user_visibility, require_user
from pydantic import BaseModel


class PdConsentModel(BaseModel):
    userId: int
    signedAt: str = ""
    scanUrl: str = ""
    uploadedBy: str = ""


def register_pd_consents_module(app, deps):
    scope = deps["record_scope"]
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    staff_manage_roles = tuple(deps.get("staff_manage_roles") or ())

    @app.get("/pd-consents")
    def get_pd_consents(request: Request = None, _current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actors = selected_actors(scope, cur, _current_user, request, staff_manage_roles)
            where, params = user_visibility(actors)
            cur.execute("SELECT id,user_id as \"userId\",signed_at as \"signedAt\",scan_url as \"scanUrl\",uploaded_by as \"uploadedBy\" FROM pd_consents WHERE user_id IN (SELECT u.id FROM users u WHERE " + where + ")", params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            cur.close(); conn.close()

    @app.post("/pd-consents")
    def create_pd_consent(p: PdConsentModel, request: Request = None, _current_user: dict = Depends(get_current_user)):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if int(p.userId) != int(_current_user.get('id') or 0):
                actors = selected_actors(scope, cur, _current_user, request, staff_manage_roles, write=True)
                require_user(cur, actors, p.userId)
            cur.execute("""
                INSERT INTO pd_consents (user_id,signed_at,scan_url,uploaded_by)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (user_id) DO UPDATE SET
                    signed_at=EXCLUDED.signed_at,scan_url=EXCLUDED.scan_url,uploaded_by=EXCLUDED.uploaded_by
                RETURNING id,user_id as "userId",signed_at as "signedAt",scan_url as "scanUrl",uploaded_by as "uploadedBy"
            """, (p.userId,p.signedAt,p.scanUrl,p.uploadedBy))
            row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.delete("/pd-consents/{user_id}")
    def delete_pd_consent(user_id: int, request: Request = None, _current_user: dict = Depends(get_current_user)):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actors = selected_actors(scope, cur, _current_user, request, staff_manage_roles, write=True)
            require_user(cur, actors, user_id)
            cur.execute('DELETE FROM pd_consents WHERE user_id=%s', (user_id,))
            conn.commit()
            return {'ok':True}
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()
