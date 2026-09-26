"""Internal append-only allocation revisions; no routes or financial writes.

Registration of proven receipt relations and runtime authorization wiring remain
separate release gates. Authorization callbacks are trusted server dependencies,
never input supplied by a client. A worker cannot commit the caller's transaction.
"""
from decimal import Decimal

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .allocation_commands import normalize_allocation_command
from .allocation_projection import Scope, Payment, Receipt, Allocation, allocation_projection
from .commands import positive_id, command_fingerprint


def _conflict(message):
    raise HTTPException(409, message)


def _enter(cur, authorize_and_lock, actor_id, company_id, command):
    positive_id(actor_id)
    positive_id(company_id)
    if not callable(authorize_and_lock):
        raise TypeError('Current allocation scope authorization is required')
    if cur.connection.autocommit:
        raise RuntimeError('Allocation worker requires a caller-owned transaction')
    cur.execute('SHOW transaction_isolation')
    if cur.fetchone()['transaction_isolation'] != 'read committed':
        _conflict('Распределение требует READ COMMITTED')
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company_id))
    # The resolver must retain current owner/payer and all receipt scope authority
    # through commit. Read calls explicitly inject a current READ resolver.
    authorize_and_lock(cur, actor_id, company_id, command)


def _latest(cur, company_id, group_id):
    cur.execute('''SELECT * FROM supplier_payment_allocation_revisions
        WHERE company_id=%s AND group_id=%s ORDER BY version DESC LIMIT 1''', (company_id, group_id))
    return cur.fetchone()


def _result(row):
    return dict(revisionId=row['id'], groupId=row['group_id'], version=row['version'],
                requestId=str(row['request_id']))


def _snapshot(cur, company_id, group_id, *, new_revision=False):
    cur.execute('''SELECT d.* FROM supplier_payment_allocation_groups g
        JOIN supplier_payment_documents d ON d.id=g.invoice_record_id AND d.company_id=g.company_id
        WHERE g.id=%s AND g.company_id=%s''', (group_id, company_id))
    root = cur.fetchone()
    if not root or root['document_kind'] != 'invoice':
        _conflict('Группа распределения недоступна')
    cur.execute('''SELECT company_id,supplier_id,status,amount,COALESCE(paid_amount,0) AS paid_amount,
        COALESCE(project_name,'') AS project_name,COALESCE(work_package,'') AS work_package
        FROM supplier_invoices WHERE id=%s FOR UPDATE''', (root['document_id'],))
    live = cur.fetchone()
    if not live or any(live[key] != root[key] for key in
                       ('company_id', 'supplier_id', 'amount', 'project_name', 'work_package')):
        _conflict('Реквизиты счёта требуют сверки')
    # Match existing 0021 admission without blocking history or saved-UUID replay.
    if new_revision and live['status'] == 'Аннулирован':
        _conflict('Счёт аннулирован; новое распределение недоступно')
    cur.execute('''SELECT COALESCE(SUM(delta),0) AS delta FROM supplier_payment_impacts
        WHERE document_record_id=%s AND company_id=%s''', (root['id'], company_id))
    if root['opening_paid'] + cur.fetchone()['delta'] != live['paid_amount']:
        _conflict('Сумма счёта не совпадает с журналом оплат')
    scope = Scope(company_id, root['payer_company_id'], root['supplier_id'], root['document_id'])
    cur.execute('''SELECT p.id,p.amount,EXISTS(SELECT 1 FROM supplier_payment_operations r
            WHERE r.reverses_id=p.id AND r.company_id=p.company_id) AS reversed
        FROM supplier_payment_operations p JOIN supplier_payment_impacts i ON i.operation_id=p.id
            AND i.company_id=p.company_id
        WHERE i.document_record_id=%s AND p.company_id=%s AND p.kind='payment'
        ORDER BY p.id LIMIT 10001''', (root['id'], company_id))
    payment_rows = cur.fetchall()
    cur.execute('''SELECT id,warehouse_invoice_id,amount FROM supplier_payment_receipt_relations
        WHERE group_id=%s AND company_id=%s ORDER BY id LIMIT 10001''', (group_id, company_id))
    receipt_rows = cur.fetchall()
    if len(payment_rows) > 10000 or len(receipt_rows) > 10000:
        _conflict('Объём истории счёта требует отдельной обработки')
    payments = [Payment(scope, row['id'], row['amount'], row['reversed']) for row in payment_rows]
    # No invented due date: the deadline adapter is a separate integration gate.
    receipts = [Receipt(scope, row['id'], row['amount']) for row in receipt_rows]
    return dict(scope=scope, invoice_amount=root['amount'], opening_paid=root['opening_paid'],
                payments=payments, receipts=receipts)


