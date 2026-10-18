"""Atomic adapter around existing delivery receipt writers, not a new ledger.

The source match is recomputed after the stock lock. A preview never authorizes a
write. All delivery writers share this transaction; an error rolls back the whole
waybill. Their original resource/ledger/quality guards remain authoritative.
"""
import json
from decimal import Decimal, InvalidOperation

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from typing import Optional

from .resolver import resolve_receipt
from .document_lock import lock_physical_document
from .originals import retain_originals
from .receipt_originals import require_receipt_originals_schema, persist_receipt_originals


class ReceiptTransaction:
    """Suppress a legacy writer's local commit/close, retain its rollback.

    Rollback marks the adapter failed as well as reverting the physical
    transaction: a writer must not accidentally swallow an error and commit a
    partial batch later. The outer owner alone closes/commits.
    """
    def __init__(self, connection):
        self.connection = connection
        self.failed = False

    @property
    def closed(self):
        return self.connection.closed

    @property
    def autocommit(self):
        return self.connection.autocommit

    @autocommit.setter
    def autocommit(self, value):
        if value:
            raise RuntimeError('Receipt requires a transaction')
        # Do not reset session characteristics inside an active transaction.

    def cursor(self, *args, **kwargs):
        return self.connection.cursor(*args, **kwargs)

    def commit(self):
        if self.failed:
            raise RuntimeError('Receipt transaction was rolled back')

    def rollback(self):
        self.failed = True
        self.connection.rollback()

    def close(self):
        pass


