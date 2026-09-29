"""Opt-in scoped journal reads/edits and guarded AI writes; no GET reconstruction."""
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from psycopg2 import DatabaseError
from psycopg2.extras import RealDictCursor

from ..company_context.service import resolve_request_company_context, effective_company_actors


def quality_access_enabled():
    return os.getenv('OWNED_QUALITY_ACCESS_ENABLED') == '1'


COMMON = 'id company_id project_id project_name invoice_id delivery_id warehouse_history_id source_type source_id source_item_key work_package supplier received_at normatives ai_filled created_at status'.split()
FIELDS = {
    'material_inspection_journal': COMMON + 'material_name unit quantity batch_number passport_number certificate_number test_protocol_number visual_inspection_result remarks inspector_name inspected_at inspected'.split(),
    'cable_journal': COMMON + 'cable_brand cross_section cores_count length_received length_installed drum_number manufacturer certificate_number passport_number insulation_before insulation_after installation_location installation_method installed_at responsible_itr cable_type'.split(),
}
EDITABLE = {
    'material_inspection_journal': 'batch_number passport_number certificate_number test_protocol_number visual_inspection_result remarks inspector_name inspected_at inspected normatives'.split(),
    'cable_journal': 'length_installed drum_number manufacturer certificate_number passport_number insulation_before insulation_after installation_location installation_method installed_at responsible_itr normatives'.split(),
}
NUMBERS = {'quantity', 'cross_section', 'length_received', 'length_installed', 'insulation_before', 'insulation_after'}
DATES = {'received_at', 'inspected_at', 'installed_at', 'created_at'}
BOOLEANS = {'inspected', 'ai_filled'}
SHORT_TEXT = {'batch_number', 'passport_number', 'certificate_number', 'test_protocol_number', 'drum_number'}
MEDIUM_TEXT = {'inspector_name', 'manufacturer', 'responsible_itr', 'installation_method'}


def camel(value):
    first, *rest = value.split('_')
    return first + ''.join(part.title() for part in rest)


def serialize(row, table):
    result = {}
    for field in FIELDS[table]:
        value = row[field]
        if field in NUMBERS:
            value = float(value or 0)
        elif field in BOOLEANS:
            value = bool(value)
        elif field in DATES:
            value = str(value) if value else ''
        elif field != 'id' and not field.endswith('_id') and field != 'cores_count':
            value = value or ''
        result[camel(field)] = value
    return result


