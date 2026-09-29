from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from . import access, policy, records, service
from ..material_traceability.guards import lock_distribution_compatible_stock
from ..work_material_accounting import runtime
from ..work_material_accounting.access import lock_actor


def register_tool_custody(app, deps, selected_actor):
    get_user = deps.get('get_current_user') or deps['require_roles'](*policy.READERS)

    def run(tool_id, user, company, mode, data=None, incident_id=None):
        if data is not None and not policy.enabled():
            raise HTTPException(404, 'Операции инструмента временно недоступны')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if not policy.schema_present(cur):
                    raise HTTPException(404, 'Учёт инструмента ещё не включён')
                roles = policy.READERS if data is None else (policy.READERS if incident_id else policy.MANAGERS)
                _, actor, company_id = selected_actor(cur, user, 'read' if data is None else 'update', company, mode, roles)
                actor = {**actor, 'companyId': company_id}
                lock_actor(cur, actor)
                recipient = None
                if data and (data.get('action') == 'issue' or
                             (data.get('action') == 'reconcile' and data.get('reconciledStatus') == 'У мастера')):
                    recipient = access.recipient(cur, data.get('recipientId'), company_id, lock=True)
                lock_distribution_compatible_stock(cur)
                tool = access.require_tool(cur, tool_id, actor, deps)
                if data is None:
                    holder_id = actor['id'] if actor['role'] in policy.WORKERS else None
                    project_ids = None
                    if actor['role'] == 'прораб':
                        cur.execute('SELECT id FROM projects WHERE company_id=%s AND name=ANY(%s)',
                                    (company_id, deps['user_project_names'](actor)))
                        project_ids = [row['id'] for row in cur.fetchall()]
                    result = {'tool': records.response(tool), 'expectedState': policy.state(tool),
                        'needsReconciliation': policy.needs_reconciliation(tool),
                        'history': records.history(cur, tool_id, company_id, holder_id, project_ids),
                        'incidents': records.incidents(cur, tool_id, company_id, holder_id, project_ids),
                        'canManage': actor['role'] in policy.MANAGERS and policy.enabled(),
                        'canDecide': actor['role'] in policy.DIRECTORS and policy.enabled(),
                        'canDispute': actor['role'] in (*policy.DIRECTORS, *policy.WORKERS) and policy.enabled(),
                        'choices': access.choices(cur, actor, deps) if actor['role'] in policy.MANAGERS else {}}
                    if holder_id and tool['master_id'] != holder_id:
                        # A former holder may follow their incident, never the next holder's identity.
                        result['tool'] = {key: result['tool'][key] for key in ('id', 'name', 'inventoryNumber', 'companyId')}
                else:
                    if incident_id and actor['role'] not in (*policy.MANAGERS, *policy.WORKERS):
                        raise HTTPException(403, 'Роль не позволяет принимать решения по происшествию')
                    operation_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'),
                        'tool-decision' if incident_id else 'tool-custody',
                        {'toolId': tool_id, 'incidentId': incident_id, 'data': data})
                    if replay is not None:
                        conn.commit()
                        return replay
                    result = (service.decide(cur, tool, actor, operation_id, incident_id, data, deps) if incident_id
                              else service.command(cur, tool, actor, operation_id, data, deps, recipient))
                    runtime.finish_operation(cur, operation_id, result)
                conn.commit()
                return result
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode in ('40P01', '40001', '55P03', '23505'):
                raise HTTPException(409, 'Инструмент занят другой операцией. Повторите исходную отправку') from error
            raise
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/tools/{tool_id}/custody')
    def read(tool_id: int,
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
             user: dict = Depends(get_user)):
        return run(tool_id, user, x_company_id, x_company_mode)

    @app.post('/tools/{tool_id}/custody')
    def command(tool_id: int, data: dict,
                x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
                user: dict = Depends(get_user)):
        return run(tool_id, user, x_company_id, x_company_mode, data)

    @app.post('/tools/{tool_id}/incidents/{incident_id}/decisions')
    def decide(tool_id: int, incident_id: int, data: dict,
               x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
               user: dict = Depends(get_user)):
        return run(tool_id, user, x_company_id, x_company_mode, data, incident_id)
