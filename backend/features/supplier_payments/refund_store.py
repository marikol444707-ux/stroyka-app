"""Internal atomic linked refund worker. No runtime endpoint is registered.

Trusted authorization callbacks pin both invoice and receipt scope. Neither
callbacks nor actor/company identity may be supplied by the request body.
"""
import os
from uuid import uuid5, UUID
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .allocation_store import _enter, _latest, _snapshot, replace_allocations_in_transaction
from .allocation_projection import Allocation
from .refund_allocation_plan import Refund, Release, plan_refund
from .refund_commands import normalize_refund_command
from .commands import command_fingerprint
from .engine import execute_in_transaction, _result

# Distinct deterministic internal revision UUID, guarded by shared namespaces.
_REVISION_NAMESPACE = UUID('4e9f651d-e125-4be0-a2ab-e633cf57886a')


def _require_schema(cur):
    from .allocation_schema import require_allocation_schema
    require_allocation_schema(cur)
    required = [
        ('supplier_payment_refund_links', 'refund_link_guard'),
        ('supplier_payment_refund_links', 'refund_link_immutable'),
        ('supplier_payment_refund_links', 'refund_link_no_truncate'),
    ] + [(table, 'refund_complete') for table in (
        'supplier_payment_refund_links', 'supplier_payment_operations',
        'supplier_payment_allocation_revisions', 'supplier_payment_allocation_rows')]
    cur.execute("""SELECT NOT EXISTS (
        SELECT 1 FROM unnest(%s::text[],%s::text[]) required(table_name,trigger_name)
        WHERE NOT EXISTS(SELECT 1 FROM pg_trigger t
            WHERE t.tgrelid=to_regclass('public.' || required.table_name)
              AND t.tgname=required.trigger_name AND t.tgenabled IN ('O','A')
        )) AS ready""", ([row[0] for row in required], [row[1] for row in required]))
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Не установлена защита возвратов по распределениям')


def refund_in_transaction(cur, authorize_allocations, authorize_payment, actor_id,
                          company_id, body, *, validate_new):
    command = normalize_refund_command(body)
    _enter(cur, authorize_allocations, actor_id, company_id, command)
    _require_schema(cur)
    fingerprint = command_fingerprint(company_id, actor_id, command)
    cur.execute('''SELECT o.*,l.fingerprint AS refund_fingerprint,l.revision_id,h.version,l.group_id
        FROM supplier_payment_operations o
        LEFT JOIN supplier_payment_refund_links l ON l.refund_operation_id=o.id
        LEFT JOIN supplier_payment_allocation_revisions h ON h.id=l.revision_id
        WHERE o.company_id=%s AND o.request_id=%s''', (company_id,command['requestId']))
    replay = cur.fetchone()
    if replay:
        if replay['refund_fingerprint'] != fingerprint:
            raise HTTPException(409, 'UUID возврата уже использован с другими данными')
        return dict(_result(replay), revisionId=replay['revision_id'], version=replay['version'], groupId=replay['group_id'])
    if os.getenv('SUPPLIER_ALLOCATED_REFUNDS_ENABLED') != '1':
        raise HTTPException(409, 'Возвраты распределённых оплат пока отключены')
    latest = _latest(cur, company_id, command['groupId'])
    version = latest['version'] if latest else 0
    if version != command['expectedVersion']:
        raise HTTPException(409, 'Распределение изменено; обновите данные')
    snapshot = _snapshot(cur, company_id, command['groupId'], new_revision=True)
    rows = []
    if latest:
        cur.execute('''SELECT * FROM supplier_payment_allocation_rows
            WHERE revision_id=%s AND company_id=%s ORDER BY payment_operation_id,receipt_relation_id''',
            (latest['id'],company_id))
        rows = cur.fetchall()
        if len(rows) != latest['row_count']:
            raise HTTPException(409, 'История распределения неполна')
    allocations = [Allocation(snapshot['scope'],i,row['payment_operation_id'],row['receipt_relation_id'],row['amount'])
                   for i,row in enumerate(rows,1)]
    # Projection-only ID; the real immutable operation ID is assigned by PostgreSQL.
    provisional_id = max([row.id for row in snapshot['payments'] + snapshot['refunds']] + [0]) + 1
    try:
        plan = plan_refund(**snapshot, allocations=allocations,
            refund=Refund(snapshot['scope'],provisional_id,command['paymentId'],command['amount']),
            releases=[Release(row['receiptId'],row['amount']) for row in command['releases']],
            unallocated_amount=command['unallocatedAmount'])
    except ValueError:
        raise HTTPException(409, 'Сумма возврата или распределения требует сверки') from None
    revision = replace_allocations_in_transaction(cur, authorize_allocations, actor_id, company_id,
        dict(requestId=str(uuid5(_REVISION_NAMESPACE, str(company_id)+':'+command['requestId'])),
             groupId=command['groupId'],expectedVersion=version,reason=command['reason'],rows=plan['rows']))

    def link(cursor, operation):
        cursor.execute('''INSERT INTO supplier_payment_refund_links
            (refund_operation_id,payment_operation_id,company_id,group_id,revision_id,fingerprint)
            VALUES(%s,%s,%s,%s,%s,%s)''',
            (operation['id'],command['paymentId'],company_id,command['groupId'],revision['revisionId'],fingerprint))

    operation = execute_in_transaction(cur, authorize_payment, actor_id, company_id,
        dict(requestId=command['requestId'],kind='refund',documentKind='invoice',
             documentId=snapshot['scope'].invoice_id,amount=command['amount'],
             paidAt=command['paidAt'],reason=command['reason']),validate_new=validate_new,before_impacts=link)
    return dict(operation, revisionId=revision['revisionId'],version=revision['version'],groupId=command['groupId'])


def refund(get_db, authorize_allocations, authorize_payment, actor_id, company_id, body, *, validate_new):
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            result = refund_in_transaction(cur, authorize_allocations, authorize_payment,
                actor_id,company_id,body,validate_new=validate_new)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