def journal_operation(deps, user, headers, table, *, project_name=None, row_id=None, data=None,
                      snapshot_only=False, expected_snapshot=None, mark_ai=False):
    if table not in FIELDS:
        raise ValueError('Unknown journal')
    write = row_id is not None
    conn = deps['get_db']()
    try:
        conn.set_session(isolation_level='READ COMMITTED', autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            context = resolve_request_company_context(cur, user, None, 'write' if write else 'read',
                x_company_id=headers.get('X-Company-Id'), x_company_mode=headers.get('X-Company-Mode'),
                platform_staff_roles=deps['platform_staff_roles'], client_account_roles=deps['client_account_roles'])
            if (context.get('mode') != 'company' or context.get('source') != 'membership'
                    or not context.get('active') or not context.get('companyActive') or not context.get('membershipId')):
                raise HTTPException(403, 'Выберите компанию с активным членством')
            # Serialize revocation with this operation, including time spent
            # waiting for a journal row. Refresh scope after acquiring the locks.
            cur.execute('SELECT id FROM users WHERE id=%s AND active=TRUE FOR SHARE', (user['id'],))
            if not cur.fetchone():
                raise HTTPException(403, 'Пользователь отключён')
            cur.execute('SELECT id FROM companies WHERE id=%s FOR SHARE', (context['companyId'],))
            cur.fetchone()
            cur.execute('SELECT id FROM user_company_roles WHERE id=%s AND user_id=%s AND company_id=%s FOR SHARE',
                        (context['membershipId'], user['id'], context['companyId']))
            if not cur.fetchone():
                raise HTTPException(403, 'Членство больше не действует')
            locked_membership_id = context['membershipId']
            context = resolve_request_company_context(cur, user, context['companyId'], 'write' if write else 'read',
                platform_staff_roles=deps['platform_staff_roles'], client_account_roles=deps['client_account_roles'])
            if (context.get('source') != 'membership' or not context.get('active') or not context.get('companyActive')
                    or context.get('membershipId') != locked_membership_id):
                raise HTTPException(403, 'Членство больше не действует')
            actors = effective_company_actors(user, context)
            if len(actors) != 1 or actors[0].get('role') not in deps['write_roles' if write else 'read_roles']:
                raise HTTPException(403, 'Нет прав на журнал в выбранной компании')
            actor = actors[0]
            actor['projectName'] = actor['project_name'] = ''
            if table == 'cable_journal' and actor['role'] in deps['worker_roles']:
                raise HTTPException(403, 'Нет прав на кабельный журнал')
            where, values = ['j.company_id=%s'], [actor['companyId']]
            allowed = deps['visible_projects'](actor)
            if allowed is not None:
                where.append('p.name = ANY(%s)')
                values.append(allowed)
                # Name-based assignments cannot disambiguate same-company objects.
                where.append('(SELECT count(*) FROM projects other WHERE other.company_id=p.company_id AND other.name=p.name)=1')
            package_sql, package_values = deps['package_filter'](actor, 'j.work_package')
            if project_name:
                where.append('p.name=%s')
                values.append(project_name)
            if write:
                where.append('j.id=%s')
                values.append(row_id)
            columns = ','.join('p.name AS project_name' if field == 'project_name' else 'j.'+field for field in FIELDS[table])
            cur.execute(f'''SELECT {columns} FROM {table} j JOIN projects p
                ON p.id=j.project_id AND p.company_id=j.company_id
                WHERE {' AND '.join(where)} {package_sql} ORDER BY j.id DESC
                LIMIT 5001''' + (' FOR UPDATE OF j' if write else ''), values + package_values)
            rows = cur.fetchall()
            if not write:
                if len(rows) > 5000:
                    raise HTTPException(409, 'Уточните объект: журнал содержит более 5000 записей')
                return [serialize(row, table) for row in rows]
            if not rows:
                raise HTTPException(404, 'Запись журнала не найдена в доступной области')
            old = serialize(rows[0], table)
            if old['status'] == 'Аннулирована':
                raise HTTPException(409, 'Аннулированную запись журнала нельзя изменять')
            snapshot = {'record': old, 'companyId': actor['companyId'], 'membershipId': locked_membership_id}
            if snapshot_only:
                return snapshot
            if expected_snapshot is not None and snapshot != expected_snapshot:
                raise HTTPException(409, 'Запись или права изменились во время подготовки подсказки; обновите журнал')
            if mark_ai and expected_snapshot is None:
                raise HTTPException(409, 'Не подтверждён исходный снимок журнала')
            editable = {camel(field): field for field in EDITABLE[table]}
            sets, params = [], []
            for key, value in (data or {}).items():
                if key not in editable:
                    if key not in old or value != old[key]:
                        raise HTTPException(409, 'Принадлежность и данные приёмки нельзя менять через журнал')
                    continue
                field = editable[key]
                value = validate_value(field, value)
                sets.append(field+'=%s')
                params.append(value)
            if sets:
                cur.execute(f"UPDATE {table} SET {','.join(sets)},ai_filled=%s WHERE id=%s AND company_id=%s AND project_id=%s",
                    params + [bool(mark_ai), row_id, actor['companyId'], rows[0]['project_id']])
            conn.commit()
            return {'ok': True}
    except DatabaseError:
        raise HTTPException(503, 'Журнал временно недоступен; повторите операцию') from None
    finally:
        # Also ends successful read-only work and any failed write transaction.
        try:
            if not conn.closed:
                conn.rollback()
        finally:
            conn.close()


def validate_value(field, value):
    if field in BOOLEANS:
        if type(value) is not bool:
            raise HTTPException(400, 'Требуется логическое значение')
    elif field in NUMBERS:
        try:
            number = Decimal(str(value))
            if not number.is_finite() or number < 0:
                raise ValueError()
            limit = Decimal('1000000') if field.startswith('insulation_') else Decimal('100000000')
            if number >= limit or number != number.quantize(Decimal('.01')):
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise HTTPException(400, 'Некорректное числовое значение')
        value = number
    elif field in DATES:
        if value is None or value == '':
            return None
        try:
            datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise HTTPException(400, 'Некорректная дата')
    elif not isinstance(value, str) or len(value) > (50 if field == 'visual_inspection_result' else 100 if field in SHORT_TEXT else 255 if field in MEDIUM_TEXT else 4000):
        raise HTTPException(400, 'Некорректное текстовое значение')
    return value
