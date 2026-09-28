"""Explicit initial paid balance, with no cash operation or line reconstruction."""
import hashlib
import json
import re
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .commands import positive_id, command_fingerprint
from .engine import _baseline, _documents
from .policy import validate_new_payment


def normalize(body):
    if not isinstance(body, dict) or set(body) != {'requestId','invoiceId','reviewedHash','reason'}:
        raise HTTPException(422, 'Нужны UUID, счёт, результат сверки и основание')
    try:
        request_id = str(UUID(body['requestId']))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Некорректный UUID подтверждения') from None
    if not isinstance(body['reviewedHash'], str) or not re.fullmatch('[a-f0-9]{64}',body['reviewedHash']):
        raise HTTPException(422, 'Некорректный результат сверки')
    reason=body['reason']
    if not isinstance(reason,str) or not 1 <= len(reason.strip()) <= 1000:
        raise HTTPException(422, 'Укажите основание сверки, до 1000 символов')
    return dict(requestId=request_id, documentKind='invoice', documentId=positive_id(body['invoiceId']),
                kind='opening', reviewedHash=body['reviewedHash'], reason=reason.strip())


def require_schema(cur):
    cur.execute("""SELECT to_regclass('public.supplier_opening_confirmations') IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM (VALUES ('supplier_opening_insert'),
            ('supplier_opening_immutable'),('supplier_opening_no_truncate')) required(name)
            WHERE NOT EXISTS (SELECT 1 FROM pg_trigger t
                WHERE t.tgrelid=to_regclass('public.supplier_opening_confirmations')
                  AND t.tgname=required.name AND t.tgenabled IN ('O','A'))) AS ready""")
    if not cur.fetchone()['ready']:
        raise HTTPException(503,'Схема подтверждения начальных остатков не подготовлена')


def candidate(cur, context, company_id, invoice_id):
    require_schema(cur)
    command=dict(documentKind='invoice',documentId=invoice_id,kind='payment')
    docs=_documents(context,company_id,command)
    if len(docs)!=1:
        raise HTTPException(409,'Связанный с накладной счёт требует отдельной сверки')
    doc=docs[0]
    validate_new_payment(cur,context,command,Decimal(1))
    cur.execute("SELECT id FROM supplier_payment_documents WHERE company_id=%s AND document_kind='invoice' AND document_id=%s",(company_id,invoice_id))
    if cur.fetchone():
        raise HTTPException(409,'Счёт уже зарегистрирован в журнале оплат')
    cur.execute('SELECT id FROM supplier_invoice_line_specs WHERE company_id=%s AND invoice_id=%s',(company_id,invoice_id))
    if cur.fetchone():
        raise HTTPException(409,'Для нового счёта с исходными строками перенос не требуется')
    cur.execute('SELECT to_jsonb(i)::text AS source,paid_amount FROM supplier_invoices i WHERE id=%s AND company_id=%s',(invoice_id,company_id))
    row=cur.fetchone()
    if row['paid_amount'] is None:
        raise HTTPException(409,'Историческая сумма оплаты не указана')
    evidence=json.dumps(doc,sort_keys=True,default=str,separators=(',',':'))+'\n'+row['source']
    digest=hashlib.sha256(evidence.encode()).hexdigest()
    return doc,row['source'],dict(invoiceId=invoice_id,companyId=company_id,
        amount=format(doc['amount'],'.2f'), openingPaid=format(doc['paidAmount'],'.2f'),
        remainingAmount=format(doc['amount']-doc['paidAmount'],'.2f'),newCashAmount='0.00',reviewedHash=digest)


def _result(cur,row):
    cur.execute('SELECT document_id,amount,opening_paid FROM supplier_payment_documents WHERE id=%s AND company_id=%s',
                (row['document_record_id'],row['company_id']))
    doc=cur.fetchone()
    return dict(confirmationId=row['id'],invoiceId=doc['document_id'],companyId=row['company_id'],
                requestId=str(row['request_id']),openingPaid=format(doc['opening_paid'],'.2f'),
                amount=format(doc['amount'],'.2f'),newCashAmount='0.00')


def confirm(get_db, resolve, actor_id, company_id, body):
    command=normalize(body)
    positive_id(actor_id);positive_id(company_id)
    fingerprint=command_fingerprint(company_id,actor_id,command)
    conn=get_db()
    try:
        conn.autocommit=False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(1735289201,company_id))
            # Live financial WRITE authorization always precedes replay.
            context=resolve(cur,actor_id,company_id,command)
            require_schema(cur)
            cur.execute('SELECT * FROM supplier_opening_confirmations WHERE company_id=%s AND request_id=%s',
                        (company_id,command['requestId']))
            row=cur.fetchone()
            if row:
                if row['fingerprint']!=fingerprint:
                    raise HTTPException(409,'UUID подтверждения уже использован с другими данными')
                return _result(cur,row)
            doc,source,preview=candidate(cur,context,company_id,command['documentId'])
            if preview['reviewedHash']!=command['reviewedHash']:
                raise HTTPException(409,'Счёт изменился после сверки. Проверьте его повторно')
            record=_baseline(cur,doc,company_id)
            cur.execute('''INSERT INTO supplier_opening_confirmations
                (company_id,request_id,fingerprint,document_record_id,actor_id,actor_name,reason,source_snapshot,reviewed_hash)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *''',
                (company_id,command['requestId'],fingerprint,record['id'],actor_id,context['actorName'],
                 command['reason'],source,command['reviewedHash']))
            result=_result(cur,cur.fetchone())
        conn.commit()
        return result
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
