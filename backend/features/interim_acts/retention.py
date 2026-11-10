"""Explicit guarantee retention; caller owns transaction and company authorization."""
import json
from decimal import Decimal

from fastapi import HTTPException

from ..accountable_payments.advances import money, act_advance


def held(act):
    return Decimal(str(act.get('retention_amount') or 0)) - Decimal(str(act.get('retention_released') or 0))


def guard_edit(cur, act_id, data):
    financial_statuses = ('Оплачен', 'Частично оплачен', 'Оплачен частично', 'Аннулирован')
    if not {'totalAmount', 'paidAmount', 'workJournalIds'} & set(data) and data.get('status') not in financial_statuses:
        return
    cur.execute('SELECT retention_amount FROM interim_acts WHERE id=%s', (act_id,))
    row = cur.fetchone()
    amount = (row.get('retention_amount') if isinstance(row, dict) else row[0]) if row else 0
    if Decimal(str(amount or 0)) > 0:
        raise HTTPException(409, 'По акту есть гарантийное удержание. Используйте отдельное подтверждение снятия удержания и оплату; обычное изменение заблокировано')


def change(cur, act_id, company_id, data, actor, release=False):
    revision = data.get('expectedRevision')
    if type(revision) is not int or revision < 0:
        raise HTTPException(409, 'Обновите данные удержания: требуется expectedRevision. Правки не сохранены')
    if data.get('confirmed') is not True:
        raise HTTPException(409, 'Бухгалтер должен подтвердить основание по договору')
    basis = data.get('basis')
    if not isinstance(basis, str) or not basis.strip() or len(basis.strip()) > 1000:
        raise HTTPException(400, 'Укажите основание по договору (до 1000 символов)')
    amount = money(data.get('amount'))
    cur.execute('SELECT * FROM interim_acts WHERE id=%s AND company_id=%s FOR UPDATE', (act_id, company_id))
    act = cur.fetchone()
    if not act:
        raise HTTPException(404, 'Акт не найден в выбранной компании')
    if act['retention_revision'] != revision:
        raise HTTPException(409, 'Удержание изменено в другой вкладке. Обновите данные и сверьте сумму; автоматического повтора нет')
    if act['source_type'] == 'daily_work' or act['status'] == 'Аннулирован':
        raise HTTPException(409, 'Для этого акта изменение удержания недоступно')
    credited = act_advance(cur, act_id)
    if release:
        if amount <= 0 or amount > held(act):
            raise HTTPException(409, 'Сумма снятия должна быть больше нуля и не превышать удержанный остаток')
        cur.execute('''UPDATE interim_acts SET retention_released=retention_released+%s,
            retention_revision=retention_revision+1 WHERE id=%s RETURNING retention_revision''', (amount, act_id))
        change_data = {'operation': 'release', 'amount': str(amount), 'basis': basis.strip(),
                       'previousReleased': str(act['retention_released'])}
    else:
        # Historic cash may precede the first explicit confirmation. It still limits the hold.
        if (money(act['paid_amount'] or 0) > 0 and act['retention_revision'] > 0) or money(act['retention_released']) > 0:
            raise HTTPException(409, 'После денежной оплаты или снятия удержания исходную сумму менять нельзя')
        if amount + credited + money(act['paid_amount'] or 0) > money(act['total_amount']):
            raise HTTPException(409, 'Удержание вместе с оплатой и зачтённым авансом превышает сумму акта')
        cur.execute('''UPDATE interim_acts SET retention_amount=%s,retention_basis=%s,
            paid_amount=COALESCE(paid_amount,0),retention_revision=retention_revision+1
            WHERE id=%s RETURNING retention_revision''', (amount, basis.strip(), act_id))
        change_data = {'operation': 'set', 'amount': str(amount), 'basis': basis.strip(),
                       'previousAmount': str(act['retention_amount'])}
    next_revision = cur.fetchone()['retention_revision']
    cur.execute('''INSERT INTO performer_retention_events(company_id,act_id,revision,actor,change)
        VALUES(%s,%s,%s,%s,%s::jsonb)''',
        (company_id, act_id, next_revision, str(actor.get('id') or actor.get('name') or ''),
         json.dumps(change_data, ensure_ascii=False)))
    return {'ok': True, 'actId': act_id, 'revision': next_revision, 'paymentCreated': False}
