from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2.extras import RealDictCursor

from ..work_material_accounting import runtime
from . import records, service
from .policy import REVIEWERS, WORKERS, enabled

READERS = (*REVIEWERS, *WORKERS, 'бухгалтер', 'сметчик')


def register_work_acceptance(app, deps):
    def run(journal_id, user, company, mode, action=None, data=None):
        if action and not enabled():
            raise HTTPException(404, 'Приёмка с доработками пока недоступна')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                actor, project, scoped = deps['resolve_mutation'](cur, user, journal_id,
                    'update' if action else 'read', company, mode, READERS, require_membership=True)
                if not deps['has_package_access'](actor, scoped['work_package']):
                    raise HTTPException(403, 'Нет доступа к пакету работ')
                if actor['role'] in WORKERS and scoped['master_id'] != actor['id']:
                    raise HTTPException(403 if action == 'resubmit' else 404, 'Работа не назначена исполнителю')
                work = records.load(cur, journal_id, project['companyId'])
                if not action:
                    result = {**records.report(cur, work, actor), 'projectId': project['id']}
                else:
                    roles = REVIEWERS if action == 'acceptance' else WORKERS
                    if actor['role'] not in roles:
                        raise HTTPException(403, 'Недостаточно прав для этого действия')
                    op_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), 'work-' + action,
                        {'journalId': journal_id, 'data': data})
                    if replay is not None:
                        conn.commit()
                        return replay
                    result = service.execute(cur, work, project, actor, op_id, action, data, deps)
                    runtime.finish_operation(cur, op_id, result)
                conn.commit()
                return result
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/work-journal/{journal_id}/acceptance')
    def read(journal_id: int,
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
             user: dict = Depends(deps['get_current_user'])):
        return run(journal_id, user, x_company_id, x_company_mode)

    @app.post('/work-journal/{journal_id}/acceptance')
    def review(journal_id: int, data: dict,
               x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
               user: dict = Depends(deps['get_current_user'])):
        return run(journal_id, user, x_company_id, x_company_mode, 'acceptance', data)

    @app.post('/work-journal/{journal_id}/resubmit')
    def resubmit(journal_id: int, data: dict,
                 x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                 x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
                 user: dict = Depends(deps['get_current_user'])):
        return run(journal_id, user, x_company_id, x_company_mode, 'resubmit', data)
