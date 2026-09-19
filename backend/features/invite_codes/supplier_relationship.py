"""A buyer invitation grants a catalog relationship, never buyer membership."""
from datetime import datetime, timedelta
import secrets

from fastapi import HTTPException
from psycopg2.extras import Json

from ..supplier_access.company_directory import CompanySupplierDirectory


def directory(deps):
    return CompanySupplierDirectory({**deps, 'finance_roles': deps.get('admin_roles', ())})


def create_supplier_invite(deps, user, data, headers):
    if data.get('supplierId'):
        raise HTTPException(409, 'Для существующей организации используйте её кабинет. Приглашение предназначено для нового поставщика')
    days = data.get('expiresInDays', 14)
    if type(days) is not int or not 1 <= days <= 90:
        raise HTTPException(422, 'Срок приглашения должен быть от 1 до 90 дней')
    name, category = str(data.get('presetName') or '').strip(), str(data.get('presetCategory') or '').strip()
    if len(name) > 255 or len(category) > 100:
        raise HTTPException(422, 'Название или категория приглашения слишком длинные')
    with directory(deps).transaction(user, headers, write=True,
                                    claimed_company_id=data.get('companyId') or data.get('company_id')) as (cur, company, actor):
        if actor.get('role') not in deps.get('admin_roles', ()):
            raise HTTPException(403, 'Приглашать поставщика может руководитель компании')
        claimed_account = data.get('platformAccountId') or data.get('platform_account_id')
        if claimed_account is not None and str(claimed_account) != str(company['platform_account_id']):
            raise HTTPException(403, 'Аккаунт приглашения не совпадает с выбранной компанией')
        cur.execute('''INSERT INTO invite_codes
            (code,role,preset_name,preset_category,created_by,expires_at,company_id,platform_account_id)
            VALUES(%s,'поставщик',%s,%s,%s,%s,%s,%s) RETURNING *''',
            (secrets.token_hex(10).upper(), name, category, actor.get('name', ''),
             datetime.now() + timedelta(days=days), company['id'], company['platform_account_id']))
        invite = dict(cur.fetchone())
        cur.execute('''INSERT INTO supplier_invite_companies
            (invite_id,company_id,platform_account_id,created_by_user_id) VALUES(%s,%s,%s,%s)''',
            (invite['id'], company['id'], company['platform_account_id'], user['id']))
        return invite


def link_registered_supplier(cur, invite, supplier_id, user, payload):
    # Legacy company_id was client-supplied. Only the new server-verified binding
    # grants a relationship; never infer it from a name, email or submitted ID.
    cur.execute('SELECT company_id,platform_account_id FROM supplier_invite_companies WHERE invite_id=%s',
                (invite['id'],))
    binding = cur.fetchone()
    if not binding:
        return None
    cur.execute('SELECT id,platform_account_id,active FROM companies WHERE id=%s FOR SHARE',
                (binding['company_id'],))
    company = cur.fetchone()
    if not company or not company.get('active') or company['platform_account_id'] != binding['platform_account_id']:
        raise HTTPException(409, 'Компания приглашения недоступна. Запросите новое приглашение')
    profile = {key: str(payload.get(key) or '').strip() for key in ('email', 'phone', 'specialization')}
    cur.execute('''INSERT INTO company_supplier_links
        (company_id,supplier_id,platform_account_id,local_category,source_type,source_detail,status,profile)
        VALUES(%s,%s,%s,%s,'invite_link',%s,'Активный',%s) RETURNING id''',
        (binding['company_id'], supplier_id, binding['platform_account_id'], invite.get('preset_category') or '',
         'Регистрация по приглашению компании', Json(profile)))
    link_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,
        entity_id,description,owner_scope,company_id)
        VALUES(%s,%s,'поставщик','supplier_relationship_registered','company_supplier_link',%s,%s,'company',%s)''',
        (user['id'], user.get('name', ''), link_id, 'Поставщик зарегистрировался по приглашению компании', binding['company_id']))
    return link_id
