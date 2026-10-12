"""An assigned diagnostic reader, never a buyer impersonation or general session.

Lock order: company -> actors (sorted) -> ticket -> grant. Revocation waits for
an already authorized read to commit; after it returns no new read can succeed.
"""
import os
import re
import uuid
from contextlib import contextmanager
from typing import Literal

from fastapi import Depends, HTTPException, Query, Response
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, conint, constr

from .service import ADMIN_ROLES, ready
from .reasons import REASONS

Id = conint(strict=True, ge=1, le=2147483647)
Reason = constr(strip_whitespace=True, min_length=5, max_length=1000)


class Grant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assigneeId: Id
    action: Literal['diagnostic.read']
    expiresInMinutes: conint(strict=True, ge=1, le=1440)
    reason: Reason


class Revocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: Reason


def enabled():
    return os.getenv('PARTICIPANT_SUPPORT_ACCESS_ENABLED', '0') == '1'


def enforce_support_route(user, request):
    """When enabled, support has a dedicated workspace, including direct URLs.

    Existing administrator/owner roles retain their ordinary independent rights.
    Public routes and auth logout/CSRF remain public/authenticated as before.
    """
    if not enabled() or user.get('role') != 'platform_support':
        return
    path = request.url.path.rstrip('/')
    allowed = path == '/participant-support/workspace' or bool(re.fullmatch(
        r'/participant-support/workspace/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}/diagnostic', path))
    if request.method != 'GET' or not allowed:
        raise HTTPException(403, 'Поддержке доступны только назначенные обращения')


@contextmanager
def transaction(deps):
    conn = deps['get_db']()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'; SET LOCAL lock_timeout='3s'")
            ready(cur)
            if not enabled():
                raise HTTPException(503, 'Доступ поддержки пока не включён')
            cur.execute("SELECT to_regclass('public.participant_support_access') AS grants, to_regclass('public.participant_support_access_events') AS events")
            if not all(cur.fetchone().values()):
                raise HTTPException(503, 'Доступ поддержки требует обновления схемы')
            yield cur
            conn.commit()
    except (errors.DeadlockDetected, errors.SerializationFailure, errors.LockNotAvailable, errors.QueryCanceled):
        conn.rollback()
        raise HTTPException(409, 'Доступ сейчас изменяется. Обновите обращение')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def company(cur, cid):
    cur.execute('SELECT id,name,platform_account_id,active FROM companies WHERE id=%s FOR SHARE', (cid,))
    row = cur.fetchone()
    if not row or not row['platform_account_id'] or row['active'] is False:
        raise HTTPException(404, 'Организация недоступна')
    return row


def actors(cur, ids, *, lock=True):
    cur.execute('SELECT id,name,role,active,supplier_team_epoch FROM users WHERE id=ANY(%s) ORDER BY id' + (' FOR SHARE' if lock else ''), (sorted(set(ids)),))
    return {r['id']: r for r in cur.fetchall()}


def administrator(row):
    return row and row['active'] is not False and row['role'] in ADMIN_ROLES


def ticket(cur, owner, tid, *, write=False):
    cur.execute('SELECT * FROM participant_access_tickets WHERE id=%s AND company_id=%s AND platform_account_id=%s' +
                (' FOR UPDATE' if write else ' FOR SHARE'), (tid, owner['id'], owner['platform_account_id']))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Обращение недоступно')
    return row


def event(cur, grant, actor_id, action):
    cur.execute('''INSERT INTO participant_support_access_events(access_id,company_id,platform_account_id,ticket_id,actor_id,action)
        VALUES(%s,%s,%s,%s,%s,%s)''', (str(grant['id']), grant['company_id'], grant['platform_account_id'], grant['ticket_id'], actor_id, action))


def view(grant):
    return dict(id=str(grant['id']), companyId=grant['company_id'], ticketId=grant['ticket_id'],
                assigneeId=grant['assignee_id'], action=grant['action'], expiresAt=grant['expires_at'],
                revokedAt=grant['revoked_at'], reason=grant['reason'])


