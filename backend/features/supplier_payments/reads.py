"""Bounded payment reads. Locks only; never creates baselines or financial rows.

READ COMMITTED + the same company advisory lock as the engine prevent a UUID
lookup racing an in-flight commit. Financial read callbacks retain live authority
locks. A read transaction always rolls back, including successful projections.
"""
from contextlib import contextmanager

from fastapi import HTTPException
from psycopg2 import DatabaseError
from psycopg2.extras import RealDictCursor

from .documents import build_document_resolver, warehouse_payment_package, TABLES
from .attachment_projection import balance_source
from .engine import _require_same_document_group


def require_schema(cur, deps, *, require_cancellations=False):
    cur.execute('''SELECT to_regclass('public.supplier_payment_documents') IS NOT NULL
        AND to_regclass('public.supplier_payment_operations') IS NOT NULL
        AND to_regclass('public.supplier_payment_impacts') IS NOT NULL
        AND to_regclass('public.supplier_payment_attachments') IS NOT NULL
        AND to_regprocedure('public.supplier_payment_warehouse_package(text)') IS NOT NULL
        AND position('supplier_payment_warehouse_package' IN
            pg_get_functiondef(to_regprocedure('public.supplier_payment_document_guard()'))) > 0
        AND position('supplier_payment_warehouse_package' IN
            pg_get_functiondef(to_regprocedure('public.supplier_payment_attachment_guard()'))) > 0
        AND NOT EXISTS (
            SELECT 1 FROM (VALUES
              ('supplier_payment_documents','supplier_payment_document_insert'),
              ('supplier_payment_operations','supplier_payment_operation_insert'),
              ('supplier_payment_impacts','supplier_payment_impact_insert'),
              ('supplier_payment_operations','supplier_payment_complete'),
              ('supplier_payment_impacts','supplier_payment_complete'),
              ('supplier_payment_documents','supplier_payment_immutable'),
              ('supplier_payment_operations','supplier_payment_immutable'),
              ('supplier_payment_impacts','supplier_payment_immutable'),
              ('supplier_payment_attachments','supplier_payment_attachment_immutable'),
              ('supplier_payment_impacts','supplier_payment_attachment_impact_insert'),
              ('supplier_payment_attachments','supplier_payment_attachment_insert'),
              ('supplier_payment_attachments','supplier_payment_attachment_complete')
            ) required(table_name,trigger_name)
            WHERE NOT EXISTS(SELECT 1 FROM pg_trigger t
              WHERE t.tgrelid=to_regclass('public.' || required.table_name)
                AND t.tgname=required.trigger_name AND t.tgenabled IN ('O','A'))
        ) AS ready''')
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Схема журнала оплат не подготовлена')
    if require_cancellations:
        cur.execute('''SELECT to_regclass('public.supplier_payment_request_cancellations') IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM (VALUES ('supplier_payment_cancellation_immutable'),
                                      ('supplier_payment_cancellation_no_truncate')) required(trigger_name)
                WHERE NOT EXISTS(SELECT 1 FROM pg_trigger t
                    WHERE t.tgrelid=to_regclass('public.supplier_payment_request_cancellations')
                      AND t.tgname=required.trigger_name AND t.tgenabled IN ('O','A'))
            ) AS ready''')
        if not cur.fetchone()['ready']:
            raise HTTPException(503, dict(code='cancellation_schema_unavailable',
                                         message='Схема отмены попыток не подготовлена'))


@contextmanager
def transaction(deps, company_id):
    if not callable(deps.get('authorize_read')):
        raise HTTPException(503, 'Чтение журнала оплат не подготовлено')
    try:
        conn = deps['get_db']()
    except DatabaseError:
        raise HTTPException(503, 'Журнал оплат временно недоступен') from None
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SHOW transaction_isolation')
            if cur.fetchone()['transaction_isolation'] != 'read committed':
                raise HTTPException(503, 'Чтение журнала оплат требует новой транзакции')
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company_id))
            require_schema(cur, deps)
            yield cur
    except DatabaseError:
        raise HTTPException(503, 'Журнал оплат временно недоступен') from None
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Баланс или связи журнала оплат требуют сверки')


