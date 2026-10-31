"""Master profile routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 8):
GET /master-profiles, GET /master-profile/{user_id} and
POST /master-profile keep their URLs, role-based field hiding and
payloads. MasterProfileModel moved here — this was its only user.
"""

import psycopg2.extras
from fastapi import Depends, HTTPException, Request
from ..legacy_project_records.user_scope import selected_actors, user_visibility, require_user
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
    get_db, authenticated, scope = deps['get_db'], deps['get_current_user'], deps['record_scope']
    finance_roles = tuple(deps['finance_roles'])
    public_roles = ('прораб','главный_инженер')
    read_roles = (*finance_roles,*public_roles,*deps['worker_execution_roles'])
    def names(actor):
        return deps['user_project_names'](actor) if actor.get('role') in public_roles else None
    def public(row):
        return {key:value for key,value in dict(row).items() if key not in SENSITIVE_PROFILE_FIELDS}

    @app.get('/master-profiles')
    def get_master_profiles(request: Request = None, current_user: dict = Depends(authenticated)):
        conn=get_db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actors=selected_actors(scope,cur,current_user,request,read_roles)
            if not actors: return []
            manager_actors=[actor for actor in actors if actor.get('role') in (*finance_roles,*public_roles)]
            where,params=user_visibility(manager_actors,project_names=names)
            cur.execute('SELECT '+PROFILE_COLUMNS+' FROM master_profiles WHERE user_id=%s OR user_id IN (SELECT u.id FROM users u WHERE '+where+')', [current_user.get('id'),*params])
            rows=cur.fetchall()
            result=[]
            for row in rows:
                if row['userId']==current_user.get('id'):
                    result.append(dict(row)); continue
                finance=[actor for actor in manager_actors if actor.get('role') in finance_roles]
                where,params=user_visibility(finance)
                cur.execute('SELECT u.id FROM users u WHERE u.id=%s AND ('+where+')',[row['userId'],*params])
                result.append(dict(row) if cur.fetchone() else public(row))
            return result
        finally:
            cur.close(); conn.close()

    @app.get('/master-profile/{user_id}')
    def get_master_profile(user_id: int, request: Request = None, current_user: dict = Depends(authenticated)):
        conn=get_db();cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            sensitive = user_id==current_user.get('id')
            if not sensitive:
                actors=selected_actors(scope,cur,current_user,request,(*finance_roles,*public_roles))
                if not actors: raise HTTPException(403,"Нет доступа к профилю")
                require_user(cur,actors,user_id,project_names=names)
                where,params=user_visibility([actor for actor in actors if actor.get('role') in finance_roles])
                cur.execute('SELECT u.id FROM users u WHERE u.id=%s AND ('+where+')',[user_id,*params])
                sensitive=bool(cur.fetchone())
            cur.execute('SELECT '+PROFILE_COLUMNS+' FROM master_profiles WHERE user_id=%s',(user_id,))
            row=cur.fetchone()
            if not row: return {'userId':user_id,'fullName':'','profileCompleted':False}
            return dict(row) if sensitive else public(row)
        finally:
            cur.close();conn.close()

    @app.post('/master-profile')
    def create_master_profile(p: MasterProfileModel, request: Request = None, current_user: dict = Depends(authenticated)):
        conn=get_db();conn.autocommit=False
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if current_user.get('id')!=p.userId:
                actors=selected_actors(scope,cur,current_user,request,finance_roles,write=True)
                require_user(cur,actors,p.userId)
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
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback();raise
        finally:
            cur.close();conn.close()