def grant_access(deps, user, cid, tid, data):
    with transaction(deps) as cur:
        owner = company(cur, cid)
        people = actors(cur, [user['id'], data.assigneeId])
        issuer, assignee = people.get(user['id']), people.get(data.assigneeId)
        if not administrator(issuer):
            raise HTTPException(403, 'Полномочия администратора изменились')
        if not assignee or assignee['active'] is False or assignee['role'] != 'platform_support':
            raise HTTPException(422, 'Выберите действующего сотрудника поддержки')
        current = ticket(cur, owner, tid, write=True)
        if current['status'] == 'closed':
            raise HTTPException(409, 'Обращение закрыто. Сначала верните его в работу')
        # Serialized by the ticket; reissue cannot extend/resurrect an old grant.
        cur.execute('''UPDATE participant_support_access SET revoked_at=clock_timestamp(),revoked_by=%s,revoke_reason='Выдан новый доступ'
            WHERE company_id=%s AND ticket_id=%s AND assignee_id=%s AND revoked_at IS NULL RETURNING *''', (user['id'], cid, tid, data.assigneeId))
        for old in cur.fetchall():
            event(cur, old, user['id'], 'revoked')
        cur.execute('''INSERT INTO participant_support_access
            (id,company_id,platform_account_id,ticket_id,ticket_version,assignee_id,assignee_epoch,issuer_id,issuer_epoch,action,reason,expires_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()+%s*INTERVAL '1 minute') RETURNING *''',
            (str(uuid.uuid4()), cid, owner['platform_account_id'], tid, current['version'], data.assigneeId,
             assignee['supplier_team_epoch'], user['id'], issuer['supplier_team_epoch'], data.action, data.reason, data.expiresInMinutes))
        grant = cur.fetchone()
        event(cur, grant, user['id'], 'granted')
        return view(grant)


def revoke_access(deps, user, cid, tid, access_id, data):
    with transaction(deps) as cur:
        owner = company(cur, cid)
        if not administrator(actors(cur, [user['id']]).get(user['id'])):
            raise HTTPException(403, 'Полномочия администратора изменились')
        ticket(cur, owner, tid)
        cur.execute('SELECT * FROM participant_support_access WHERE id=%s AND company_id=%s AND platform_account_id=%s AND ticket_id=%s FOR UPDATE',
                    (str(access_id), cid, owner['platform_account_id'], tid))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Доступ недоступен в этом обращении')
        if not row['revoked_at']:
            cur.execute('UPDATE participant_support_access SET revoked_at=clock_timestamp(),revoked_by=%s,revoke_reason=%s WHERE id=%s RETURNING *',
                        (user['id'], data.reason, str(access_id)))
            row = cur.fetchone()
            event(cur, row, user['id'], 'revoked')
        return view(row)


def valid(cur, grant, people, current):
    assignee, issuer = people.get(grant['assignee_id']), people.get(grant['issuer_id'])
    cur.execute('SELECT expires_at>clock_timestamp() AS valid FROM participant_support_access WHERE id=%s', (str(grant['id']),))
    return bool(grant['revoked_at'] is None and cur.fetchone()['valid'] and grant['action'] == 'diagnostic.read'
                and assignee and assignee['role'] == 'platform_support' and assignee['active'] is not False
                and assignee['supplier_team_epoch'] == grant['assignee_epoch'] and administrator(issuer)
                and issuer['supplier_team_epoch'] == grant['issuer_epoch'] and current['version'] == grant['ticket_version']
                and current['status'] != 'closed')


def authorized_grant(cur, user, access_id):
    if user.get('role') != 'platform_support':
        raise HTTPException(403, 'Доступ предназначен назначенному сотруднику поддержки')
    cur.execute('SELECT * FROM participant_support_access WHERE id=%s AND assignee_id=%s', (str(access_id), user['id']))
    hint = cur.fetchone()
    if not hint:
        raise HTTPException(404, 'Обращение недоступно')
    owner = company(cur, hint['company_id'])
    people = actors(cur, [hint['assignee_id'], hint['issuer_id']])
    current = ticket(cur, owner, hint['ticket_id'])
    cur.execute('SELECT * FROM participant_support_access WHERE id=%s FOR SHARE', (str(access_id),))
    grant = cur.fetchone()
    if not grant or not valid(cur, grant, people, current):
        raise HTTPException(403, 'Доступ закончился или изменился. Нужен новый доступ администратора')
    return grant, owner, current


