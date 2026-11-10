"""Manual advance ledger. Callers own the transaction; no implicit commits."""
from decimal import Decimal, InvalidOperation
import json
from fastapi import HTTPException

KINDS = {'expense', 'salary_advance'}


def money(value):
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result >= Decimal('1000000000000'):
            raise ValueError()
        if result != result.quantize(Decimal('.01')):
            raise ValueError()
        return result
    except (ValueError, InvalidOperation):
        raise HTTPException(400, 'Укажите неотрицательную сумму с точностью до копейки')


def expected_revision(value):
    if type(value) is not int or value < 0:
        raise HTTPException(409, 'Обновите данные выдачи: требуется expectedRevision. Правки не сохранены')
    return value


def lock_ledger(cur):
    # Same ordering in allocation, classification and every legacy act writer.
    cur.execute('SELECT pg_advisory_xact_lock(721014)')


def act_advance(cur, act_id):
    cur.execute('SELECT COALESCE(sum(amount),0) AS amount FROM performer_advance_allocations WHERE act_id=%s', (act_id,))
    row = cur.fetchone()
    return Decimal(str(row['amount'] if isinstance(row, dict) else row[0]))


def guard_act_edit(cur, act_id, data):
    if {'totalAmount','paidAmount','workJournalIds','status'} & set(data) and act_advance(cur, act_id) > 0:
        raise HTTPException(409, 'По акту зачтён аванс. Изменение финансовых данных или аннулирование требует отмены зачёта до оплаты')


def payment_for_update(cur, company_id, payment_id, revision):
    revision = expected_revision(revision)
    cur.execute('''SELECT * FROM public.accountable_payments
        WHERE id=%s AND company_id=%s AND company_scope_verified IS TRUE FOR UPDATE''', (payment_id, company_id))
    payment = cur.fetchone()
    if not payment:
        raise HTTPException(404, 'Выдача не найдена в выбранной компании')
    if payment['revision'] != revision:
        raise HTTPException(409, 'Выдача изменена в другой вкладке. Обновите данные и проверьте суммы; автоматического повтора нет')
    return payment


def record_change(cur, payment, actor, change):
    cur.execute('UPDATE accountable_payments SET revision=revision+1 WHERE id=%s RETURNING revision', (payment['id'],))
    revision = cur.fetchone()['revision']
    cur.execute('''INSERT INTO performer_advance_events(company_id,payment_id,revision,actor,change)
        VALUES(%s,%s,%s,%s,%s::jsonb)''', (payment['company_id'], payment['id'], revision,
        str(actor.get('id') or actor.get('name') or ''), json.dumps(change, ensure_ascii=False)))
    return {'ok': True, 'revision': revision}


def classify(cur, company_id, payment_id, data, actor):
    lock_ledger(cur)
    payment = payment_for_update(cur, company_id, payment_id, data.get('expectedRevision'))
    kind = data.get('paymentKind')
    if not isinstance(kind, str) or kind not in KINDS:
        raise HTTPException(400, 'Выберите подотчёт на расходы или зарплатный аванс')
    cur.execute('SELECT 1 FROM performer_advance_allocations WHERE payment_id=%s AND amount>0 LIMIT 1', (payment_id,))
    if cur.fetchone():
        raise HTTPException(409, 'Тип выдачи нельзя менять после зачёта')
    if kind == 'salary_advance':
        cur.execute('SELECT 1 FROM accountable_expenses WHERE payment_id=%s LIMIT 1', (payment_id,))
        if cur.fetchone() or Decimal(str(payment['spent_amount'] or 0)) != 0:
            raise HTTPException(409, 'У выдачи есть отчёты о расходах: её нельзя считать зарплатным авансом')
        cur.execute('SELECT 1 FROM staff WHERE id=%s AND company_id=%s AND company_scope_verified IS TRUE',
                    (payment['given_to_id'], company_id))
        if not cur.fetchone():
            raise HTTPException(409, 'Сначала подтвердите точного получателя выдачи в выбранной компании')
    cur.execute('UPDATE accountable_payments SET payment_kind=%s WHERE id=%s', (kind, payment_id))
    return record_change(cur, payment, actor, {'paymentKind': kind, 'previousKind': payment['payment_kind']})


