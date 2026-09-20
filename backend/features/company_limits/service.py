"""The company row serializes admission; caller owns the transaction."""
from fastapi import HTTPException


def lock_company(cur, company_id):
    cur.execute('SELECT max_projects,max_users FROM companies WHERE id=%s FOR UPDATE',(company_id,))
    company = cur.fetchone()
    if not company:
        raise HTTPException(404,'Компания не найдена')
    return company


def require_project_capacity(cur, company_id):
    company = lock_company(cur, company_id)
    limit = company['max_projects']
    if not limit or limit < 0:
        return
    cur.execute('SELECT COUNT(*) AS count FROM projects WHERE company_id=%s AND NOT COALESCE(archived,FALSE)',(company_id,))
    if cur.fetchone()['count'] >= limit:
        raise HTTPException(409,'Достигнут лимит активных объектов компании. Обратитесь к владельцу платформы для изменения тарифа.')


def require_user_capacity(cur, company_id, user_id=None):
    company = lock_company(cur, company_id)
    limit = company['max_users']
    if not limit or limit < 0:
        return
    # Explicit memberships supersede legacy company_id, including revoked access.
    cur.execute('''SELECT u.id FROM users u WHERE COALESCE(u.active,TRUE) AND (
        EXISTS(SELECT 1 FROM user_company_roles m WHERE m.user_id=u.id AND m.company_id=%s AND m.active)
        OR (u.company_id=%s AND NOT EXISTS(SELECT 1 FROM user_company_roles m WHERE m.user_id=u.id)))''',
        (company_id,company_id))
    active_ids = {row['id'] for row in cur.fetchall()}
    if user_id in active_ids:
        return
    if len(active_ids) >= limit:
        raise HTTPException(409,'Достигнут лимит пользователей компании. Отключите ненужный доступ или измените тариф.')
