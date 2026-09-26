"""INTERNAL ONLY: one full single-line delivery -> one full warehouse mirror.

NOT a receipt endpoint or a completed managed-delivery workflow. No stock,
delivery or warehouse creation here; caller must prepare BEFORE those writes,
then attach in the SAME transaction. No commits, connections or runtime DDL.
Multiline, partial/multiple deliveries/invoices, VAT and inferred prices are
unsupported. Coverage is against locked persisted request/KP/delivery lines,
not an immutable invoice-line specification (the current schema has none).
Runtime writer-protocol review and ship/receive integration remain release gates.
"""
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

from fastapi import HTTPException

from ..material_traceability.guards import lock_distribution_compatible_stock
from .attachments import attach_receipt_in_transaction
from .commands import positive_id
from .contract_context import load_invoice_contract
from .documents import _snapshot
from .statuses import payment_status_eligible


_NAMESPACE = UUID('937b41f9-4eec-48da-9634-92aa19c98e72')
_REASON = 'Автоматическое зеркало полной однопозиционной приёмки'


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Поддерживается только точная полная однопозиционная приёмка одного счёта. '
                            'Связи, частичная/многопозиционная поставка или суммы требуют отдельной сверки.')


def _number(value, scale=2, *, zero=False):
    try:
        _require(not isinstance(value, bool) and value is not None)
        number = Decimal(str(value))
        _require(number.is_finite() and (number >= 0 if zero else number > 0)
                 and number < Decimal('1000000000000')
                 and number == number.quantize(Decimal(10) ** -scale))
        return number
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(409, 'Количество или цена требуют сверки') from None


def _single(raw):
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise HTTPException(409, 'Спецификация требует сверки') from None
    _require(isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict))
    return items[0]


def _text(item, *keys):
    values = [item[key] for key in keys if key in item]
    _require(values and all(isinstance(value, str) and value.strip() for value in values))
    values = [value.strip() for value in values]
    _require(len(set(values)) == 1)
    return values[0]


