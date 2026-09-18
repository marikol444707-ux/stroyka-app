"""Guards also apply when the rollout flag is off: persisted obligations remain."""
import json

from fastapi import HTTPException


def require_unacted_work(cur, journal_id):
    cur.execute('''SELECT 1 FROM work_journal w JOIN brigade_contract_items i ON i.id=w.contract_item_id
        JOIN brigade_contracts c ON c.id=i.contract_id WHERE w.id=%s AND c.settlement_version=2''', (journal_id,))
    if not cur.fetchone():
        return
    cur.execute('SELECT 1 FROM work_contract_act_items WHERE journal_id=%s', (journal_id,))
    if cur.fetchone():
        raise HTTPException(409, 'Работа включена в акт. Изменение требует отдельного акта корректировки')


def require_legacy_work(cur, work_ids, contract_id=None):
    if isinstance(work_ids, str):
        try:
            work_ids = json.loads(work_ids or '[]')
        except (ValueError, TypeError):
            raise HTTPException(409, 'Связь акта с работами требует сверки')
    cur.execute("SELECT to_regclass('public.work_contract_act_items') AS ledger")
    row = cur.fetchone()
    if row and (row.get('ledger') if isinstance(row, dict) else row[0]):
        cur.execute('SELECT 1 FROM work_contract_act_items WHERE journal_id=ANY(%s) LIMIT 1', (list(work_ids or []),))
        if cur.fetchone():
            raise HTTPException(409, 'Работа уже включена в акт договора')
    cur.execute('''SELECT 1 FROM brigade_contracts c WHERE c.settlement_version=2
        AND EXISTS(SELECT 1 FROM work_journal w
            JOIN brigade_contract_items i ON i.id=w.contract_item_id
            WHERE i.contract_id=c.id AND w.id=ANY(%s)) LIMIT 1''', (list(work_ids or []),))
    if cur.fetchone():
        raise HTTPException(409, 'Работы этого договора оплачиваются через акт договора с учётом штрафов')


def require_legacy_interim(cur, act_id):
    cur.execute('SELECT work_journal_ids,contract_id,source_type FROM interim_acts WHERE id=%s', (act_id,))
    row = cur.fetchone()
    if not row:
        return
    values = (row['work_journal_ids'], row['contract_id'], row['source_type']) if isinstance(row, dict) else row
    if values[2] != 'daily_work':
        require_legacy_work(cur, values[0], values[1])


def require_legacy_project_payment(cur, payment_id):
    cur.execute('''SELECT 1 FROM brigade_payments p JOIN brigade_contracts c
        ON c.id=p.contract_id AND c.company_id=p.company_id
        WHERE p.project_payment_id=%s AND c.settlement_version=2 LIMIT 1''', (payment_id,))
    if cur.fetchone():
        raise HTTPException(409, 'Этот платёж связан с актом договора. Возврат требует отдельной денежной корректировки')