def _project(snapshot, rows, *, new_revision):
    reversed_ids = {row.id for row in snapshot['payments'] if row.reversed}
    if new_revision and any(row['paymentId'] in reversed_ids for row in rows):
        _conflict('Платёж сторнирован; обновите карту распределения')
    allocations = [Allocation(snapshot['scope'], index, row['paymentId'], row['receiptId'], row['amount'])
                   for index, row in enumerate(rows, 1)]
    try:
        return allocation_projection(**snapshot, allocations=allocations)
    except ValueError:
        _conflict('Суммы или принадлежность распределения требуют сверки')


def replace_allocations_in_transaction(cur, authorize_and_lock, actor_id, company_id, body):
    """Save the entire confirmed map, or replay its stable receipt, after auth.

An empty rows list explicitly releases all designations. It never reverses money.
expectedVersion protects another accountant's map; live payments are validated
again because their reversals do not increment allocation version.
"""
    command = normalize_allocation_command(body)
    _enter(cur, authorize_and_lock, actor_id, company_id, command)
    fingerprint = command_fingerprint(company_id, actor_id, command)
    cur.execute('''SELECT * FROM supplier_payment_allocation_revisions
        WHERE company_id=%s AND request_id=%s''', (company_id, command['requestId']))
    replay = cur.fetchone()
    if replay:
        if replay['fingerprint'] != fingerprint:
            _conflict('UUID распределения уже использован с другими данными')
        return _result(replay)
    latest = _latest(cur, company_id, command['groupId'])
    version = latest['version'] if latest else 0
    if command['expectedVersion'] != version:
        _conflict('Распределение уже изменено; обновите данные перед сохранением')
    snapshot = _snapshot(cur, company_id, command['groupId'], new_revision=True)
    _project(snapshot, command['rows'], new_revision=True)
    cur.execute('''INSERT INTO supplier_payment_allocation_revisions
        (company_id,group_id,version,previous_revision_id,request_id,fingerprint,actor_id,reason,row_count)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (company_id, command['groupId'], version + 1, latest['id'] if latest else None,
         command['requestId'], fingerprint, actor_id, command['reason'], len(command['rows'])))
    revision = cur.fetchone()
    for row in command['rows']:
        cur.execute('''INSERT INTO supplier_payment_allocation_rows
            (revision_id,group_id,company_id,payment_operation_id,receipt_relation_id,amount)
            VALUES(%s,%s,%s,%s,%s,%s)''',
            (revision['id'], command['groupId'], company_id, row['paymentId'], row['receiptId'], row['amount']))
    return _result(revision)


def replace_allocations(get_db, authorize_and_lock, actor_id, company_id, body):
    """Transaction-owning wrapper; success is returned only after commit."""
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            result = replace_allocations_in_transaction(cur, authorize_and_lock, actor_id, company_id, body)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def read_allocations_in_transaction(cur, authorize_and_lock, actor_id, company_id, group_id):
    """Current projection, not a replay receipt; caller retains/ends transaction."""
    positive_id(group_id, 9223372036854775807)
    _enter(cur, authorize_and_lock, actor_id, company_id, dict(groupId=group_id))
    snapshot = _snapshot(cur, company_id, group_id)
    latest = _latest(cur, company_id, group_id)
    rows = []
    if latest:
        cur.execute('''SELECT payment_operation_id AS "paymentId",receipt_relation_id AS "receiptId",amount
            FROM supplier_payment_allocation_rows WHERE revision_id=%s AND company_id=%s
            ORDER BY payment_operation_id,receipt_relation_id''', (latest['id'], company_id))
        rows = cur.fetchall()
        if len(rows) != latest['row_count']:
            _conflict('История распределения неполна')
    projection = _project(snapshot, rows, new_revision=False)
    reversed_ids = {payment.id for payment in snapshot['payments'] if payment.reversed}
    active, reversed_rows = [], []
    for row in rows:
        target = reversed_rows if row['paymentId'] in reversed_ids else active
        target.append(dict(paymentId=row['paymentId'], receiptId=row['receiptId'],
                           amount=format(Decimal(row['amount']), '.2f')))
    return dict(projection, groupId=group_id, version=latest['version'] if latest else 0,
                allocations=active, reversedAllocations=reversed_rows)