class ManagedDeliveryReceipt:
    """Trusted server dependencies only; warehouse authority, never finance grants.

    prepare/attach acquire stock -> company -> live authority/source locks.
    Call before any conflicting locks; retain the caller transaction through
    warehouse/stock writes and attach. Results contain IDs, never paid balances.
    Receipt metadata/photo correction and public request parsing are NOT supplied.
    """
    def __init__(self, deps):
        self.deps = deps

    def _authorize(self, cur, actor_id, company_id, delivery):
        deps = self.deps
        cur.execute('''SELECT id,name,email,role,company_id,platform_account_id,
            project_name,assigned_projects,assigned_packages,active
            FROM users WHERE id=%s AND active=TRUE FOR SHARE''', (actor_id,))
        user = cur.fetchone()
        if not user or user['role'] == 'поставщик' or user['role'] in deps['platform_staff_roles']:
            raise HTTPException(403, 'Нет полномочий приёмки')
        cur.execute('SELECT id FROM companies WHERE id=%s FOR SHARE', (company_id,))
        if not cur.fetchone():
            raise HTTPException(403, 'Компания недоступна')
        cur.execute('''SELECT id FROM user_company_roles WHERE user_id=%s AND company_id=%s
            ORDER BY id FOR SHARE''', (actor_id,company_id))
        membership_ids = {row['id'] for row in cur.fetchall()}
        context, actor = deps['resolve_resource_company_actor'](
            cur, dict(user), company_id, 'update', allowed_roles=deps['warehouse_roles'],
            platform_staff_roles=deps['platform_staff_roles'], client_account_roles=deps['client_account_roles'])
        if (context.get('mode') != 'company' or context.get('companyId') != company_id
                or context.get('source') != 'membership' or context.get('membershipId') not in membership_ids
                or not context.get('active') or not context.get('companyActive') or context.get('readOnly')
                or context.get('role') not in deps['warehouse_roles']):
            raise HTTPException(403, 'Требуется действующее складское членство компании')
        deps['require_project_or_warehouse_access'](actor, delivery['project'])
        if not deps['has_package_access'](actor, delivery['work_package'] or 'Основная'):
            raise HTTPException(403, 'Нет доступа к пакету поставки')
        return actor

    def _load(self, cur, actor_id, company_id, *, delivery_id, invoice_id, contract_version_id,
              received_quantity, quality_status='Принято'):
        for value in (actor_id, company_id, delivery_id, invoice_id, contract_version_id):
            positive_id(value)
        if cur.connection.autocommit:
            raise RuntimeError('Managed receipt requires a caller-owned transaction')
        cur.execute('SHOW transaction_isolation')
        _require(cur.fetchone()['transaction_isolation'] == 'read committed')
        lock_distribution_compatible_stock(cur)
        cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201,company_id))
        cur.execute('SELECT * FROM supply_deliveries WHERE id=%s AND company_id=%s', (delivery_id,company_id))
        discovery = cur.fetchone()
        if not discovery:
            raise HTTPException(404, 'Поставка выбранной компании не найдена')
        actor = self._authorize(cur, actor_id, company_id, discovery)
        _require(discovery['source_supplier_invoice_id'] == invoice_id
                 and discovery['contract_version_id'] == contract_version_id)
        contract = load_invoice_contract(cur, invoice_id, company_id)
        invoice = contract['invoice']
        _require(contract['contractVersionId'] == contract_version_id)
        cur.execute('SELECT * FROM supply_requests WHERE id=%s FOR UPDATE', (invoice['request_id'],))
        request = cur.fetchone()
        cur.execute('SELECT * FROM supplier_offers WHERE id=%s FOR UPDATE', (invoice['offer_id'],))
        offer = cur.fetchone()
        _require(request and offer)
        cur.execute('''SELECT id FROM supplier_invoices WHERE offer_id=%s OR request_id=%s
            ORDER BY id FOR UPDATE''', (offer['id'],request['id']))
        _require([row['id'] for row in cur.fetchall()] == [invoice_id])
        cur.execute('''SELECT * FROM supply_deliveries WHERE source_supplier_invoice_id=%s
            OR offer_id=%s OR request_id=%s ORDER BY id FOR UPDATE''', (invoice_id,offer['id'],request['id']))
        deliveries = cur.fetchall()
        _require(len(deliveries) == 1 and deliveries[0]['id'] == delivery_id)
        delivery = deliveries[0]
        _require(all(delivery[key] == invoice[key] for key in
                     ('company_id','supplier_id','offer_id','request_id','contract_version_id'))
                 and delivery['source_supplier_invoice_id'] == invoice_id
                 and delivery['project'] == invoice['project_name'] == request['project']
                 and delivery['work_package'] == invoice['work_package'] == request['work_package']
                 and delivery.get('project_id') in (None,contract['projectId']))
        # Scope may have changed while the initial discovery waited for row locks.
        actor = self._authorize(cur, actor_id, company_id, delivery)
        line, kp = _single(request['items_json']), _single(offer['items_kp_json'])
        identity = (_text(line,'materialName','name'), _text(line,'unit'), _text(line,'workPackage','work_package'))
        _require(identity == (_text(kp,'materialName','name'),_text(kp,'unit'),_text(kp,'workPackage','work_package'))
                 == (delivery['material_name'],delivery['unit'],delivery['work_package']))
        quantity, price = _number(line.get('quantity'),4), _number(kp.get('pricePerUnit'))
        _require(quantity == _number(kp.get('quantity'),4) == _number(delivery['planned_quantity'],4)
                 == _number(delivery['shipped_quantity'],4) == _number(received_quantity,4)
                 and price == _number(delivery['price_per_unit']) and quality_status == 'Принято')
        amount = _number(quantity * price)
        _require(amount == _number(kp.get('totalPrice')) == _number(offer['total_price'])
                 == _number(delivery['total_price']) == _number(invoice['amount'])
                 and _number(invoice.get('vat_amount') or 0, zero=True) == 0)
        source = _snapshot('invoice', invoice, contract['payerCompanyId'], cur=cur)
        cur.execute('''SELECT d.*, (SELECT COUNT(*) FROM supplier_payment_impacts i
            WHERE i.document_record_id=d.id) AS impact_count,
            (SELECT COALESCE(SUM(delta),0) FROM supplier_payment_impacts i
            WHERE i.document_record_id=d.id) AS delta FROM supplier_payment_documents d
            WHERE document_kind='invoice' AND document_id=%s''', (invoice_id,))
        record = cur.fetchone()
        _require(record and record['impact_count'] > 0 and record['company_id'] == company_id
                 and record['payer_company_id'] == contract['payerCompanyId']
                 and record['supplier_id'] == invoice['supplier_id']
                 and record['project_name'] == invoice['project_name']
                 and record['work_package'] == invoice['work_package'] and record['amount'] == amount
                 and record['opening_paid'] + record['delta'] == source['paidAmount'])
        cur.execute('SELECT * FROM supplier_payment_attachments WHERE invoice_record_id=%s', (record['id'],))
        attachment = cur.fetchone()
        if not attachment:
            _require(offer['status'] == 'Утверждено' and payment_status_eligible('invoice',invoice))
        cur.execute('''SELECT * FROM warehouse_invoices WHERE supply_delivery_id=%s OR supplier_invoice_id=%s
            OR id=%s OR (source_type='supply_delivery' AND source_id=%s) ORDER BY id FOR UPDATE''',
            (delivery_id,invoice_id,invoice['warehouse_invoice_id'],str(delivery_id)))
        warehouses = cur.fetchall()
        _require(len(warehouses) <= 1)
        warehouse = warehouses[0] if warehouses else None
        received = delivery['received_at'] is not None
        if warehouse:
            _require(received and delivery['status'] == 'Принято' and delivery['quality_status'] == 'Принято'
                     and _number(delivery['received_quantity'],4) == quantity
                     and _number(delivery.get('shortage_quantity') or 0,4,zero=True) == 0
                     and warehouse['status'] == 'Принята' and warehouse['company_id'] == company_id
                     and warehouse['supplier_id'] == invoice['supplier_id']
                     and warehouse['project'] == invoice['project_name']
                     and warehouse.get('project_id') in (None,contract['projectId'])
                     and warehouse['source_type'] == 'supply_delivery' and str(warehouse['source_id']) == str(delivery_id)
                     and warehouse['supply_delivery_id'] == delivery_id and warehouse['supply_request_id'] == request['id']
                     and warehouse['supplier_invoice_id'] == invoice_id and invoice['warehouse_invoice_id'] == warehouse['id'])
            cur.execute('SELECT id FROM supplier_invoices WHERE warehouse_invoice_id=%s ORDER BY id', (warehouse['id'],))
            _require([row['id'] for row in cur.fetchall()] == [invoice_id])
            item = _single(warehouse['items'])
            _require((_text(item,'name','materialName'),_text(item,'unit'),_text(item,'workPackage','work_package')) == identity
                     and _number(item.get('quantity'),4) == quantity and _number(item.get('price')) == price
                     and _number(item.get('total')) == amount and item.get('source') == 'supply_delivery'
                     and item.get('deliveryId') == delivery_id and item.get('requestId') == request['id']
                     and _number(warehouse['total_base']) == _number(warehouse['total_with_vat']) == amount
                     and _number(warehouse.get('total_vat') or 0,zero=True) == 0)
        else:
            _require(not received and delivery['status'] == 'В пути' and not attachment
                     and invoice['warehouse_invoice_id'] is None)
        request_uuid = str(uuid5(_NAMESPACE, f'full-receipt:v1:{company_id}:{delivery_id}:{invoice_id}:{contract_version_id}'))
        if attachment:
            _require(warehouse and attachment['company_id'] == company_id and str(attachment['request_id']) == request_uuid)
            cur.execute('SELECT * FROM supplier_payment_documents WHERE id=%s', (attachment['warehouse_record_id'],))
            target = cur.fetchone()
            _require(target and target['document_kind'] == 'warehouse' and target['document_id'] == warehouse['id']
                     and all(target[key] == record[key] for key in
                             ('company_id','payer_company_id','supplier_id','project_name','work_package','amount'))
                     and _number(warehouse['paid_amount'],zero=True) == source['paidAmount'])
        return dict(actor=actor,delivery=delivery,invoice=invoice,warehouse=warehouse,attachment=attachment,
                    source=source,request_uuid=request_uuid,contract=contract)

    @staticmethod
    def _result(context):
        return dict(deliveryId=context['delivery']['id'],
                    invoiceId=context['warehouse']['id'] if context['warehouse'] else None,
                    requestId=context['request_uuid'], alreadyReceived=bool(context['attachment']))

    def prepare(self, cur, actor_id, company_id, **source):
        """Read/lock only. Call BEFORE receipt writes; replay never repairs."""
        context = self._load(cur, actor_id, company_id, **source)
        _require(not context['warehouse'] or context['attachment'])
        return self._result(context)

    def attach(self, cur, actor_id, company_id, *, warehouse_id, **source):
        """Validate caller-created full receipt, attach atomically; return IDs only."""
        positive_id(warehouse_id)
        context = self._load(cur, actor_id, company_id, **source)
        _require(context['warehouse'] and context['warehouse']['id'] == warehouse_id)
        if context['attachment']:
            return self._result(context)  # Current warehouse authority, not original actor fingerprint.
        _require(_number(context['warehouse']['paid_amount'],zero=True) == 0)
        target = _snapshot('warehouse',context['warehouse'],context['contract']['payerCompanyId'],cur=cur)
        def authorize(cursor, current_actor, current_company, command):
            actor = self._authorize(cursor,current_actor,current_company,context['delivery'])
            _require(command['documentId'] == context['invoice']['id'] and command['warehouseId'] == warehouse_id)
            return dict(actorName=actor['name'], documents=[context['source'],target])
        def validate(cursor, checked, command):
            # Exact rows/coverage were read and locked above on this same cursor;
            # no external mutable context or caller-supplied policy is accepted.
            _require(cursor is cur and command['requestId'] == context['request_uuid'])
        attach_receipt_in_transaction(cur,authorize,actor_id,company_id,
            dict(requestId=context['request_uuid'],invoiceId=context['invoice']['id'],
                 warehouseId=warehouse_id,reason=_REASON),validate_new=validate)
        result = self._result(context)
        result['alreadyReceived'] = False
        return result
