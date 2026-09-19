from datetime import date

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from . import access, policy, records
from ..work_material_accounting.quantities import money

LABELS = {'issue': 'Выдача', 'return': 'Возврат', 'repair': 'Ремонт завершён',
          'recover': 'Найден', 'write_off': 'Списание', 'archive': 'Архивирование', 'reconcile': 'Уточнение прежней записи'}


def command(cur, tool, actor, operation_id, data, deps, recipient=None):
    if data.get('expectedState') != policy.state(tool):
        raise HTTPException(409, 'Инструмент изменился. Обновите карточку перед действием')
    action, condition = data.get('action'), data.get('condition', '')
    status = policy.next_status(tool, action, condition, actor['role'], data.get('reconciledStatus'))
    reason = policy.text(data, required=action != 'issue' and (action != 'return' or condition != 'good'))
    holder_id, holder_name = tool['master_id'], tool['master_name'] or ''
    project_id, project_name = tool['project_id'], tool['project'] or ''
    contract_id = tool.get('custody_contract_id')
    assigned = action == 'issue' or (action == 'reconcile' and status == 'У мастера')
    if action == 'reconcile':
        cur.execute('SELECT 1 FROM tool_custody_events WHERE tool_id=%s LIMIT 1', (tool['id'],))
        if cur.fetchone():
            raise HTTPException(409, 'У инструмента уже есть проведённые операции')
        holder_id, holder_name, project_id, project_name, contract_id = None, '', None, '', None
    if assigned:
        if recipient is None:
            raise HTTPException(400, 'Выберите исполнителя')
        target = access.project(cur, data.get('projectId'), actor, deps, issue=True)
        if target['name'] not in deps['user_project_names'](recipient):
            raise HTTPException(409, 'Исполнитель не назначен на выбранный объект')
        holder_id, holder_name = recipient['id'], recipient['name']
        project_id, project_name = target['id'], target['name']
        contract_id = data.get('contractId')
        if contract_id is not None:
            access.contract(cur, contract_id, actor['companyId'], project_id, holder_id)
    if action == 'return' and (not holder_id or not project_id):
        raise HTTPException(409, 'У прежней выдачи не указан точный получатель или объект. Требуется сверка назначения')
    if action == 'return':
        access.project(cur, project_id, actor, deps)
    location = 'У мастера' if assigned else ('Утерян' if status == 'Утерян' else 'Основной склад')
    cur.execute('''UPDATE tools SET status=%s,location=%s,project=%s,project_id=%s,owner_scope=%s,
        master_id=%s,master_name=%s,issue_type=%s,custody_contract_id=%s,custody_version=custody_version+1
        WHERE id=%s AND company_id=%s RETURNING *''',
        (status, location, project_name if assigned else '', project_id if assigned else None,
         'project' if assigned else 'company', holder_id if assigned else None, holder_name if assigned else '',
         'Временно' if assigned else '', contract_id if assigned else None, tool['id'], actor['companyId']))
    updated = dict(cur.fetchone())
    cur.execute('''INSERT INTO tool_custody_events(tool_id,company_id,project_id,holder_id,contract_id,
        operation_id,actor_id,actor_name,action,condition,reason,before_state,after_state)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (tool['id'], actor['companyId'], project_id, holder_id, contract_id, operation_id, actor['id'],
         actor.get('name') or '', action, condition, reason,
         Json(jsonable_encoder(records.response(tool))), Json(jsonable_encoder(records.response(updated)))))
    event_id = cur.fetchone()['id']
    incident_id = None
    if action == 'return' and condition in ('damaged', 'lost'):
        cur.execute('''INSERT INTO tool_incidents(company_id,tool_id,event_id,project_id,holder_id,contract_id,
            kind,reason,tool_name,holder_name) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (actor['companyId'], tool['id'], event_id, project_id, holder_id, contract_id,
             condition, reason, tool['name'], holder_name))
        incident_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO tool_history(tool_id,tool_name,action,from_location,to_location,master_name,
        project,issue_type,condition,date,created_by,owner_scope,company_id,project_id,master_id,custody_event_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (tool['id'], tool['name'], LABELS[action], tool['location'], location, holder_name, project_name,
         'Временно', {'good': 'Исправен', 'damaged': 'Требует ремонта', 'lost': 'Утерян'}.get(condition, ''),
         date.today().isoformat(), actor.get('name') or '', 'project' if project_id else 'company',
         actor['companyId'], project_id, holder_id, event_id))
    return {'ok': True, 'toolId': tool['id'], 'eventId': event_id, 'incidentId': incident_id}


def decide(cur, tool, actor, operation_id, incident_id, data, deps):
    cur.execute('SELECT * FROM tool_incidents WHERE id=%s AND tool_id=%s AND company_id=%s FOR UPDATE',
                (incident_id, tool['id'], actor['companyId']))
    incident = cur.fetchone()
    if not incident or (actor['role'] in policy.WORKERS and incident['holder_id'] != actor['id']):
        raise HTTPException(404, 'Происшествие не найдено')
    access.project(cur, incident['project_id'], actor, deps)
    decision = data.get('decision')
    if decision not in ('confirmed', 'disputed', 'cancelled'):
        raise HTTPException(400, 'Выберите решение по ответственности')
    if decision != 'disputed' and actor['role'] not in policy.DIRECTORS:
        raise HTTPException(403, 'Денежную ответственность подтверждает директор')
    if decision == 'disputed' and actor['role'] not in policy.DIRECTORS and incident['holder_id'] != actor['id']:
        raise HTTPException(403, 'Оспорить ответственность может только получатель инструмента или директор')
    cur.execute('SELECT 1 FROM tool_fine_allocations WHERE incident_id=%s LIMIT 1', (incident_id,))
    if cur.fetchone():
        raise HTTPException(409, 'Штраф уже включён в акт. Изменение требует отдельного акта корректировки')
    cur.execute('SELECT id,decision FROM tool_incident_decisions WHERE incident_id=%s ORDER BY id DESC LIMIT 1', (incident_id,))
    latest = cur.fetchone()
    if latest and latest['decision'] in ('cancelled', decision):
        raise HTTPException(409, 'Решение уже зафиксировано. Обновите происшествие')
    if 'expectedDecisionId' in data and data['expectedDecisionId'] != (latest['id'] if latest else None):
        raise HTTPException(409, 'Решение изменилось. Обновите происшествие')
    reason, amount, price_evidence, contract_evidence = policy.text(data), money(0), '', ''
    if decision == 'confirmed':
        if not incident['contract_id']:
            raise HTTPException(409, 'Выдача не связана с договором подряда. Автоматическое удержание с сотрудника недоступно')
        access.contract(cur, incident['contract_id'], actor['companyId'], incident['project_id'], incident['holder_id'])
        amount = money(data.get('amount'), zero=False)
        price_evidence = policy.text(data, 'priceEvidence')
        contract_evidence = policy.text(data, 'contractEvidence')
        cur.execute('UPDATE brigade_contracts SET settlement_version=2 WHERE id=%s', (incident['contract_id'],))
    cur.execute('''INSERT INTO tool_incident_decisions(company_id,incident_id,operation_id,actor_id,
        decision,reason,amount,price_evidence,contract_evidence) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (actor['companyId'], incident_id, operation_id, actor['id'], decision, reason, amount, price_evidence, contract_evidence))
    result = next(row for row in records.incidents(cur, tool['id'], actor['companyId']) if row['id'] == incident_id)
    return {'ok': True, **result}
