from datetime import date

from fastapi import HTTPException
from psycopg2.extras import Json

from . import adjustments, policy, snapshot


def load(cur, inventory_id, actor, deps):
    cur.execute('''SELECT r.*,i.project,i.date,i.notes,i.created_by FROM inventory_reconciliations r
        JOIN inventory i ON i.id=r.inventory_id AND i.company_id=r.company_id
        WHERE r.inventory_id=%s AND r.company_id=%s FOR UPDATE OF r''', (inventory_id, actor['companyId']))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Сверка не найдена в выбранной компании')
    session = dict(row)
    snapshot.project(cur, session['project_id'], actor, deps)
    return session


def state(session):
    return policy.fingerprint({key: session[key] for key in ('inventory_id', 'company_id', 'version', 'state', 'counts', 'snapshot')})


def event(cur, session, actor, operation_id, action, reason):
    cur.execute('''INSERT INTO inventory_reconciliation_events(inventory_id,company_id,operation_id,
        actor_id,actor_name,action,reason,state,counts) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (session['inventory_id'], actor['companyId'], operation_id, actor['id'], actor.get('name') or '',
         action, reason, session['state'], Json(session['counts'])))
    return cur.fetchone()['id']


def create(cur, actor, data, operation_id, deps):
    notes = policy.text(data.get('notes'))
    captured = snapshot.capture(cur, actor, data.get('projectId'), deps)
    scope = 'project' if captured['projectId'] else 'company'
    cur.execute('''INSERT INTO inventory(project,date,created_by,status,notes,owner_scope,company_id,project_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (captured['project'], date.today().isoformat(), actor.get('name') or '', policy.STATUSES['draft'],
         notes, scope, actor['companyId'], captured['projectId']))
    inventory_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO inventory_reconciliations(inventory_id,company_id,project_id,stock_scope,
        state,snapshot,actor_id) VALUES(%s,%s,%s,%s,'draft',%s,%s)''',
        (inventory_id, actor['companyId'], captured['projectId'], 'project' if captured['projectId'] else 'main',
         Json(captured), actor['id']))
    session = {'inventory_id': inventory_id, 'state': 'draft', 'counts': {}}
    event_id = event(cur, session, actor, operation_id, 'create', notes)
    return {'ok': True, 'inventoryId': inventory_id, 'eventId': event_id}


def command(cur, session, actor, data, operation_id, deps):
    if data.get('expectedState') != state(session):
        raise HTTPException(409, 'Ведомость изменена. Обновите её перед новым действием')
    action = data.get('action')
    current = session['state']
    if current in ('approved', 'cancelled'):
        raise HTTPException(409, 'Завершённая ведомость сохраняется без изменений')
    if action in ('approve', 'return', 'cancel') and actor['role'] not in policy.DIRECTORS:
        raise HTTPException(403, 'Решение по ведомости принимает директор')
    reason = policy.text(data.get('reason'), required=action in ('approve', 'return', 'cancel'))
    if action == 'save' and current == 'draft':
        values = policy.validate_counts(session['snapshot']['rows'], data.get('counts'))
        session['counts'] = {**session['counts'], **values}
    elif action == 'submit' and current == 'draft':
        policy.require_complete(session['snapshot']['rows'], session['counts'])
        session['state'] = 'submitted'
    elif action == 'return' and current == 'submitted':
        session['state'] = 'draft'
    elif action == 'cancel':
        session['state'] = 'cancelled'
    elif action == 'approve' and current == 'submitted':
        policy.require_complete(session['snapshot']['rows'], session['counts'])
        current_snapshot = snapshot.capture(cur, actor, session['project_id'], deps)
        if current_snapshot != session['snapshot']:
            raise HTTPException(409, 'Учёт изменился после начала пересчёта. Отмените эту ведомость и начните новую сверку')
        deductions = adjustments.allocations(session['snapshot']['rows'], session['counts'], data.get('lotDeductions', []))
        session['state'] = 'approved'
    else:
        raise HTTPException(409, 'Действие недоступно в текущем состоянии ведомости')
    event_id = event(cur, session, actor, operation_id, action, reason)
    if action == 'approve':
        adjustments.apply(cur, session, actor, event_id, deductions)
    cur.execute('UPDATE inventory_reconciliations SET counts=%s,state=%s,version=version+1 WHERE inventory_id=%s',
                (Json(session['counts']), session['state'], session['inventory_id']))
    cur.execute('UPDATE inventory SET status=%s WHERE id=%s AND company_id=%s',
                (policy.STATUSES[session['state']], session['inventory_id'], actor['companyId']))
    return {'ok': True, 'inventoryId': session['inventory_id'], 'eventId': event_id}


def view(cur, session, actor):
    cur.execute('''SELECT id,action,reason,actor_name AS "actorName",created_at AS "createdAt",state,counts
        FROM inventory_reconciliation_events WHERE inventory_id=%s AND company_id=%s ORDER BY id''',
        (session['inventory_id'], actor['companyId']))
    history = [dict(r) for r in cur.fetchall()]
    rows = []
    for row in session['snapshot']['rows']:
        count = session['counts'].get(row['key'], {})
        rows.append({**row, 'actual': None, 'condition': None, 'reason': '', **count,
                     'difference': policy.difference(row, count) if row['kind'] == 'material' else None})
    return {'inventory': {'id': session['inventory_id'], 'project': session['project'], 'date': session['date'],
                         'createdBy': session['created_by'], 'notes': session['notes'], 'state': session['state'],
                         'status': policy.STATUSES[session['state']], 'projectId': session['project_id']},
            'rows': rows, 'expectedState': state(session), 'history': history,
            'canCount': policy.enabled() and actor['role'] in policy.COUNTERS and session['state'] == 'draft',
            'canDecide': policy.enabled() and actor['role'] in policy.DIRECTORS and session['state'] not in ('approved', 'cancelled')}
