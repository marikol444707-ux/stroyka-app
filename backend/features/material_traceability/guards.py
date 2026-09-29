"""Integrity guards remain active even when distribution UI/API is disabled."""
from decimal import Decimal
from fastapi import HTTPException
from psycopg2 import Error as DatabaseError


def _has_lots(cur):
    cur.execute("SELECT to_regclass('public.warehouse_receipt_lots') IS NOT NULL AS present")
    return bool((cur.fetchone() or {}).get('present'))


def lock_distribution_compatible_stock(cur):
    """Same order as batch commands, before receipt/material row locks.

    Schema-based, not feature-flag-based: disabling new commands does not remove
    integrity requirements for existing allocations. No runtime DDL.
    """
    cur.execute("SELECT to_regclass('public.warehouse_distribution_operations') IS NOT NULL AS present")
    row = cur.fetchone()
    present = row.get('present') if isinstance(row, dict) else bool(row and row[0])
    if present:
        cur.execute("SET LOCAL lock_timeout='3s'")
        try:
            cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')
        except DatabaseError as error:
            if error.pgcode in ('40P01', '40001', '55P03'):
                raise HTTPException(409, 'Склад занят другой операцией. Обновите данные и повторите действие.') from error
            raise


def close_receipt_lots_for_cancellation(cur, company_id, invoice_id):
    # Caller has locked the receipt. Legacy source movements lock it too.
    if not _has_lots(cur):
        return
    cur.execute('''SELECT received_quantity,available_quantity FROM warehouse_receipt_lots
                   WHERE company_id=%s AND warehouse_invoice_id=%s ORDER BY id FOR UPDATE''',
                (company_id, invoice_id))
    for lot in cur.fetchall():
        received, available = Decimal(str(lot['received_quantity'])), Decimal(str(lot['available_quantity']))
        if not received.is_finite() or not available.is_finite() or received != available:
            raise HTTPException(409, 'Нельзя аннулировать накладную: её партия распределена или требует сверки. Сначала оформите возврат.')
    cur.execute("UPDATE warehouse_receipt_lots SET status='cancelled' WHERE company_id=%s AND warehouse_invoice_id=%s",
                (company_id, invoice_id))


def guard_main_stock_edit(cur, row, *, name, unit, quantity):
    if (name == row.get('name') and unit == row.get('unit')
            and Decimal(str(quantity or 0)) == Decimal(str(row.get('quantity') or 0))):
        return
    if not _has_lots(cur):
        return
    cur.execute('''SELECT EXISTS(SELECT 1 FROM warehouse_receipt_lots
                   WHERE company_id=%s AND LOWER(material_name)=LOWER(%s)
                     AND warehouse_location='Основной склад' AND status='active') AS present''',
                (row['company_id'], row['name']))
    if (cur.fetchone() or {}).get('present'):
        raise HTTPException(409, 'У материала есть приходные партии. Остаток, название и единицу меняйте через складские операции, не прямой правкой.')
