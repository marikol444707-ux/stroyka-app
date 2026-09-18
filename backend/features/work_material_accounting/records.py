"""Read the immutable ledger and its current, explicitly corrected quantities."""
from fastapi import HTTPException


def account(cur, journal_id, company_id):
    cur.execute('''SELECT a.*,u.name AS actor_name,c.contractor_type,c.status AS contract_status
        FROM work_material_accounts a JOIN users u ON u.id=a.actor_id
        JOIN brigade_contracts c ON c.id=a.contract_id AND c.company_id=a.company_id AND c.project_id=a.project_id
        WHERE a.journal_id=%s AND a.company_id=%s FOR SHARE OF c''', (journal_id, company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Фактический расход по этой работе не найден')
    return dict(row)


def entries(cur, journal_id, company_id):
    cur.execute('''SELECT e.*,e.quantity+COALESCE((SELECT SUM(c.quantity)
        FROM work_material_entries c WHERE c.corrects_entry_id=e.id),0) AS current_quantity
        FROM work_material_entries e WHERE e.journal_id=%s AND e.company_id=%s
        AND e.corrects_entry_id IS NULL ORDER BY e.id''', (journal_id, company_id))
    return [dict(row) for row in cur.fetchall()]


def defects(cur, journal_id, company_id):
    cur.execute('''SELECT d.*,a.contract_id,COALESCE(s.decision,'pending') AS status,
        COALESCE(s.amount,0) AS amount,s.id AS decision_id,s.valuations,s.contract_evidence,
        s.reason AS decision_reason FROM work_material_defects d
        JOIN work_material_accounts a ON a.journal_id=d.journal_id AND a.company_id=d.company_id
        LEFT JOIN LATERAL(SELECT * FROM work_material_defect_decisions s
            WHERE s.defect_id=d.id ORDER BY s.id DESC LIMIT 1) s ON TRUE
        WHERE d.journal_id=%s AND d.company_id=%s ORDER BY d.id''', (journal_id, company_id))
    rows = []
    for record in cur.fetchall():
        row = dict(record)
        cur.execute('''SELECT i.entry_id,i.quantity,e.material_name,e.unit,e.source
            FROM work_material_defect_items i JOIN work_material_entries e ON e.id=i.entry_id
            WHERE i.defect_id=%s ORDER BY i.entry_id''', (row['id'],))
        row['items'] = [dict(item) for item in cur.fetchall()]
        rows.append(row)
    return rows


def reserved_quantities(cur, journal_id, company_id):
    quantities = {}
    for defect in defects(cur, journal_id, company_id):
        if defect['status'] == 'cancelled':
            continue
        for item in defect['items']:
            quantities[item['entry_id']] = quantities.get(item['entry_id'], 0) + item['quantity']
    return quantities


def defect_response(row):
    return {'id': row['id'], 'journalId': row['journal_id'], 'contractId': row['contract_id'],
            'reason': row['reason'], 'photos': row['photos'], 'status': row['status'],
            'amount': row['amount'], 'decisionId': row['decision_id'],
            'valuations': row['valuations'] or [], 'contractEvidence': row['contract_evidence'] or '',
            'decisionReason': row['decision_reason'] or '',
            'items': [{'entryId': item['entry_id'], 'name': item['material_name'], 'unit': item['unit'],
                       'source': item['source'], 'quantity': item['quantity']} for item in row['items']]}


def report(cur, journal_id, company_id):
    owner = account(cur, journal_id, company_id)
    reserved = reserved_quantities(cur, journal_id, company_id)
    return {'journalId': journal_id, 'contractId': owner['contract_id'], 'actorId': owner['actor_id'],
            'projectId': owner['project_id'], 'actorName': owner['actor_name'],
            'entries': [{'id': row['id'], 'name': row['material_name'], 'unit': row['unit'],
                         'source': row['source'], 'quantity': row['current_quantity'],
                         'initialQuantity': row['quantity'], 'workPackage': row['work_package'],
                         'warehouseMaterialId': row['warehouse_material_id'],
                         'defectQuantity': reserved.get(row['id'], 0)}
                        for row in entries(cur, journal_id, company_id)],
            'defects': [defect_response(row) for row in defects(cur, journal_id, company_id)]}
