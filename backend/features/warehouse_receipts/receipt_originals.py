"""Company-scoped receipt evidence linkage, independent of stock quantity.

The caller validates ownership/availability and pins every original first, then
calls this helper on its existing receipt transaction. No DDL or local commit.
"""
import json
import re

from fastapi import HTTPException


def require_receipt_originals_schema(cur):
    """Fail closed before receipt writers when the explicit migration is absent."""
    cur.execute('''SELECT
        EXISTS(SELECT 1 FROM pg_attribute
            WHERE attrelid=to_regclass('supply_deliveries')
              AND attname='receipt_original_urls' AND NOT attisdropped
              AND atttypid='jsonb'::regtype)
        AND EXISTS(SELECT 1 FROM pg_constraint
            WHERE conrelid=to_regclass('supply_deliveries')
              AND conname='supply_delivery_receipt_originals_shape'
              AND contype='c' AND convalidated)
        AND EXISTS(SELECT 1 FROM pg_trigger
            WHERE tgrelid=to_regclass('supply_deliveries')
              AND tgname='supply_delivery_receipt_originals_immutable'
              AND tgfoid=to_regprocedure('preserve_receipt_original_urls()')
              AND tgenabled IN ('O','A') AND NOT tgisinternal) AS ready''')
    row = cur.fetchone()
    if not row or not row['ready']:
        raise HTTPException(503, 'Хранение оригиналов приёмки ещё не подготовлено. Требуется обновление базы данных')


def persist_receipt_originals(cur, delivery_id, company_id, originals):
    """Set evidence once; an exact retry is harmless, a changed list is rejected."""
    if (not isinstance(originals, list) or not 1 <= len(originals) <= 30
            or any(not isinstance(url, str)
                   or not re.fullmatch(r'/tenant-files/[1-9][0-9]*/content', url)
                   for url in originals)
            or len(set(originals)) != len(originals)):
        raise HTTPException(400, 'Требуется проверенный список оригиналов в защищённом хранилище')
    cur.execute('''UPDATE supply_deliveries SET receipt_original_urls=%s::jsonb
        WHERE id=%s AND company_id=%s AND receipt_original_urls IS NULL''',
        (json.dumps(originals), delivery_id, company_id))
    if cur.rowcount == 1:
        return
    cur.execute('''SELECT receipt_original_urls FROM supply_deliveries
        WHERE id=%s AND company_id=%s''', (delivery_id, company_id))
    row = cur.fetchone()
    if not row or row['receipt_original_urls'] != originals:
        raise HTTPException(409, 'Сохранённые оригиналы приёмки изменять нельзя. Обновите карточку')
