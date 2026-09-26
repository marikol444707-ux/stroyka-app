"""Internal bound-invoice evidence; no authorization or new-payment decision.

Caller must authorize the owning company before returning any of this context,
then authorize its canonical payer. Shared legacy-writer locking and runtime
registration remain release gates. No profile or latest-version fallback.
"""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException

from .commands import positive_id
from ..supplier_deal_parties.payment_schedule import PaymentSchedule, schedule_paid_amount


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Связи счёта и проверенной версии договора требуют сверки')


def load_invoice_contract(cur, invoice_id, company_id):
    """Lock and resolve exact persisted evidence using a RealDict cursor.

    This narrow resolver requires a bound invoice and matching request-level
    package. Item-level/mixed packages need a separate authoritative resolver.
    The saved contract is reviewed data, not proof of electronic signature.
    """
    positive_id(invoice_id)
    positive_id(company_id)
    if cur.connection.autocommit:
        raise RuntimeError('Contract context requires an explicit transaction')
    cur.execute('SELECT * FROM supplier_invoices WHERE id=%s AND company_id=%s FOR UPDATE',
                (invoice_id, company_id))
    invoice = cur.fetchone()
    if not invoice:
        raise HTTPException(404, 'Счёт выбранной компании не найден')
    _require(invoice.get('contract_version_id'))
    cur.execute('''SELECT o.id,o.company_id,o.request_id,o.supplier_id,r.project,
                          r.work_package FROM supplier_offers o JOIN supply_requests r
                          ON r.id=o.request_id AND r.company_id=o.company_id
                   WHERE o.id=%s AND o.company_id=%s FOR SHARE OF o,r''',
                (invoice['offer_id'], company_id))
    offer = cur.fetchone()
    _require(offer and offer['request_id'] == invoice['request_id']
             and offer['supplier_id'] == invoice['supplier_id']
             and offer['project'] == invoice['project_name']
             and (offer['work_package'] or '') == (invoice['work_package'] or ''))
    cur.execute('SELECT id FROM projects WHERE company_id=%s AND name=%s ORDER BY id LIMIT 2 FOR SHARE',
                (company_id, invoice['project_name']))
    projects = cur.fetchall()
    _require(len(projects) == 1)
    cur.execute('''SELECT * FROM supplier_contract_versions
                   WHERE id=%s AND company_id=%s AND offer_id=%s FOR SHARE''',
                (invoice['contract_version_id'], company_id, invoice['offer_id']))
    contract = cur.fetchone()
    _require(contract and contract['reviewed_by_id'] and contract['reviewed_at'] and contract['reviewed_by'])
    cur.execute('''SELECT * FROM supplier_deal_parties
                   WHERE offer_id=%s AND company_id=%s AND version=%s FOR SHARE''',
                (invoice['offer_id'], company_id, contract['party_version']))
    parties = cur.fetchone()
    _require(parties and parties['request_id'] == invoice['request_id']
             and parties['supplier_id'] == invoice['supplier_id'])
    snapshot = contract['snapshot_json']
    try:
        _require(isinstance(snapshot, dict))
        encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        _require(hashlib.sha256(encoded.encode()).hexdigest() == contract['snapshot_hash'])
        for side, key, expected in (
            ('buyer', 'companyId', parties['buyer_company_id']),
            ('payer', 'companyId', parties['payer_company_id']),
            ('supplier', 'supplierId', invoice['supplier_id']),
        ):
            identity = snapshot[side][key]
            _require(type(identity) is int and identity > 0 and identity == expected)
        if snapshot.get('paymentSchedule') is not None:
            PaymentSchedule.model_validate(snapshot['paymentSchedule'])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(409, 'Сохранённые стороны или график договора требуют проверки')
    return dict(invoice=dict(invoice), contractVersionId=contract['id'],
                payerCompanyId=snapshot['payer']['companyId'],
                buyerCompanyId=snapshot['buyer']['companyId'],
                projectId=projects[0]['id'], snapshot=snapshot)


def load_invoice_receipts(cur, context):
    """Exact source-invoice receipts, not every delivery of the same offer.

    Locks existing receipts; preventing new concurrent receipts requires the
    shared offer/invoice writer protocol before runtime activation.
    """
    if cur.connection.autocommit:
        raise RuntimeError('Receipt context requires an explicit transaction')
    invoice = context['invoice']
    cur.execute('''SELECT * FROM supply_deliveries WHERE source_supplier_invoice_id=%s
                   ORDER BY id LIMIT 1001 FOR SHARE''', (invoice['id'],))
    rows = cur.fetchall()
    _require(len(rows) <= 1000)
    accepted, received_count, problem = Decimal('0'), 0, False
    for row in rows:
        _require(all(row[key] == invoice[key] for key in
                     ('company_id', 'offer_id', 'request_id', 'supplier_id', 'contract_version_id'))
                 and row['project'] == invoice['project_name']
                 and (row['work_package'] or '') == (invoice['work_package'] or ''))
        if row['status'] not in ('Принято', 'Проблема'):
            _require(row['received_at'] is None)
            continue
        _require(row['received_at'] is not None)
        try:
            quantity = Decimal(str(row['received_quantity']))
            shipped = Decimal(str(row['shipped_quantity']))
            _require(quantity.is_finite() and shipped.is_finite() and 0 <= quantity <= shipped)
            price = schedule_paid_amount(row['price_per_unit'])
            value = quantity * price
            # Legacy receipt writers use float rounding. Do not silently give
            # the same receipt a new valuation at half-kopeck boundaries.
            if value != value.quantize(Decimal('.01')):
                raise HTTPException(409, 'Стоимость дробного количества требует сверки с накладной')
            accepted += value
        except (ValueError, InvalidOperation):
            raise HTTPException(409, 'Количество или стоимость приёмки требуют проверки')
        received_count += 1
        problem = problem or row['status'] == 'Проблема'
    return dict(acceptedAmount=accepted, receivedCount=received_count,
                pendingCount=len(rows)-received_count, hasProblem=problem)
