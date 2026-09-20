"""Company-scoped replacement for legacy global /users administration."""
import json
from typing import Optional
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .access import ADMIN_ROLES, COMPANY_ROLES, transaction, target, assignments, require_role, save_membership, string_list, audit

class UserModel(BaseModel):
    name:str
    email:str
    password:str=''
    role:str='прораб'
    projectId:str=''
    projectName:str=''
    assignedProjects:list[str]=Field(default_factory=list)
    assignedPackages:list[str]=Field(default_factory=list)
    active:Optional[bool]=None


def register_company_users(app,deps):
    authenticated=deps['authenticated'];hash_password=deps['hash_password'];requires_2fa=deps['requires_2fa']
    revoke=deps['revoke_sessions']

    @app.get('/users')
    def listing(user:dict=Depends(authenticated),request:Request=None):
        with transaction(deps,user,request) as (cur,actor,company):
            where='';params=[company,company,list(COMPANY_ROLES)]
            if actor['role'] not in (*ADMIN_ROLES,'бухгалтер'):
                where=' AND u.id=%s';params.append(actor['id'])
            cur.execute('''SELECT u.id,u.name,u.email,u.company_id,u.project_id,u.project_name,
                COALESCE(m.role,u.role) AS role,
                CASE WHEN m.id IS NULL THEN u.assigned_projects ELSE m.assigned_projects END AS assigned_projects,
                CASE WHEN m.id IS NULL THEN u.assigned_packages ELSE m.assigned_packages END AS assigned_packages,
                COALESCE(u.active,TRUE) AND COALESCE(m.active,TRUE) AS active,
                u.two_factor_required,u.two_factor_enabled,u.two_factor_confirmed_at
                FROM users u LEFT JOIN LATERAL (SELECT * FROM user_company_roles
                WHERE user_id=u.id AND company_id=%s ORDER BY active DESC,id DESC LIMIT 1) m ON TRUE
                WHERE (m.id IS NOT NULL OR (u.company_id=%s AND NOT EXISTS
                    (SELECT 1 FROM user_company_roles any_membership WHERE any_membership.user_id=u.id))) AND u.role=ANY(%s)'''+where+' ORDER BY u.id',params)
            result=[]
            for row in cur.fetchall():
                names=string_list(row['assigned_projects'])
                result.append({'id':row['id'],'companyId':company,'name':row['name'],'email':row['email'],
                    'role':row['role'],'active':row['active'],'assignedProjects':names,
                    'assignedPackages':string_list(row['assigned_packages']),
                    'projectId':row['project_id'] if row['company_id']==company else None,
                    'projectName':row['project_name'] if row['company_id']==company else (names[0] if len(names)==1 else ''),
                    'twoFactorRequired':bool(row['two_factor_required']) or requires_2fa(row['role']),
                    'twoFactorEnabled':bool(row['two_factor_enabled']),
                    'twoFactorConfirmedAt':str(row['two_factor_confirmed_at'] or '')})
            return result

    @app.post('/users')
    def create(data:UserModel,user:dict=Depends(authenticated),request:Request=None):
        values=data.model_dump();name=data.name.strip();email=data.email.strip().lower();password=data.password.strip()
        if not name or not email or len(password)<5:raise HTTPException(400,'Укажите имя, email и пароль не короче 5 символов')
        with transaction(deps,user,request,True) as (cur,actor,company):
            require_role(actor,data.role)
            project_id,project_name,names,packages=assignments(cur,company,values)
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('user-email:'+email,))
            cur.execute('SELECT id FROM users WHERE LOWER(email)=%s',(email,))
            if cur.fetchone():raise HTTPException(409,'Email уже зарегистрирован. Для существующего аккаунта используйте доступ сотрудника в разделе «Персонал».')
            cur.execute('''INSERT INTO users(name,email,password,role,company_id,project_id,project_name,
                assigned_projects,assigned_packages,active,two_factor_required)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING id''',
                (name,email,hash_password(password),data.role,company,project_id,project_name,json.dumps(names),json.dumps(packages),data.active is not False,requires_2fa(data.role)))
            user_id=cur.fetchone()['id']
            save_membership(cur,user_id,company,data.role,names,packages,data.active is not False,{'is_default':True})
            audit(cur,actor,company,user_id,'create')
            return {'id':user_id,'name':name,'email':email,'role':data.role,'companyId':company}

    def update(cur,actor,company,user_id,values,only_assignments=False):
        row,membership,shared=target(cur,user_id,company)
        role=values.get('role') or membership['role'];require_role(actor,role)
        if membership['role'] in ('директор','зам_директора') and actor['role']=='зам_директора':
            raise HTTPException(403,'Изменять доступ руководителя может директор')
        active=membership.get('active') is not False if values.get('active') is None else values['active'] is not False
        if user_id==actor['id'] and (not active or role!=membership['role']):
            raise HTTPException(400,'Нельзя отключить себя или изменить собственную роль')
        source=dict(values,role=role)
        if only_assignments:source.update(projectName='',projectId='')
        project_id,project_name,names,packages=assignments(cur,company,source)
        name=str(values.get('name',row['name']) or '').strip();email=str(values.get('email',row['email']) or '').strip().lower()
        password=str(values.get('password') or '').strip()
        if shared and (name!=row['name'] or email!=row['email'] or password):
            raise HTTPException(409,'Учётная запись используется в других компаниях. Здесь можно менять только доступ в выбранной компании.')
        if not shared:
            if not name or not email:raise HTTPException(400,'Укажите имя и email')
            if password and len(password)<5:raise HTTPException(400,'Пароль минимум 5 символов')
            cur.execute('SELECT id FROM users WHERE LOWER(email)=%s AND id<>%s',(email,user_id))
            if cur.fetchone():raise HTTPException(409,'Email уже зарегистрирован')
            cur.execute('''UPDATE users SET name=%s,email=%s,role=%s,project_id=%s,project_name=%s,
                assigned_projects=%s::jsonb,assigned_packages=%s::jsonb,active=%s,
                password=CASE WHEN %s<>'' THEN %s ELSE password END,
                two_factor_required=two_factor_required OR %s WHERE id=%s''',
                (name,email,role,project_id,project_name,json.dumps(names),json.dumps(packages),active,password,
                 hash_password(password) if password else '',requires_2fa(role),user_id))
            if password or not active or role!=membership['role']:revoke(cur,user_id)
        elif requires_2fa(role):
            cur.execute('UPDATE users SET two_factor_required=TRUE WHERE id=%s',(user_id,))
        save_membership(cur,user_id,company,role,names,packages,active,membership)
        audit(cur,actor,company,user_id,'access_update')
        return {'ok':True}

    @app.put('/users/{user_id}')
    def edit(user_id:int,data:UserModel,user:dict=Depends(authenticated),request:Request=None):
        with transaction(deps,user,request,True) as (cur,actor,company):
            return update(cur,actor,company,user_id,data.model_dump())

    @app.put('/users/{user_id}/assigned-projects')
    def assign(user_id:int,data:dict,user:dict=Depends(authenticated),request:Request=None):
        if set(data)-{'assignedProjects','assignedPackages'}:
            raise HTTPException(422,'Допустимы только объекты и пакеты работ')
        if any(not isinstance(data.get(key,[]),list) for key in ('assignedProjects','assignedPackages')):
            raise HTTPException(422,'Объекты и пакеты должны быть списками')
        with transaction(deps,user,request,True) as (cur,actor,company):
            return update(cur,actor,company,user_id,data,True)

    @app.delete('/users/{user_id}')
    def deactivate(user_id:int,user:dict=Depends(authenticated),request:Request=None):
        with transaction(deps,user,request,True) as (cur,actor,company):
            row,membership,shared=target(cur,user_id,company)
            if user_id==actor['id']:raise HTTPException(400,'Нельзя отключить собственный доступ')
            if membership['role'] in ('директор','зам_директора') and actor['role']=='зам_директора':
                raise HTTPException(403,'Отключить руководителя может директор')
            save_membership(cur,user_id,company,membership['role'],string_list(membership.get('assigned_projects')),
                            string_list(membership.get('assigned_packages')),False,membership)
            if not shared:
                cur.execute('UPDATE users SET active=FALSE WHERE id=%s',(user_id,));revoke(cur,user_id)
            audit(cur,actor,company,user_id,'deactivate')
            return {'ok':True}

    @app.post('/users/{user_id}/2fa-reset')
    def reset(user_id:int,user:dict=Depends(authenticated),request:Request=None):
        with transaction(deps,user,request,True) as (cur,actor,company):
            row,membership,shared=target(cur,user_id,company)
            if shared:raise HTTPException(409,'Для общего аккаунта сброс 2FA выполняется владельцем платформы')
            if membership['role'] in ('директор','зам_директора') and actor['role']=='зам_директора':
                raise HTTPException(403,'Сброс 2FA руководителя выполняет директор')
            cur.execute('UPDATE users SET two_factor_enabled=FALSE,two_factor_secret=NULL,two_factor_confirmed_at=NULL,two_factor_required=%s WHERE id=%s',(requires_2fa(membership['role']),user_id))
            revoke(cur,user_id);audit(cur,actor,company,user_id,'2fa_reset')
            return {'ok':True}
