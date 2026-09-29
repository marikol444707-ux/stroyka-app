"""Pin the actual company membership before a stock transaction can wait."""
import json

from fastapi import HTTPException

from .service import as_dict


def _values(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = []
    return sorted(str(item) for item in (value or []))


def lock_actor(cur, actor):
    company_id = actor.get('companyId') or actor.get('company_id')
    membership_id = actor.get('membershipId') or actor.get('membership_id')
    if not company_id or not membership_id:
        raise HTTPException(403, 'Нужно действующее членство в выбранной компании')
    cur.execute('SELECT id FROM users WHERE id=%s AND COALESCE(active,TRUE) FOR SHARE', (actor['id'],))
    if not cur.fetchone():
        raise HTTPException(403, 'Пользователь отключён')
    cur.execute('SELECT id FROM companies WHERE id=%s AND COALESCE(active,TRUE) FOR SHARE', (company_id,))
    if not cur.fetchone():
        raise HTTPException(403, 'Компания отключена')
    cur.execute('''SELECT role,assigned_projects,assigned_packages FROM user_company_roles
        WHERE id=%s AND user_id=%s AND company_id=%s AND COALESCE(active,TRUE) FOR SHARE''',
                (membership_id, actor['id'], company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(403, 'Членство в компании больше не действует')
    row = as_dict(row, ('role', 'assigned_projects', 'assigned_packages'))
    if row['role'] != actor.get('role'):
        raise HTTPException(403, 'Права в компании изменились; обновите страницу')
    for camel, snake in (('assignedProjects', 'assigned_projects'), ('assignedPackages', 'assigned_packages')):
        if _values(row[snake]) != _values(actor.get(camel, actor.get(snake))):
            raise HTTPException(403, 'Назначения исполнителя изменились; обновите страницу')
