"""Claim replies use the same current delivery disclosure boundary as reads."""
import psycopg2.extras
from fastapi import HTTPException

from .fulfilment import assert_delivery_chain
from .service import supplier_delivery_visibility_filter


def update_claim(get_db, claim_id, data, user, authorize_internal, supplier_ids):
    conn = get_db()
    cur = None
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute('SELECT * FROM supply_claims WHERE id=%s FOR UPDATE', (claim_id,))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(404, 'Претензия не найдена')
        cur.execute('''SELECT * FROM supply_deliveries WHERE id=%s AND request_id=%s
            AND offer_id=%s AND supplier_id=%s AND project=%s FOR SHARE''',
            (claim['delivery_id'], claim['request_id'], claim['offer_id'], claim['supplier_id'], claim['project']))
        delivery = cur.fetchone()
        if not delivery:
            raise HTTPException(409, 'Нарушена связь претензии с поставкой')
        if user.get('role') == 'поставщик':
            visible, params = supplier_delivery_visibility_filter(supplier_ids(cur, user), user['id'])
            cur.execute('SELECT d.id FROM supply_deliveries d WHERE d.id=%s AND ' + visible,
                        [delivery['id']] + params)
            if not cur.fetchone():
                raise HTTPException(403, 'Нет доступа к претензии')
            if {'status', 'resolvedAt'}.intersection(data):
                raise HTTPException(403, 'Закрытие претензии доступно только внутренним ролям')
        else:
            authorize_internal(cur, delivery)
        assert_delivery_chain(cur, delivery)
        fields, values = [], []
        for key, column in (('status', 'status'), ('resolution', 'resolution'), ('resolvedAt', 'resolved_at')):
            if key in data:
                fields.append(column + '=%s')
                values.append((data[key] or None) if key == 'resolvedAt' else data[key])
        if data.get('status') in ('Закрыта', 'Решена') and 'resolvedAt' not in data:
            fields.append('resolved_at=NOW()')
        if fields:
            cur.execute('UPDATE supply_claims SET ' + ','.join(fields) + ' WHERE id=%s', values + [claim_id])
        conn.commit()
        return {'ok': True}
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()
