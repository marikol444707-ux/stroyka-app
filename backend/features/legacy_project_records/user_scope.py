"""Selected-company access to user-owned records; self access remains personal."""
from fastapi import HTTPException
from ..project_access.service import require_project_write_actor


def selected_actors(scope, cur, user, request, roles, *, write=False):
    headers = request.headers if request is not None else {}
    context = scope.resolve_context(cur, user, None, 'write' if write else 'read',
        x_company_id=headers.get('x-company-id'), x_company_mode=headers.get('x-company-mode'))
    actors = scope.effective_actors(user, context)
    if write:
        return [require_project_write_actor(actors, roles)]
    return [actor for actor in actors if actor.get('role') in roles]


def user_visibility(actors, *, project_names=None):
    clauses, params = [], []
    for actor in actors:
        company = actor.get('companyId') or actor.get('company_id')
        if not company:
            continue
        membership = """EXISTS (SELECT 1 FROM user_company_roles m JOIN companies c ON c.id=m.company_id
            WHERE m.user_id=u.id AND m.company_id=%s AND COALESCE(m.active,TRUE)
              AND COALESCE(c.active,TRUE) AND NULLIF(TRIM(m.role),'') IS NOT NULL
              AND COALESCE(m.platform_account_id,c.platform_account_id)=c.platform_account_id
              AND COALESCE(u.platform_account_id,(SELECT home.platform_account_id FROM companies home WHERE home.id=u.company_id))=c.platform_account_id"""
        values = [company]
        names = project_names(actor) if project_names else None
        if names is not None:
            membership += " AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(m.assigned_projects,'[]'::jsonb)) ap(name) WHERE ap.name=ANY(%s))"
            values.append(names)
        membership += ')'
        legacy = 'u.company_id=%s AND NOT EXISTS (SELECT 1 FROM user_company_roles any_membership WHERE any_membership.user_id=u.id)'
        values.append(company)
        if names is not None:
            legacy += " AND (u.project_name=ANY(%s) OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(u.assigned_projects,'[]'::jsonb)) ap(name) WHERE ap.name=ANY(%s)))"
            values.extend([names,names])
        clauses.append('('+membership+' OR ('+legacy+'))');params.extend(values)
    return (' OR '.join(clauses) or 'FALSE'), params


def require_user(cur, actors, user_id, *, project_names=None):
    where, params = user_visibility(actors, project_names=project_names)
    cur.execute('SELECT u.id FROM users u WHERE u.id=%s AND ('+where+') FOR SHARE OF u', [user_id,*params])
    if not cur.fetchone():
        raise HTTPException(404, 'Пользователь не найден в доступной компании')
