"""Tool purchase deductions. All writers hold the shared settlement ledger lock."""
import hashlib
import json
import re
from decimal import Decimal

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from ..accountable_payments.advances import money, act_advance


def digest(value):
    return hashlib.sha256(json.dumps(jsonable_encoder(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def confirmation(data):
    if data.get('confirmed') is not True:
        raise HTTPException(409, 'Нужно явное подтверждение бухгалтера после сверки документов')
    basis = data.get('basis')
    if not isinstance(basis, str) or not basis.strip() or len(basis) > 2000:
        raise HTTPException(400, 'Укажите основание по документам (до 2000 символов)')
    return basis.strip()


def identifier(value):
    if type(value) is not int or value <= 0:
        raise HTTPException(400, 'Выберите запись по идентификатору')
    return value


def act_amount(cur, act_id):
    cur.execute('SELECT COALESCE(sum(amount-refunded),0) AS amount FROM tool_deduction_allocations WHERE act_id=%s', (act_id,))
    row = cur.fetchone()
    return money(row['amount'] if isinstance(row, dict) else row[0])


def guard_act_edit(cur, act_id, data):
    if {'totalAmount', 'paidAmount', 'workJournalIds', 'status'} & set(data):
        cur.execute('SELECT 1 FROM tool_deduction_allocations WHERE act_id=%s AND amount>0 LIMIT 1', (act_id,))
        if cur.fetchone() and (set(data)-{'scanUrl'} != {'status'} or data.get('status') not in ('Подписан',)):
            raise HTTPException(409, 'По акту есть удержания за инструмент. До оплаты отмените распределение; после оплаты оформите отдельный возврат')


def candidates(cur, company):
    cur.execute('''SELECT h.id AS history_id,t.id AS tool_id,t.name,t.inventory_number,t.cost,
        h.master_id,h.master_name,h.project_id,h.project,h.date,h.issue_type
        FROM tool_history h JOIN tools t ON t.id=h.tool_id AND t.company_id=h.company_id
        WHERE h.company_id=%s AND h.action='Выдача' AND h.issue_type='В счёт зарплаты'
        UNION ALL
        SELECT NULL,t.id,t.name,t.inventory_number,t.cost,t.master_id,t.master_name,t.project_id,t.project,
        NULL,t.issue_type FROM tools t WHERE t.company_id=%s AND t.issue_type='В счёт зарплаты'
        AND NOT EXISTS(SELECT 1 FROM tool_history h WHERE h.tool_id=t.id AND h.company_id=t.company_id
                       AND h.action='Выдача' AND h.issue_type='В счёт зарплаты')''', (company, company))
    result = []
    for raw in cur.fetchall():
        row = dict(raw)
        key = ('history:' + str(row['history_id'])) if row['history_id'] else ('card:' + str(row['tool_id']))
        result.append({**jsonable_encoder(row), 'sourceKey': key, 'expectedState': digest(row)})
    return result


def record(cur, source, actor, change):
    cur.execute('UPDATE tool_deduction_sources SET revision=revision+1 WHERE id=%s RETURNING revision', (source['id'],))
    revision = cur.fetchone()['revision']
    cur.execute('''INSERT INTO tool_deduction_events(company_id,source_id,revision,actor,change,project_payment_id)
        VALUES(%s,%s,%s,%s,%s,%s)''', (source['company_id'], source['id'], revision,
        str(actor.get('id') or actor.get('name') or ''), Json(jsonable_encoder(change)), change.get('projectPaymentId')))
    return {'ok': True, 'id': source['id'], 'revision': revision}


def source_for_update(cur, company, source_id, data):
    revision = data.get('expectedRevision')
    if type(revision) is not int or revision < 0:
        raise HTTPException(409, 'Обновите данные: требуется expectedRevision, сохранение не выполнено')
    cur.execute('SELECT * FROM tool_deduction_sources WHERE id=%s AND company_id=%s FOR UPDATE', (source_id, company))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Выдача не найдена в выбранной компании')
    if row['revision'] != revision:
        raise HTTPException(409, 'Распределение изменено в другой вкладке. Ваш ввод сохранён; обновите данные и сверьте остаток')
    return row


def review_recipient(cur, company, staff_id, snapshot):
    cur.execute('SELECT id,name FROM staff WHERE id=%s AND company_id=%s AND company_scope_verified IS TRUE', (staff_id, company))
    staff = cur.fetchone()
    if not staff:
        raise HTTPException(404, 'Сотрудник не подтверждён в выбранной компании')
    if snapshot.get('master_id'):
        cur.execute('''SELECT staff_id FROM user_company_roles WHERE user_id=%s AND company_id=%s
            AND COALESCE(active,TRUE) IS TRUE''', (snapshot['master_id'], company))
        links = {r['staff_id'] for r in cur.fetchall() if r['staff_id']}
        if links != {staff_id}:
            raise HTTPException(409, 'Точный получатель выдачи не связан с выбранным сотрудником. Сначала сверьте связь учётной записи')
    return staff


def correct_review(cur, company, source_id, data, actor):
    basis = confirmation(data)
    if set(data) - {'expectedRevision', 'confirmed', 'basis', 'staffId', 'amount'}:
        raise HTTPException(400, 'Исправляются только получатель и стоимость; исходная выдача, объект и прошлые удержания сохраняются')
    source = source_for_update(cur, company, source_id, data)
    cur.execute('SELECT 1 FROM tool_deduction_allocations WHERE source_id=%s AND (amount>0 OR refunded>0) LIMIT 1', (source_id,))
    if cur.fetchone() or money(source['previously_deducted']) > 0:
        raise HTTPException(409, 'Сначала отмените неоплаченные распределения. При прошлых или оплаченных удержаниях сверка не переписывается; требуется отдельная финансовая корректировка')
    staff_id, amount = identifier(data.get('staffId')), money(data.get('amount'))
    if amount <= 0:
        raise HTTPException(400, 'Стоимость выдачи должна быть больше нуля')
    staff = review_recipient(cur, company, staff_id, source['snapshot'])
    if staff_id == source['staff_id'] and amount == money(source['amount']):
        raise HTTPException(409, 'Получатель и стоимость не изменились')
    cur.execute('SELECT name FROM staff WHERE id=%s AND company_id=%s', (source['staff_id'], company))
    old_staff = cur.fetchone()
    before = {'staffId': source['staff_id'], 'staffName': old_staff['name'], 'amount': money(source['amount'])}
    after = {'staffId': staff_id, 'staffName': staff['name'], 'amount': amount}
    # Keep the original warehouse snapshot, review basis and zeroed allocation history.
    cur.execute('UPDATE tool_deduction_sources SET staff_id=%s,amount=%s WHERE id=%s AND company_id=%s',
                (staff_id, amount, source_id, company))
    return {**record(cur, source, actor, {'operation': 'correct_review', 'before': before, 'after': after, 'basis': basis}),
            'staffId': staff_id, 'amount': float(amount)}


def review_source(cur, company, data, actor):
    basis = confirmation(data)
    key = data.get('sourceKey')
    source = next((r for r in candidates(cur, company) if r['sourceKey'] == key), None)
    if not source:
        raise HTTPException(404, 'Исходная выдача не найдена в выбранной компании')
    cur.execute('SELECT id FROM tools WHERE id=%s AND company_id=%s FOR UPDATE', (source['tool_id'], company))
    if not cur.fetchone():
        raise HTTPException(404, 'Инструмент не найден')
    # Re-read after locking the catalog; a return/reassignment cannot replace the reviewed snapshot.
    source = next((r for r in candidates(cur, company) if r['sourceKey'] == key), None)
    if not source or data.get('expectedState') != source['expectedState']:
        raise HTTPException(409, 'Исходная запись изменилась. Обновите и повторно сверьте документы')
    cur.execute('SELECT id FROM tool_deduction_sources WHERE company_id=%s AND source_key=%s', (company, key))
    if cur.fetchone():
        raise HTTPException(409, 'Эта выдача уже проверена; используйте существующее распределение')
    staff_id, project_id = identifier(data.get('staffId')), identifier(data.get('projectId'))
    review_recipient(cur, company, staff_id, source)
    cur.execute('SELECT id,name FROM projects WHERE id=%s AND company_id=%s', (project_id, company))
    project = cur.fetchone()
    if not project or (source['project_id'] and source['project_id'] != project_id):
        raise HTTPException(404, 'Объект не соответствует выдаче в выбранной компании')
    if not source['project_id'] and source['project'] and source['project'] != project['name']:
        raise HTTPException(409, 'Название объекта в старой выдаче не соответствует выбранному объекту. Сначала сверьте исходную запись')
    amount, previous = money(data.get('amount')), money(data.get('previouslyDeducted'))
    if amount <= 0 or previous > amount:
        raise HTTPException(400, 'Проверьте стоимость выдачи и уже удержанную сумму')
    cur.execute('''INSERT INTO tool_deduction_sources(company_id,tool_id,history_id,source_key,staff_id,project_id,
        amount,previously_deducted,basis,snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (company, source['tool_id'], source['history_id'], key, staff_id, project_id, amount, previous, basis, Json(source)))
    row = cur.fetchone()
    return record(cur, row, actor, {'operation': 'review', 'amount': amount, 'previouslyDeducted': previous,
                                  'staffId': staff_id, 'projectId': project_id, 'basis': basis})


def salary_state(cur, company, staff_id, month):
    cur.execute('''SELECT a.id,a.amount,a.refunded FROM tool_deduction_allocations a
        WHERE a.company_id=%s AND a.staff_id=%s AND a.month=%s ORDER BY a.id''', (company, staff_id, month))
    rows = [dict(r) for r in cur.fetchall()]
    # Refunds do not rewrite the original deduction applied when the salary was paid.
    amount = sum((money(r['amount']) for r in rows), Decimal(0))
    return {'staffId': staff_id, 'month': month, 'amount': float(amount), 'state': digest({'company': company, 'staff': staff_id, 'month': month, 'rows': rows}), 'allocations': rows}


def salary_paid(cur, company, staff_id, month):
    cur.execute('''SELECT id,amount,tool_deduction_snapshot FROM salary_payments
        WHERE company_id=%s AND staff_id=%s AND month=%s AND company_scope_verified IS TRUE''', (company, staff_id, month))
    return cur.fetchall()


def allocate(cur, company, source_id, data, actor, legacy_guard, package_access):
    basis = confirmation(data)
    source = source_for_update(cur, company, source_id, data)
    amount = money(data.get('amount'))
    act_id, month = data.get('actId'), data.get('month')
    act = None
    if act_id is not None:
        identifier(act_id)
        if month is not None:
            raise HTTPException(400, 'Выберите только один акт или месяц')
        cur.execute('''SELECT a.* FROM interim_acts a JOIN projects p ON p.name=a.project AND p.company_id=a.company_id
            WHERE a.id=%s AND a.company_id=%s AND a.master_id=%s AND p.id=%s
            AND NOT EXISTS(SELECT 1 FROM projects x WHERE x.company_id=p.company_id AND x.name=p.name AND x.id<>p.id)
            FOR UPDATE OF a''', (act_id, company, source['staff_id'], source['project_id']))
        act = cur.fetchone()
        if not act or act['source_type'] == 'daily_work':
            raise HTTPException(404, 'Акт этого сотрудника и объекта не найден')
        legacy_guard(cur, act_id)
        if not package_access(actor, act['work_package'] or 'Основная'):
            raise HTTPException(403, 'Нет доступа к пакету работ')
        if act['status'] == 'Аннулирован' or money(act['paid_amount'] or 0) > 0:
            raise HTTPException(409, 'После оплаты или аннулирования распределение не меняется; нужен отдельный возврат')
        cur.execute('SELECT * FROM tool_deduction_allocations WHERE source_id=%s AND act_id=%s', (source_id, act_id))
    else:
        if not isinstance(month, str) or not re.fullmatch(r'(19|20)\d{2}-(0[1-9]|1[0-2])', month):
            raise HTTPException(400, 'Выберите месяц зарплаты')
        if salary_paid(cur, company, source['staff_id'], month):
            raise HTTPException(409, 'Зарплата за месяц уже выплачена; нужен отдельный возврат')
        cur.execute('SELECT * FROM tool_deduction_allocations WHERE source_id=%s AND staff_id=%s AND month=%s',
                    (source_id, source['staff_id'], month))
    old = cur.fetchone()
    old_amount = money(old['amount']) if old else Decimal(0)
    if old and money(old['refunded']) > 0:
        raise HTTPException(409, 'Распределение с возвратом сохраняется в истории')
    cur.execute('SELECT COALESCE(sum(amount),0) AS amount FROM tool_deduction_allocations WHERE source_id=%s', (source_id,))
    used = money(cur.fetchone()['amount'])
    if money(source['previously_deducted']) + used - old_amount + amount > money(source['amount']):
        raise HTTPException(409, 'Распределение превышает подтверждённую стоимость выдачи с учётом прошлых удержаний')
    if act:
        previous_tools = act_amount(cur, act_id)
        total_tools = previous_tools - old_amount + amount
        if total_tools + act_advance(cur, act_id) + money(act['retention_amount']) - money(act['retention_released']) > money(act['total_amount']):
            raise HTTPException(409, 'Удержание превышает доступный остаток акта')
    if old:
        cur.execute('UPDATE tool_deduction_allocations SET amount=%s WHERE id=%s', (amount, old['id']))
        allocation_id = old['id']
    else:
        cur.execute('''INSERT INTO tool_deduction_allocations(company_id,source_id,act_id,staff_id,month,amount)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''', (company, source_id, act_id, source['staff_id'], month, amount))
        allocation_id = cur.fetchone()['id']
    if act:
        settled = act_advance(cur, act_id) + act_amount(cur, act_id)
        prior = act.get('tool_deduction_prior_status') or act.get('advance_prior_status') or act['status']
        status = ('Оплачен' if settled >= money(act['total_amount']) else 'Частично оплачен') if settled else prior
        cur.execute('UPDATE interim_acts SET status=%s,tool_deduction_prior_status=%s,paid_amount=COALESCE(paid_amount,0) WHERE id=%s', (status, prior if settled else None, act_id))
    return {**record(cur, source, actor, {'operation': 'allocate', 'allocationId': allocation_id,
        'actId': act_id, 'month': month, 'amount': amount, 'previousAmount': old_amount, 'basis': basis}), 'allocationId': allocation_id}


def refund(cur, company, source_id, data, actor, package_access):
    basis = confirmation(data)
    source = source_for_update(cur, company, source_id, data)
    allocation_id, amount = identifier(data.get('allocationId')), money(data.get('amount'))
    cur.execute('SELECT * FROM tool_deduction_allocations WHERE id=%s AND source_id=%s AND company_id=%s FOR UPDATE',
                (allocation_id, source_id, company))
    allocation = cur.fetchone()
    if not allocation or amount <= 0 or amount > money(allocation['amount']) - money(allocation['refunded']):
        raise HTTPException(409, 'Возврат превышает удержанную сумму этого распределения')
    package = ''
    if allocation['act_id']:
        cur.execute('SELECT * FROM interim_acts WHERE id=%s AND company_id=%s FOR UPDATE', (allocation['act_id'], company))
        act = cur.fetchone()
        if not act or (money(act['paid_amount'] or 0) <= 0 and act['status'] != 'Оплачен'):
            raise HTTPException(409, 'Денежной оплаты ещё нет. Отмените неоплаченное распределение')
        package = act['work_package'] or 'Основная'
        if not package_access(actor, package):
            raise HTTPException(403, 'Нет доступа к пакету работ')
    elif not salary_paid(cur, company, source['staff_id'], allocation['month']):
        raise HTTPException(409, 'Зарплата ещё не выплачена. Отмените неоплаченное распределение')
    cur.execute('UPDATE tool_deduction_allocations SET refunded=refunded+%s WHERE id=%s', (amount, allocation_id))
    if allocation['act_id']:
        cur.execute('UPDATE interim_acts SET paid_amount=paid_amount+%s WHERE id=%s', (amount, allocation['act_id']))
    cur.execute('SELECT name FROM projects WHERE id=%s AND company_id=%s', (source['project_id'], company))
    project = cur.fetchone()
    if not project:
        raise HTTPException(409, 'Исходный объект требует сверки')
    cur.execute('''INSERT INTO project_payments(company_id,project_name,amount,note,date,added_by,work_package)
        VALUES(%s,%s,%s,%s,CURRENT_DATE::text,%s,%s) RETURNING id''',
        (company, project['name'], -amount, 'Возврат удержания за инструмент: ' + basis,
         str(actor.get('name') or ''), package))
    payment_id = cur.fetchone()['id']
    return {**record(cur, source, actor, {'operation': 'refund', 'allocationId': allocation_id,
        'amount': amount, 'basis': basis, 'projectPaymentId': payment_id}), 'projectPaymentId': payment_id}


def historical_refund_state(source, events):
    opening = next((e['change'] for e in events if e['change']['operation'] == 'historical_refund_review'), None)
    refunded = sum((money(e['change']['amount']) for e in events
                    if e['change']['operation'] == 'historical_refund'), Decimal(0))
    previous = money(opening['previouslyRefunded']) if opening else None
    return {'reviewed': opening is not None, 'previouslyRefunded': previous, 'refunded': refunded,
            'remaining': money(source['previously_deducted']) - previous - refunded if opening else None}


def historical_refund(cur, company, source_id, data, actor, *, review=False):
    basis = confirmation(data)
    amount_field = 'previouslyRefunded' if review else 'amount'
    if set(data) - {'expectedRevision', 'confirmed', 'basis', amount_field}:
        raise HTTPException(400, 'Получатель, объект и компания берутся из проверенной выдачи')
    source = source_for_update(cur, company, source_id, data)
    previous_deducted = money(source['previously_deducted'])
    if previous_deducted <= 0:
        raise HTTPException(409, 'В этой выдаче нет подтверждённых старых удержаний')
    cur.execute('SELECT change FROM tool_deduction_events WHERE source_id=%s AND company_id=%s ORDER BY revision',
                (source_id, company))
    state = historical_refund_state(source, cur.fetchall())
    amount = money(data.get(amount_field))
    if review:
        if state['reviewed']:
            raise HTTPException(409, 'Прежние возвраты уже подтверждены. История сверки не переписывается')
        if amount > previous_deducted:
            raise HTTPException(409, 'Ранее возвращённая сумма превышает подтверждённое старое удержание')
        return record(cur, source, actor, {'operation': 'historical_refund_review',
            'previouslyRefunded': amount, 'basis': basis})
    if not state['reviewed']:
        raise HTTPException(409, 'Сначала подтвердите прежние возвраты по документам, включая явный ноль')
    if amount <= 0:
        raise HTTPException(400, 'Сумма возврата должна быть больше нуля')
    if amount > state['remaining']:
        raise HTTPException(409, 'Возврат превышает остаток старого удержания с учётом всех подтверждённых возвратов')
    cur.execute('''SELECT p.name FROM projects p WHERE p.id=%s AND p.company_id=%s
        AND NOT EXISTS(SELECT 1 FROM projects other WHERE other.company_id=p.company_id
                       AND other.name=p.name AND other.id<>p.id)''', (source['project_id'], company))
    project = cur.fetchone()
    if not project:
        raise HTTPException(409, 'Объект не найден или его название неоднозначно; денежная запись не создана')
    # Never change the old act/salary or free capacity for another deduction.
    cur.execute('''INSERT INTO project_payments(company_id,project_name,amount,note,date,added_by,work_package)
        VALUES(%s,%s,%s,%s,CURRENT_DATE::text,%s,'') RETURNING id''',
        (company, project['name'], -amount,
         f"Возврат старого удержания за инструмент: выдача №{source_id}, сотрудник №{source['staff_id']}. {basis}",
         str(actor.get('name') or '')))
    payment_id = cur.fetchone()['id']
    return {**record(cur, source, actor, {'operation': 'historical_refund', 'amount': amount,
        'staffId': source['staff_id'], 'projectId': source['project_id'],
        'basis': basis, 'projectPaymentId': payment_id}), 'projectPaymentId': payment_id}


def prepare_salary(cur, company, staff_id, month, data):
    current = salary_state(cur, company, staff_id, month)
    if data.get('expectedToolState') != current['state']:
        raise HTTPException(409, 'Удержания за инструмент не сверены или изменились. Обновите расчёт зарплаты; выплата не записана')
    if money(data.get('toolDeductionAmount')) != money(current['amount']):
        raise HTTPException(409, 'Удержание не совпадает с серверным распределением')
    if salary_paid(cur, company, staff_id, month):
        raise HTTPException(409, 'Выплата за этот месяц уже записана. Повторная выплата не создана')
    return current


def guard_salary_delete(cur, company, payment_id):
    cur.execute('SELECT tool_deduction_snapshot FROM salary_payments WHERE id=%s AND company_id=%s', (payment_id, company))
    row = cur.fetchone()
    snapshot = row['tool_deduction_snapshot'] if row else {}
    if money((snapshot or {}).get('amount') or 0) > 0:
        raise HTTPException(409, 'Выплата содержит удержание за инструмент. Оформите отдельный подтверждённый возврат')
