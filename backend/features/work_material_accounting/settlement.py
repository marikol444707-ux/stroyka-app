"""One immutable contract act owns work, material penalties and net payments."""
from datetime import date
from decimal import Decimal
import json

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json, RealDictCursor

from . import runtime
from .quantities import money
from .documents import owned_document_url
from ..tool_custody import fines as tool_fines

CONTRACT_TYPES = {'Субподрядчик', 'ГПХ', 'Самозанятый', 'ИП', 'ООО', 'Своя бригада'}


def identifier(value, label):
    if type(value) is not int or value <= 0:
        raise HTTPException(400, 'Укажите ' + label)
    return value


def period(data):
    try:
        start, end = (date.fromisoformat(data[key]) for key in ('periodFrom', 'periodTo'))
        if end < start:
            raise ValueError()
        return start.isoformat(), end.isoformat()
    except (TypeError, ValueError, KeyError):
        raise HTTPException(400, 'Укажите корректные даты периода акта')


def require_contract(cur, contract):
    cur.execute('SELECT contractor_type,status FROM brigade_contracts WHERE id=%s FOR SHARE', (contract['id'],))
    row = cur.fetchone()
    if row['contractor_type'] not in CONTRACT_TYPES or row['status'] != 'Подписан':
        raise HTTPException(409, 'Акт доступен по подписанному договору подряда. Уточните вид и статус договора')


def require_reconciled(cur, contract):
    """Never infer a starting balance for existing money or another payable family."""
    cur.execute('''SELECT 1 FROM brigade_acts b WHERE b.contract_id=%s
        AND NOT EXISTS(SELECT 1 FROM work_contract_acts a WHERE a.act_id=b.id)
        AND COALESCE(b.status,'')<>'Аннулирован'
        UNION ALL SELECT 1 FROM brigade_payments p WHERE p.contract_id=%s
        AND NOT EXISTS(SELECT 1 FROM work_contract_act_payments a WHERE a.payment_id=p.id)
        UNION ALL SELECT 1 FROM piecework p JOIN work_journal w ON w.id=p.work_journal_id
        JOIN brigade_contract_items i ON i.id=w.contract_item_id WHERE i.contract_id=%s LIMIT 1''',
        (contract['id'], contract['id'], contract['id']))
    if cur.fetchone():
        raise HTTPException(409, 'По договору есть прежние акты, выплаты или начисления. Сначала нужна сверка переходящего остатка')
    cur.execute('SELECT w.id FROM work_journal w JOIN brigade_contract_items i ON i.id=w.contract_item_id WHERE i.contract_id=%s',
                (contract['id'],))
    work_ids = {row['id'] for row in cur.fetchall()}
    cur.execute('''SELECT contract_id,work_journal_ids,master_id FROM interim_acts
        WHERE project=%s AND COALESCE(NULLIF(work_package,''),'Основная')=%s
        AND (COALESCE(status,'')<>'Аннулирован' OR COALESCE(paid_amount,0)<>0)
        AND COALESCE(source_type,'')<>'daily_work' ''',
                (contract['projectName'], contract['workPackage']))
    for row in cur.fetchall():
        try:
            raw_ids = row['work_journal_ids'] or []
            ids = set(int(value) for value in (json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids))
        except (ValueError, TypeError):
            raise HTTPException(409, 'В прежних актах найдена неоднозначная связь с работами. Нужна сверка')
        # interim.contract_id belongs to `contracts`, never brigade_contracts.
        if (work_ids & ids or (not ids and row['master_id'] == contract['contractorId'])):
            raise HTTPException(409, 'Работы договора уже связаны с прежним актом. Сначала нужна сверка')


