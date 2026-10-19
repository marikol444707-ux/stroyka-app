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
    response = test.client.post('/upload-photo',
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
