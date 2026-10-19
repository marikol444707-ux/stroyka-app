"""Ensure the merge fixture reaches real receipt/signup writers with original evidence."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from . import test_company_merge_postgres as postgres


class CompanyMergeReceiptFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {'users': {'director': {'id': 10}}}
        self.main = SimpleNamespace(create_auth_token=Mock(return_value='synthetic-token'))
        self.client = SimpleNamespace(post=Mock(return_value=SimpleNamespace(
            status_code=200, text='', json=lambda: {'contentUrl': '/tenant-files/7/content'})))
        self.sql = Mock(side_effect=[[('7702222222',)], [(1,)], [(1,)]])
        self.api = Mock(return_value={'status': 'no_match'})

    def test_original_and_preview_do_not_precreate_accounting_supplier(self):
        payload = postgres.CompanyMergePostgresTests.receipt_payload(self, 'Synthetic supplier', '7799110000')
        self.assertEqual((payload['supplierName'], payload['supplierInn']), ('Synthetic supplier', '7799110000'))
        self.assertTrue(payload['syncSupplierInvoice'])
        self.assertNotIn('inventoryOnly', payload)
        self.assertTrue(payload['physicalReceiptConfirmed'])
        self.assertTrue(payload['newDocumentConfirmed'])
        self.assertEqual(payload['originalUrls'], ['/tenant-files/7/content'])
        document = payload['receiptDocument']
        self.assertEqual(document, dict(documentType='waybill', waybillNumber=payload['number'],
            waybillDate=payload['date'], supplierInn=payload['supplierInn'], buyerInn='7702222222',
            lines=[dict(materialName='Synthetic supplier material', unit='шт', quantity=2)]))
        self.assertEqual(json.loads(self.client.post.call_args.kwargs['files']['file'][1]), document)
        self.assertEqual(self.client.post.call_args.kwargs['data'], {'context': 'warehouse-receipt'})
        self.api.assert_called_once_with('director', 'POST', '/warehouse-receipts/resolve',
            dict(companyId=2, document=document, originalUrls=payload['originalUrls']), **{'X-Company-Id': '2'})
        self.assertTrue(all(call.args[0].startswith('SELECT ') for call in self.sql.call_args_list))

    def test_review_or_preview_supplier_mutation_rejects_fixture(self):
        self.api.return_value = {'status': 'review'}
        with self.assertRaises(AssertionError):
            postgres.CompanyMergePostgresTests.receipt_payload(self, 'Synthetic supplier', '7799110000')
        self.api.return_value = {'status': 'no_match'}
        self.sql.side_effect = [[('7702222222',)], [(1,)], [(1,), (2,)]]
        with self.assertRaises(AssertionError):
            postgres.CompanyMergePostgresTests.receipt_payload(self, 'Synthetic supplier', '7799110000')
