from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2.extras import RealDictCursor

from . import corrections, defects, records, runtime

DIRECTORS = ('директор', 'зам_директора')
REVIEWERS = (*DIRECTORS, 'прораб', 'главный_инженер')
WORKERS = ('мастер', 'субподрядчик', 'бригадир')
READERS = (*REVIEWERS, *WORKERS, 'бухгалтер', 'сметчик')


def register_material_accounting(app, deps):
    get_current_user = deps['get_current_user']

    def run(journal_id, user, company, mode, roles, action=None, data=None, defect_id=None):
        if action and not runtime.enabled():
            raise HTTPException(404, 'Новый учёт расхода пока недоступен')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                actor, project, work = deps['resolve_mutation'](cur, user, journal_id,
                    'update' if action else 'read', company, mode, roles, require_membership=True)
                if not deps['has_package_access'](actor, work['work_package']):
                    raise HTTPException(403, 'Нет доступа к пакету работ')
                if actor['role'] in WORKERS and work['master_id'] != actor['id']:
                    raise HTTPException(404, 'Запись журнала не найдена')
                owner = records.account(cur, journal_id, project['companyId'])
                if not action:
                    result = records.report(cur, journal_id, project['companyId'])
                    result['canCorrect'] = actor['role'] in DIRECTORS
                    result['canRecordDefect'] = actor['role'] in REVIEWERS
                    result['canConfirmDefect'] = actor['role'] in DIRECTORS
                    conn.commit()
                    return result
                if action == 'defect-decision' and data.get('decision') != 'disputed' and actor['role'] not in DIRECTORS:
                    raise HTTPException(403, 'Денежную ответственность подтверждает директор')
                op_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), action,
                    {'journalId': journal_id, 'defectId': defect_id, 'data': data})
                if replay is not None:
                    conn.commit()
                    return replay
                if action == 'material-correction':
                    result = corrections.correct(cur, owner, project, actor, op_id, data, deps['personal_balance'])
                elif action == 'material-defect':
                    result = defects.create(cur, owner, actor, op_id, data)
                else:
                    result = defects.decide(cur, owner, actor, op_id, defect_id, data)
                result = {'ok': True, **result}
                runtime.finish_operation(cur, op_id, result)
                conn.commit()
                return result
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/work-journal/{journal_id}/material-accounting')
    def read(journal_id: int,
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
             user: dict = Depends(get_current_user)):
        return run(journal_id, user, x_company_id, x_company_mode, READERS)

    @app.post('/work-journal/{journal_id}/material-corrections')
    def correct(journal_id: int, data: dict,
                x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
                user: dict = Depends(get_current_user)):
        return run(journal_id, user, x_company_id, x_company_mode, DIRECTORS, 'material-correction', data)

    @app.post('/work-journal/{journal_id}/material-defects')
    def record_defect(journal_id: int, data: dict,
                      x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                      x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
                      user: dict = Depends(get_current_user)):
        return run(journal_id, user, x_company_id, x_company_mode, REVIEWERS, 'material-defect', data)

    @app.post('/work-journal/{journal_id}/material-defects/{defect_id}/decisions')
    def decide_defect(journal_id: int, defect_id: int, data: dict,
                      x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                      x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
                      user: dict = Depends(get_current_user)):
        return run(journal_id, user, x_company_id, x_company_mode, (*REVIEWERS, *WORKERS), 'defect-decision', data, defect_id)
