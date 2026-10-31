"""Caller-independent validation and transaction ownership. Never opens a second DB."""
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID
from fastapi import HTTPException


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('0.01')):
            raise ValueError()
        return amount
    except (InvalidOperation, ValueError):
        raise HTTPException(422, 'Сумма должна быть неотрицательной и точной до копейки') from None


def normalize(body, invoice_id):
    if not isinstance(body, dict) or set(body) != {'requestId','companyId','amount','expectedPaidAmount','paidAt'}:
        raise HTTPException(422, 'Неверные поля команды оплаты')
    try:
        key = str(UUID(body['requestId']))
        paid_at = date.fromisoformat(body['paidAt']).isoformat()
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(422, 'Неверный UUID или дата оплаты') from None
    company = body['companyId']
    if type(company) is not int or company <= 0 or type(invoice_id) is not int or invoice_id <= 0:
        raise HTTPException(422, 'Требуется точная компания и счёт')
    amount, expected = money(body['amount']), money(body['expectedPaidAmount'])
    if amount <= 0:
        raise HTTPException(422, 'Сумма оплаты должна быть больше нуля')
    return dict(requestId=key, companyId=company, invoiceId=invoice_id,
                amount=format(amount,'.2f'), expectedPaidAmount=format(expected,'.2f'), paidAt=paid_at)


def fingerprint(command, actor_id):
    return hashlib.sha256(json.dumps({**command,'actorId':actor_id}, sort_keys=True,
                                     separators=(',',':')).encode()).hexdigest()


def replay(cur, command, actor_id):
    cur.execute('SELECT fingerprint,result FROM legacy_supplier_payment_requests WHERE company_id=%s AND request_id=%s',
                (command['companyId'],command['requestId']))
    row = cur.fetchone()
    if row:
        if row[0] != fingerprint(command,actor_id):
            raise HTTPException(409, 'Идентификатор оплаты уже использован с другими данными')
        return row[1]
    return None


def complete(cur, command, actor_id, result):
    cur.execute('''INSERT INTO legacy_supplier_payment_requests
        (company_id,request_id,invoice_id,actor_id,fingerprint,project_payment_id,result)
        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)''',
        (command['companyId'],command['requestId'],command['invoiceId'],actor_id,
         fingerprint(command,actor_id),result['projectPaymentId'],json.dumps(result)))
    return result


def execute(get_db, worker, invoice_id, body, user, company_header, mode_header):
    command = normalize(body,invoice_id)
    if company_header != str(command['companyId']) or mode_header != 'company':
        raise HTTPException(409, 'Выбранная компания не совпадает с командой оплаты')
    conn = get_db()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        try:
            # Same company/request key across invoices serializes before physical locks.
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                        (f"legacy-supplier-payment:{command['companyId']}:{command['requestId']}",))
            result = worker(cur,invoice_id,{},company_header,mode_header,user,payment_command=command)
            conn.commit()
            return result
        finally:
            cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
