"""Master profile routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 8):
GET /master-profiles, GET /master-profile/{user_id} and
POST /master-profile keep their URLs, role-based field hiding and
payloads. MasterProfileModel moved here — this was its only user.
"""

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from .access import authorized_profile_users, require_profile_user
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
    kpp: str = ""
    ogrn: str = ""
    legalAddress: str = ""
    bankBik: str = ""
    bankCorr: str = ""
    signatoryName: str = ""
    signatoryPosition: str = ""
    signatoryBasis: str = ""


PROFILE_COLUMNS = '''id,user_id as "userId",full_name as "fullName",passport,inn,
    contract_type as "contractType",bank_account as "bankAccount",bank_name as "bankName",
    phone,specialization,ogrnip,kpp,ogrn,legal_address as "legalAddress",bank_bik as "bankBik",
    bank_corr as "bankCorr",signatory_name as "signatoryName",
    signatory_position as "signatoryPosition",signatory_basis as "signatoryBasis",
    profile_completed as "profileCompleted"'''

SENSITIVE_PROFILE_FIELDS = ("passport", "inn", "bankAccount", "bankName", "ogrnip", "kpp", "ogrn",
    "legalAddress", "bankBik", "bankCorr", "signatoryName", "signatoryPosition", "signatoryBasis")


def register_master_profiles_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    finance_roles = tuple(deps.get("finance_roles") or ())

    @app.get("/master-profiles")
    def get_master_profiles(current_user: dict = Depends(get_current_user),
                            x_company_id: str = Header(default=None, alias="X-Company-Id"),
                            x_company_mode: str = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                allowed = authorized_profile_users(cur, current_user, deps, manager_roles=finance_roles,
                    project_roles=("прораб", "главный_инженер"), company_id=x_company_id, company_mode=x_company_mode)
                cur.execute("SELECT " + PROFILE_COLUMNS + " FROM master_profiles WHERE user_id=ANY(%s)", (list(allowed),))
                rows = [dict(row) for row in cur.fetchall()]
            for row in rows:
                if not allowed.get(row['userId']):
                    for key in SENSITIVE_PROFILE_FIELDS:
                        row.pop(key, None)
            return rows
        finally:
            conn.close()

    @app.get("/master-profile/{user_id}")
    def get_master_profile(user_id: int, current_user: dict = Depends(get_current_user),
                           x_company_id: str = Header(default=None, alias="X-Company-Id"),
                           x_company_mode: str = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                allowed = authorized_profile_users(cur, current_user, deps, manager_roles=finance_roles,
                    project_roles=("прораб", "главный_инженер"), company_id=x_company_id, company_mode=x_company_mode)
                require_profile_user(allowed, user_id)
                cur.execute("SELECT " + PROFILE_COLUMNS + " FROM master_profiles WHERE user_id=%s", (user_id,))
                row = cur.fetchone()
            if not row:
                return {"userId": user_id, "fullName": "", "profileCompleted": False}
            data = dict(row)
            if not allowed.get(user_id):
                for key in SENSITIVE_PROFILE_FIELDS:
                    data.pop(key, None)
            return data
        finally:
            conn.close()

    @app.post("/master-profile")
    def create_master_profile(p: MasterProfileModel, current_user: dict = Depends(get_current_user),
                              x_company_id: str = Header(default=None, alias="X-Company-Id"),
                              x_company_mode: str = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            allowed = authorized_profile_users(cur, current_user, deps, manager_roles=finance_roles,
                company_id=x_company_id, company_mode=x_company_mode, write=True)
            require_profile_user(allowed, p.userId)
            cur.execute("""
                INSERT INTO master_profiles (user_id,full_name,passport,inn,contract_type,bank_account,bank_name,
                    phone,specialization,ogrnip,kpp,ogrn,legal_address,bank_bik,bank_corr,signatory_name,
                    signatory_position,signatory_basis,profile_completed)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                ON CONFLICT (user_id) DO UPDATE SET
                    full_name=EXCLUDED.full_name,passport=EXCLUDED.passport,inn=EXCLUDED.inn,
                    contract_type=EXCLUDED.contract_type,bank_account=EXCLUDED.bank_account,
                    bank_name=EXCLUDED.bank_name,phone=EXCLUDED.phone,
                    specialization=EXCLUDED.specialization,ogrnip=EXCLUDED.ogrnip,kpp=EXCLUDED.kpp,
                    ogrn=EXCLUDED.ogrn,legal_address=EXCLUDED.legal_address,bank_bik=EXCLUDED.bank_bik,
                    bank_corr=EXCLUDED.bank_corr,signatory_name=EXCLUDED.signatory_name,
                    signatory_position=EXCLUDED.signatory_position,signatory_basis=EXCLUDED.signatory_basis,
                    profile_completed=TRUE
                RETURNING id,user_id as "userId",full_name as "fullName",passport,inn,
                    contract_type as "contractType",bank_account as "bankAccount",
                    bank_name as "bankName",phone,specialization,ogrnip,kpp,ogrn,legal_address as "legalAddress",
                    bank_bik as "bankBik",bank_corr as "bankCorr",signatory_name as "signatoryName",
                    signatory_position as "signatoryPosition",signatory_basis as "signatoryBasis",
                    profile_completed as "profileCompleted"
            """, (p.userId,p.fullName,p.passport,p.inn,p.contractType,p.bankAccount,p.bankName,p.phone,
                    p.specialization,p.ogrnip,p.kpp,p.ogrn,p.legalAddress,p.bankBik,p.bankCorr,
                    p.signatoryName,p.signatoryPosition,p.signatoryBasis))
            row = cur.fetchone()
            return dict(row)
        finally:
            conn.close()
