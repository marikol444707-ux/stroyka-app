"""Company, project and recipient identities for tool custody."""
from collections import Counter

from fastapi import HTTPException

from . import policy
from ..work_material_accounting.access import lock_actor
from ..work_material_accounting.settlement import CONTRACT_TYPES


def recipient(cur, user_id, company_id, *, lock=False):
    policy.identifier(user_id, 'получателя инструмента')
    cur.execute('''SELECT u.id,u.name,m.id AS "membershipId",m.company_id AS "companyId",
        m.role,m.assigned_projects AS "assignedProjects",m.assigned_packages AS "assignedPackages"
        FROM users u JOIN user_company_roles m ON m.user_id=u.id
        WHERE u.id=%s AND m.company_id=%s AND COALESCE(u.active,TRUE) AND COALESCE(m.active,TRUE)
        AND m.role=ANY(%s) ORDER BY m.id''', (user_id, company_id, list(policy.WORKERS)))
    rows = cur.fetchall()
    if not rows:
        raise HTTPException(404, 'Исполнитель не найден в выбранной компании')
    if len(rows) != 1:
        raise HTTPException(409, 'Нужен однозначный активный исполнитель выбранной компании')
    actor = dict(rows[0])
    if lock:
        lock_actor(cur, actor)
    return actor


def project(cur, project_id, actor, deps, *, issue=False):
    policy.identifier(project_id, 'объект')
    cur.execute('SELECT id,name,company_id,archived FROM projects WHERE id=%s AND company_id=%s FOR SHARE',
                (project_id, actor['companyId']))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Объект не найден в выбранной компании')
    if issue and row['archived']:
        raise HTTPException(409, 'Выдача на архивный объект недоступна')
    if actor['role'] == 'прораб' and row['name'] not in deps['user_project_names'](actor):
        raise HTTPException(403, 'Нет доступа к объекту')
    return dict(row)


def contract(cur, contract_id, company_id, project_id, holder_id):
    policy.identifier(contract_id, 'договор')
    cur.execute('''SELECT id,company_id,project_id,contractor_id,contractor_type,status
        FROM brigade_contracts WHERE id=%s AND company_id=%s FOR UPDATE''', (contract_id, company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Договор не найден в выбранной компании')
    if (row['project_id'] != project_id or row['contractor_id'] != holder_id
            or row['contractor_type'] not in CONTRACT_TYPES or row['status'] != 'Подписан'):
        raise HTTPException(409, 'Нужен подписанный договор подряда именно этого получателя и объекта')
    return dict(row)


def require_tool(cur, tool_id, actor, deps):
    cur.execute('SELECT * FROM tools WHERE id=%s AND company_id=%s FOR UPDATE', (tool_id, actor['companyId']))
    tool = cur.fetchone()
    if not tool:
        raise HTTPException(404, 'Инструмент не найден в выбранной компании')
    if actor['role'] == 'прораб' and tool['project_id']:
        project(cur, tool['project_id'], actor, deps)
    if actor['role'] in policy.WORKERS and tool['master_id'] != actor['id']:
        cur.execute('SELECT 1 FROM tool_incidents WHERE tool_id=%s AND company_id=%s AND holder_id=%s',
                    (tool_id, actor['companyId'], actor['id']))
        if not cur.fetchone():
            raise HTTPException(404, 'Инструмент не найден')
    return dict(tool)


def choices(cur, actor, deps):
    cur.execute('SELECT id,name FROM projects WHERE company_id=%s AND NOT COALESCE(archived,FALSE) ORDER BY name,id',
                (actor['companyId'],))
    projects = [dict(row) for row in cur.fetchall()
                if actor['role'] != 'прораб' or row['name'] in deps['user_project_names'](actor)]
    cur.execute('''SELECT u.id,u.name,m.role,m.assigned_projects AS "assignedProjects",m.id AS membership_id
        FROM users u JOIN user_company_roles m ON m.user_id=u.id
        WHERE m.company_id=%s AND COALESCE(u.active,TRUE) AND COALESCE(m.active,TRUE)
        AND m.role=ANY(%s) ORDER BY u.name,u.id,m.id''', (actor['companyId'], list(policy.WORKERS)))
    members = [dict(row) for row in cur.fetchall()]
    counts = Counter(row['id'] for row in members)
    recipients = [{'id': row['id'], 'name': row['name'], 'role': row['role'],
                   'projectIds': [p['id'] for p in projects if p['name'] in deps['user_project_names'](row)]}
                  for row in members if counts[row['id']] == 1]
    recipients = [row for row in recipients if row['projectIds']]
    cur.execute('''SELECT id,project_id AS "projectId",contractor_id AS "recipientId",brigade_name AS name
        FROM brigade_contracts WHERE company_id=%s AND project_id=ANY(%s) AND contractor_id=ANY(%s)
        AND status='Подписан' AND contractor_type=ANY(%s) ORDER BY id''',
        (actor['companyId'], [p['id'] for p in projects], [r['id'] for r in recipients], list(CONTRACT_TYPES)))
    return {'projects': projects, 'recipients': recipients, 'contracts': [dict(row) for row in cur.fetchall()]}
