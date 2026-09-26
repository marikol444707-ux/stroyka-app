"""Internal read-only resolver; deliberately not registered with any route.

Caller owns an explicit READ COMMITTED transaction and already holds the engine
company advisory lock (1735289201, company_id). All physical link writers must
share that protocol before runtime activation: row locks cannot prevent phantom
reverse links. No DDL, baselines, payments, commits, or eligibility decisions.
"""
import json

from fastapi import HTTPException
from psycopg2.errors import CheckViolation

from .commands import positive_id
from .contract_context import load_invoice_contract
from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


TABLES = {'invoice': ('supplier_invoices', 'warehouse_invoice_id'),
          'warehouse': ('warehouse_invoices', 'supplier_invoice_id')}


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Принадлежность, связи или реквизиты документов требуют сверки')


def _warehouse_package(raw):
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise HTTPException(409, 'Пакет накладной требует сверки')
    _require(isinstance(items, list) and bool(items))
    packages = set()
    for item in items:
        _require(isinstance(item, dict))
        values = [item[key] for key in ('workPackage', 'work_package') if key in item]
        _require(bool(values) and all(isinstance(value, str) for value in values))
        # Do not discard empty/malformed lines or collapse conflicting aliases.
        _require(len(set(values)) == 1)
        packages.add(values[0])
    _require(len(packages) == 1)
    package = packages.pop()
    # 0017 validates warehouse baseline against literal ''. Never erase a real
    # item/invoice package to make that schema accept a document.
    _require(package == '')
    return package


def warehouse_payment_package(cur, raw, *, legacy_literal=False):
    """Validate persisted items from an already locked row using 0019 SQL.

    No stored-baseline fallback. Before 0019, the document resolver retains its
    strict explicit-empty rule; attachment projection retains its literal ''.
    """
    if cur.connection.autocommit:
        raise RuntimeError('Package validation requires the document transaction')
    cur.execute("SELECT to_regprocedure('public.supplier_payment_warehouse_package(text)') IS NOT NULL AS available")
    if not cur.fetchone()['available']:
        return '' if legacy_literal else _warehouse_package(raw)
    # A savepoint converts the helper's 23514 into a domain conflict without
    # leaving read-only callers with an aborted transaction. Outer writes still
    # roll back on HTTPException; no prior mutation is committed here.
    cur.execute('SAVEPOINT supplier_payment_package_validation')
    try:
        cur.execute('SELECT public.supplier_payment_warehouse_package(%s::text) AS package', (raw,))
        package = cur.fetchone()['package']
    except Exception as exc:
        cur.execute('ROLLBACK TO SAVEPOINT supplier_payment_package_validation')
        cur.execute('RELEASE SAVEPOINT supplier_payment_package_validation')
        if isinstance(exc, CheckViolation):
            raise HTTPException(409, 'Пакет накладной требует сверки') from None
        raise
    cur.execute('RELEASE SAVEPOINT supplier_payment_package_validation')
    return package


def _discover(cur, kind, document_id):
    ids = {'invoice': set(), 'warehouse': set()}
    ids[kind].add(document_id)
    rows = {}
    # A valid component has at most one invoice and one warehouse. Follow both
    # persisted directions, without company filtering that could hide corruption.
    for _ in range(3):
        before = {key: set(value) for key, value in ids.items()}
        for current, (table, link) in TABLES.items():
            other = 'warehouse' if current == 'invoice' else 'invoice'
            cur.execute(f'''SELECT * FROM {table} WHERE id=ANY(%s::int[])
                            OR {link}=ANY(%s::int[]) ORDER BY id LIMIT 3''',
                        (sorted(ids[current]), sorted(ids[other])))
            rows[current] = list(cur.fetchall())
            for row in rows[current]:
                ids[current].add(row['id'])
                if row[link] is not None:
                    _require(type(row[link]) is int and row[link] > 0)
                    ids[other].add(row[link])
            _require(all(len(values) <= 1 for values in ids.values()))
        if ids == before:
            break
    _require(all({r['id'] for r in rows[key]} == ids[key] for key in ids))
    return rows