def acts(cur, contract):
    cur.execute('''SELECT a.*,s.scan_url,s.signed_by,COALESCE((SELECT SUM(p.amount)
        FROM work_contract_act_payments l JOIN brigade_payments p ON p.id=l.payment_id
        WHERE l.act_id=a.act_id),0) AS paid_amount
        FROM work_contract_acts a LEFT JOIN work_contract_act_signatures s ON s.act_id=a.act_id
        WHERE a.contract_id=%s AND a.company_id=%s ORDER BY a.act_id DESC''',
        (contract['id'], contract['companyId']))
    result = []
    for row in cur.fetchall():
        status = 'Сформирован'
        if row['scan_url']:
            status = 'Подписан'
            if row['paid_amount'] > 0:
                status = 'Оплачен' if row['paid_amount'] == row['net_amount'] else 'Частично оплачен'
        result.append({'id': row['act_id'], 'contractId': row['contract_id'], 'companyId': row['company_id'],
            'totalAmount': row['gross_amount'], 'fineAmount': row['fine_amount'], 'netAmount': row['net_amount'],
            'paidAmount': row['paid_amount'], 'remainingAmount': row['net_amount'] - row['paid_amount'],
            'scanUrl': row['scan_url'] or '', 'status': status, 'snapshot': row['snapshot']})
    return result


def require_work_scope(cur, contract):
    # A legacy journal can still be edited before act formation. Do not expose
    # mismatched work or silently omit its money from the contract balance.
    cur.execute('''SELECT w.company_id,w.project,w.work_package,i.work_package AS item_package
        FROM work_journal w JOIN brigade_contract_items i ON i.id=w.contract_item_id
        WHERE i.contract_id=%s ORDER BY w.id FOR SHARE OF w,i''', (contract['id'],))
    package = contract['workPackage'].strip() or 'Основная'
    for work in cur.fetchall():
        if (work['company_id'] != contract['companyId'] or work['project'] != contract['projectName']
                or ((work['work_package'] or '').strip() or 'Основная') != package
                or ((work['item_package'] or '').strip() or 'Основная') != package):
            raise HTTPException(409, 'Объект или пакет работ не совпадает с договором. Нужна сверка привязки ЖПР')


def preview(cur, contract, *, start=None, end=None, selected_ids=None):
    require_work_scope(cur, contract)
    clauses, params = [], [contract['id'], contract['companyId'], contract['projectName']]
    if start:
        clauses.append('w.date>=%s'); params.append(start)
    if end:
        clauses.append('w.date<=%s'); params.append(end)
    if selected_ids is not None:
        clauses.append('w.id=ANY(%s)'); params.append(selected_ids)
    cur.execute('''SELECT w.id,w.description,w.unit,w.quantity,w.execution_price_per_unit,
        w.execution_total,w.date,w.master_id,w.master_name,w.room_name,w.contract_item_id
        FROM work_journal w JOIN brigade_contract_items i ON i.id=w.contract_item_id
        WHERE i.contract_id=%s AND w.company_id=%s AND w.project=%s AND w.status='Подтверждено'
        AND (w.room_id IS NOT NULL OR COALESCE(trim(w.room_name),'')<>'')
        AND NOT EXISTS(SELECT 1 FROM work_contract_act_items a WHERE a.journal_id=w.id)'''
        + ((' AND ' + ' AND '.join(clauses)) if clauses else '') + ' ORDER BY w.id FOR SHARE OF w,i', tuple(params))
    works = [dict(row) for row in cur.fetchall()]
    gross = money(sum((money(row['execution_total']) for row in works), Decimal('0.00')))
    cur.execute('''SELECT d.id AS defect_id,s.id AS decision_id,s.amount,s.reason,s.contract_evidence,
        s.valuations,d.journal_id,COALESCE((SELECT SUM(f.amount) FROM work_contract_fine_allocations f
        WHERE f.defect_id=d.id),0) AS allocated
        FROM work_material_defects d JOIN work_material_accounts a ON a.journal_id=d.journal_id
        JOIN LATERAL(SELECT * FROM work_material_defect_decisions s WHERE s.defect_id=d.id
            ORDER BY s.id DESC LIMIT 1) s ON TRUE
        WHERE a.contract_id=%s AND a.company_id=%s AND s.decision='confirmed' ORDER BY d.id''',
        (contract['id'], contract['companyId']))
    allocations, available_fines, capacity = [], Decimal('0.00'), gross
    for row in cur.fetchall():
        available = money(row['amount'] - row['allocated'])
        available_fines += available
        applied = min(available, capacity)
        if applied:
            allocations.append({'defectId': row['defect_id'], 'decisionId': row['decision_id'],
                'amount': applied, 'journalId': row['journal_id'], 'reason': row['reason'],
                'contractEvidence': row['contract_evidence'], 'valuations': row['valuations']})
            capacity -= applied
    tool_allocations, available_tools, capacity = tool_fines.preview(cur, contract, capacity)
    allocations.extend(tool_allocations)
    available_fines += available_tools
    fine = gross - capacity
    return {'eligibleWorks': works, 'grossAmount': gross, 'fineAmount': fine, 'netAmount': capacity,
            'carryFineAmount': available_fines - fine, 'fineAllocations': allocations, 'acts': acts(cur, contract)}