def document(cur, deps, actor_id, company_id, kind, document_id):
    """Return one debt, not a sum of the invoice and its physical mirror."""
    context = build_document_resolver(deps['authorize_read'])(cur, actor_id, company_id,
        dict(documentKind=kind, documentId=document_id))
    documents = context['documents']
    by_key = {(d['kind'], d['id']): d for d in documents}
    predicates = ' OR '.join('(document_kind=%s AND document_id=%s)' for _ in documents)
    cur.execute('SELECT * FROM supplier_payment_documents WHERE ' + predicates,
                tuple(value for doc in documents for value in (doc['kind'], doc['id'])))
    records = cur.fetchall()
    _require(not records or len(records) == len(documents))
    by_record = {}
    sources = {}
    for record in records:
        _require(record['company_id'] == company_id)
        doc = by_key.get((record['document_kind'], record['document_id']))
        _require(doc is not None and all(record[stored] == doc[live] for stored, live in (
            ('payer_company_id', 'payerCompanyId'), ('supplier_id', 'supplierId'),
            ('project_name', 'projectName'), ('work_package', 'workPackage'), ('amount', 'amount'))))
        by_record[(doc['kind'], doc['id'])] = record
        source = balance_source(cur, record, company_id)
        _require((source['document_kind'], source['document_id']) in by_key)
        sources[record['id']] = source
        cur.execute('''SELECT COALESCE(SUM(delta),0) AS total FROM supplier_payment_impacts
                       WHERE document_record_id=%s AND company_id=%s''', (source['id'], company_id))
        _require(source['opening_paid'] + cur.fetchone()['total'] == doc['paidAmount'])
    if records:
        unique_sources = {source['id']: source for source in sources.values()}
        _require_same_document_group(cur, list(unique_sources.values()), company_id)
    doc = by_key[(kind, document_id)]
    record = by_record.get((kind, document_id))
    source = sources[record['id']] if record else None
    canonical = next((d for d in documents if d['kind'] == 'invoice'), doc)
    table = TABLES[kind][0]
    status_column = 'accounting_status' if kind == 'warehouse' else 'NULL::text AS accounting_status'
    cur.execute(f'SELECT status,{status_column} FROM {table} WHERE id=%s AND company_id=%s',
                (document_id, company_id))
    status = cur.fetchone()
    _require(status is not None)
    return dict(schemaVersion=1, companyId=company_id, documentKind=kind, documentId=document_id,
        canonicalTarget=dict(documentKind=canonical['kind'], documentId=canonical['id']),
        scope={key: doc[key] for key in ('payerCompanyId', 'supplierId', 'projectName', 'workPackage')},
        amount=format(doc['amount'], '.2f'), paidAmount=format(doc['paidAmount'], '.2f'),
        remainingAmount=format(doc['amount'] - doc['paidAmount'], '.2f'),
        openingPaidAmount=format(source['opening_paid'], '.2f') if source else None,
        registered=record is not None, isMirror=bool(record and source['id'] != record['id']),
        status=status['status'], accountingStatus=status['accounting_status'])


def _authorize_operations(cur, deps, actor_id, company_id, rows):
    # Authorize the entire bounded set, including lookahead/UUID evidence, before
    # any physical conflict can disclose state to a denied recorded payer/scope.
    authorize = deps['authorize_read']
    for row in rows:
        authorize(cur, actor_id, company_id, row['project_name'] or '', row['work_package'] or '',
                  payer_company_id=row['payer_company_id'])
    physical_rows = []
    for row in rows:
        kind = row['document_kind']
        table = TABLES[kind][0]
        columns = ("project_name AS project,COALESCE(work_package,'') AS package" if kind == 'invoice'
                   else "COALESCE(NULLIF(project,''),location,'') AS project,items")
        cur.execute(f'SELECT company_id,{columns} FROM {table} WHERE id=%s FOR SHARE', (row['document_id'],))
        physical = cur.fetchone()
        physical_rows.append(physical)
        if physical and physical['company_id'] == company_id:
            # Warehouse JSON is not authority. Check raw current project access
            # first; check its exact package only after validated SQL extraction.
            authorize(cur, actor_id, company_id, physical['project'],
                      physical['package'] if kind == 'invoice' else '',
                      payer_company_id=row['payer_company_id'])
    for row, physical in zip(rows, physical_rows):
        _require(row['project_name'] is not None and row['work_package'] is not None)
        _require(physical and physical['company_id'] == company_id)
        if row['document_kind'] == 'warehouse':
            # Shared helper uses a savepoint and maps SQLSTATE 23514 to domain
            # 409 without poisoning the caller's transaction.
            package = warehouse_payment_package(cur, physical['items'])
            authorize(cur, actor_id, company_id, physical['project'], package,
                      payer_company_id=row['payer_company_id'])


