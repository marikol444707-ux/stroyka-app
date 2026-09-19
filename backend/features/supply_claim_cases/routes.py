"""Authenticated, versioned claim actions with exact retry recovery."""
from typing import Optional

from fastapi import Depends, Header, HTTPException, Response
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from . import access, service
from ..work_material_accounting import runtime


def register_supply_claim_cases_module(app, deps):
    get_user = deps['get_current_user']

    def run(user, company, mode, claim_id=None, data=None, legacy=False):
        if claim_id is not None and not 0 < claim_id <= 2147483647:
            raise HTTPException(400, 'Некорректный номер претензии')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if data is None:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                cur.execute("SET LOCAL statement_timeout='15s'")
                cur.execute("SELECT to_regclass('supply_claim_events') AS present")
                ready = bool(cur.fetchone()['present'])
                if not ready and not legacy:
                    raise HTTPException(503, 'Карточки претензий ещё не подготовлены')
                actor = None if legacy else access.selected_actor(cur, user, company, mode, deps, data is not None)
                rows = access.visible_rows(cur, user, company, mode, deps, claim_id, ready, None if legacy else 201)
                if legacy:
                    return rows
                if claim_id is None:
                    return {'items': rows[:200], 'truncated': len(rows) > 200}
                if not rows:
                    raise HTTPException(404, 'Претензия не найдена в доступных поставках')
                claim = rows[0]
                actor = {**actor, 'companyId': claim['companyId']}
                if data is None:
                    cur.execute('''SELECT id,actor_id AS "actorId",actor_name AS "actorName",action,text,
                        before_state AS "beforeState",after_state AS "afterState",created_at AS "createdAt"
                        FROM supply_claim_events WHERE claim_id=%s AND company_id=%s ORDER BY id DESC LIMIT 201''',
                        (claim_id, claim['companyId']))
                    history = [dict(row) for row in cur.fetchall()]
                    caps = service.capabilities(actor['role'], claim['status'])
                    return {'claim': claim, 'history': list(reversed(history[:200])), 'historyTruncated': len(history)>200,
                            **{key: value and service.enabled() for key, value in caps.items()}}
                if not service.enabled():
                    raise HTTPException(409, 'Изменения претензий временно отключены')
                action, _ = service.validate(data)
                # Authorize role before replay; state/version are checked only
                # for new commands so a successful closing command can replay.
                allowed = ('reply',) if actor['role'] == 'поставщик' else (
                    ('start','comment','resolve','reopen') if actor['role'] in service.DIRECTORS else
                    ('start','comment') if actor['role'] in service.WRITERS else ())
                if action not in allowed:
                    raise HTTPException(403, 'Роль не позволяет выполнить действие с претензией')
                access.pin(cur, actor, claim)
                cur.execute('SELECT pg_advisory_xact_lock(178993,%s)', (claim['companyId'],))
                access.lock_chain(cur, claim)
                current = access.visible_rows(cur, user, company, mode, deps, claim_id)
                if not current or any(current[0][key] != claim[key] for key in
                        ('companyId','deliveryId','requestId','offerId','supplierId','project','workPackage')):
                    raise HTTPException(403, 'Доступ к претензии изменился. Обновите список')
                operation_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), 'supply-claim-case',
                                                              {'claimId': claim_id, 'data': data})
                if replay is not None:
                    conn.commit()
                    return replay
                result = service.command(cur, current[0], actor, data, operation_id)
                runtime.finish_operation(cur, operation_id, result)
                conn.commit()
                return result
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode in ('23505', '40P01', '40001', '55P03'):
                raise HTTPException(409, 'Претензию меняет другой пользователь. Повторите исходную отправку') from error
            raise
        finally:
            conn.rollback()
            conn.close()

    @app.get('/supply-claims')
    def legacy_list(response: Response, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                    x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        response.headers['Cache-Control'] = 'no-store'
        return run(user, x_company_id, x_company_mode, legacy=True)

    @app.get('/supply-claims/cases')
    def listing(response: Response, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        response.headers['Cache-Control'] = 'no-store'
        return run(user, x_company_id, x_company_mode)

    @app.get('/supply-claims/{id}/case')
    def detail(id: int, response: Response, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        response.headers['Cache-Control'] = 'no-store'
        return run(user, x_company_id, x_company_mode, id)

    @app.post('/supply-claims/{id}/case')
    def command(id: int, data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, id, data)

    @app.put('/supply-claims/{id}')
    def old_update(user: dict = Depends(get_user)):
        raise HTTPException(409, 'Откройте карточку претензии и сохраните действие с историей')
