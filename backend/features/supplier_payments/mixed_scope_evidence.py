"""Internal transactional review save; no cash baseline or opening confirmation."""
import re
from uuid import UUID
from fastapi import HTTPException
from .commands import positive_id
from .reads import transaction
from .mixed_opening_review import review, source_evidence


def normalize(body):
    if not isinstance(body,dict) or set(body)!={'requestId','invoiceId','evidenceHash','reason'}:
        raise HTTPException(422,'Нужны UUID, счёт, результат сверки и основание')
    try: request_id=str(UUID(body['requestId']))
    except (ValueError,TypeError,AttributeError):
        raise HTTPException(422,'Некорректный UUID сверки') from None
    invoice_id=positive_id(body['invoiceId'])
    if not isinstance(body['evidenceHash'],str) or not re.fullmatch('[a-f0-9]{64}',body['evidenceHash']):
        raise HTTPException(422,'Некорректный результат сверки')
    if not isinstance(body['reason'],str) or not 1<=len(body['reason'].strip())<=1000:
        raise HTTPException(422,'Укажите основание сверки')
    return dict(requestId=request_id,invoiceId=invoice_id,evidenceHash=body['evidenceHash'],reason=body['reason'].strip())


def save_review(get_db, authorize_write, actor_id, company_id, body):
    """Caller supplies current financial WRITE authority, never a client callback.

    The read transaction context always rolls back on exit, including failures;
    only this explicit successful save commits. Company locking serializes UUIDs.
    """
    command=normalize(body); positive_id(actor_id);positive_id(company_id)
    with transaction(dict(get_db=get_db,authorize_read=authorize_write),company_id) as cur:
        current=review(cur,authorize_write,actor_id,company_id,command['invoiceId'])
        if current['evidenceHash']!=command['evidenceHash']:
            raise HTTPException(409,'Документы изменились после просмотра. Выполните сверку повторно')
        cur.execute('''SELECT to_regclass('public.supplier_mixed_scope_reviews') IS NOT NULL
            AND NOT EXISTS(SELECT 1 FROM (VALUES ('supplier_mixed_scope_insert'),
                ('supplier_mixed_scope_no_truncate')) required(name)
                WHERE NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('public.supplier_mixed_scope_reviews')
                    AND tgname=required.name AND tgenabled IN ('O','A'))) AS ready''')
        if not cur.fetchone()['ready']:
            raise HTTPException(503,'Схема сохранения сверки не подготовлена')
        cur.execute('SELECT * FROM supplier_mixed_scope_reviews WHERE company_id=%s AND request_id=%s',
                    (company_id,command['requestId']))
        previous=cur.fetchone()
        if previous:
            if (previous['actor_id'],previous['invoice_id'],previous['warehouse_id'],previous['reason'])!=(
                    actor_id,command['invoiceId'],current['warehouseId'],command['reason']):
                raise HTTPException(409,'UUID сверки уже использован с другими данными')
            # Compare stored JSON directly in SQL to avoid numeric decoding loss.
            cur.execute('''SELECT invoice_snapshot=to_jsonb(i) AND warehouse_snapshot=to_jsonb(w)
                AND package_scope=supplier_mixed_package_scope(w.items::text,i.work_package) AS same
                FROM supplier_mixed_scope_reviews r JOIN supplier_invoices i ON i.id=r.invoice_id
                JOIN warehouse_invoices w ON w.id=r.warehouse_id WHERE r.id=%s''',(previous['id'],))
            if not cur.fetchone()['same']:
                raise HTTPException(409,'Сохранённая сверка относится к прежней версии документов')
            review_id=previous['id']
        else:
            sources=source_evidence(cur,company_id,command['invoiceId'],current['warehouseId'])
            cur.execute('''INSERT INTO supplier_mixed_scope_reviews
                (company_id,invoice_id,warehouse_id,request_id,actor_id,reason,package_scope,invoice_snapshot,warehouse_snapshot)
                SELECT %s,i.id,w.id,%s,%s,%s,supplier_mixed_package_scope(w.items::text,i.work_package),%s::jsonb,%s::jsonb
                FROM supplier_invoices i JOIN warehouse_invoices w ON w.id=i.warehouse_invoice_id
                WHERE i.id=%s AND i.company_id=%s AND w.company_id=%s RETURNING id''',
                (company_id,command['requestId'],actor_id,command['reason'],sources['invoice'],sources['warehouse'],
                 command['invoiceId'],company_id,company_id))
            review_id=cur.fetchone()['id']
            cur.connection.commit()
        return dict(reviewId=review_id,companyId=company_id,invoiceId=command['invoiceId'],
                    warehouseId=current['warehouseId'],requestId=command['requestId'],
                    evidenceHash=command['evidenceHash'],newCashAmount='0.00',openingConfirmed=False)
