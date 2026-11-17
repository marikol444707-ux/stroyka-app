"""Factory tests only; PostgreSQL suites exercise the actual HTTP writers."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from .test_http_support import physical_receipt_payload


class ReceiptHttpFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {'users': {'foreman': {'id': 10}}}
        self.main = SimpleNamespace(create_auth_token=Mock(return_value='synthetic-token'))
        self.client = SimpleNamespace(post=Mock(return_value=SimpleNamespace(
            status_code=200, text='', json=lambda: {'contentUrl': '/tenant-files/7/content'})))
        self.sql = Mock(return_value=[(12,)])
        self.delivery = dict(id=31, companyId=2, project='Synthetic project',
            waybillNumber='Synthetic 31', waybillDate='2026-10-15', materialName='Synthetic cable',
            unit='m', shippedQuantity=2, documentParties=dict(reviewRequired=False,
                buyer=dict(inn='7702222222'), supplier=dict(inn='7701234567')))
        self.preview = dict(status='match', matchedBatch=dict(lines=[dict(id=31)]))
        self.api = Mock(side_effect=lambda _actor, method, _path, *args:
                        [copy.deepcopy(self.delivery)] if method == 'GET' else copy.deepcopy(self.preview))

    def test_upload_preview_and_actual_quantity_keep_document_quantity(self):
        payload = physical_receipt_payload(self, 'foreman', 31, 1)
        self.assertEqual(payload['document']['lines'][0]['quantity'], 2)
        self.assertEqual(payload['actualLines'], [dict(deliveryId=31, receivedQuantity=1, qualityStatus='Принято')])
        self.assertTrue(payload['physicalReceiptConfirmed'])
        self.assertEqual(payload['originalUrls'], ['/tenant-files/7/content'])
        args, kwargs = self.client.post.call_args
        self.assertEqual(args, ('/upload-photo',))
        self.assertEqual(kwargs['data'], dict(context='warehouse-receipt', projectId='12', projectName='Synthetic project'))
        self.assertEqual(kwargs['headers']['X-Company-Id'], '2')
        self.assertEqual(json.loads(kwargs['files']['file'][1]), payload['document'])
        self.sql.assert_called_once_with('SELECT id FROM projects WHERE company_id=%s AND name=%s', (2, 'Synthetic project'))
        self.assertEqual(self.api.call_args.args, ('foreman', 'POST', '/warehouse-receipts/resolve', payload))

    def test_shared_original_is_reused_without_upload(self):
        payload = physical_receipt_payload(self, 'foreman', 31, 1, '/tenant-files/99/content')
        self.assertEqual(payload['originalUrls'], ['/tenant-files/99/content'])
        self.client.post.assert_not_called()
        self.sql.assert_not_called()

    def test_unreviewable_history_or_different_match_fails_fixture(self):
        self.delivery['documentParties']['reviewRequired'] = True
        with self.assertRaises(AssertionError):
            physical_receipt_payload(self, 'foreman', 31, 1)
        self.client.post.assert_not_called()
        self.delivery['documentParties']['reviewRequired'] = False
        for preview in (dict(status='review'), dict(status='match', matchedBatch=dict(lines=[dict(id=99)]))):
            self.preview = preview
            with self.assertRaises(AssertionError):
                physical_receipt_payload(self, 'foreman', 31, 1)