def history(cur, deps, actor_id, company_id, *, limit, before_id=None, request_id=None,
            documentKind=None, documentId=None, payerCompanyId=None, supplierId=None, projectName=None):
    authorize = deps['authorize_read']
    authorize(cur, actor_id, company_id, '', '', payer_company_id=company_id)
    if payerCompanyId is not None:
        authorize(cur, actor_id, company_id, '', '', payer_company_id=payerCompanyId)
    where, params = ['o.company_id=%s'], [company_id]
    for expression, value in [('o.id<%s', before_id), ('o.request_id=%s', request_id),
                              ('o.payer_company_id=%s', payerCompanyId), ('o.supplier_id=%s', supplierId),
                              ('d.project_name=%s', projectName)]:
        if value is not None:
            where.append(expression)
            params.append(value)
    if documentKind is not None:
        # Both 0017 paired impacts and 0018 invoice-only mirrored impacts.
        where.append('''EXISTS(SELECT 1 FROM supplier_payment_impacts i
            JOIN supplier_payment_documents target ON target.id=i.document_record_id AND target.company_id=i.company_id
            LEFT JOIN supplier_payment_attachments a ON a.invoice_record_id=target.id AND a.company_id=target.company_id
            LEFT JOIN supplier_payment_documents mirror ON mirror.id=a.warehouse_record_id AND mirror.company_id=a.company_id
            WHERE i.operation_id=o.id AND i.company_id=o.company_id AND
              ((target.document_kind=%s AND target.document_id=%s) OR
               (mirror.document_kind=%s AND mirror.document_id=%s)))''')
        params.extend([documentKind, documentId, documentKind, documentId])
    cur.execute('''SELECT o.*,d.project_name,d.work_package,
        (SELECT r.id FROM supplier_payment_operations r WHERE r.reverses_id=o.id AND r.company_id=o.company_id) AS reversed_by_id
        FROM supplier_payment_operations o LEFT JOIN supplier_payment_documents d
          ON d.company_id=o.company_id AND d.document_kind=o.document_kind AND d.document_id=o.document_id
        WHERE ''' + ' AND '.join(where) + ' ORDER BY o.id DESC LIMIT %s', (*params, limit + 1))
    rows = cur.fetchall()
    attachment = None
    if request_id is not None:
        cur.execute('''SELECT a.*,d.document_kind,d.document_id,d.project_name,d.work_package,d.payer_company_id
            FROM supplier_payment_attachments a JOIN supplier_payment_documents d
              ON d.id=a.invoice_record_id AND d.company_id=a.company_id
            WHERE a.company_id=%s AND a.request_id=%s''', (company_id, request_id))
        attachment = cur.fetchone()
    # Authorize the lookahead too: pagination must not reveal a foreign payer's
    # operation. Conservative whole-page denial rather than silent truncation.
    _authorize_operations(cur, deps, actor_id, company_id, rows + ([attachment] if attachment else []))
    if attachment:
        _require(not rows)
    items = [dict(operationId=r['id'], projectPaymentId=r['project_payment_id'], companyId=company_id,
        requestId=str(r['request_id']), documentKind=r['document_kind'], documentId=r['document_id'],
        kind=r['kind'], amount=format(r['amount'], '.2f'),
        signedAmount=format(-r['amount'] if r['kind'] == 'reversal' else r['amount'], '.2f'),
        payerCompanyId=r['payer_company_id'], supplierId=r['supplier_id'], projectName=r['project_name'],
        workPackage=r['work_package'], paidAt=r['payment_date'].isoformat(), createdAt=r['created_at'].isoformat(),
        actorId=r['actor_id'], actorName=r['actor_name'], reason=r['reason'],
        reversesId=r['reverses_id'], reversedById=r['reversed_by_id']) for r in rows[:limit]]
    result = dict(schemaVersion=1, companyId=company_id, items=items, hasMore=len(rows) > limit,
                  nextCursor=items[-1]['operationId'] if len(rows) > limit else None)
    if request_id is not None:
        result['lookup'] = dict(requestId=request_id,
            status='found' if rows else 'used_for_attachment' if attachment else 'not_found')
    return result
