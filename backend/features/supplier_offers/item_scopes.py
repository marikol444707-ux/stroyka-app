"""RFQ line assignment and one-time awards. Callers hold request/company locks."""
import json
from decimal import Decimal, DecimalException
from fastapi import HTTPException
from .shipments import line_key


def rows(raw):
    return json.loads(raw) if isinstance(raw, str) else (raw or [])


def positions(raw, allowed):
    if not isinstance(raw, list) or not raw or any(type(p) is not int or p not in allowed for p in raw) or len(set(raw)) != len(raw):
        raise HTTPException(422, 'Выберите неповторяющиеся позиции заявки')
    return sorted(raw)


def request_lines(request):
    lines = rows(request.get('items_json')) or [dict(materialName=request.get('material_name'),
        quantity=request.get('quantity'), unit=request.get('unit'), workPackage=request.get('work_package') or 'Основная')]
    if len({line_key(line) for line in lines}) != len(lines):
        raise HTTPException(409, 'Объедините повторяющиеся материалы заявки перед распределением')
    return [dict(materialName=line.get('materialName') or line.get('name'), quantity=line.get('quantity'),
                 unit=line.get('unit') or request.get('unit') or 'шт',
                 workPackage=line.get('workPackage') or line.get('work_package') or request.get('work_package') or 'Основная',
                 requestPosition=index) for index, line in enumerate(lines)]


def dispatch_scopes(request, supplier_ids, raw):
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {str(sid) for sid in supplier_ids}:
        raise HTTPException(422, 'Укажите позиции для каждого выбранного поставщика')
    lines = request_lines(request)
    return {int(sid): [lines[p] for p in positions(selected, range(len(lines)))] for sid, selected in raw.items()}


def persist_scopes(cur, request_id, company_id, scopes, created):
    if scopes is None:
        return
    cur.execute('''SELECT id,supplier_id,to_jsonb(supplier_offers)->>'requested_items_json' AS requested
        FROM supplier_offers WHERE request_id=%s AND company_id=%s ORDER BY id''', (request_id, company_id))
    for offer in cur.fetchall():
        selected = scopes.get(offer['supplier_id'])
        if selected is None:
            continue
        if offer['id'] not in created:
            if rows(offer['requested']) != selected:
                raise HTTPException(409, 'Позиции уже отправленного запроса нельзя изменить. Создайте дополнительную заявку')
            continue
        cur.execute('UPDATE supplier_offers SET requested_items_json=%s WHERE id=%s',
                    (json.dumps(selected, ensure_ascii=False), offer['id']))


def offer_scope(cur, offer_id):
    cur.execute('''SELECT to_jsonb(o)->>'requested_items_json' AS requested,
        to_jsonb(o)->>'awarded_items_json' AS awarded FROM supplier_offers o WHERE id=%s''', (offer_id,))
    return cur.fetchone() or {}


def validate_response_items(requested, offered):
    """Use the server quantities; reject injected, missing and duplicate lines."""
    wanted = {line_key(line): line for line in rows(requested)}
    if not isinstance(offered, list) or len(offered) != len(wanted) or any(not isinstance(line, dict) for line in offered):
        raise HTTPException(422, 'Укажите цены по всем назначенным позициям')
    seen = set()
    result = []
    for line in offered:
        key = line_key(line)
        if key not in wanted or key in seen:
            raise HTTPException(422, 'В КП есть неназначенная или повторная позиция')
        seen.add(key)
        try:
            price = Decimal(str(line.get('pricePerUnit')))
            qty = Decimal(str(line.get('quantity')))
            expected = Decimal(str(wanted[key]['quantity']))
            if not price.is_finite() or not qty.is_finite() or price <= 0 or qty != expected or price * qty >= Decimal('1e12'):
                raise ValueError()
        except (DecimalException, ValueError, TypeError, OverflowError):
            raise HTTPException(422, 'Проверьте цену и количество назначенной позиции')
        result.append(dict(line, **{k: wanted[key][k] for k in ('materialName', 'quantity', 'unit', 'workPackage', 'requestPosition') if k in wanted[key]},
                           totalPrice=float(round(price * qty, 2))))
    return result


