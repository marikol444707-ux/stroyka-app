"""Strict intent for atomic refunds; no endpoint or financial authority here."""
import datetime as dt
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from .commands import positive_id
from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


def _invalid(message):
    raise HTTPException(422, message)


def _amount(value, *, positive=False):
    try:
        if type(value) not in (str, int):
            raise ValueError()
        amount = schedule_paid_amount(value)
        if positive and amount <= 0:
            raise ValueError()
        return amount
    except ValueError:
        _invalid('Сумма возврата должна быть точной до копейки и неотрицательной; возврат и строки должны быть положительными')


def normalize_refund_command(body):
    fields = {'requestId', 'groupId', 'expectedVersion', 'paymentId', 'amount',
              'unallocatedAmount', 'paidAt', 'reason', 'releases'}
    if not isinstance(body, dict) or set(body) != fields:
        _invalid('Укажите UUID, группу, версию, платёж, сумму, дату, основание и распределение возврата')
    try:
        request_id = str(UUID(body['requestId']))
        paid_at = dt.date.fromisoformat(body['paidAt']).isoformat()
    except (TypeError, ValueError, AttributeError):
        _invalid('Нужны UUID операции и дата YYYY-MM-DD')
    group_id = positive_id(body['groupId'], 9223372036854775807)
    payment_id = positive_id(body['paymentId'], 9223372036854775807)
    version = body['expectedVersion']
    if type(version) is not int or not 0 <= version < 2147483647:
        _invalid('Некорректная версия распределения')
    reason = body['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        _invalid('Укажите основание возврата, до 1000 символов')
    amount = _amount(body['amount'], positive=True)
    free = _amount(body['unallocatedAmount'])
    releases = body['releases']
    if not isinstance(releases, list) or len(releases) > 2000:
        _invalid('Допускается не более 2000 строк возврата')
    rows, seen, total = [], set(), Decimal(0)
    for row in releases:
        if not isinstance(row, dict) or set(row) != {'receiptId', 'amount'}:
            _invalid('Недопустимые поля строки возврата')
        receipt_id = positive_id(row['receiptId'], 9223372036854775807)
        if receipt_id in seen:
            _invalid('Приёмка указана повторно')
        seen.add(receipt_id)
        released = _amount(row['amount'], positive=True)
        total += released
        rows.append(dict(receiptId=receipt_id, amount=format(released, '.2f')))
    if total + free != amount:
        _invalid('Сумма по приёмкам и свободному остатку должна совпадать с возвратом')
    return dict(requestId=request_id, groupId=group_id, expectedVersion=version,
                paymentId=payment_id, amount=format(amount, '.2f'),
                unallocatedAmount=format(free, '.2f'), paidAt=paid_at,
                reason=reason.strip(), releases=sorted(rows, key=lambda row: row['receiptId']))
