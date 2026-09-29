"""Document references to reviewed contract versions, never live profile data."""
from fastapi import HTTPException


def contract_version_id(data, enabled):
    if 'contractVersionId' not in data:
        return None
    value = data['contractVersionId']
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise HTTPException(422, 'contractVersionId должен быть положительным целым числом')
    if not enabled:
        raise HTTPException(409, 'Привязка документов к версии договора ещё не включена')
    return value


def select_invoice_contract(cur, offer_id, requested_id):
    # Caller holds the offer lock shared with contract/party version writers.
    cur.execute('''SELECT v.*, (SELECT MAX(p.version) FROM supplier_deal_parties p
                   WHERE p.offer_id=v.offer_id) AS current_party_version
                   FROM supplier_contract_versions v WHERE v.offer_id=%s
                   ORDER BY v.version DESC LIMIT 1''', (offer_id,))
    row = cur.fetchone()
    if requested_id is None:
        if row:
            raise HTTPException(409, 'Выберите проверенную версию договора для нового счёта')
        return None
    if not row or row['id'] != requested_id:
        cur.execute('SELECT id FROM supplier_contract_versions WHERE id=%s AND offer_id=%s', (requested_id, offer_id))
        if not cur.fetchone():
            raise HTTPException(403, 'Версия договора не принадлежит этой сделке')
        raise HTTPException(409, 'Версия договора изменилась. Обновите карточку')
    if row['party_version'] != row['current_party_version']:
        raise HTTPException(409, 'Состав сторон изменился. Сначала проверьте новую версию договора')
    return dict(row)


def select_shipment_contract(cur, offer_id, invoice, requested_id):
    bound_id = (invoice or {}).get('contract_version_id')
    if requested_id is not None and requested_id != bound_id:
        raise HTTPException(409, 'Отгрузка должна использовать версию договора выставленного счёта')
    if bound_id is None:
        cur.execute('SELECT id FROM supplier_contract_versions WHERE offer_id=%s LIMIT 1', (offer_id,))
        if cur.fetchone():
            raise HTTPException(409, 'Для отгрузки по договору нужен счёт с сохранённой привязкой')
        return None
    cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s AND offer_id=%s', (bound_id, offer_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(409, 'Версия договора счёта не найдена')
    return dict(row)
