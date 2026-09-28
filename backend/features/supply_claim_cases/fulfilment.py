"""Physical claim actions. No new invoice, payment or usable stock on shipment."""
import os
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException


def quantity(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 < number < 10000000000 or number != number.quantize(Decimal('.0001')):
            raise ValueError()
        return number
    except (InvalidOperation, ValueError):
        raise HTTPException(400, 'Укажите положительное количество, не более четырёх знаков после запятой') from None


def context(cur, claim, role):
    empty = dict(canReturn=False, canReplace=False)
    if any(os.getenv(flag) != '1' for flag in ('SUPPLY_CLAIM_FULFILMENT_ENABLED','SUPPLY_CLAIMS_ENABLED',
            'SUPPLIER_PARTIAL_RECEIPTS_ENABLED','OWNED_DELIVERY_SOURCES_ENABLED','OWNED_DELIVERY_QUALITY_ENABLED')):
        return empty
    cur.execute("SELECT to_regclass('supply_claim_fulfilments') AS ready")
    if not cur.fetchone()['ready']:
        return empty
    cur.execute('''SELECT d.* FROM supply_deliveries d WHERE d.id=%s AND d.company_id=%s
        AND (EXISTS(SELECT 1 FROM supplier_receipt_exceptions e WHERE e.delivery_id=d.id)
          OR EXISTS(SELECT 1 FROM supplier_receipt_line_proofs p JOIN supplier_payment_receipt_relations r
            ON r.id=p.receipt_relation_id WHERE r.source_delivery_id=d.id))''', (claim['deliveryId'],claim['companyId']))
    delivery = cur.fetchone()
    if not delivery:
        return empty
    rejected = delivery['received_quantity'] if delivery['quality_status'] in ('Брак','Несоответствие') else Decimal(0)
    cur.execute('SELECT action,COALESCE(sum(quantity),0) AS quantity FROM supply_claim_fulfilments WHERE claim_id=%s GROUP BY action', (claim['id'],))
    totals = {row['action']:row['quantity'] for row in cur.fetchall()}
    remaining_return = rejected-totals.get('return',0)
    remaining_replace = rejected+delivery['shortage_quantity']-totals.get('replace',0)
    opened = claim['status'] in ('Открыта','В работе')
    return dict(canReturn=opened and remaining_return>0 and role in ('директор','зам_директора','кладовщик','прораб'),
                canReplace=opened and remaining_replace>0 and role=='поставщик',
                returnRemaining=str(remaining_return), replacementRemaining=str(remaining_replace), unit=delivery['unit'])


def execute(cur, claim, actor, data):
    from ..supplier_payments.partial_receipt_runtime import supports_managed_receipts
    caps = context(cur,claim,actor['role'])
    key = 'canReturn' if data['action']=='return' else 'canReplace'
    if not caps[key]:
        raise HTTPException(409, 'Действие недоступно: проверьте состояние претензии и оставшееся количество')
    qty = quantity(data.get('quantity'))
    remaining = caps['returnRemaining' if data['action']=='return' else 'replacementRemaining']
    if qty>Decimal(remaining):
        raise HTTPException(409, 'Количество превышает остаток по претензии')
    cur.execute('SELECT * FROM supply_deliveries WHERE id=%s AND company_id=%s', (claim['deliveryId'],claim['companyId']))
    source = cur.fetchone()
    if not supports_managed_receipts(cur,claim['companyId'],source['source_supplier_invoice_id']):
        raise HTTPException(409, 'Для действия требуется поддерживаемая приёмка по счёту')
    delivery_id = None
    if data['action']=='replace':
        # Copy only immutable source identity. Receipt/quality/claim fields start empty.
        cur.execute('''INSERT INTO supply_deliveries
            (company_id,request_id,offer_id,supplier_id,supplier_name,project,work_package,
             material_name,unit,planned_quantity,shipped_quantity,price_per_unit,total_price,
             contract_version_id,source_supplier_invoice_id,status,shipped_at,waybill_number)
            SELECT company_id,request_id,offer_id,supplier_id,supplier_name,project,work_package,
             material_name,unit,planned_quantity,%s,price_per_unit,round(%s*price_per_unit,2),
             contract_version_id,source_supplier_invoice_id,'В пути',now(),%s
            FROM supply_deliveries WHERE id=%s RETURNING id''',
            (qty,qty,'Замена по претензии №'+str(claim['id']),claim['deliveryId']))
        delivery_id = cur.fetchone()['id']
    return dict(quantity=str(qty),replacementDeliveryId=delivery_id)


def record(cur, claim, action, event_id, result):
    cur.execute('''INSERT INTO supply_claim_fulfilments
        (event_id,claim_id,company_id,action,quantity,replacement_delivery_id)
        VALUES(%s,%s,%s,%s,%s,%s)''',
        (event_id,claim['id'],claim['companyId'],action,result['quantity'],result['replacementDeliveryId']))


def has_fulfilment(cur, claim):
    cur.execute("SELECT to_regclass('supply_claim_fulfilments') AS ready")
    if not cur.fetchone()['ready']:
        return False
    cur.execute('SELECT 1 FROM supply_claim_fulfilments WHERE claim_id=%s AND company_id=%s LIMIT 1',
                (claim['id'],claim['companyId']))
    return bool(cur.fetchone())


def effective_status_rows(cur, rows):
    """Keep original receipt facts; resolved claims no longer block fulfilment forever."""
    cur.execute("SELECT to_regclass('supply_claim_fulfilments') AS ready")
    ready=cur.fetchone()
    if not (ready['ready'] if isinstance(ready,dict) else ready[0]):
        return rows
    cur.execute('''SELECT d.id,d.quality_status FROM supply_deliveries d JOIN supply_claims c ON c.id=d.claim_id
        WHERE d.id=ANY(%s) AND d.status='Проблема' AND c.status IN ('Решена','Закрыта')
            AND EXISTS(SELECT 1 FROM supply_claim_fulfilments f WHERE f.claim_id=c.id)''',
        ([row['id'] for row in rows],))
    resolved={(row['id'] if isinstance(row,dict) else row[0]):
              (row['quality_status'] if isinstance(row,dict) else row[1]) for row in cur.fetchall()}
    return [{**row,'status':'Принято','received_quantity':0 if resolved[row['id']] in ('Брак','Несоответствие')
             else row['received_quantity']} if row['id'] in resolved else row for row in rows]


def enrich_deliveries(cur, rows):
    """Add provenance only to deliveries already filtered by current authorization."""
    if not rows:
        return
    cur.execute("SELECT to_regclass('supply_claim_fulfilments') AS ready")
    if not cur.fetchone()['ready']:
        return
    cur.execute('''SELECT d.id,d.company_id,f.claim_id AS replacement_claim_id,
        (c.status IN ('Решена','Закрыта') AND EXISTS(SELECT 1 FROM supply_claim_fulfilments x WHERE x.claim_id=c.id)) AS claim_resolved
        FROM supply_deliveries d LEFT JOIN supply_claim_fulfilments f ON f.replacement_delivery_id=d.id AND f.company_id=d.company_id
        LEFT JOIN supply_claims c ON c.id=d.claim_id WHERE d.id=ANY(%s)''', ([row['id'] for row in rows],))
    contexts={(row['id'],row['company_id']):row for row in cur.fetchall()}
    for row in rows:
        context=contexts.get((row['id'],row['companyId']))
        if context:
            row.update(replacementClaimId=context['replacement_claim_id'],claimResolved=bool(context['claim_resolved']))
