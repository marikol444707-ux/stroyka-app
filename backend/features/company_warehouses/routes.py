"""Selected-company directory with versioned commands and permanent legacy guards."""
from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from . import service
from ..work_material_accounting import runtime
from ..work_material_accounting.access import lock_actor


def register_company_warehouses(app, deps):
    get_user = deps['get_current_user']

    def run(user, company, mode, warehouse_id=None, data=None, legacy=False):
        if warehouse_id is not None and not 0 < warehouse_id <= 2147483647:
            raise HTTPException(400, 'Некорректный номер склада')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                context = deps['resolve_work_company_context'](cur, user, None, 'read' if data is None else 'write',
                                                               x_company_id=company, x_company_mode=mode)
                if context.get('mode') != 'company':
                    if legacy:
                        return []
                    raise HTTPException(409, 'Выберите компанию для работы со складами')
                actors = deps['effective_company_actors'](user, context)
                actor = {**actors[0], 'companyId': context['companyId']} if len(actors) == 1 else {}
                if actor.get('role') not in (service.READERS if data is None else service.WRITERS):
                    raise HTTPException(403, 'Роль в выбранной компании не позволяет выполнить действие')
                lock_actor(cur, actor)
                cur.execute("SELECT to_regclass('warehouse_directory_events') AS present")
                if not cur.fetchone()['present']:
                    if legacy:
                        return []
                    raise HTTPException(503, 'Каталог складов ещё не подготовлен')
                if data is not None:
                    if not service.enabled():
                        raise HTTPException(409, 'Изменения каталога временно отключены')
                    cur.execute('SELECT pg_advisory_xact_lock(178991,%s)', (actor['companyId'],))
                card = service.load(cur, warehouse_id, actor['companyId']) if warehouse_id is not None else None
                if data is None:
                    result = service.detail(cur, card, actor) if card else service.listing(cur, actor, legacy)
                else:
                    operation_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), 'company-warehouse',
                                                                  {'warehouseId': warehouse_id, 'data': data})
                    if replay is not None:
                        conn.commit()
                        return replay
                    result = service.command(cur, actor, card, data, operation_id)
                    runtime.finish_operation(cur, operation_id, result)
                conn.commit()
                return result
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode == '23505':
                raise HTTPException(409, 'В компании уже есть действующий склад с таким названием') from error
            if error.pgcode in ('40P01', '40001', '55P03'):
                raise HTTPException(409, 'Карточку меняет другой пользователь. Повторите исходную отправку') from error
            raise
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/warehouses')
    def legacy_list(x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                    x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, legacy=True)

    @app.post('/warehouses')
    @app.put('/warehouses/{id}')
    @app.delete('/warehouses/{id}')
    def legacy_write(user: dict = Depends(get_user)):
        raise HTTPException(409, 'Откройте обновлённый каталог складов. Прежнее изменение и удаление закрыты')

    @app.get('/warehouses/directory')
    def listing(x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode)

    @app.post('/warehouses/directory')
    def create(data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, data=data)

    @app.get('/warehouses/{warehouse_id}/directory')
    def detail(warehouse_id: int, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, warehouse_id)

    @app.post('/warehouses/{warehouse_id}/directory')
    def command(warehouse_id: int, data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, warehouse_id, data)