def _quantity(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise HTTPException(400, 'Укажите фактически принятое количество')
    try:
        amount = Decimal(str(value).replace(',', '.'))
        if not amount.is_finite() or amount < 0 or amount > Decimal('9999999999.9999') or amount != amount.quantize(Decimal('.0001')):
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise HTTPException(400, 'Количество должно быть неотрицательным числом с точностью до 4 знаков') from None
    return amount


def _final(line):
    return bool(line.get('receivedAt')) or line.get('status') in ('Принято', 'Проблема')


def confirm_receipt(data, user, headers, deps):
    if data.get('physicalReceiptConfirmed') is not True:
        raise HTTPException(400, 'Подтвердите фактическое прибытие и проверку количества')
    actual = data.get('actualLines')
    if not isinstance(actual, list) or len(actual) > 1000:
        raise HTTPException(400, 'Укажите строки фактической приёмки')
    by_id = {}
    for row in actual:
        if not isinstance(row, dict) or type(row.get('deliveryId')) is not int or row['deliveryId'] <= 0 or row['deliveryId'] in by_id:
            raise HTTPException(400, 'Некорректная или повторная строка приёмки')
        row = dict(row)
        row['receivedQuantity'] = _quantity(row.get('receivedQuantity'))
        if row.get('qualityStatus') not in ('Принято', 'Брак', 'Несоответствие', 'Недостача', 'Частично'):
            raise HTTPException(400, 'Укажите результат проверки качества')
        by_id[row['deliveryId']] = row
    conn = deps['get_db']()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    callbacks = []
    try:
        cur.execute("SET LOCAL statement_timeout='30s'")
        deps['lock_stock'](cur)
        # Legacy writers still prepare schema; serialize before resolver reads
        # to avoid a read-lock/document-lock/DDL upgrade deadlock.
        deps['prepare_receipt_transaction'](cur)
        require_receipt_originals_schema(cur)
        match = resolve_receipt(cur, data, user, headers, deps)
        if match.get('status') != 'match' or not match.get('matchedBatch'):
            raise HTTPException(409, 'Документ не сопоставлен однозначно. Повторите проверку')
        batch = match['matchedBatch']
        # Different duplicate batch IDs must share the same document lock, even
        # when the optional stock-distribution schema is not installed.
        lock_physical_document(cur, batch['companyId'], data.get('document') or {})
        cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                    ('physical-receipt-batch:' + str(batch['companyId']) + ':' + str(batch['id']),))
        retain_originals(cur, match['originalUrls'], batch['companyId'])
        # A concurrent confirmation may have finished while this caller waited.
        match = resolve_receipt(cur, data, user, headers, deps)
        if match.get('status') != 'match' or not match.get('matchedBatch') or (match['matchedBatch']['id'], match['matchedBatch']['companyId']) != (batch['id'], batch['companyId']):
            raise HTTPException(409, 'Связь документа изменилась; повторите проверку')
        batch = match['matchedBatch']
        lines = batch['lines']
        line_ids = {line['id'] for line in lines}
        if set(by_id) - line_ids:
            raise HTTPException(409, 'Строка не относится к проверенной накладной')
        if any(not _final(line) and (line.get('warehouseInvoiceId') or
                   _quantity(line.get('receivedQuantity') or 0) > 0) for line in lines):
            raise HTTPException(409, 'История приёмки противоречива; требуется сверка без повторного оприходования')
        remaining = [line for line in lines if not _final(line)]
        if any(line['id'] not in by_id for line in remaining):
            raise HTTPException(400, 'Проверьте фактическое количество всех непринятых строк')
        if not remaining:
            conn.rollback()
            return {'ok': True, 'alreadyReceived': True, 'warehouseInvoiceIds': match.get('warehouseInvoiceIds', []), 'matchedBatch': batch}
        # Resolver validates and canonicalizes every original URL in this scope.
        originals = match['originalUrls']
        transaction = ReceiptTransaction(conn)
        results = []
        for line in sorted(remaining, key=lambda item: item['id']):
            row = by_id[line['id']]
            if row['receivedQuantity'] > _quantity(line['shippedQuantity']):
                raise HTTPException(400, 'Принятое количество превышает отгруженное')
            payload = {**row, 'receivedQuantity': str(row['receivedQuantity']),
                       'photoUrl': originals[0], 'receivedBy': user.get('name') or '',
                       'physicalReceiptConfirmed': True}
            result = deps['receive_delivery'](line['id'], payload,
                x_company_id=headers.get('x_company_id'), x_company_mode=headers.get('x_company_mode'),
                _current_user=user, connection=transaction, after_commit=callbacks)
            if transaction.failed or not result.get('ok') or (row['receivedQuantity'] > 0 and not result.get('invoiceId')):
                raise HTTPException(409, 'Приёмка не завершена; изменения отменены')
            persist_receipt_originals(cur, line['id'], batch['companyId'], originals)
            if isinstance(result.get('delivery'), dict):
                result['delivery']['receiptOriginalUrls'] = list(originals)
            results.append(result)
            if not result.get('invoiceId'):
                continue
            cur.execute('''UPDATE warehouse_invoices SET photo_urls=%s,pages_count=%s
                WHERE id=%s AND company_id=%s AND supply_delivery_id=%s''',
                (json.dumps(originals), len(originals), result['invoiceId'], batch['companyId'], line['id']))
            if cur.rowcount != 1:
                raise HTTPException(409, 'Связь накладной изменилась; повторите проверку')
        conn.commit()
    except Exception:
        if not conn.closed:
            conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    for callback in callbacks:
        try:
            callback()
        except Exception:
            # Stock is committed; optional analysis must not misreport rollback.
            pass
    return {'ok': True, 'alreadyReceived': False,
            'warehouseInvoiceIds': sorted(set(match.get('warehouseInvoiceIds', []) + [result['invoiceId'] for result in results if result.get('invoiceId')])),
            'receipts': results}


def register_receipt_confirmation(app, deps):
    @app.post('/warehouse-receipts/confirm')
    def confirm(data: dict,
                x_company_id: Optional[str] = Header(default=None, alias='X-Company-Id'),
                x_company_mode: Optional[str] = Header(default=None, alias='X-Company-Mode'),
                user: dict = Depends(deps['get_current_user'])):
        return confirm_receipt(data, user, {'x_company_id': x_company_id, 'x_company_mode': x_company_mode}, deps)