def award(cur, offer_id, request_id, company_id, selected=None):
    cur.execute('''SELECT o.id,o.supplier_id,o.status,o.items_kp_json,
        to_jsonb(o)->>'requested_items_json' AS requested,
        to_jsonb(o)->>'awarded_items_json' AS awarded
        FROM supplier_offers o WHERE request_id=%s AND company_id=%s ORDER BY id''', (request_id, company_id))
    offers = cur.fetchall()
    current = next(o for o in offers if o['id'] == offer_id)
    if not current['requested']:
        if any(o['requested'] for o in offers):
            raise HTTPException(409, 'Старое КП на всю заявку нельзя выбрать вместе с распределёнными позициями')
        if selected is not None:
            raise HTTPException(409, 'Это КП создано без распределения позиций')
        return False
    if current['status'] != 'Получено':
        raise HTTPException(409, 'Состав утверждённого заказа уже зафиксирован')
    quoted = validate_response_items(current['requested'], rows(current['items_kp_json']))
    available = {line['requestPosition'] for line in quoted}
    selected = positions(selected if selected is not None else sorted(available), available)
    occupied = set()
    for other in offers:
        if other['id'] == offer_id:
            continue
        if other['status'] == 'Утверждено' and not other['awarded']:
            raise HTTPException(409, 'По этой заявке уже утверждено КП на весь состав')
        occupied.update(line['requestPosition'] for line in rows(other['awarded']))
    if occupied.intersection(selected):
        raise HTTPException(409, 'Одна из позиций уже заказана у другого поставщика. Обновите КП')
    chosen = [line for line in quoted if line['requestPosition'] in selected]
    total = sum(Decimal(str(line['totalPrice'])) for line in chosen)
    # Original complete quote remains in the append-only responded event/PDF.
    cur.execute('''UPDATE supplier_offers SET status='Утверждено',awarded_items_json=%s,
        items_kp_json=%s,total_price=%s WHERE id=%s''',
        (json.dumps(chosen, ensure_ascii=False), json.dumps(chosen, ensure_ascii=False), total, offer_id))
    occupied.update(selected)
    for other in offers:
        if other['id'] == offer_id or other['status'] not in ('Получено', 'Ожидает ответа') or not other['requested']:
            continue
        if {line['requestPosition'] for line in rows(other['requested'])}.issubset(occupied):
            cur.execute("UPDATE supplier_offers SET status='Отклонено' WHERE id=%s", (other['id'],))
            cur.execute("""UPDATE supply_request_recipients SET status='КП отклонено'
                WHERE request_id=%s AND company_id=%s AND target_supplier_id=%s""", (request_id, company_id, other['supplier_id']))
    return True


def project_request(row, selected):
    result = dict(row)
    result['itemsJson'] = json.dumps(selected, ensure_ascii=False)
    result['materialName'] = selected[0]['materialName'] if len(selected) == 1 else f'{len(selected)} позиций'
    result['quantity'] = selected[0]['quantity'] if len(selected) == 1 else len(selected)
    result['unit'] = selected[0]['unit'] if len(selected) == 1 else 'поз.'
    return result


def supplier_request_scopes(cur, requests, supplier_ids, visibility_sql='', visibility_params=()):
    if not requests:
        return requests
    cur.execute('''SELECT request_id,to_jsonb(supplier_offers)->>'requested_items_json' AS requested
        FROM supplier_offers WHERE request_id=ANY(%s) AND supplier_id=ANY(%s)''' + visibility_sql,
        ([r['id'] for r in requests], supplier_ids, *visibility_params))
    scopes = {}
    legacy = set()
    for offer in cur.fetchall():
        if not offer['requested']:
            legacy.add(offer['request_id'])
        else:
            scopes.setdefault(offer['request_id'], {}).update({line['requestPosition']: line for line in rows(offer['requested'])})
    return [project_request(r, [line for _, line in sorted(scopes[r['id']].items())])
            if r['id'] in scopes and r['id'] not in legacy else r for r in requests]