def allocate(cur, company_id, payment_id, data, actor, require_legacy, has_package_access):
    lock_ledger(cur)
    payment = payment_for_update(cur, company_id, payment_id, data.get('expectedRevision'))
    if payment['payment_kind'] != 'salary_advance':
        raise HTTPException(409, 'Зачесть можно только подтверждённый зарплатный аванс')
    act_id = data.get('actId')
    if type(act_id) is not int or act_id <= 0:
        raise HTTPException(400, 'Выберите акт конкретного пакета')
    amount = money(data.get('amount'))
    cur.execute('''SELECT a.* FROM interim_acts a
        JOIN projects p ON p.id=%s AND p.company_id=a.company_id AND p.name=a.project
        JOIN staff s ON s.id=a.master_id AND s.company_id=a.company_id AND s.company_scope_verified IS TRUE
        WHERE a.id=%s AND a.company_id=%s AND a.master_id=%s
          AND NOT EXISTS(SELECT 1 FROM projects other WHERE other.company_id=p.company_id AND other.name=p.name AND other.id<>p.id)
        FOR UPDATE OF a''',
        (payment['project_id'], act_id, company_id, payment['given_to_id']))
    act = cur.fetchone()
    if not act or act['source_type'] == 'daily_work':
        raise HTTPException(404, 'Акт этого сотрудника и объекта не найден')
    require_legacy(cur, act_id)
    if not has_package_access(actor, act['work_package'] or 'Основная'):
        raise HTTPException(403, 'Нет доступа к пакету работ')
    if act['status'] == 'Аннулирован' or money(act['paid_amount'] or 0) > 0:
        raise HTTPException(409, 'Зачёт нельзя менять после денежной оплаты или аннулирования акта')
    cur.execute('SELECT amount FROM performer_advance_allocations WHERE payment_id=%s AND act_id=%s', (payment_id, act_id))
    old = cur.fetchone()
    old_amount = old['amount'] if old else Decimal(0)
    cur.execute('SELECT COALESCE(sum(amount),0) AS amount FROM performer_advance_allocations WHERE payment_id=%s', (payment_id,))
    used = cur.fetchone()['amount']
    if used - old_amount + amount > money(payment['amount']):
        raise HTTPException(409, 'Сумма распределения превышает остаток зарплатного аванса')
    previously_credited = act_advance(cur, act_id)
    credited = previously_credited - old_amount + amount
    from ..tool_deductions.service import act_amount
    tools = act_amount(cur, act_id)
    retained = money(act.get('retention_amount') or 0)-money(act.get('retention_released') or 0)
    if credited + retained + tools > money(act['total_amount']):
        raise HTTPException(409, 'Зачёт превышает остаток по акту')
    cur.execute('''INSERT INTO performer_advance_allocations(company_id,payment_id,act_id,amount)
        VALUES(%s,%s,%s,%s) ON CONFLICT(payment_id,act_id)
        DO UPDATE SET amount=EXCLUDED.amount,updated_at=now()''', (company_id, payment_id, act_id, amount))
    prior_status = act['status'] if previously_credited == 0 else act.get('advance_prior_status')
    status = ('Оплачен' if credited + tools >= money(act['total_amount']) else 'Частично оплачен') if credited + tools else (act.get('tool_deduction_prior_status') or prior_status or 'Новый')
    cur.execute('UPDATE interim_acts SET status=%s,advance_prior_status=%s WHERE id=%s', (status, prior_status if credited else None, act_id))
    return {**record_change(cur, payment, actor, {'actId': act_id, 'amount': str(amount), 'previousAmount': str(old_amount)}),
            'actId': act_id, 'advanceAmount': float(credited), 'remainingAmount': float(money(act['total_amount']) - credited - retained - tools), 'status': status}
