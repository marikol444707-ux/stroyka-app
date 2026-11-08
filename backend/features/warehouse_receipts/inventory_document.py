"""Reviewed originals for the existing director-only stock-without-supplier path."""
from fastapi import HTTPException

from .duplicate_guard import normalize_invoice_number
from .matching import _date, _lines
from .policy import resolve_warehouse_receipt_policy, WarehouseReceiptPolicyError


def resolve_inventory_act(cur, data, document, actor, company_id, project):
    try:
        policy = resolve_warehouse_receipt_policy(data, target_project=project, role=actor.get('role'))
    except WarehouseReceiptPolicyError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    if not policy['inventoryOnly']:
        raise HTTPException(400, 'Для акта выберите приход без поставщика и оплаты')
    references = ('supplierInn', 'buyerInn', 'sourceSupplierInvoiceId', 'supplyRequestId',
                  'supplyDeliveryId', 'offerId', 'selectedBatchId', 'contractVersionId',
                  'source_supplier_invoice_id', 'supply_request_id', 'supply_delivery_id',
                  'offer_id', 'contract_version_id')
    if any(data.get(key) or document.get(key) for key in references):
        raise HTTPException(400, 'Акт прихода без поставщика нельзя связывать с закупкой или поставщиком')
    number = document.get('waybillNumber')
    day = _date(document.get('waybillDate'))
    if not isinstance(number, str) or not normalize_invoice_number(number) or not day:
        raise HTTPException(400, 'Укажите номер и действительную дату оригинала акта')
    _, error = _lines(document.get('lines'), 'quantity')
    if error:
        raise HTTPException(400, 'Проверьте наименования, единицы и положительное количество строк акта')
    # No supplier identity is guessed. This is the main warehouse's own act.
    # Include historical stock-only documents in the duplicate guard.
    cur.execute('''SELECT id,number,date FROM warehouse_invoices
        WHERE company_id=%s AND supplier_id IS NULL AND supplier_invoice_id IS NULL
          AND COALESCE(project,'')='' AND location='Основной склад' ''', (company_id,))
    if any(normalize_invoice_number(row['number']) == normalize_invoice_number(number)
           and _date(row['date']) == day for row in cur.fetchall()):
        return {'status': 'review', 'postingAllowed': False,
                'reason': 'Акт уже зарегистрирован. Проверьте существующий приход без повторного оприходования'}
    return {'status': 'no_match', 'postingAllowed': False, 'reasons': ['reviewed_inventory_act']}