def register_capabilities(app, deps, admin):
    authenticated = deps.get('authenticated') or deps['require_roles']('platform_support')
    base = '/system/companies/{company_id}/participant-tickets/{ticket_id}/support-access'

    @app.get('/system/companies/{company_id}/support-assignees')
    def assignees(company_id: int, user: dict = Depends(admin)):
        with transaction(deps) as cur:
            company(cur, company_id)
            if not administrator(actors(cur, [user['id']]).get(user['id'])):
                raise HTTPException(403, 'Полномочия администратора изменились')
            cur.execute("SELECT id,name FROM users WHERE role='platform_support' AND COALESCE(active,TRUE) ORDER BY name,id LIMIT 100")
            return dict(items=[dict(r) for r in cur.fetchall()])

    @app.post(base)
    def grant(company_id: int, ticket_id: int, data: Grant, user: dict = Depends(admin)):
        return grant_access(deps, user, company_id, ticket_id, data)

    @app.post(base + '/{access_id}/revoke')
    def revoke(company_id: int, ticket_id: int, access_id: uuid.UUID, data: Revocation, user: dict = Depends(admin)):
        return revoke_access(deps, user, company_id, ticket_id, access_id, data)

    @app.get(base)
    def history(company_id: int, ticket_id: int, response: Response, user: dict = Depends(admin), offset: int = Query(0, ge=0)):
        response.headers['Cache-Control'] = 'private, no-store'
        with transaction(deps) as cur:
            owner = company(cur, company_id)
            if not administrator(actors(cur, [user['id']]).get(user['id'])):
                raise HTTPException(403, 'Полномочия администратора изменились')
            current = ticket(cur, owner, ticket_id)
            cur.execute('''SELECT g.*,u.name AS assignee_name FROM participant_support_access g JOIN users u ON u.id=g.assignee_id
                WHERE g.company_id=%s AND g.platform_account_id=%s AND g.ticket_id=%s ORDER BY g.created_at DESC,g.id LIMIT 26 OFFSET %s''',
                (company_id, owner['platform_account_id'], ticket_id, offset))
            rows = cur.fetchall()
            items = []
            for row in rows[:25]:
                people = actors(cur, [row['assignee_id'], row['issuer_id']], lock=False)
                cur.execute('SELECT action,actor_id,created_at FROM participant_support_access_events WHERE access_id=%s ORDER BY id DESC LIMIT 25', (str(row['id']),))
                audit = list(reversed([dict(e) for e in cur.fetchall()]))
                items.append(dict(view(row), assigneeName=row['assignee_name'], active=valid(cur, row, people, current), history=audit))
            return dict(items=items, hasMore=len(rows)>25)

    @app.get('/participant-support/workspace')
    def workspace(response: Response, user: dict = Depends(authenticated), offset: int = Query(0, ge=0)):
        response.headers['Cache-Control'] = 'private, no-store'
        if user.get('role') != 'platform_support':
            raise HTTPException(403, 'Раздел доступен сотруднику поддержки')
        with transaction(deps) as cur:
            # Scan bounded candidates; each is reauthorized and audited under locks.
            cur.execute('''SELECT g.id FROM participant_support_access g
                JOIN users a ON a.id=g.assignee_id JOIN users i ON i.id=g.issuer_id
                JOIN participant_access_tickets t ON t.id=g.ticket_id JOIN companies c ON c.id=g.company_id
                WHERE g.assignee_id=%s AND g.revoked_at IS NULL AND g.expires_at>clock_timestamp()
                AND a.role='platform_support' AND COALESCE(a.active,TRUE) AND a.supplier_team_epoch=g.assignee_epoch
                AND i.role IN ('system_owner','platform_admin') AND COALESCE(i.active,TRUE) AND i.supplier_team_epoch=g.issuer_epoch
                AND t.version=g.ticket_version AND t.status<>'closed' AND COALESCE(c.active,TRUE)
                ORDER BY g.company_id,g.ticket_id,g.id LIMIT 26 OFFSET %s''', (user['id'], offset))
            candidates = cur.fetchall()
            items = []
            for candidate in candidates[:25]:
                # A concurrent revoke may finish between discovery and locks.
                cur.execute('SAVEPOINT access_candidate')
                try:
                    grant, owner, current = authorized_grant(cur, user, candidate['id'])
                except HTTPException as exc:
                    cur.execute('ROLLBACK TO SAVEPOINT access_candidate')
                    if exc.status_code not in (403,404):
                        raise
                    continue
                event(cur, grant, user['id'], 'listed')
                items.append(dict(view(grant), companyName=owner['name'], status=current['status'],
                                  reasonLabel=REASONS.get(current['reason_code'], ('Проверка доступа',))[0]))
            return dict(items=items, hasMore=len(candidates)>25)

    @app.get('/participant-support/workspace/{access_id}/diagnostic')
    def diagnostic(access_id: uuid.UUID, response: Response, user: dict = Depends(authenticated)):
        response.headers['Cache-Control'] = 'private, no-store'
        with transaction(deps) as cur:
            grant, owner, current = authorized_grant(cur, user, access_id)
            cur.execute('SELECT context FROM participant_access_diagnostics WHERE id=%s AND company_id=%s AND platform_account_id=%s',
                        (current['diagnostic_id'], owner['id'], owner['platform_account_id']))
            evidence = cur.fetchone()
            if not evidence:
                raise HTTPException(404, 'Диагностика недоступна')
            allowed = ('participantName','sourceType','relationshipVersion','role','screen','action','applicationVersion')
            result = dict(view(grant), companyName=owner['name'], status=current['status'],
                          reasonCode=current['reason_code'], reasonLabel=REASONS.get(current['reason_code'], ('Проверка доступа',))[0],
                          comment=current['comment'], result=current['result'],
                          context={key:evidence['context'][key] for key in allowed if key in evidence['context']})
            event(cur, grant, user['id'], 'diagnostic.read')
            return result
