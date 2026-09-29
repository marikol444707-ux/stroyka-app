from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2.extras import RealDictCursor

from . import runtime, settlement

FINANCE = ('директор', 'зам_директора', 'бухгалтер')
READERS = (*FINANCE, 'прораб', 'главный_инженер', 'сметчик', 'мастер', 'бригадир', 'субподрядчик')


def register_contract_settlement(app, deps):
    get_current_user = deps['get_current_user']

    def run(contract_id, user, company, mode, action=None, data=None, act_id=None, start=None, end=None):
        if action and not runtime.enabled():
            raise HTTPException(404, 'Новый учёт актов пока недоступен')
        conn = deps['get_db']()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                roles = FINANCE if action else READERS
                deps['lock_actor'](cur, user, contract_id, roles, company, mode)
                contract, actor, project = deps['resolve_contract'](cur, user, contract_id, roles,
                    x_company_id=company, x_company_mode=mode, for_update=True)
                if not deps['has_package_access'](actor, contract['workPackage']):
                    raise HTTPException(403, 'Нет доступа к пакету договора')
                if actor['role'] in ('мастер', 'бригадир', 'субподрядчик') and contract['contractorId'] != actor['id']:
                    raise HTTPException(404, 'Договор не найден')
                if not action:
                    if start or end:
                        start, end = settlement.period({'periodFrom': start, 'periodTo': end})
                    result = settlement.preview(cur, contract, start=start, end=end)
                    result.update(contractId=contract_id, projectId=project['id'],
                        canManage=actor['role'] in FINANCE and runtime.enabled())
                else:
                    operation_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), action,
                        {'contractId': contract_id, 'actId': act_id, 'data': data})
                    if replay is not None:
                        conn.commit()
                        return replay
                    if action == 'contract-act':
                        result = settlement.create_act(cur, contract, actor, operation_id, data)
                    else:
                        result = settlement.sign(cur, contract, actor, operation_id, act_id, data)
                    runtime.finish_operation(cur, operation_id, result)
                conn.commit()
                return result
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get('/brigade-contracts/{contract_id}/settlement')
    def read(contract_id: int, periodFrom: Optional[str] = None, periodTo: Optional[str] = None,
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
             user: dict = Depends(get_current_user)):
        return run(contract_id, user, x_company_id, x_company_mode, start=periodFrom, end=periodTo)

    @app.post('/brigade-contracts/{contract_id}/acts')
    def create(contract_id: int, data: dict,
               x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
               x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
               user: dict = Depends(get_current_user)):
        return run(contract_id, user, x_company_id, x_company_mode, 'contract-act', data)

    @app.post('/brigade-contracts/{contract_id}/acts/{act_id}/signature')
    def sign(contract_id: int, act_id: int, data: dict,
             x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
             x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
             user: dict = Depends(get_current_user)):
        return run(contract_id, user, x_company_id, x_company_mode, 'contract-act-signature', data, act_id)
