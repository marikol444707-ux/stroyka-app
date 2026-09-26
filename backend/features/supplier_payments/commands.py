"""Strict commands: identity and money are not inferred from free-form notes."""
import datetime as dt
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


def positive_id(value, maximum=2147483647):
    if type(value) is not int or not 0 < value <= maximum:
        raise HTTPException(422, 'Некорректный идентификатор')
    return value


def normalize_command(body):
    allowed = {'requestId', 'kind', 'documentKind', 'documentId', 'amount', 'paidAt', 'reason', 'reversesId'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise HTTPException(422, 'Недопустимые поля операции')
    try:
        request_id = str(UUID(body['requestId']))
        paid_at = dt.date.fromisoformat(body['paidAt']).isoformat()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(422, 'Нужны UUID операции и дата YYYY-MM-DD')
    kind = body.get('kind')
    if kind not in ('payment', 'reversal') or body.get('documentKind') not in ('invoice', 'warehouse'):
        raise HTTPException(422, 'Недопустимый вид операции или документа')
    reason = body.get('reason')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise HTTPException(422, 'Укажите основание операции, до 1000 символов')
    amount, reverses_id = None, None
    if kind == 'payment':
        if 'reversesId' in body:
            raise HTTPException(422, 'Платёж не является сторно')
        try:
            value = schedule_paid_amount(body.get('amount'))
            if value <= 0:
                raise ValueError()
            amount = format(value, '.2f')
        except ValueError:
            raise HTTPException(422, 'Сумма должна быть положительной и точной до копейки')
    else:
        if 'amount' in body:
            raise HTTPException(422, 'Сумма сторно берётся из исходной операции')
        reverses_id = positive_id(body.get('reversesId'), 9223372036854775807)
    return dict(requestId=request_id, kind=kind, documentKind=body['documentKind'],
                documentId=positive_id(body.get('documentId')), amount=amount, paidAt=paid_at,
                reason=reason.strip(), reversesId=reverses_id)


def command_fingerprint(company_id, actor_id, command):
    serialized = json.dumps([company_id, actor_id, command], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()
