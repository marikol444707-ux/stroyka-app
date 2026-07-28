"""Master profile routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 8):
GET /master-profiles, GET /master-profile/{user_id} and
POST /master-profile keep their URLs, role-based field hiding and
payloads. MasterProfileModel moved here — this was its only user.
"""

import psycopg2.extras
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class MasterProfileModel(BaseModel):
    userId: int
    fullName: str
    passport: str = ""
    inn: str = ""
    contractType: str = "ГПХ"
    bankAccount: str = ""
    bankName: str = ""
    phone: str = ""
    specialization: str = ""
    ogrnip: str = ""


def register_master_profiles_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    finance_roles = tuple(deps.get("finance_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    user_project_names = deps["user_project_names"]

    @app.get("/master-profiles")
    def get_master_profiles(current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        def _public_master_profile(row):
            data = dict(row)
            for key in ("passport", "inn", "bankAccount", "bankName", "ogrnip"):
                data.pop(key, None)
            return data
        if current_user.get("role") in finance_roles:
            cur.execute("SELECT id,user_id as \"userId\",full_name as \"fullName\",passport,inn,contract_type as \"contractType\",bank_account as \"bankAccount\",bank_name as \"bankName\",phone,specialization,ogrnip,profile_completed as \"profileCompleted\" FROM master_profiles")
        elif current_user.get("role") in ("прораб", "главный_инженер"):
            allowed_projects = user_project_names(current_user)
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute("""
                SELECT mp.id,mp.user_id as "userId",mp.full_name as "fullName",mp.passport,mp.inn,
                       mp.contract_type as "contractType",mp.bank_account as "bankAccount",
                       mp.bank_name as "bankName",mp.phone,mp.specialization,mp.ogrnip,
                       mp.profile_completed as "profileCompleted"
                FROM master_profiles mp
                JOIN users u ON u.id=mp.user_id
                WHERE COALESCE(u.project_name,'') = ANY(%s)
                   OR EXISTS (
                       SELECT 1 FROM jsonb_array_elements_text(COALESCE(u.assigned_projects,'[]'::jsonb)) ap(project_name)
                       WHERE ap.project_name = ANY(%s)
                   )
                ORDER BY mp.id DESC
            """, (allowed_projects, allowed_projects))
        elif current_user.get("role") in worker_execution_roles:
            cur.execute("SELECT id,user_id as \"userId\",full_name as \"fullName\",passport,inn,contract_type as \"contractType\",bank_account as \"bankAccount\",bank_name as \"bankName\",phone,specialization,ogrnip,profile_completed as \"profileCompleted\" FROM master_profiles WHERE user_id=%s", (current_user.get("id"),))
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        if current_user.get("role") in ("прораб", "главный_инженер"):
            return [_public_master_profile(r) for r in rows]
        return [dict(r) for r in rows]

    @app.get("/master-profile/{user_id}")
    def get_master_profile(user_id: int, current_user: dict = Depends(get_current_user)):
        if current_user.get("id") != user_id and current_user.get("role") not in finance_roles and current_user.get("role") not in ("прораб", "главный_инженер"):
            raise HTTPException(status_code=403, detail="Нет доступа к профилю")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if current_user.get("id") != user_id and current_user.get("role") in ("прораб", "главный_инженер"):
            allowed_projects = user_project_names(current_user)
            cur.execute("""
                SELECT 1 FROM users u
                WHERE u.id=%s AND (
                    COALESCE(u.project_name,'') = ANY(%s)
                    OR EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(COALESCE(u.assigned_projects,'[]'::jsonb)) ap(project_name)
                        WHERE ap.project_name = ANY(%s)
                    )
                )
            """, (user_id, allowed_projects, allowed_projects))
            if not cur.fetchone():
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к профилю исполнителя другого объекта")
        cur.execute("SELECT id,user_id as \"userId\",full_name as \"fullName\",passport,inn,contract_type as \"contractType\",bank_account as \"bankAccount\",bank_name as \"bankName\",phone,specialization,ogrnip,profile_completed as \"profileCompleted\" FROM master_profiles WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"userId": user_id, "fullName": "", "profileCompleted": False}
        if current_user.get("id") != user_id and current_user.get("role") in ("прораб", "главный_инженер"):
            data = dict(row)
            for key in ("passport", "inn", "bankAccount", "bankName", "ogrnip"):
                data.pop(key, None)
            return data
        return dict(row)

    @app.post("/master-profile")
    def create_master_profile(p: MasterProfileModel, current_user: dict = Depends(get_current_user)):
        if current_user.get("id") != p.userId and current_user.get("role") not in finance_roles:
            raise HTTPException(status_code=403, detail="Можно редактировать только свой профиль")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO master_profiles (user_id,full_name,passport,inn,contract_type,bank_account,bank_name,phone,specialization,ogrnip,profile_completed)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
            ON CONFLICT (user_id) DO UPDATE SET
                full_name=EXCLUDED.full_name,passport=EXCLUDED.passport,inn=EXCLUDED.inn,
                contract_type=EXCLUDED.contract_type,bank_account=EXCLUDED.bank_account,
                bank_name=EXCLUDED.bank_name,phone=EXCLUDED.phone,
                specialization=EXCLUDED.specialization,ogrnip=EXCLUDED.ogrnip,profile_completed=TRUE
            RETURNING id,user_id as "userId",full_name as "fullName",passport,inn,
                contract_type as "contractType",bank_account as "bankAccount",
                bank_name as "bankName",phone,specialization,ogrnip,profile_completed as "profileCompleted"
        """, (p.userId,p.fullName,p.passport,p.inn,p.contractType,p.bankAccount,p.bankName,p.phone,p.specialization,p.ogrnip))
        row = cur.fetchone()
        conn.close()
        return dict(row)
