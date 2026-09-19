from fastapi import HTTPException

from . import policy


def response(tool):
    return {'id': tool['id'], 'name': tool['name'], 'inventoryNumber': tool['inventory_number'],
            'status': tool['status'], 'location': tool['location'], 'project': tool['project'],
            'projectId': tool['project_id'], 'companyId': tool['company_id'],
            'masterId': tool['master_id'], 'masterName': tool['master_name'],
            'contractId': tool.get('custody_contract_id'), 'cost': tool['cost'],
            'notes': tool['notes'], 'version': tool.get('custody_version', 0)}


def incidents(cur, tool_id, company_id, holder_id=None, project_ids=None):
    cur.execute('''SELECT i.*,s.id AS decision_id,COALESCE(s.decision,'pending') AS status,
        COALESCE(s.amount,0) AS amount,s.reason AS decision_reason,s.price_evidence,s.contract_evidence,
        COALESCE((SELECT SUM(f.amount) FROM tool_fine_allocations f WHERE f.incident_id=i.id),0) AS allocated,
        COALESCE((SELECT jsonb_agg(jsonb_build_object('id',d.id,'decision',d.decision,'reason',d.reason,
            'amount',d.amount,'priceEvidence',d.price_evidence,'contractEvidence',d.contract_evidence,
            'actorId',d.actor_id,'createdAt',d.created_at) ORDER BY d.id)
            FROM tool_incident_decisions d WHERE d.incident_id=i.id),'[]'::jsonb) AS decisions
        FROM tool_incidents i LEFT JOIN LATERAL(SELECT * FROM tool_incident_decisions s
            WHERE s.incident_id=i.id ORDER BY s.id DESC LIMIT 1) s ON TRUE
        WHERE i.tool_id=%s AND i.company_id=%s AND (%s IS NULL OR i.holder_id=%s)
        AND (%s::int[] IS NULL OR i.project_id=ANY(%s)) ORDER BY i.id DESC''',
        (tool_id, company_id, holder_id, holder_id, project_ids, project_ids))
    result = []
    for row in cur.fetchall():
        result.append({'id': row['id'], 'kind': row['kind'], 'reason': row['reason'],
            'holderId': row['holder_id'], 'holderName': row['holder_name'], 'contractId': row['contract_id'],
            'status': row['status'], 'amount': row['amount'], 'allocatedAmount': row['allocated'],
            'decisionId': row['decision_id'], 'decisionReason': row['decision_reason'],
            'priceEvidence': row['price_evidence'], 'contractEvidence': row['contract_evidence'],
            'decisions': row['decisions']})
    return result


def history(cur, tool_id, company_id, holder_id=None, project_ids=None):
    cur.execute('''SELECT id,action,condition,reason,actor_name AS "actorName",
        before_state AS "before",after_state AS "after",created_at AS "createdAt"
        FROM tool_custody_events WHERE tool_id=%s AND company_id=%s
        AND (%s IS NULL OR holder_id=%s)
        AND (%s::int[] IS NULL OR project_id=ANY(%s)) ORDER BY id DESC LIMIT 200''',
        (tool_id, company_id, holder_id, holder_id, project_ids, project_ids))
    result = [dict(row) for row in cur.fetchall()]
    for event in result:
        for key in ('before', 'after'):
            snapshot = event[key]
            if ((holder_id is not None and snapshot.get('masterId') != holder_id)
                    or (project_ids is not None and snapshot.get('projectId') not in project_ids)):
                event[key] = {field: snapshot.get(field) for field in ('name', 'inventoryNumber', 'status')}
    return result


def guard_catalog(cur, tool_id, data=None, *, deleting=False):
    if not policy.schema_present(cur):
        return
    cur.execute('SELECT * FROM tools WHERE id=%s FOR UPDATE', (tool_id,))
    raw = cur.fetchone()
    tool = dict(raw) if isinstance(raw, dict) else dict(zip([d.name for d in cur.description], raw))
    if not policy.enabled() and not tool['custody_version']:
        return
    if deleting:
        raise HTTPException(409, 'История инструмента сохраняется. Используйте архивирование в карточке')
    fields = {'status': 'status', 'location': 'location', 'project': 'project',
              'masterId': 'master_id', 'masterName': 'master_name', 'issueType': 'issue_type'}
    if any((getattr(data, key) or '') != (tool[column] or '') for key, column in fields.items()):
        raise HTTPException(409, 'Получатель и состояние меняются через операции карточки инструмента')