def create_act(cur, contract, actor, operation_id, data):
    require_contract(cur, contract)
    require_reconciled(cur, contract)
    start, end = period(data)
    ids = data.get('workJournalIds')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 1000:
        raise HTTPException(400, 'Выберите работы для акта')
    ids = [identifier(value, 'работу журнала') for value in ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, 'Работа повторяется в акте')
    current = preview(cur, contract, start=start, end=end, selected_ids=ids)
    if {row['id'] for row in current['eligibleWorks']} != set(ids):
        raise HTTPException(409, 'Работы изменились, уже включены в акт или относятся к другому договору и периоду')
    if not current['grossAmount']:
        raise HTTPException(400, 'Сумма принятых работ должна быть больше нуля')
    if (money(data.get('expectedGrossAmount')) != current['grossAmount'] or
            money(data.get('expectedFineAmount')) != current['fineAmount']):
        raise HTTPException(409, 'Стоимость работ или штрафы изменились. Проверьте предварительный расчёт заново')
    submitted = data.get('fineAllocations')
    if not isinstance(submitted, list) or any(not isinstance(row, dict) for row in submitted):
        raise HTTPException(400, 'Подтвердите штрафы предварительного расчёта')
    given = [tool_fines.allocation_identity(row) for row in submitted]
    actual = [tool_fines.allocation_identity(row) for row in current['fineAllocations']]
    if given != actual:
        raise HTTPException(409, 'Состав штрафов изменился. Проверьте предварительный расчёт заново')
    snapshot = {'contractId': contract['id'], 'projectName': contract['projectName'],
        'brigadeName': contract['brigadeName'], 'workPackage': contract['workPackage'],
        'periodFrom': start, 'periodTo': end, 'works': current['eligibleWorks'],
        'fines': current['fineAllocations'], 'grossAmount': str(current['grossAmount']),
        'fineAmount': str(current['fineAmount']), 'netAmount': str(current['netAmount'])}
    cur.execute('''INSERT INTO brigade_acts(contract_id,project_name,brigade_name,period_from,period_to,total_amount,status)
        VALUES(%s,%s,%s,%s,%s,%s,'Сформирован') RETURNING id''',
        (contract['id'], contract['projectName'], contract['brigadeName'], start, end, current['grossAmount']))
    act_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO work_contract_acts(act_id,company_id,contract_id,operation_id,gross_amount,fine_amount,net_amount,snapshot)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''', (act_id, contract['companyId'], contract['id'], operation_id,
        current['grossAmount'], current['fineAmount'], current['netAmount'], Json(jsonable_encoder(snapshot))))
    for work in current['eligibleWorks']:
        cur.execute('INSERT INTO work_contract_act_items(journal_id,act_id,company_id,snapshot) VALUES(%s,%s,%s,%s)',
                    (work['id'], act_id, contract['companyId'], Json(jsonable_encoder(work))))
    for allocation in current['fineAllocations']:
        if allocation.get('source') == 'tool':
            tool_fines.allocate(cur, act_id, contract['companyId'], allocation)
            continue
        cur.execute('''INSERT INTO work_contract_fine_allocations(act_id,company_id,defect_id,decision_id,amount)
            VALUES(%s,%s,%s,%s,%s)''', (act_id, contract['companyId'], allocation['defectId'],
            allocation['decisionId'], allocation['amount']))
    cur.execute('UPDATE brigade_contracts SET settlement_version=2 WHERE id=%s', (contract['id'],))
    return {'ok': True, **next(row for row in acts(cur, contract) if row['id'] == act_id)}


def sign(cur, contract, actor, operation_id, act_id, data):
    act = next((row for row in acts(cur, contract) if row['id'] == act_id), None)
    if not act:
        raise HTTPException(404, 'Акт договора не найден')
    if act['scanUrl']:
        raise HTTPException(409, 'Подписанный акт уже сохранён')
    scan = owned_document_url(cur, data.get('scanUrl'), contract['companyId'], contract['projectId'], require_upload=True)
    cur.execute('''INSERT INTO work_contract_act_signatures(act_id,company_id,operation_id,scan_url,signed_by)
        VALUES(%s,%s,%s,%s,%s)''', (act_id, contract['companyId'], operation_id, scan, actor['id']))
    cur.execute("UPDATE brigade_acts SET status='Подписан' WHERE id=%s", (act_id,))
    return {'ok': True, **next(row for row in acts(cur, contract) if row['id'] == act_id)}


def pay(conn, contract, actor, data):
    if not runtime.enabled():
        raise HTTPException(404, 'Оплата по новому учёту временно недоступна')
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        op_id, replay = runtime.begin_operation(cur, actor, data.get('requestId'), 'contract-act-payment', data)
        if replay is not None:
            return replay
        act_id = identifier(data.get('actId'), 'акт для оплаты')
        act = next((row for row in acts(cur, contract) if row['id'] == act_id), None)
        if not act:
            raise HTTPException(404, 'Акт договора не найден')
        if not act['scanUrl']:
            raise HTTPException(400, 'Загрузите подписанный акт перед оплатой')
        owned_document_url(cur, act['scanUrl'], contract['companyId'], contract['projectId'], require_upload=True)
        amount = money(data.get('amount'), zero=False)
        if amount > act['remainingAmount']:
            raise HTTPException(400, 'Сумма превышает остаток к оплате по акту после штрафов')
        try:
            paid_date = date.fromisoformat(data.get('paidDate') or '')
        except (ValueError, TypeError):
            raise HTTPException(400, 'Укажите дату оплаты')
        paid_by = actor.get('name') or ''
        note = 'Оплата бригаде ' + contract['brigadeName'] + ' · акт №' + str(act_id)
        cur.execute('''INSERT INTO brigade_payments(company_id,contract_id,amount,paid_by,paid_date,note)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',
            (contract['companyId'], contract['id'], amount, paid_by, paid_date, note))
        payment_id = cur.fetchone()['id']
        cur.execute('''INSERT INTO project_payments(company_id,project_name,work_package,amount,note,date,added_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (contract['companyId'], contract['projectName'], contract['workPackage'], amount, note, paid_date, paid_by))
        project_payment_id = cur.fetchone()['id']
        cur.execute('UPDATE brigade_payments SET project_payment_id=%s WHERE id=%s', (project_payment_id, payment_id))
        cur.execute('''INSERT INTO work_contract_act_payments(payment_id,act_id,company_id,operation_id)
            VALUES(%s,%s,%s,%s)''', (payment_id, act_id, contract['companyId'], op_id))
        result = {'ok': True, 'id': payment_id, 'companyId': contract['companyId'], 'actId': act_id,
                  'projectPaymentId': project_payment_id}
        runtime.finish_operation(cur, op_id, result)
        return result
