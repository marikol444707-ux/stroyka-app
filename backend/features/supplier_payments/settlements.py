"""Cash and liability are separate. The original invoice amount never changes."""
import os
from decimal import Decimal

from fastapi import HTTPException


def available(cur):
    cur.execute("SELECT to_regprocedure('supplier_invoice_credits(integer,integer)') IS NOT NULL AS ready")
    return cur.fetchone()['ready']


def credits(cur, company_id, invoice_id):
    if not available(cur):
        return Decimal(0)
    cur.execute('SELECT supplier_invoice_credits(%s,%s) AS amount',(company_id,invoice_id))
    return cur.fetchone()['amount']


def cash_amount(kind, amount, original_kind=None):
    if kind=='credit' or (kind=='reversal' and original_kind=='credit'):
        return Decimal(0)
    if kind=='refund' or (kind=='reversal' and original_kind=='payment'):
        return -amount
    if kind=='payment' or (kind=='reversal' and original_kind=='refund'):
        return amount
    raise HTTPException(409,'Не определено направление операции')


def prepare(cur, documents, command, original, amount):
    extended=command['kind'] in ('refund','credit') or (original and original['kind'] in ('refund','credit'))
    if extended:
        if os.getenv('SUPPLIER_SETTLEMENTS_ENABLED')!='1':
            raise HTTPException(409,'Возвраты денег и корректировки пока отключены')
        if not available(cur):
            raise HTTPException(503,'Не установлена схема возвратов и корректировок')
        if len(documents)!=1 or documents[0]['kind']!='invoice':
            raise HTTPException(409,'Операция поддерживается только по самостоятельному счёту')
        cur.execute("SELECT id FROM supplier_payment_documents WHERE company_id=%s AND document_kind='invoice' AND document_id=%s",
                    (documents[0]['companyId'],documents[0]['id']))
        root=cur.fetchone()
        if not root:
            raise HTTPException(409,'Сначала зарегистрируйте счёт в журнале оплат')
        cur.execute('SELECT supplier_allocation_root(%s,%s)',(root['id'],documents[0]['companyId']))
    effective={}
    for doc in documents:
        reduction=credits(cur,doc['companyId'],doc['id']) if doc['kind']=='invoice' else Decimal(0)
        if command['kind']=='credit':
            reduction+=amount
        elif original and original['kind']=='credit':
            reduction-=amount
        if not 0<=reduction<=doc['amount']:
            raise HTTPException(409,'Корректировка превышает оставшуюся сумму счёта')
        effective[(doc['kind'],doc['id'])]=doc['amount']-reduction
    return effective


def projection(cur, doc):
    reduction=credits(cur,doc['companyId'],doc['id']) if doc['kind']=='invoice' else Decimal(0)
    effective=doc['amount']-reduction
    return dict(creditAmount=format(reduction,'.2f'),effectiveAmount=format(effective,'.2f'),
                remainingAmount=format(max(Decimal(0),effective-doc['paidAmount']),'.2f'),
                overpaidAmount=format(max(Decimal(0),doc['paidAmount']-effective),'.2f'),
                settlementsEnabled=os.getenv('SUPPLIER_SETTLEMENTS_ENABLED')=='1' and doc['kind']=='invoice' and available(cur))


def invoice_reductions(cur, rows):
    if not rows or not available(cur):
        return {}
    cur.execute('''SELECT company_id,document_id,sum(amount) AS amount FROM supplier_payment_operations o
        WHERE document_kind='invoice' AND document_id=ANY(%s) AND kind='credit'
          AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations r WHERE r.reverses_id=o.id)
        GROUP BY company_id,document_id''',([row['id'] for row in rows],))
    return {(row['company_id'],row['document_id']):row['amount'] for row in cur.fetchall()}


def invoice_fields(row, reductions):
    reduction=reductions.get((row['company_id'],row['id']))
    if reduction is None:
        return {}
    effective=row['amount']-reduction
    paid=row['paid_amount'] or Decimal(0)
    return dict(creditAmount=float(reduction),effectiveAmount=float(effective),
                remainingAmount=float(max(Decimal(0),effective-paid)),
                overpaidAmount=float(max(Decimal(0),paid-effective)))
