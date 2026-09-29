"""Authenticated selected-company templates with retryable commands."""
from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from . import service
from ..work_material_accounting import runtime
from ..work_material_accounting.access import lock_actor


def register_supply_request_templates_module(app, deps):
    get_user = deps['get_current_user']

    def run(user, company, mode, data=None, template_id=None, legacy=False):
        if template_id is not None and not 0 < template_id <= 2147483647:
            raise HTTPException(400, 'Некорректный номер шаблона')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                context = deps['resolve_work_company_context'](cur, user, None, 'read' if data is None else 'write',
                                                               x_company_id=company, x_company_mode=mode)
                if context.get('mode') != 'company':
                    if legacy:
                        return []
                    raise HTTPException(409, 'Выберите компанию для работы с шаблонами')
                actors = deps['effective_company_actors'](user, context)
                actor = {**actors[0], 'companyId': context['companyId']} if len(actors) == 1 else {}
                if actor.get('role') not in (service.READERS if data is None else service.WRITERS):
                    raise HTTPException(403, 'Роль в выбранной компании не позволяет выполнить действие')
                lock_actor(cur, actor)
                cur.execute("SELECT to_regclass('supply_template_events') AS present")
                if not cur.fetchone()['present']:
                    if legacy:
                        return []
                    raise HTTPException(503, 'Шаблоны компании ещё не подготовлены')
                if data is None:
                    return service.listing(cur, actor, legacy)
                if not service.enabled():
                    raise HTTPException(409, 'Изменения шаблонов временно отключены')
                for field in ('expectedCompanyId', 'expectedActorId'):
                    if type(data.get(field)) is not int or data[field] <= 0:
                        raise HTTPException(400, 'Откройте обновлённую форму в выбранной компании')
                if template_id is not None and actor['role'] not in service.DIRECTORS:
                    raise HTTPException(403, 'Архивировать шаблоны может руководитель компании')
                cur.execute('SELECT pg_advisory_xact_lock(178992,%s)', (actor['companyId'],))
                operation_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), 'supply-template',
                                                              {'templateId': template_id, 'data': data})
                if replay is not None:
                    conn.commit()
                    return replay
                result = service.command(cur, actor, template_id, data, operation_id)
                runtime.finish_operation(cur, operation_id, result)
                conn.commit()
                return result
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode == '23505':
                raise HTTPException(409, 'В компании уже есть действующий шаблон с таким названием') from error
            if error.pgcode in ('40P01', '40001', '55P03'):
                raise HTTPException(409, 'Шаблоны меняет другой пользователь. Повторите исходную отправку') from error
            raise
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/supply-request-templates')
    def listing(x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, legacy=True)

    @app.get('/supply-request-templates/catalog')
    def catalog(x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode)

    @app.post('/supply-request-templates')
    def create(data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, data=data)

    @app.post('/supply-request-templates/{id}/archive')
    def archive(id: int, data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, data=data, template_id=id)

    @app.delete('/supply-request-templates/{id}')
    def legacy_delete(user: dict = Depends(get_user)):
        raise HTTPException(409, 'Откройте обновлённую форму и перенесите шаблон в архив')
