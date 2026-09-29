"""Shared company boundary for procurement reads and resource actions."""

from contextlib import contextmanager

from fastapi import HTTPException
import psycopg2.extras


def explicit_supplier_targets(cursor, company_id, supplier_ids):
    """Lock the exact selected relationships and direct portal identities through dispatch."""
    # Directory writers lock company before relationship; use the same order.
    cursor.execute('SELECT id FROM companies WHERE id=%s FOR SHARE', (company_id,))
    if not cursor.fetchone():
        raise HTTPException(409, 'Компания заявки больше не доступна')
    cursor.execute('''SELECT link.supplier_id,s.user_id FROM company_supplier_links link
        JOIN companies company ON company.id=link.company_id
            AND company.platform_account_id=link.platform_account_id
        JOIN suppliers s ON s.id=link.supplier_id
        JOIN users u ON u.id=s.user_id AND u.role='поставщик' AND COALESCE(u.active,TRUE)
        WHERE link.company_id=%s AND link.supplier_id=ANY(%s) AND link.status='Активный'
            AND COALESCE(s.status,'Активный') IN ('Активный','')
        ORDER BY link.supplier_id FOR SHARE OF link,company,s,u''', (company_id, supplier_ids))
    rows = cursor.fetchall()
    if {row['supplier_id'] for row in rows} != set(supplier_ids):
        raise HTTPException(409, 'Выбранный поставщик неактивен в компании или не имеет привязанного кабинета. Обновите каталог')
    return [dict(requested_id=row['supplier_id'], target_id=row['supplier_id'],
                 scope_ids=[row['supplier_id']], user_id=row['user_id'], ai_recommended=False)
            for row in rows]


@contextmanager
def procurement_read_cursor(get_db):
    connection = get_db()
    cursor = None
    try:
        connection.autocommit = False
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SET LOCAL statement_timeout='15s'")
        yield cursor
    finally:
        try:
            connection.rollback()
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()


def authorize_procurement_document(
    cursor, row, user, *, resolve_actor, project_access, package_access,
    allowed_roles, platform_staff_roles=(), client_account_roles=(),
    x_company_id=None, x_company_mode=None, action_mode="read",
):
    if not row:
        raise HTTPException(404, detail="Документ снабжения не найден")
    context, actor = resolve_actor(
        cursor, user, row.get("company_id"), action_mode,
        x_company_id=x_company_id, x_company_mode=x_company_mode,
        allowed_roles=allowed_roles,
        forbidden_detail="Роль в выбранной компании не позволяет работать с этим документом",
        platform_staff_roles=platform_staff_roles,
        client_account_roles=client_account_roles,
    )
    project = row.get("project") or row.get("project_name") or ""
    if project:
        project_access(actor, project)
    if not package_access(actor, row.get("work_package") or "Основная"):
        raise HTTPException(403, detail="Нет доступа к пакету документа снабжения")
    return int(context["companyId"]), actor
