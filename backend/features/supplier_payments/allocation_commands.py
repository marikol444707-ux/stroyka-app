"""A complete replacement map with optimistic version, not an extra payment."""
from uuid import UUID

from fastapi import HTTPException

from .commands import positive_id
from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


def normalize_allocation_command(body):
    fields = {'requestId', 'groupId', 'expectedVersion', 'reason', 'rows'}
    if not isinstance(body, dict) or set(body) != fields:
        raise HTTPException(422, 'Нужны UUID, группа, версия, основание и полная карта распределения')
    try:
        request_id = str(UUID(body['requestId']))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Некорректный UUID распределения') from None
    group_id = positive_id(body['groupId'], 9223372036854775807)
    version = body['expectedVersion']
    if type(version) is not int or not 0 <= version < 2147483647:
        raise HTTPException(422, 'Некорректная версия распределения')
    reason = body['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise HTTPException(422, 'Укажите основание распределения, до 1000 символов')
    rows = body['rows']
    if not isinstance(rows, list) or len(rows) > 2000:
        raise HTTPException(422, 'Допускается не более 2000 строк распределения одного счёта')
    result, pairs = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'paymentId', 'receiptId', 'amount'}:
            raise HTTPException(422, 'Недопустимые поля строки распределения')
        payment_id = positive_id(row['paymentId'], 9223372036854775807)
        receipt_id = positive_id(row['receiptId'], 9223372036854775807)
        pair = (payment_id, receipt_id)
        if pair in pairs:
            raise HTTPException(422, 'Одна пара платёж/накладная указана повторно')
        pairs.add(pair)
        try:
            if type(row['amount']) not in (str, int):
                raise ValueError()
            amount = schedule_paid_amount(row['amount'])
            if amount <= 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, 'Распределяемая сумма должна быть положительной и точной до копейки') from None
        result.append(dict(paymentId=payment_id, receiptId=receipt_id, amount=format(amount, '.2f')))
    result.sort(key=lambda row: (row['paymentId'], row['receiptId']))
    return dict(requestId=request_id, groupId=group_id, expectedVersion=version,
                reason=reason.strip(), rows=result)
