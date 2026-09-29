"""Replay protection for quote responses; caller holds the request's offer locks."""
import datetime as dt
import hashlib
import json
from uuid import UUID
from fastapi import HTTPException


def submission_identity(data, actor):
    token = data.get('requestId')
    if token is None:
        return None  # Existing API clients remain supported.
    try:
        token = str(UUID(str(token)))
        serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError):
        raise HTTPException(400, 'Некорректный идентификатор или данные отправки КП')
    return dict(requestId=token, actorId=actor.get('id'), fingerprint=hashlib.sha256(serialized.encode()).hexdigest())


def is_submission_replay(cur, offer_id, identity):
    if identity is None:
        return False
    cur.execute("SELECT payload_json FROM supplier_offer_events WHERE offer_id=%s AND event_type='responded' ORDER BY id DESC", (offer_id,))
    for row in cur.fetchall():
        payload = json.loads(row['payload_json'] or '{}')
        prior = payload.get('_submission', {})
        if prior.get('requestId') == identity['requestId']:
            if prior != identity:
                raise HTTPException(409, 'Эта отправка уже выполнена с другими данными')
            return True
    return False


def require_current_response(data, current):
    if current['status'] not in ('Ожидает ответа', 'Получено', 'Отозвано'):
        raise HTTPException(409, 'Решение по КП уже принято. Обновите заявки.')
    if 'expectedRespondedAt' in data:
        raw = data['expectedRespondedAt']
        try:
            expected = dt.datetime.fromisoformat(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise HTTPException(400, 'Некорректная версия КП')
        if expected != current.get('responded_at'):
            raise HTTPException(409, 'КП уже изменено. Обновите заявки перед редактированием.')


def log_response(cur, offer_id, status_from, actor, data, identity):
    allowed = {'action', 'pricePerUnit', 'totalPrice', 'deliveryDays', 'paymentTerms',
               'vatIncluded', 'validUntil', 'supplierMessage', 'pdfUrl', 'itemsKp'}
    payload = {key: data[key] for key in allowed if key in data}
    if identity is not None:
        payload['_submission'] = identity
    cur.execute("""INSERT INTO supplier_offer_events
        (offer_id,event_type,status_from,status_to,actor_name,actor_role,payload_json)
        VALUES (%s,'responded',%s,'Получено',%s,%s,%s)""", (
            offer_id, status_from, actor.get('name') or actor.get('email') or '',
            actor.get('role') or '', json.dumps(payload, ensure_ascii=False)))
