"""Company invitations never infer ownership from a name or a submitted company."""
from datetime import datetime, timedelta
import json
import secrets
from types import SimpleNamespace

from fastapi import HTTPException
from ..company_limits.service import require_user_capacity
from ..company_users.access import assignments, require_role, transaction


def request_headers(headers):
    return SimpleNamespace(headers={'x-company-id': headers[0], 'x-company-mode': headers[1]})


def create_company_invite(deps, user, data, headers):
    days = data.get('expiresInDays', 14)
    if type(days) is not int or not 1 <= days <= 90:
        raise HTTPException(422, 'Срок приглашения должен быть от 1 до 90 дней')
    with transaction(deps, user, request_headers(headers), True) as (cur, actor, company):
        role = data.get('role')
        require_role(actor, role)
        claimed_company = data.get('companyId', data.get('company_id'))
        if claimed_company is not None and str(claimed_company) != str(company):
            raise HTTPException(403, 'Приглашение относится к другой компании')
        cur.execute('SELECT platform_account_id,active FROM companies WHERE id=%s', (company,))
        owner = cur.fetchone()
        if not owner or not owner['active']:
            raise HTTPException(409, 'Компания недоступна')
        claimed_account = data.get('platformAccountId', data.get('platform_account_id'))
        if claimed_account is not None and str(claimed_account) != str(owner['platform_account_id']):
            raise HTTPException(403, 'Аккаунт приглашения не совпадает с компанией')
        _, name, projects, packages = assignments(cur, company, data)
        cur.execute('''INSERT INTO invite_codes
            (code,role,created_by,expires_at,project_name,assigned_projects,assigned_packages,company_id,platform_account_id)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING *''',
            (secrets.token_hex(10).upper(), role, actor.get('name',''), datetime.now()+timedelta(days=days),
             name, json.dumps(projects), json.dumps(packages), company, owner['platform_account_id']))
        invite = dict(cur.fetchone())
        cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,owner_scope,company_id)
            VALUES(%s,%s,%s,'invite_created','invite_code',%s,'company',%s)''',
            (actor['id'],actor.get('name',''),actor['role'],invite['id'],company))
        return invite


def registration_scope(cur, invite):
    company = invite.get('company_id')
    if not company:
        raise HTTPException(409, 'У приглашения не указана компания. Попросите руководителя создать новое приглашение')
    cur.execute('SELECT id,platform_account_id,active FROM companies WHERE id=%s FOR UPDATE', (company,))
    owner = cur.fetchone()
    if not owner or not owner['active']:
        raise HTTPException(409, 'Компания приглашения недоступна')
    if invite.get('platform_account_id') and invite['platform_account_id'] != owner['platform_account_id']:
        raise HTTPException(409, 'Аккаунт приглашения не совпадает с компанией')
    require_user_capacity(cur, company)
    values = {'role':invite['role'], 'projectName':invite.get('project_name'),
              'assignedProjects':invite.get('assigned_projects'), 'assignedPackages':invite.get('assigned_packages')}
    project_id, name, projects, packages = assignments(cur, company, values)
    return company, owner['platform_account_id'], project_id, name, projects, packages