def _snapshot(kind, row, payer, *, cur=None):
    if kind == 'invoice':
        project, package = row['project_name'], row['work_package'] or ''
        amount = row['amount']
    else:
        project = row['project'] or row['location'] or ''
        package = (_warehouse_package(row['items']) if cur is None
                   else warehouse_payment_package(cur, row['items']))
        amount = row['total_with_vat'] or row['total_base']
    _require(isinstance(project, str) and bool(project.strip()) and isinstance(package, str))
    _require(type(row['supplier_id']) is int and row['supplier_id'] > 0)
    try:
        amount = schedule_paid_amount(amount)
        paid = schedule_paid_amount(row['paid_amount'] if row['paid_amount'] is not None else 0)
    except ValueError:
        raise HTTPException(409, 'Суммы документа требуют сверки')
    _require(amount > 0 and paid <= amount)
    return dict(kind=kind, id=row['id'], companyId=row['company_id'],
                payerCompanyId=payer, supplierId=row['supplier_id'], projectName=project,
                workPackage=package, amount=amount, paidAmount=paid)


def build_document_resolver(authorize):
    """Inject server-side build_payment_access(...) result, never HTTP callbacks.

    The returned engine-shaped callback authenticates live owner/payer scope on
    every call, including replay. Status/receipt/deadline policy belongs ONLY to
    validate_new after replay. Returned contract evidence stays internal.
    """
    if not callable(authorize):
        raise TypeError('Server payment authorization is required')

    def resolve(cur, actor_id, company_id, command):
        positive_id(actor_id); positive_id(company_id)
        kind, document_id = command['documentKind'], positive_id(command['documentId'])
        if kind not in TABLES:
            raise HTTPException(422, 'Недопустимый вид документа')
        if cur.connection.autocommit:
            raise RuntimeError('Document resolution requires an explicit transaction')
        cur.execute('SHOW transaction_isolation')
        _require(cur.fetchone()['transaction_isolation'] == 'read committed')
        table = TABLES[kind][0]
        scope_columns = 'project_name,work_package' if kind == 'invoice' else 'project,location'
        cur.execute(f'SELECT company_id,{scope_columns} FROM {table} WHERE id=%s', (document_id,))
        root = cur.fetchone()
        if not root or root['company_id'] != company_id:
            raise HTTPException(404, 'Документ выбранной компании не найден')
        # Authorize the current owner before detailed link/contract/amount errors
        # or document row locks, including engine replay callbacks. Only raw root
        # scope is needed here; exact warehouse package auth follows SQL validation.
        # Do not parse malformed items or infer a payer before this check.
        project = root['project_name'] if kind == 'invoice' else root['project'] or root['location'] or ''
        package = (root['work_package'] or '') if kind == 'invoice' else ''
        authorize(cur, actor_id, company_id, project, package, payer_company_id=company_id)
        discovered = _discover(cur, kind, document_id)
        locked = {}
        for current, (table, _) in TABLES.items():
            cur.execute(f'SELECT * FROM {table} WHERE id=ANY(%s::int[]) ORDER BY id FOR UPDATE',
                        ([row['id'] for row in discovered[current]],))
            locked[current] = list(cur.fetchall())
        _require(locked == _discover(cur, kind, document_id))
        _require(all(row['company_id'] == company_id for rows in locked.values() for row in rows))
        invoice = next(iter(locked['invoice']), None)
        warehouse = next(iter(locked['warehouse']), None)
        if invoice and warehouse:
            _require(invoice['warehouse_invoice_id'] == warehouse['id']
                     and warehouse['supplier_invoice_id'] == invoice['id'])
        contract = None
        payer = company_id
        if invoice:
            if invoice.get('contract_version_id') is not None:
                contract = load_invoice_contract(cur, invoice['id'], company_id)
                payer = contract['payerCompanyId']
            else:
                _require(invoice.get('offer_id') is None)
        documents = [_snapshot(current, row, payer, cur=cur)
                     for current, rows in locked.items() for row in rows]
        _require(len({tuple(d[key] for key in ('supplierId', 'projectName', 'workPackage',
                                              'amount', 'paidAmount')) for d in documents}) == 1)
        first = documents[0]
        actor = authorize(cur, actor_id, company_id, first['projectName'], first['workPackage'],
                          payer_company_id=payer)
        _require(isinstance(actor, dict) and isinstance(actor.get('name'), str) and bool(actor['name'].strip()))
        return dict(actorName=actor['name'], documents=documents, contract=contract)

    return resolve
