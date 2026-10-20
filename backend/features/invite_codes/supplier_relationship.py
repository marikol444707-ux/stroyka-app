"""A buyer invitation grants a catalog relationship, never buyer membership."""
from datetime import datetime, timedelta
import secrets

from fastapi import HTTPException
from psycopg2.extras import Json

from ..supplier_access.company_directory import CompanySupplierDirectory
from ..supplier_access.legal_identity import canonical_legal, legal_sql, lock_legal_keys
from ..participant_support.reasons import InviteDiagnostic


def directory(deps):
    return CompanySupplierDirectory({**deps, 'finance_roles': deps.get('admin_roles', ())})


def unclaimed_supplier(cur, supplier_id, company_id, account_id, canonical_id=None):
    """Only an exclusive buyer catalog card can be handed to its first owner."""
    cur.execute('SELECT id,user_id,inn,ogrn FROM suppliers WHERE id=%s FOR UPDATE', (supplier_id,))
    supplier = cur.fetchone()
    cur.execute('SELECT company_id,platform_account_id,profile FROM company_supplier_links WHERE supplier_id=%s', (supplier_id,))
    links = cur.fetchall()
    if not supplier or not any(r['company_id'] == company_id and r['platform_account_id'] == account_id for r in links):
        raise HTTPException(404, 'Поставщик не найден в выбранной компании')
    if supplier['user_id']:
        raise InviteDiagnostic('SUPPLIER_ACCOUNT_EXISTS', supplier_id)
    if any(r['company_id'] != company_id or r['platform_account_id'] != account_id for r in links):
        raise InviteDiagnostic('SUPPLIER_SHARED_CARD', supplier_id)
    if any((r.get('profile') or {}).get('mergedIntoSupplierId') and
           (r.get('profile') or {}).get('mergedIntoSupplierId') != canonical_id for r in links):
        raise InviteDiagnostic('SUPPLIER_CARD_MERGED', supplier_id)
    from ..supplier_access.company_merge import check_company_documents
    try:
        check_company_documents(cur, supplier_id, company_id)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        raise InviteDiagnostic('SUPPLIER_DOCUMENT_OWNERSHIP', supplier_id) from error
    cur.execute('SELECT 1 FROM supplier_team_members WHERE supplier_id=%s LIMIT 1', (supplier_id,))
    if cur.fetchone():
        raise InviteDiagnostic('SUPPLIER_TEAM_EXISTS', supplier_id)
    return supplier


