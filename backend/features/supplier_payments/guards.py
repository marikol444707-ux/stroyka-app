"""Legacy document writers cannot bypass registered payment history.

These guards do not enable the payment engine or authorize requests. Call the
lock before document row locks, then the denial check AFTER normal route access
checks and BEFORE any writes. No flag may hide an existing baseline.
"""
from fastapi import HTTPException
from psycopg2.errors import LockNotAvailable


def _value(row, key):
    return row.get(key) if isinstance(row, dict) else row[0] if row else None


def ledger_available(cur):
    cur.execute("SELECT to_regclass('public.supplier_payment_documents') IS NOT NULL AS present")
    return bool(_value(cur.fetchone(), 'present'))


def lock_legacy_supply_writer(cur):
    """Before any legacy DDL/company/row locks; retain until business commit.

    NOWAIT is essential: unmodified legacy writers can hold these tables in a
    different order. A conflict aborts this transaction; the caller must roll
    back, not continue or commit schema preparation separately.
    """
    if cur.connection.autocommit:
        raise RuntimeError('Legacy supply writer requires an explicit transaction')
    try:
        cur.execute('''LOCK TABLE supplier_invoices, warehouse_invoices,
            supply_requests, supplier_offers IN ACCESS EXCLUSIVE MODE NOWAIT''')
    except LockNotAvailable:
        raise HTTPException(409, 'Документы снабжения заняты другой операцией. Повторите запрос.') from None


def lock_document_writer(cur, kind, document_id):
    """Caller checked schema availability and has an explicit transaction.

    Get company from the database, never HTTP input. Reject an ownership change
    across lock acquisition instead of locking a second company out of order.
    Current payment callbacks do not take stock locks; stock cancellation takes
    its existing stock locks first. Revisit that order before receipt integration.
    """
    table = {'invoice': 'supplier_invoices', 'warehouse': 'warehouse_invoices',
             'delivery': 'supply_deliveries'}[kind]
    if cur.connection.autocommit:
        raise RuntimeError('Document writer guard requires an explicit transaction')
    cur.execute('SHOW transaction_isolation')
    if _value(cur.fetchone(), 'transaction_isolation') != 'read committed':
        raise HTTPException(409, 'Изменение документа требует новой транзакции')
    cur.execute(f'SELECT company_id FROM {table} WHERE id=%s', (document_id,))
    initial = cur.fetchone()
    if not initial:
        raise HTTPException(404, {'invoice': 'Счёт не найден', 'warehouse': 'Накладная не найдена',
                                  'delivery': 'Поставка не найдена'}[kind])
    company = _value(initial, 'company_id')
    if type(company) is not int or company <= 0:
        raise HTTPException(409, 'Принадлежность документа требует сверки')
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company))
    cur.execute(f'SELECT company_id FROM {table} WHERE id=%s FOR UPDATE', (document_id,))
    current = cur.fetchone()
    if not current or _value(current, 'company_id') != company:
        raise HTTPException(409, 'Принадлежность документа изменилась. Повторите запрос')


def require_unmanaged_document(cur, kind, document_id, *, proposed_link=None):
    """Deny direct/current/proposed/reverse-linked registered documents.

    IDs are global in the physical tables. Do not filter ledger rows by current
    owner: corrupted ownership must not make historical evidence disappear.
    Query a bounded one-hop neighbourhood from root AND proposed counterpart.
    """
    table = {'invoice': 'supplier_invoices', 'warehouse': 'warehouse_invoices'}[kind]
    cur.execute(f'SELECT company_id FROM {table} WHERE id=%s', (document_id,))
    root = cur.fetchone()
    if not root:
        raise HTTPException(409, 'Документ больше не существует')
    company = _value(root, 'company_id')
    invoice_ids = [document_id] if kind == 'invoice' else []
    warehouse_ids = [document_id] if kind == 'warehouse' else []
    if proposed_link is not None:
        try:
            linked_id = int(proposed_link or 0)
        except (TypeError, ValueError, OverflowError):
            raise HTTPException(422, 'Некорректная ссылка документа')
        if isinstance(proposed_link, bool) or linked_id < 0 or linked_id > 2147483647:
            raise HTTPException(422, 'Некорректная ссылка документа')
        if linked_id:
            (warehouse_ids if kind == 'invoice' else invoice_ids).append(linked_id)
    cur.execute('''WITH invoices AS (
        SELECT id,warehouse_invoice_id FROM supplier_invoices WHERE id=ANY(%s::int[])
    ), warehouses AS (
        SELECT id,supplier_invoice_id FROM warehouse_invoices WHERE id=ANY(%s::int[])
    ), related AS (
        SELECT 'invoice'::text AS kind,id FROM invoices
        UNION SELECT 'warehouse',id FROM warehouses
        UNION SELECT 'warehouse',warehouse_invoice_id FROM invoices
        UNION SELECT 'invoice',supplier_invoice_id FROM warehouses
        UNION SELECT 'warehouse',w.id FROM warehouse_invoices w
              WHERE w.supplier_invoice_id IN (SELECT id FROM invoices)
        UNION SELECT 'invoice',i.id FROM supplier_invoices i
              WHERE i.warehouse_invoice_id IN (SELECT id FROM warehouses)
    ) SELECT EXISTS(SELECT 1 FROM supplier_payment_documents d JOIN related r
        ON d.document_kind=r.kind AND d.document_id=r.id) AS managed,
        EXISTS(SELECT 1 FROM supplier_invoices i
               WHERE i.id IN (SELECT id FROM related WHERE kind='invoice') AND i.company_id IS DISTINCT FROM %s
               UNION ALL SELECT 1 FROM warehouse_invoices w
               WHERE w.id IN (SELECT id FROM related WHERE kind='warehouse') AND w.company_id IS DISTINCT FROM %s
        ) AS foreign_owner''', (invoice_ids, warehouse_ids, company, company))
    row = cur.fetchone()
    foreign_owner = row['foreign_owner'] if isinstance(row, dict) else row[1]
    if foreign_owner:
        raise HTTPException(409, 'Связанные документы относятся к разным компаниям и требуют сверки')
    if _value(row, 'managed'):
        raise HTTPException(409, 'Документ учтён в журнале оплат. Прямое изменение или аннулирование запрещено; нужна операция по журналу.')
