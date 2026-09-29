"""Tool fines share a contract act's remaining capacity with material fines."""
from fastapi import HTTPException

from .policy import schema_present, identifier
from ..work_material_accounting.quantities import money


def preview(cur, contract, capacity):
    if not schema_present(cur):
        return [], money(0), capacity
    cur.execute('''SELECT i.id AS incident_id,i.tool_name,i.kind,s.id AS decision_id,
        s.amount,s.reason,s.price_evidence,s.contract_evidence,
        COALESCE((SELECT SUM(f.amount) FROM tool_fine_allocations f WHERE f.incident_id=i.id),0) AS allocated
        FROM tool_incidents i JOIN LATERAL(SELECT * FROM tool_incident_decisions s
            WHERE s.incident_id=i.id ORDER BY s.id DESC LIMIT 1) s ON TRUE
        WHERE i.contract_id=%s AND i.company_id=%s AND s.decision='confirmed' ORDER BY i.id''',
        (contract['id'], contract['companyId']))
    allocations, available_total = [], money(0)
    for row in cur.fetchall():
        available = money(row['amount'] - row['allocated'])
        available_total += available
        applied = min(available, capacity)
        if applied:
            allocations.append({'source': 'tool', 'incidentId': row['incident_id'],
                'decisionId': row['decision_id'], 'amount': applied, 'toolName': row['tool_name'],
                'kind': row['kind'], 'reason': row['reason'], 'priceEvidence': row['price_evidence'],
                'contractEvidence': row['contract_evidence']})
            capacity -= applied
    return allocations, available_total, capacity


def allocation_identity(row):
    source = row.get('source', 'material')
    if source not in ('material', 'tool'):
        raise HTTPException(400, 'Неизвестный источник штрафа')
    key = 'incidentId' if source == 'tool' else 'defectId'
    return source, identifier(row.get(key), 'основание штрафа'), identifier(row.get('decisionId'), 'решение'), money(row.get('amount'), zero=False)


def allocate(cur, act_id, company_id, row):
    cur.execute('''INSERT INTO tool_fine_allocations(act_id,company_id,incident_id,decision_id,amount)
        VALUES(%s,%s,%s,%s,%s)''', (act_id, company_id, row['incidentId'], row['decisionId'], row['amount']))
