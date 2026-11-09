"""Authorize personal profiles through exact company memberships, never names."""
from fastapi import HTTPException


def authorized_profile_users(cur, user, deps, *, manager_roles=(), project_roles=(),
                             company_id=None, company_mode=None, write=False, allow_self=True):
    context = deps['resolve_work_company_context'](
        cur, user, None, 'write' if write else 'read',
        x_company_id=company_id, x_company_mode=company_mode,
    )
    actors = deps['effective_company_actors'](user, context)
    allowed = {}
    for actor in actors:
        actor_id = int(actor.get('id') or 0)
        if actor_id and allow_self:
            allowed[actor_id] = True
        role = actor.get('role')
        if role not in manager_roles and role not in project_roles:
            continue
        owner = actor.get('companyId') or actor.get('company_id')
        if not owner:
            raise HTTPException(409, 'Компания профиля не определена')
        cur.execute('''SELECT u.id,
                    CASE WHEN m.id IS NULL THEN COALESCE(u.assigned_projects,'[]'::jsonb)
                         ELSE COALESCE(m.assigned_projects,'[]'::jsonb) END AS projects,
                    CASE WHEN m.id IS NULL THEN COALESCE(u.project_name,'') ELSE '' END AS project
                 FROM users u
                 LEFT JOIN user_company_roles m ON m.user_id=u.id AND m.company_id=%s
                    AND COALESCE(m.active,TRUE)
                 WHERE COALESCE(u.active,TRUE) AND (
                    m.id IS NOT NULL OR (u.company_id=%s AND NOT EXISTS (
                        SELECT 1 FROM user_company_roles any_membership WHERE any_membership.user_id=u.id
                    ))
                 )''', (owner, owner))
        projects = set(actor.get('assignedProjects') or actor.get('assigned_projects') or [])
        projects.add(actor.get('projectName') or actor.get('project_name') or '')
        projects.discard('')
        for row in cur.fetchall():
            if role in manager_roles or projects.intersection(set(row.get('projects') or []) | {row.get('project')}):
                target = int(row['id'])
                allowed[target] = allowed.get(target, False) or role in manager_roles
    return allowed


def require_profile_user(allowed, target_id):
    if int(target_id) not in allowed:
        raise HTTPException(403, 'Нет доступа к данным этого пользователя в выбранной компании')
