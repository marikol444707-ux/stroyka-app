"""Admission for explicitly confirmed standalone documents inside their writer."""
from fastapi import HTTPException
from .resolver import resolve_receipt
from .document_lock import lock_physical_document
from .originals import retain_originals


def require_standalone_receipt(cur, data, user, headers, deps):
    if data.get('physicalReceiptConfirmed') is not True or data.get('newDocumentConfirmed') is not True:
        raise HTTPException(400, 'Подтвердите фактическую приёмку и создание отдельного документа')
    document = data.get('receiptDocument')
    if not isinstance(document, dict):
        raise HTTPException(400, 'Сначала проверьте оригинал накладной')
    if document.get('documentType') not in ('waybill', 'delivery_note', 'upd'):
        raise HTTPException(409, 'Для приёмки требуется накладная или УПД, счёт на оплату не подтверждает поставку')
    # Recheck edited header/lines rather than a stale successful OCR preview.
    document = {**document,
                'waybillNumber': data.get('number'), 'waybillDate': data.get('date'),
                'supplierInn': data.get('supplierInn') or document.get('supplierInn'),
                'lines': [{'materialName': item.get('name'), 'unit': item.get('unit'),
                           'quantity': item.get('quantity')} for item in data.get('items', [])]}
    lock_physical_document(cur, data.get('companyId'), document)
    target_project = data.get('project') or (data.get('location') if data.get('location') != 'Основной склад' else '') or ''
    retain_originals(cur, data.get('originalUrls'), data.get('companyId'), target_project=target_project)
    preview = resolve_receipt(cur, {'document': document,
        'originalUrls': data.get('originalUrls'), 'companyId': data.get('companyId'),
        'project': data.get('project') or (data.get('location') if data.get('location') != 'Основной склад' else '') or '',
        'projectId': data.get('projectId')}, user, headers, deps)
    if preview.get('status') != 'no_match' or preview.get('requiresWaybill'):
        raise HTTPException(409, 'Документ связан с поставкой или требует сверки. Вернитесь к проверке оригинала')
    return {**preview, 'originalUrls': list(dict.fromkeys(data['originalUrls']))}