def create_supplier_invite(deps, user, data, headers):
    supplier_id = data.get('supplierId') or None
    if supplier_id is not None:
        try:
            supplier_id = int(supplier_id)
            if supplier_id <= 0: raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'Некорректный поставщик')
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
        if supplier_id:
            binding = dict(company_id=company['id'], platform_account_id=company['platform_account_id'])
            supplier_id = canonical_invited_card(company_catalog(cur, binding), supplier_id)
            unclaimed_supplier(cur, supplier_id, company['id'], company['platform_account_id'])
        cur.execute('''INSERT INTO invite_codes
            (code,role,preset_name,preset_category,created_by,expires_at,company_id,platform_account_id,supplier_id)
            VALUES(%s,'поставщик',%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (secrets.token_hex(10).upper(), name, category, actor.get('name', ''),
             datetime.now() + timedelta(days=days), company['id'], company['platform_account_id'], supplier_id))
        invite = dict(cur.fetchone())
        cur.execute('''INSERT INTO supplier_invite_companies
            (invite_id,company_id,platform_account_id,created_by_user_id) VALUES(%s,%s,%s,%s)''',
            (invite['id'], company['id'], company['platform_account_id'], user['id']))
        return invite


def lock_inviting_company(cur, invite):
    # Receipt/catalog writers pin the company before legal-identity locks too.
    # Keep the same order so simultaneous receipt creation and signup can wait.
    cur.execute("""SELECT c.id FROM supplier_invite_companies b
        JOIN companies c ON c.id=b.company_id AND c.platform_account_id=b.platform_account_id
        WHERE b.invite_id=%s FOR SHARE OF c""", (invite['id'],))
    cur.fetchall()


def company_catalog(cur, binding):
    """Resolve aliases only inside the server-bound inviting company."""
    cur.execute('''SELECT s.id,s.name,s.inn,s.ogrn,l.profile FROM suppliers s
        JOIN company_supplier_links l ON l.supplier_id=s.id
        WHERE l.company_id=%s AND l.platform_account_id=%s ORDER BY s.id''',
        (binding['company_id'], binding['platform_account_id']))
    return {row['id']: row for row in cur.fetchall()}


def canonical_invited_card(rows, supplier_id):
    row = rows.get(supplier_id)
    if not row:
        raise HTTPException(409, 'Карточка приглашения недоступна в выбранной компании')
    profile = row.get('profile') or {}
    if not isinstance(profile, dict):
        raise HTTPException(409, 'Связь объединённых карточек требует проверки')
    value = profile.get('mergedIntoSupplierId')
    if value is None:
        return supplier_id
    # The merge writer permits only a direct source -> canonical target. Legacy
    # chains, dangling links and cycles need explicit ownership review, not guesses.
    if type(value) is not int or value <= 0 or value == supplier_id:
        raise HTTPException(409, 'Связь объединённых карточек требует проверки')
    target = rows.get(value)
    target_profile = (target.get('profile') or {}) if target else {}
    if not target or not isinstance(target_profile, dict) or 'mergedIntoSupplierId' in target_profile:
        raise HTTPException(409, 'Основная карточка приглашения требует проверки')
    return value


def same_legal(left, right, key):
    lengths = (10, 12) if key == 'inn' else (13, 15)
    a, b = canonical_legal(left, lengths), canonical_legal(right, lengths)
    return a is not None and b is not None and a == b


def lock_invited_identity(cur, invite, requisites):
    """Pin old and new legal keys together, before taking any supplier row lock."""
    cur.execute('SELECT company_id,platform_account_id FROM supplier_invite_companies WHERE invite_id=%s', (invite['id'],))
    binding = cur.fetchone()
    rows = company_catalog(cur, binding) if binding else {}
    roots = set()
    if invite.get('supplier_id') and binding:
        roots.add(canonical_invited_card(rows, invite['supplier_id']))
    else:
        for row in rows.values():
            if any(requisites.get(key) and same_legal(requisites[key], row.get(key), key)
                   for key in ('inn', 'ogrn')):
                roots.add(canonical_invited_card(rows, row['id']))
    selected = {}
    for sid, row in rows.items():
        profile = row.get('profile') or {}
        alias = profile.get('mergedIntoSupplierId') if isinstance(profile, dict) else None
        if sid in roots or (type(alias) is int and alias in roots):
            selected[sid] = row
    before = {sid: (row.get('inn'), row.get('ogrn')) for sid, row in selected.items()}
    keys = [(key, requisites.get(key, '')) for key in ('inn', 'ogrn')]
    keys += [(key, row.get(key)) for row in selected.values() for key in ('inn', 'ogrn')]
    lock_legal_keys(cur, keys)
    if selected:
        cur.execute('SELECT id,inn,ogrn FROM suppliers WHERE id=ANY(%s) ORDER BY id FOR UPDATE', (sorted(selected),))
        after = {row['id']: (row.get('inn'), row.get('ogrn')) for row in cur.fetchall()}
        if before != after:
            raise HTTPException(409, 'Реквизиты приглашённого поставщика изменились. Повторите регистрацию')


def claim_invited_supplier(cur, invite, user, requisites):
    cur.execute('SELECT company_id,platform_account_id FROM supplier_invite_companies WHERE invite_id=%s', (invite['id'],))
    binding = cur.fetchone()
    if not binding:
        raise HTTPException(409, 'Приглашение не подтверждает право подключить существующего поставщика')
    rows = company_catalog(cur, binding)
    supplier_id = canonical_invited_card(rows, invite['supplier_id'])
    supplier = unclaimed_supplier(cur, supplier_id, binding['company_id'], binding['platform_account_id'])
    for key in ('inn', 'ogrn'):
        if requisites.get(key) and supplier.get(key) and not same_legal(requisites[key], supplier[key], key):
            raise HTTPException(409, 'Реквизиты не совпадают с приглашённым поставщиком')
    for key in ('inn', 'ogrn'):
        if requisites.get(key) and not supplier.get(key):
            cur.execute(f"SELECT id FROM suppliers s WHERE {legal_sql('s.' + key, (10, 12) if key == 'inn' else (13, 15))}=%s AND id<>%s AND NOT EXISTS(SELECT 1 FROM company_supplier_links l WHERE l.supplier_id=s.id AND l.company_id=%s AND l.profile->>'mergedIntoSupplierId'=%s) LIMIT 1",
                        (requisites[key], supplier['id'], binding['company_id'], str(supplier['id'])))
            if cur.fetchone():
                raise HTTPException(409, 'С этими реквизитами уже есть карточка. Сначала объедините карточки в каталоге')
    for key, lengths in (('inn', (10, 12)), ('ogrn', (13, 15))):
        identity = canonical_legal(requisites.get(key) or supplier.get(key), lengths)
        if identity:
            cur.execute('SELECT 1 FROM suppliers WHERE ' + legal_sql(key, lengths) +
                        '=%s AND user_id IS NOT NULL AND id<>%s LIMIT 1', (identity, supplier['id']))
            if cur.fetchone():
                raise HTTPException(409, 'С этими реквизитами уже есть кабинет. Нужна проверка владельца')
    cur.execute("SELECT supplier_id FROM company_supplier_links WHERE company_id=%s AND platform_account_id=%s AND profile->>'mergedIntoSupplierId'=%s ORDER BY supplier_id FOR UPDATE",
                (binding['company_id'], binding['platform_account_id'], str(supplier['id'])))
    children = [row['supplier_id'] for row in cur.fetchall()]
    for child in children:
        child_supplier = unclaimed_supplier(cur, child, binding['company_id'], binding['platform_account_id'], canonical_id=supplier['id'])
        for key in ('inn', 'ogrn'):
            legal_key = requisites.get(key) or supplier.get(key)
            if legal_key and child_supplier.get(key) and not same_legal(legal_key, child_supplier[key], key):
                raise HTTPException(409, 'Реквизиты объединённой карточки различаются. Нужна проверка каталога')
    if children:
        cur.execute('UPDATE suppliers SET user_id=%s WHERE id=ANY(%s)', (user['id'], children))
    cur.execute('''UPDATE suppliers SET user_id=%s,registered_at=NOW(),
        inn=COALESCE(NULLIF(inn,''),NULLIF(%s,'')),
        ogrn=COALESCE(NULLIF(ogrn,''),NULLIF(%s,'')) WHERE id=%s''',
        (user['id'], requisites.get('inn', ''), requisites.get('ogrn', ''), supplier['id']))
    return supplier['id']


def matching_invited_card(cur, invite, requisites, normalize_name):
    """Reuse only one exact legal identity in the inviting buyer's catalog."""
    inn, ogrn = requisites.get('inn', ''), requisites.get('ogrn', '')
    cur.execute('SELECT company_id,platform_account_id FROM supplier_invite_companies WHERE invite_id=%s', (invite['id'],))
    binding = cur.fetchone()
    if not binding:
        return None
    rows = company_catalog(cur, binding)
    matches = set()
    for row in rows.values():
        if ((inn and same_legal(inn, row.get('inn'), 'inn')) or
                (ogrn and same_legal(ogrn, row.get('ogrn'), 'ogrn'))):
            matches.add(canonical_invited_card(rows, row['id']))
    if len(matches) > 1:
        raise HTTPException(409, 'Найдено несколько карточек с этими реквизитами. Объедините их в каталоге компании')
    if matches:
        return next(iter(matches))
    name_key = normalize_name(requisites.get('name', ''))
    if name_key and any(normalize_name(r['name']) == name_key and
                        (not (inn or ogrn) or not (r.get('inn') or r.get('ogrn'))) for r in rows.values()):
        raise HTTPException(409, 'В каталоге уже есть похожая карточка. Попросите ссылку из этой карточки, чтобы сохранить историю')
    return None


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
        VALUES(%s,%s,%s,%s,'invite_link',%s,'Активный',%s)
        ON CONFLICT(company_id,supplier_id) DO UPDATE SET
            profile=company_supplier_links.profile || EXCLUDED.profile,
            version=company_supplier_links.version+1
        RETURNING id''',
        (binding['company_id'], supplier_id, binding['platform_account_id'], invite.get('preset_category') or '',
         'Регистрация по приглашению компании', Json(profile)))
    link_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,
        entity_id,description,owner_scope,company_id)
        VALUES(%s,%s,'поставщик','supplier_relationship_registered','company_supplier_link',%s,%s,'company',%s)''',
        (user['id'], user.get('name', ''), link_id, 'Поставщик зарегистрировался по приглашению компании', binding['company_id']))
    return link_id
