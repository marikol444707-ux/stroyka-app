"""Test-only real HTTP receipt setup with manually reviewed synthetic waybills.

The uploaded UTF-8 originals contain every asserted document field. This helper
covers upload/authorization/resolve, not OCR; it never substitutes a stock or
accounting writer. Callers explicitly invoke the public confirmation route.
"""
import json


def upload_receipt_document(test, actor, company, project, document):
    fixture = getattr(test, 'f', None) or test.fixture
    token = test.main.create_auth_token(fixture['users'][actor], two_factor_passed=True)
    data = {'context': 'warehouse-receipt'}
    if project:
        rows = test.sql('SELECT id FROM projects WHERE company_id=%s AND name=%s', (company, project))
        test.assertEqual(len(rows), 1)
        data.update(projectId=str(rows[0][0]), projectName=project)
    from contextlib import nullcontext
    from fastapi.testclient import TestClient
    client = getattr(test, 'client', None)
    with nullcontext(client) if client is not None else TestClient(test.main.app) as upload_client:
        response = upload_client.post('/upload-photo',
            files={'file': ('synthetic-waybill.txt', json.dumps(document, ensure_ascii=False).encode('utf-8'), 'text/plain')},
            data=data, headers={'Authorization': 'Bearer '+token, 'X-Company-Id': str(company)})
    test.assertEqual(response.status_code, 200, response.text)
    return response.json()['contentUrl']


def physical_receipt_payload(test, actor, delivery_id, quantity, original_url=None):
    deliveries = test.api(actor, 'GET', '/supply-deliveries')
    delivery = next(row for row in deliveries if row['id'] == delivery_id)
    parties = delivery['documentParties']
    test.assertFalse(parties['reviewRequired'])
    document = dict(documentType='waybill', waybillNumber=delivery['waybillNumber'],
        waybillDate=delivery['waybillDate'], supplierInn=parties['supplier']['inn'],
        buyerInn=parties['buyer']['inn'], lines=[dict(materialName=delivery['materialName'],
            unit=delivery['unit'], quantity=delivery['shippedQuantity'])])
    url = original_url or upload_receipt_document(test, actor, delivery['companyId'], delivery['project'], document)
    payload = dict(companyId=delivery['companyId'], project=delivery['project'], document=document,
        originalUrls=[url], physicalReceiptConfirmed=True,
        actualLines=[dict(deliveryId=delivery_id, receivedQuantity=quantity, qualityStatus='Принято')])
    preview = test.api(actor, 'POST', '/warehouse-receipts/resolve', payload)
    test.assertEqual(preview['status'], 'match', preview)
    test.assertEqual([line['id'] for line in preview['matchedBatch']['lines']], [delivery_id])
    return payload


def confirm_test_receipt(test, actor, delivery_id, data=None, **kwargs):
    """Explicit supported workflow, keeping accounting assertions on its result.

    Legacy URL tests must call client.put directly. This helper never intercepts
    API calls and exercises upload, resolver and atomic confirmation over HTTP.
    """
    data = data or dict(receivedQuantity=1, qualityStatus='Принято')
    cached = getattr(test, '_receipt_payloads', {})
    if delivery_id not in cached:
        cached[delivery_id] = physical_receipt_payload(test, actor, delivery_id,
                                                      data['receivedQuantity'])
        test._receipt_payloads = cached
    import copy
    payload = copy.deepcopy(cached[delivery_id])
    payload['actualLines'][0].update(data)
    result = test.api(actor, 'POST', '/warehouse-receipts/confirm', payload, **kwargs)
    if kwargs.get('expected', 200) != 200:
        return result
    if result.get('alreadyReceived'):
        line = next(row for row in result['matchedBatch']['lines'] if row['id'] == delivery_id)
        delivery = next(row for row in test.api(actor, 'GET', '/supply-deliveries') if row['id'] == delivery_id)
        return dict(result, invoiceId=line.get('warehouseInvoiceId'), claimId=delivery.get('claimId'), delivery=delivery)
    test.assertEqual(len(result['receipts']), 1, result)
    return dict(result['receipts'][0], alreadyReceived=False)


def physical_receipt_batch_payload(test, actor, actual_lines):
    """Build one real uploaded document for an explicitly selected full batch.

    actual_lines carries deliveryId/receivedQuantity/qualityStatus. Never infer
    missing batch members or accept just a subset of a supplier's document.
    """
    ids = {row['deliveryId'] for row in actual_lines}
    test.assertEqual(len(ids), len(actual_lines))
    rows = [r for r in test.api(actor, 'GET', '/supply-deliveries') if r['id'] in ids]
    test.assertEqual({r['id'] for r in rows}, ids)
    first = rows[0]
    for row in rows:
        test.assertFalse(row['documentParties']['reviewRequired'])
        for key in ('companyId', 'project', 'waybillNumber', 'waybillDate'):
            test.assertEqual(row[key], first[key])
        for party in ('supplier', 'buyer'):
            test.assertEqual(row['documentParties'][party]['inn'], first['documentParties'][party]['inn'])
    document = dict(documentType='waybill', waybillNumber=first['waybillNumber'],
        waybillDate=first['waybillDate'], supplierInn=first['documentParties']['supplier']['inn'],
        buyerInn=first['documentParties']['buyer']['inn'], lines=[dict(materialName=r['materialName'],
            unit=r['unit'], quantity=r['shippedQuantity']) for r in rows])
    original = upload_receipt_document(test, actor, first['companyId'], first['project'], document)
    payload = dict(companyId=first['companyId'], project=first['project'], document=document,
        originalUrls=[original], physicalReceiptConfirmed=True, actualLines=actual_lines)
    preview = test.api(actor, 'POST', '/warehouse-receipts/resolve', payload)
    test.assertEqual(preview['status'], 'match', preview)
    test.assertEqual({r['id'] for r in preview['matchedBatch']['lines']}, ids)
    return payload


def inventory_receipt_payload(test, actor, payload):
    """Upload and explicitly confirm a real synthetic internal act in tests."""
    document = dict(documentType='inventory_act', waybillNumber=payload['number'],
        waybillDate=payload['date'], lines=[dict(materialName=item['name'],
        unit=item['unit'],quantity=item['quantity']) for item in payload['items']])
    original = upload_receipt_document(test, actor, payload['companyId'], '', document)
    return {**payload, 'receiptDocument': document, 'originalUrls': [original],
            'physicalReceiptConfirmed': True, 'newDocumentConfirmed': True}
