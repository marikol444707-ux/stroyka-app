"""Manual payment commands preserve exact amounts and retry identity."""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import uuid

import psycopg2.extras
from fastapi import HTTPException


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not 0 < amount <= Decimal('99999999.99'):
            raise ValueError()
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError()
        return amount.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(422, 'Сумма должна быть положительным числом рублей с точностью до копейки')


def optional_date(value):
    if value in (None, ''):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        raise HTTPException(422, 'Дата должна быть в формате ГГГГ-ММ-ДД')


def normalize(data):
    try:
        command_id = str(uuid.UUID(str(data.get('requestId') or '')))
        company = int(data.get('companyId') or data.get('company_id'))
        contract = int(data.get('clientContractId') or data.get('client_contract_id') or 0) or None
        if company <= 0 or (contract is not None and contract <= 0):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Укажите компанию и UUID команды платежа')
    if (data.get('status') or 'paid') != 'paid':
        raise HTTPException(422, 'Зачислить можно только подтверждённый платёж')
    if (data.get('currency') or 'RUB') != 'RUB':
        raise HTTPException(422, 'Платёж учитывается в рублях')
    values = {'companyId':company, 'clientContractId':contract, 'amount':str(money(data.get('amount'))),
              'status':'paid', 'paymentDate':optional_date(data.get('paymentDate')),
              'periodStart':optional_date(data.get('periodStart')), 'periodEnd':optional_date(data.get('periodEnd'))}
    if values['periodStart'] and values['periodEnd'] and values['periodStart'] > values['periodEnd']:
        raise HTTPException(422, 'Конец периода не может быть раньше начала')
    for key, maximum in (('method',50), ('invoiceNumber',100), ('notes',4000)):
        values[key] = str(data.get(key) or '').strip()
        if len(values[key]) > maximum:
            raise HTTPException(422, 'Слишком длинное поле платежа: '+key)
    fingerprint = hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return command_id, values, fingerprint


def extend_paid_period(cur, company_id, period_end):
    if not period_end:
        return
    # Payment extends time; administrative blocking remains a separate decision.
    cur.execute('''UPDATE companies SET plan_expires_at=GREATEST(plan_expires_at,%s::date),
        payment_status=CASE WHEN GREATEST(plan_expires_at,%s::date)>=CURRENT_DATE
            THEN 'active' ELSE payment_status END WHERE id=%s''',(period_end,period_end,company_id))


def create_manual_payment(get_db, data, actor, *, load_contract, audit):
    command_id, values, fingerprint = normalize(data)
    conn = get_db()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('platform-payment:'+command_id,))
            cur.execute('SELECT id,command_fingerprint FROM company_payments WHERE command_id=%s',(command_id,))
            previous = cur.fetchone()
            if previous:
                if previous['command_fingerprint'] != fingerprint:
                    raise HTTPException(409, 'Этот UUID уже использован для другого платежа. Проверьте список зачислений.')
                conn.commit()
                return {'id':previous['id'], 'ok':True, 'replayed':True}
            cur.execute('SELECT id,name,platform_account_id FROM companies WHERE id=%s FOR UPDATE',(values['companyId'],))
            company = cur.fetchone()
            if not company:
                raise HTTPException(404, 'Компания не найдена')
            contract = load_contract(cur,values['clientContractId'],values['companyId'],company['platform_account_id'])
            cur.execute('''INSERT INTO company_payments
                (company_id,client_contract_id,amount,payment_date,method,invoice_number,status,
                 period_start,period_end,notes,created_by,command_id,command_fingerprint)
                VALUES(%s,%s,%s,%s,%s,%s,'paid',%s,%s,%s,%s,%s,%s) RETURNING id''',
                (values['companyId'],values['clientContractId'],Decimal(values['amount']),values['paymentDate'],
                 values['method'],values['invoiceNumber'],values['periodStart'],values['periodEnd'],values['notes'],
                 actor.get('name') or actor.get('email') or str(actor['id']),command_id,fingerprint))
            payment_id = cur.fetchone()['id']
            extend_paid_period(cur,values['companyId'],values['periodEnd'])
            audit(cur,actor,'payment_added','company_payment',payment_id,values['invoiceNumber'] or company['name'],
                  platform_account_id=company['platform_account_id'],company_id=values['companyId'],
                  details={**values,'requestId':command_id,'clientContractNumber':contract.get('number') if contract else None})
        conn.commit()
        return {'id':payment_id,'ok':True,'replayed':False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
