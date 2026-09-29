from decimal import Decimal
import os

from fastapi import HTTPException

from ..work_material_accounting.quantities import quantity

REVIEWERS = ('директор', 'зам_директора', 'прораб', 'главный_инженер')
WORKERS = ('мастер', 'субподрядчик', 'бригадир')


def enabled():
    return os.environ.get('WORK_ACCEPTANCE_ENABLED') == '1'


def review_quantities(submitted, accepted, decision, reason):
    total = quantity(submitted)
    if decision == 'accept':
        accepted = quantity(accepted)
        if accepted > total:
            raise HTTPException(400, 'Нельзя принять больше заявленного объёма')
    elif decision == 'return' and accepted in (None, 0, '0') and not isinstance(accepted, bool):
        accepted = Decimal('0')
    else:
        raise HTTPException(400, 'Выберите приёмку или возврат всего объёма на доработку')
    remaining = total - accepted
    if remaining and not str(reason or '').strip():
        raise HTTPException(400, 'Укажите замечания для непринятого объёма')
    return accepted, remaining


def guard_legacy_update(work, actor, data):
    status = work.get('status')
    if status == 'Подтверждено':
        if actor.get('role') in WORKERS or 'status' in data or 'quantity' in data:
            raise HTTPException(409, 'Принятая работа защищена от изменения. Требуется отдельная корректировка')
    if 'quantity' in data:
        quantity(data['quantity'])
    if data.get('status') == 'Подтверждено':
        accepted = quantity(data.get('quantity', work.get('quantity')))
        if accepted > quantity(work.get('quantity')):
            raise HTTPException(400, 'Нельзя принять больше заявленного объёма')
    if data.get('status') in ('Подтверждено', 'Отклонено', 'Аннулировано') and actor.get('role') not in REVIEWERS:
        raise HTTPException(403, 'Решение по приёмке принимает прораб, главный инженер или руководство')
