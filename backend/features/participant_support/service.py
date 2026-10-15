"""Failure evidence is saved after the rejected invitation transaction rolls back."""
import os
import uuid
from pathlib import Path
from contextlib import contextmanager

import psycopg2.extras
from fastapi import HTTPException
from psycopg2.extras import Json

from .reasons import REASONS
from ..invite_codes.supplier_relationship import directory
from ..runtime_version.service import app_version

ADMIN_ROLES = ('system_owner', 'platform_admin')


def enabled():
    return os.getenv('PARTICIPANT_SUPPORT_ENABLED', '0') == '1'


def ready(cur):
    if not enabled():
        raise HTTPException(503, 'Раздел обращений пока не включён')
    cur.execute("SELECT to_regclass('public.participant_access_tickets') AS relation")
    if not cur.fetchone()['relation']:
        raise HTTPException(503, 'Раздел обращений требует обновления схемы')


def record_failure(deps, user, headers, failure):
    with directory(deps).transaction(user, headers, write=True) as (cur, company, actor):
        ready(cur)
        if actor['role'] not in deps['admin_roles']:
            raise HTTPException(403, 'Обращение доступно руководителю организации')
        cur.execute('''SELECT s.name,l.source_type,l.version
            FROM company_supplier_links l JOIN suppliers s ON s.id=l.supplier_id
            WHERE l.company_id=%s AND l.platform_account_id=%s AND l.supplier_id=%s''',
            (company['id'], company['platform_account_id'], failure.supplier_id))
        link = cur.fetchone()
        if not link:
            raise HTTPException(404, 'Поставщик не найден в выбранной организации')
        # Serialize this reporter across organizations as well as this company.
        # The dedicated advisory namespace avoids unrelated application locks.
        cur.execute('SELECT pg_advisory_xact_lock(94001, %s)', (user['id'],))
        cur.execute('''SELECT id FROM participant_access_diagnostics WHERE company_id=%s
            AND reporter_id=%s AND participant_id=%s AND reason_code=%s
            AND created_at>NOW()-INTERVAL '5 minutes' AND expires_at>NOW()
            ORDER BY created_at DESC LIMIT 1''', (company['id'],user['id'],failure.supplier_id,failure.code))
        existing = cur.fetchone()
        if existing:
            return str(existing['id'])
        cur.execute("SELECT count(*) AS n FROM participant_access_diagnostics WHERE reporter_id=%s AND created_at>NOW()-INTERVAL '1 hour'", (user['id'],))
        if cur.fetchone()['n'] >= 20:
            raise HTTPException(429, 'Слишком много запросов помощи. Повторите позже')
        diagnostic_id = str(uuid.uuid4())
        # No request bodies, invite codes, credentials, contacts or other tenants.
        context = dict(participantName=link['name'], sourceType=link['source_type'] or 'unknown',
                       relationshipVersion=link['version'],
                       role=actor['role'], screen='supplier_invitation', action='create_supplier_invite',
                       applicationVersion=app_version(str(Path(__file__).resolve().parents[3]),os.environ))
        cur.execute('''INSERT INTO participant_access_diagnostics
            (id,company_id,platform_account_id,reporter_id,participant_type,participant_id,reason_code,context)
            VALUES(%s,%s,%s,%s,'supplier',%s,%s,%s)''',
            (diagnostic_id,company['id'],company['platform_account_id'],user['id'],failure.supplier_id,failure.code,Json(context)))
        return diagnostic_id


def create_ticket(deps, user, headers, data):
    if set(data) - {'diagnosticId','comment'}:
        raise HTTPException(422, 'Контекст обращения определяется сервером')
    try:
        diagnostic_id = str(uuid.UUID(str(data.get('diagnosticId'))))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Некорректное обращение')
    comment = data.get('comment', '')
    if not isinstance(comment,str) or not 5 <= len(comment.strip()) <= 2000:
        raise HTTPException(422, 'Опишите желаемый результат: от 5 до 2000 символов')
    with directory(deps).transaction(user, headers, write=True) as (cur, company, actor):
        ready(cur)
        if actor['role'] not in deps['admin_roles']:
            raise HTTPException(403, 'Обращение доступно руководителю организации')
        cur.execute('''SELECT * FROM participant_access_diagnostics WHERE id=%s
            AND company_id=%s AND platform_account_id=%s AND reporter_id=%s FOR UPDATE''',
            (diagnostic_id,company['id'],company['platform_account_id'],user['id']))
        evidence = cur.fetchone()
        if not evidence:
            raise HTTPException(404, 'Обращение недоступно')
        cur.execute('''SELECT id,status FROM participant_access_tickets WHERE company_id=%s AND reporter_id=%s
            AND participant_type=%s AND participant_id=%s AND reason_code=%s
            AND (diagnostic_id=%s OR status<>'closed') ORDER BY id DESC LIMIT 1''',
            (company['id'],user['id'],evidence['participant_type'],evidence['participant_id'],evidence['reason_code'],diagnostic_id))
        existing = cur.fetchone()
        if existing:
            return dict(existing, reused=True)
        cur.execute('SELECT expires_at>NOW() AS valid FROM participant_access_diagnostics WHERE id=%s', (diagnostic_id,))
        if not cur.fetchone()['valid']:
            raise HTTPException(409, 'Диагностика устарела. Повторите исходное действие')
        cur.execute('''INSERT INTO participant_access_tickets
            (diagnostic_id,company_id,platform_account_id,reporter_id,participant_type,participant_id,reason_code,comment)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,status''',
            (diagnostic_id,company['id'],company['platform_account_id'],user['id'],evidence['participant_type'],
             evidence['participant_id'],evidence['reason_code'],comment.strip()))
        ticket = dict(cur.fetchone())
        cur.execute("INSERT INTO participant_access_ticket_events(ticket_id,actor_id,to_status) VALUES(%s,%s,'new')", (ticket['id'],user['id']))
        return dict(ticket,reused=False)


@contextmanager
def admin_transaction(deps, user, company_id, *, snapshot=False):
    # Support session labels grant no authority here. Least privilege until stage 2.
    if user.get('role') not in ADMIN_ROLES:
        raise HTTPException(403, 'Раздел доступен администратору платформы')
    conn = deps['get_db']()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if snapshot:
                cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            cur.execute("SET LOCAL statement_timeout='15s'")
            ready(cur)
            cur.execute('SELECT id,platform_account_id FROM companies WHERE id=%s'+
                        ('' if snapshot else ' FOR SHARE'), (company_id,))
            company = cur.fetchone()
            if not company or not company['platform_account_id']:
                raise HTTPException(404, 'Организация недоступна')
            yield cur,company
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ticket_view(row, internal=False):
    item = dict(row)
    item['reason'] = REASONS.get(item['reason_code'], ('Нужна проверка доступа','Проверить доступ'))[0]
    if internal:
        item['recommendedAction'] = REASONS.get(item['reason_code'], ('','Проверить доступ'))[1]
    return item
