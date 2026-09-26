"""Authenticated two-customer supplier flow in an explicitly isolated database."""
import datetime as dt
import os
import unittest
from unittest.mock import patch

from . import test_postgres_chain as baseline


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class MultiCompanyChainTest(unittest.TestCase):
    api = baseline.PostgresSupplyChainTests.api
    sql = baseline.PostgresSupplyChainTests.sql

    @classmethod
    def setUpClass(cls):
        from .test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture(contract_review=True)
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def seed_second_customer(self):
        f = self.fixture
        project = f['project'] + ' B'
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(2,'CHAIN second account','pro','active')")
        self.sql('UPDATE companies SET platform_account_id=2 WHERE id=3')
        self.sql('UPDATE users SET platform_account_id=2 WHERE id=%s', (f['users']['stranger']['id'],))
        self.sql('UPDATE user_company_roles SET platform_account_id=2 WHERE company_id=3')
        f['users']['stranger']['platform_account_id'] = 2
        project_id = self.sql("INSERT INTO projects(name,company_id,status,budget,archived) VALUES(%s,3,'В работе',100000,FALSE) RETURNING id", (project,))[0][0]
        self.sql('''INSERT INTO estimates(company_id,project_id,project_name,name,version,sections_json,
                    status,is_template,smeta_type,work_package)
                    SELECT 3,%s,%s,'CHAIN second estimate',version,sections_json,status,is_template,smeta_type,work_package
                    FROM estimates WHERE id=%s''', (project_id, project, f['estimateId']))
        for company, inn in ((2, '7702222222'), (3, '7703333333')):
            self.sql('INSERT INTO company_requisites(company_id,full_name,inn) VALUES(%s,%s,%s)',
                     (company, 'CHAIN customer ' + str(company), inn))
        return project

    def create_offer(self, actor, company, project):
        f = self.fixture
        item = {key: f[key] for key in ('materialName', 'quantity', 'unit', 'workPackage')}
        request_id = self.api(actor, 'POST', '/supply-requests', {
            'project': project, 'companyId': company, 'workPackage': f['workPackage'], 'items': [item]})['id']
        path = f'/supply-requests/{request_id}'
        self.api(actor, 'PUT', path, {'action': 'confirm_prorab', 'reviewerAbsenceReason': 'Тест замещения отсутствующего прораба'})
        self.api(actor, 'PUT', path, {'action': 'approve_director'})
        self.api(actor, 'POST', path + '/request-kp', {'supplierIds': [f['supplierId']]})
        offer = next(row for row in self.api('supplier', 'GET', '/supplier-offers') if row['requestId'] == request_id)
        path = f"/supplier-offers/{offer['id']}"
        self.api('supplier', 'PUT', path, {'action': 'respond', 'pricePerUnit': 100, 'totalPrice': 200,
            'deliveryDays': 1, 'paymentTerms': 'Предоплата 100%' if company == 2 else 'Постоплата 100%', 'vatIncluded': False,
            'itemsKp': [{**item, 'pricePerUnit': 100, 'totalPrice': 200}]})
        self.api(actor, 'PUT', path, {'action': 'select'})
        return request_id, offer['id']

    def test_one_supplier_sees_both_accounts_without_customer_cross_access(self):
        f = self.fixture
        project_b = self.seed_second_customer()
        deals = [self.create_offer('director', 2, f['project']), self.create_offer('stranger', 3, project_b)]
        requests = self.api('supplier', 'GET', '/supply-requests')
        self.assertEqual({row['companyId'] for row in requests if row['id'] in [d[0] for d in deals]}, {2, 3})
        offers = self.api('supplier', 'GET', '/supplier-offers')
        self.assertEqual({row['id'] for row in offers}, {deal[1] for deal in deals})
        self.assertEqual(self.api('stranger_supplier', 'GET', '/supplier-offers'), [])
        for actor, company, other, project, deal in (
            ('director', 2, 'stranger', f['project'], deals[0]), ('stranger', 3, 'director', project_b, deals[1])):
            with self.subTest(company=company):
                request_id, offer_id = deal
                self.assertNotIn(offer_id, [row['id'] for row in self.api(other, 'GET', '/supplier-offers')])
                path = f'/supplier-offers/{offer_id}'
                self.api(other, 'GET', path + '/contracts', expected=403)
                self.api(actor, 'PUT', path + '/parties', {'buyerCompanyId': company, 'payerCompanyId': company,
                    'expectedVersion': 0, 'reason': 'Договор отдельного заказчика'})
                context = self.api(actor, 'GET', path + '/contract-review-context')
                self.assertEqual(context['companyId'], company)
                self.api('supplier', 'GET', path + '/contract-review-context', expected=403)
                with self.subTest(manual_history=company):
                    self.api(other, 'POST', '/supply-history', {
                        'companyId': company, 'supplierId': f['supplierId'], 'materialName': f['materialName'],
                        'project': project, 'quantity': 2, 'pricePerUnit': 100, 'totalPrice': 200,
                    }, expected=403)
                with self.subTest(contract=offer_id):
                    self.check_contract(actor, other, company, offer_id, context)
                self.check_invoice_and_receipt(actor, other, company, project, offer_id, request_id)

    def check_contract(self, actor, other, company, offer_id, context):
        content = '\n'.join(
            f"{label}:\nНаименование: {context[side]['fullName']}\nИНН: {context[side]['inn']}"
            for side, label in (('buyer', 'Покупатель'), ('payer', 'Плательщик'), ('supplier', 'Поставщик'))
        ).encode('utf-8')
        token = self.main.create_auth_token(self.fixture['users'][actor], two_factor_passed=True)
        upload = self.client.post('/upload-photo', files={'file': ('contract.txt', content, 'text/plain')},
            data={'context': 'supplier-contract'}, headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(upload.status_code, 200, upload.text)
        file_id = upload.json()['fileId']
        self.api('supplier', 'GET', f'/tenant-files/{file_id}/content', expected=403)
        path = f'/supplier-offers/{offer_id}'
        recognition = {'sourceFileId': file_id, 'partyVersion': 1, 'expectedVersion': 0}
        self.api(other, 'POST', path + '/contract-recognition', recognition, expected=403)
        preview = self.api(actor, 'POST', path + '/contract-recognition', recognition)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_contract_versions WHERE offer_id=%s', (offer_id,)), [(0,)])
        self.assertTrue(all(preview['parties'][side]['status'] == 'matched' for side in ('buyer', 'payer', 'supplier')))
        payload = {**recognition, 'number': 'SAME-CONTRACT', 'date': dt.date.today().isoformat(),
            'reviewConfirmed': True, 'paymentTerms': 'Предоплата 100%' if company == 2 else 'Постоплата 100%',
            'reason': 'Проверено по исходному файлу',
            **{side: {key: context[side][key] for key in ('fullName', 'inn')} for side in ('buyer', 'payer', 'supplier')},
            'recognitionReview': {'sourceContentHash': preview['sourceContentHash'],
                'acceptedFields': [{'side': side, 'field': 'fullName'} for side in ('buyer', 'payer', 'supplier')]}}
        saved = self.api(actor, 'POST', path + '/contracts', payload)
        self.assertEqual(saved['reviewedBy'], self.fixture['users'][actor]['name'])
        self.assertTrue(saved['reviewedAt'])
        audit = saved['snapshot']['recognitionReview']
        self.assertEqual(audit['sourceFileId'], file_id)
        self.assertEqual(len(audit['acceptedFields']), 3)
        self.assertTrue(all(field['value'] in field['quote'] for field in audit['acceptedFields']))
        self.api(actor, 'POST', path + '/contracts', payload, expected=409)
        self.api(other, 'POST', path + '/contracts', payload, expected=403)
        self.api('supplier', 'POST', path + '/contracts', payload, expected=403)
        self.assertEqual(self.api('supplier', 'GET', path + '/contracts')['items'], [saved])
        self.api(other, 'GET', path + '/contracts', expected=403)
        self.api('stranger_supplier', 'GET', path + '/contracts', expected=403)
        self.api(actor, 'DELETE', f'/tenant-files/{file_id}', expected=409)
        self.api('supplier', 'DELETE', f'/tenant-files/{file_id}', expected=403)
        document = self.api(actor, 'POST', '/supplier-documents', {
            'companyId': company, 'supplierId': self.fixture['supplierId'], 'docType': 'Договор',
            'title': 'SAME-CONTRACT', 'fileUrl': f'/tenant-files/{file_id}/content'})['id']
        # The buyer's archive remains private; only the saved contract source is shared.
        self.assertNotIn(document, [row['id'] for row in self.api('supplier', 'GET', '/supplier-documents')])
        self.assertNotIn(document, [row['id'] for row in self.api(other, 'GET', '/supplier-documents')])
        self.assertEqual(self.api('stranger_supplier', 'GET', '/supplier-documents'), [])
        self.api(other, 'DELETE', f'/supplier-documents/{document}', expected=403)
        self.api('supplier', 'DELETE', f'/supplier-documents/{document}', expected=403)
        for reader, expected in ((actor, 200), (other, 403), ('stranger_supplier', 403), ('supplier', 200)):
            with self.subTest(file=file_id, reader=reader):
                token = self.main.create_auth_token(self.fixture['users'][reader], two_factor_passed=True)
                response = self.client.get(f'/tenant-files/{file_id}/content', headers={'Authorization': 'Bearer ' + token})
                self.assertEqual(response.status_code, expected, response.text)
                if expected == 200:
                    self.assertEqual(response.content, content)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=(SELECT request_id FROM supplier_offers WHERE id=%s)', (offer_id,))
        try:
            self.api('supplier', 'GET', f'/tenant-files/{file_id}/content', expected=403)
        finally:
            self.sql('UPDATE supply_request_recipients SET visible_to_supplier=TRUE WHERE request_id=(SELECT request_id FROM supplier_offers WHERE id=%s)', (offer_id,))

    def check_invoice_and_receipt(self, actor, other, company, project, offer_id, request_id):
        path = f'/supplier-offers/{offer_id}'
        today = dt.date.today().isoformat()
        invoice = self.api('supplier', 'POST', path + '/create-invoice', {
            'invoiceNumber': 'SAME-NUMBER', 'invoiceDate': today, 'amount': 200, 'vatAmount': 0})['id']
        self.api(other, 'PUT', f'/supplier-invoices/{invoice}', {'status': 'Утверждён'}, expected=403)
        self.api(actor, 'PUT', f'/supplier-invoices/{invoice}', {'status': 'Утверждён'})
        if company == 2:
            self.api('supplier', 'POST', path + '/ship', {'shippedQuantity': 2}, expected=400)
            self.api(actor, 'PUT', f'/supplier-invoices/{invoice}', {'status': 'Оплачен', 'paidAmount': 200, 'paidAt': today})
        delivery = self.api('supplier', 'POST', path + '/ship', {
            'shippedQuantity': 2, 'waybillNumber': 'SAME-NUMBER', 'waybillDate': today})['id']
        receive = f'/supply-deliveries/{delivery}/receive'
        received_qty = 2 if company == 2 else 1
        body = {'receivedQuantity': received_qty, 'qualityStatus': 'Принято', 'receivedBy': 'CHAIN reviewer'}
        self.api(other, 'PUT', receive, body, expected=403)
        self.api(actor, 'PUT', receive, {**body, 'receivedQuantity': 3}, expected=400)
        # A global director role must not override a lower local membership.
        user_id = self.fixture['users'][actor]['id']
        self.sql("UPDATE user_company_roles SET role='бухгалтер' WHERE user_id=%s AND company_id=%s", (user_id, company))
        try:
            self.api(actor, 'PUT', receive, body, expected=403)
        finally:
            self.sql("UPDATE user_company_roles SET role='директор' WHERE user_id=%s AND company_id=%s", (user_id, company))
        # Corrupt parent linkage must not write to another company's request.
        other_request = self.sql('SELECT id FROM supply_requests WHERE company_id<>%s LIMIT 1', (company,))[0][0]
        self.sql('UPDATE supply_deliveries SET request_id=%s WHERE id=%s', (other_request, delivery))
        try:
            with self.subTest(corrupt_delivery=delivery):
                self.api(actor, 'PUT', receive, body, expected=409)
        finally:
            self.sql('UPDATE supply_deliveries SET request_id=%s WHERE id=%s', (request_id, delivery))
        with patch.object(self.main, '_create_supply_delivery_history', side_effect=RuntimeError('synthetic receipt failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic receipt failure'):
                self.api(actor, 'PUT', receive, body)
        self.assertEqual(self.sql('SELECT received_at FROM supply_deliveries WHERE id=%s', (delivery,)), [(None,)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM warehouse_invoices WHERE supply_delivery_id=%s', (delivery,)), [(0,)])
        self.api(actor, 'PUT', receive, body)
        self.assertTrue(self.api(actor, 'PUT', receive, body)['alreadyReceived'])
        self.api(other, 'PUT', receive, body, expected=403)
        self.api(other, 'PUT', receive, body, expected=403, **{'X-Company-Id': str(company)})
        self.assertEqual(self.sql('SELECT company_id,quantity FROM materials WHERE project=%s AND name=%s',
                                 (project, self.fixture['materialName'])), [(company, received_qty)])
        self.assertEqual(self.sql('SELECT company_id,status FROM supply_requests WHERE id=%s', (request_id,)),
                         [(company, 'Поставлено' if company == 2 else 'Проблема поставки')])
        self.assertEqual(self.sql('SELECT company_id FROM warehouse_invoices WHERE supply_delivery_id=%s', (delivery,)), [(company,)])
        if company == 3:
            self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s', (invoice,)), [('Утверждён',)])
            self.api(actor, 'PUT', f'/supplier-invoices/{invoice}', {'status': 'Оплачен', 'paidAmount': 200, 'paidAt': today}, expected=400)
            self.api(actor, 'PUT', f'/supplier-invoices/{invoice}', {'status': 'Оплачен', 'paidAmount': 100, 'paidAt': today})
            self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (invoice,)), [(100,)])
            self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s', (invoice,)), [('Частично оплачен',)])
        if company == 3:
            claim = self.sql('SELECT id FROM supply_claims WHERE delivery_id=%s', (delivery,))[0][0]
            self.assertEqual(self.sql('SELECT shortage_quantity FROM supply_claims WHERE id=%s', (claim,)), [(1,)])
        else:
            claim = self.sql('''INSERT INTO supply_claims(delivery_id,request_id,offer_id,supplier_id,project,work_package)
                            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',
                         (delivery, request_id, offer_id, self.fixture['supplierId'], project, self.fixture['workPackage']))[0][0]
        history = self.sql('SELECT id FROM supply_history WHERE company_id=%s', (company,))[0][0]
        for endpoint, identifier in (('/supply-deliveries', delivery), ('/supply-claims', claim), ('/supply-history', history)):
            with self.subTest(endpoint=endpoint, company=company):
                self.assertIn(identifier, [row['id'] for row in self.api(actor, 'GET', endpoint)])
                self.assertIn(identifier, [row['id'] for row in self.api('supplier', 'GET', endpoint)])
                self.assertNotIn(identifier, [row['id'] for row in self.api(other, 'GET', endpoint)])
                self.assertEqual(self.api('stranger_supplier', 'GET', endpoint), [])
        for method, endpoint, payload in (
            ('POST', f'/supply-deliveries/{delivery}/ai-check', {'parsedItems': [{'name': self.fixture['materialName'], 'quantity': 2}]}),
            ('PUT', f'/supply-claims/{claim}', {'resolution': 'Only owning company'}),
            ('PUT', f'/supply-history/{history}', {'status': 'Принято'}),
        ):
            with self.subTest(mutation=endpoint, company=company):
                self.api(other, method, endpoint, payload, expected=403)
                self.api(actor, method, endpoint, payload)
