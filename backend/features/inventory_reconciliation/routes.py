from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from . import policy, service, snapshot
from ..material_traceability.guards import lock_distribution_compatible_stock
from ..work_material_accounting import runtime
from ..work_material_accounting.access import lock_actor


def register_inventory_reconciliation(app, deps, selected_actor):
    get_user = deps.get('get_current_user') or deps['require_roles'](*policy.READERS)

    def listing(cur, actor):
        cur.execute('SELECT id,name FROM projects WHERE company_id=%s AND NOT COALESCE(archived,FALSE) ORDER BY name,id',
                    (actor['companyId'],))
        projects = [dict(r) for r in cur.fetchall()
                    if actor['role'] != 'прораб' or r['name'] in deps['user_project_names'](actor)]
        project_ids = [p['id'] for p in projects]
        extra = ' AND i.project_id=ANY(%s)' if actor['role'] == 'прораб' else ''
        cur.execute('''SELECT i.id,i.project,i.date,i.status,i.notes,(r.inventory_id IS NULL) AS legacy
            FROM inventory i LEFT JOIN inventory_reconciliations r ON r.inventory_id=i.id
            WHERE i.company_id=%s''' + extra + ' ORDER BY i.id DESC LIMIT 501',
            [actor['companyId'], *([project_ids] if extra else [])])
        rows = [dict(r) for r in cur.fetchall()]
        return {'items': rows[:500], 'truncated': len(rows) > 500, 'projects': projects,
                'canCreate': policy.enabled() and actor['role'] in policy.COUNTERS,
                'canCountMain': actor['role'] != 'прораб'}

    def legacy_view(cur, inventory_id, actor):
        cur.execute('SELECT * FROM inventory WHERE id=%s AND company_id=%s', (inventory_id, actor['companyId']))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Ведомость не найдена')
        snapshot.project(cur, row['project_id'], actor, deps)
        cur.execute('SELECT * FROM inventory_items WHERE inventory_id=%s AND company_id=%s ORDER BY id',
                    (inventory_id, actor['companyId']))
        rows = [{**dict(r), 'key': f'legacy:{r["id"]}', 'kind': 'material', 'name': r['material_name']} for r in cur.fetchall()]
        return {'inventory': {**dict(row), 'legacy': True}, 'rows': rows, 'history': [], 'canCount': False, 'canDecide': False}

    def run(user, company, mode, inventory_id=None, data=None):
        if inventory_id is not None and not 0 < inventory_id <= 2147483647:
            raise HTTPException(400, 'Некорректный номер ведомости')
        if data is not None and not policy.enabled():
            raise HTTPException(404, 'Операции инвентаризации временно недоступны')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if not policy.schema_present(cur):
                    raise HTTPException(404, 'Новая инвентаризация ещё не включена')
                _, actor, company_id = selected_actor(cur, user, 'read' if data is None else 'update', company, mode,
                                                      policy.READERS if data is None else policy.COUNTERS)
                actor = {**actor, 'companyId': company_id}
                lock_actor(cur, actor)
                lock_distribution_compatible_stock(cur)
                if data is None:
                    if inventory_id is None:
                        result = listing(cur, actor)
                    else:
                        cur.execute('SELECT 1 FROM inventory_reconciliations WHERE inventory_id=%s AND company_id=%s',
                                    (inventory_id, company_id))
                        result = service.view(cur, service.load(cur, inventory_id, actor, deps), actor) if cur.fetchone() else legacy_view(cur, inventory_id, actor)
                else:
                    allowed = {'requestId', 'expectedCompanyId', 'expectedActorId', 'materialAccountingVersion'}
                    allowed |= {'action', 'expectedState', 'counts', 'reason', 'lotDeductions'} if inventory_id is not None else {'projectId', 'notes'}
                    if set(data) - allowed or (inventory_id is None and 'projectId' not in data):
                        raise HTTPException(400, 'Переданы неизвестные поля или не выбрано место сверки')
                    session = service.load(cur, inventory_id, actor, deps) if inventory_id is not None else None
                    operation_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), 'inventory-reconciliation',
                                                                  {'inventoryId': inventory_id, 'data': data})
                    if replay is not None:
                        conn.commit()
                        return replay
                    result = service.command(cur, session, actor, data, operation_id, deps) if session else service.create(cur, actor, data, operation_id, deps)
                    runtime.finish_operation(cur, operation_id, result)
                conn.commit()
                return result
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode in ('40P01', '40001', '55P03', '23505'):
                raise HTTPException(409, 'Сверка занята другой операцией. Повторите исходную отправку') from error
            raise
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/inventory/reconciliation')
    def list_inventory(x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                       x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode)

    @app.post('/inventory/reconciliation')
    def create_inventory(data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                         x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, data=data)

    @app.get('/inventory/{inventory_id}/reconciliation')
    def read_inventory(inventory_id: int, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                       x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, inventory_id)

    @app.post('/inventory/{inventory_id}/reconciliation')
    def command(inventory_id: int, data: dict, x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'), user: dict = Depends(get_user)):
        return run(user, x_company_id, x_company_mode, inventory_id, data)
