"""Selected-company access and membership writes shared by user administration."""
import json
from contextlib import contextmanager

import psycopg2.extras
from fastapi import HTTPException

ADMIN_ROLES = ('директор','зам_директора','system_owner','platform_admin')
COMPANY_ROLES = ('директор','зам_директора','бухгалтер','главный_инженер','сметчик',
    'прораб','снабженец','кладовщик','мастер','субподрядчик','бригадир','заказчик',
    'технадзор','стройконтроль','менеджер_crm')
PROJECT_ROLES = ('прораб','главный_инженер','технадзор','стройконтроль','мастер','субподрядчик','бригадир','заказчик')


def string_list(value):
    if isinstance(value,str):
        try:value=json.loads(value)
        except ValueError:value=[]
    return list(dict.fromkeys(str(v).strip() for v in (value or []) if str(v).strip())) if isinstance(value,list) else []


@contextmanager
def transaction(deps,user,request,write=False):
    conn=deps['get_db']();conn.autocommit=False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            headers=request.headers if request else {}
            context=deps['resolve_context'](cur,user,None,'write' if write else 'read',
                x_company_id=headers.get('x-company-id'),x_company_mode=headers.get('x-company-mode'))
            actors=deps['effective_actors'](user,context)
            if len(actors)!=1:
                raise HTTPException(403,'Выберите одну компанию для управления доступом')
            actor=actors[0];company=int(actor.get('companyId') or actor['company_id'])
            if write:
                if actor['role'] not in ADMIN_ROLES:
                    raise HTTPException(403,'Нет прав на управление доступом в выбранной компании')
                cur.execute('SELECT id FROM companies WHERE id=%s FOR UPDATE',(company,))
                # A preceding access change may have committed while we waited.
                context=deps['resolve_context'](cur,user,None,'write',
                    x_company_id=headers.get('x-company-id'),x_company_mode=headers.get('x-company-mode'))
                actors=deps['effective_actors'](user,context)
                if len(actors)!=1 or actors[0]['role'] not in ADMIN_ROLES:
                    raise HTTPException(403,'Полномочия в выбранной компании изменились')
                actor=actors[0]
            yield cur,actor,company
        if write:conn.commit()
    except Exception:
        conn.rollback();raise
    finally:conn.close()


def target(cur,user_id,company):
    cur.execute('SELECT * FROM users WHERE id=%s FOR UPDATE',(user_id,))
    user=cur.fetchone()
    if not user or user['role'] not in COMPANY_ROLES:raise HTTPException(404,'Пользователь не найден в выбранной компании')
    cur.execute('SELECT * FROM user_company_roles WHERE user_id=%s ORDER BY active DESC,id DESC FOR UPDATE',(user_id,))
    memberships=cur.fetchall()
    own=[m for m in memberships if m['company_id']==company]
    if not own:
        if memberships or user.get('company_id')!=company:
            raise HTTPException(404,'Пользователь не найден в выбранной компании')
        own=[dict(role=user['role'],assigned_projects=user.get('assigned_projects'),
                  assigned_packages=user.get('assigned_packages'),active=user.get('active') is not False,
                  is_default=True,staff_id=None)]
    shared=any(m['company_id']!=company for m in memberships)
    return user,own[0],shared


def assignments(cur,company,data):
    role=data['role'];names=string_list(data.get('assignedProjects'));packages=string_list(data.get('assignedPackages'))
    name=str(data.get('projectName') or '').strip();project_id=data.get('projectId')
    if project_id:
        try:project_id=int(project_id)
        except (TypeError,ValueError):raise HTTPException(422,'Некорректный объект')
        cur.execute('SELECT id,name FROM projects WHERE company_id=%s AND id=%s',(company,project_id))
        row=cur.fetchone()
        if not row:raise HTTPException(404,'Объект не найден в выбранной компании')
        if name and name!=row['name']:raise HTTPException(409,'Название и идентификатор объекта не совпадают')
        name=row['name']
    if name and name not in names:names.append(name)
    resolved={}
    if names:
        cur.execute('SELECT id,name FROM projects WHERE company_id=%s AND name=ANY(%s)',(company,names))
        for row in cur.fetchall():resolved.setdefault(row['name'],[]).append(row['id'])
        if set(resolved)!=set(names):raise HTTPException(404,'Один из объектов не найден в выбранной компании')
        if any(len(ids)!=1 for ids in resolved.values()):raise HTTPException(409,'Названия объектов неоднозначны; уточните объекты перед назначением')
    if role in PROJECT_ROLES and not names:raise HTTPException(400,'Назначьте хотя бы один объект')
    if role=='заказчик' and len(names)!=1:raise HTTPException(400,'Для кабинета заказчика выберите один объект')
    if role in ('мастер','субподрядчик','бригадир') and not packages:raise HTTPException(400,'Назначьте виды работ или пакеты смет')
    if not name and len(names)==1:name=names[0]
    project_id=resolved[name][0] if name else None
    return project_id,name,names,packages


def require_role(actor,role):
    if role not in COMPANY_ROLES:raise HTTPException(403,'Эта роль не создаётся в разделе сотрудников компании')
    if role in ('директор','зам_директора') and actor['role']=='зам_директора':
        raise HTTPException(403,'Назначать руководителей может директор')


def save_membership(cur,user_id,company,role,names,packages,active,previous=None):
    previous=previous or {}
    cur.execute('UPDATE user_company_roles SET active=FALSE,updated_at=NOW() WHERE user_id=%s AND company_id=%s AND role<>%s',(user_id,company,role))
    cur.execute('''INSERT INTO user_company_roles(user_id,company_id,role,assigned_projects,assigned_packages,active,is_default,staff_id)
        VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
        ON CONFLICT(user_id,company_id,role) DO UPDATE SET assigned_projects=EXCLUDED.assigned_projects,
        assigned_packages=EXCLUDED.assigned_packages,active=EXCLUDED.active,
        is_default=EXCLUDED.is_default,staff_id=COALESCE(EXCLUDED.staff_id,user_company_roles.staff_id),updated_at=NOW()''',
        (user_id,company,role,json.dumps(names),json.dumps(packages),active,bool(previous.get('is_default')),previous.get('staff_id')))


def audit(cur,actor,company,user_id,action):
    cur.execute("""INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,description,owner_scope,company_id)
        VALUES(%s,%s,%s,%s,'user',%s,%s,'company',%s)""",
        (actor['id'],actor.get('name',''),actor['role'],action,user_id,'Изменён доступ пользователя в компании',company))
