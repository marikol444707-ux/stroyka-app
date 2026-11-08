import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from .admission import require_standalone_receipt


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        retention = patch('backend.features.warehouse_receipts.admission.retain_originals')
        self.retain = retention.start()
        self.addCleanup(retention.stop)
        self.data = dict(physicalReceiptConfirmed=True, newDocumentConfirmed=True,
            receiptDocument={'documentType':'waybill','supplierInn':'1234567890','waybillNumber':'OLD'},
            number='NEW',date='2026-10-18',supplierInn='1234567890',
            items=[{'name':'Brick','quantity':'2','unit':'шт'}],
            originalUrls=['/tenant-files/1/content'], companyId=2,project='School')

    def test_rechecks_edited_fields_and_owned_original(self):
        with patch('backend.features.warehouse_receipts.admission.resolve_receipt',return_value={'status':'no_match'}) as resolve:
            require_standalone_receipt(Mock(),self.data,{'id':1},{},{})
        payload=resolve.call_args.args[1]
        self.assertEqual(payload['document']['waybillNumber'],'NEW')
        self.assertEqual(payload['document']['lines'][0]['quantity'],'2')
        self.assertEqual(payload['originalUrls'],self.data['originalUrls'])

    def test_both_confirmations_are_required(self):
        for key in ('physicalReceiptConfirmed','newDocumentConfirmed'):
            with self.subTest(key=key), self.assertRaises(HTTPException):
                require_standalone_receipt(Mock(),{**self.data,key:False},{},{},{})

    def test_match_ambiguity_or_review_never_posts_as_new(self):
        for status in ('match','ambiguous','review','existing_receipt','source_selection'):
            with self.subTest(status=status), patch('backend.features.warehouse_receipts.admission.resolve_receipt',return_value={'status':status}), self.assertRaises(HTTPException) as error:
                require_standalone_receipt(Mock(),self.data,{},{},{})
            self.assertEqual(error.exception.status_code,409)

    def test_missing_document_does_not_resolve(self):
        with patch('backend.features.warehouse_receipts.admission.resolve_receipt') as resolve, self.assertRaises(HTTPException):
            require_standalone_receipt(Mock(),{**self.data,'receiptDocument':None},{},{},{})
        resolve.assert_not_called()

    def test_payment_invoice_no_match_never_admits_stock(self):
        for kind in ('payment_invoice','invoice',''):
            data={**self.data,'receiptDocument':{**self.data['receiptDocument'],'documentType':kind}}
            with self.subTest(kind=kind),patch('backend.features.warehouse_receipts.admission.resolve_receipt',return_value={'status':'no_match','requiresWaybill':True}) as resolve,self.assertRaises(HTTPException):
                require_standalone_receipt(Mock(),data,{},{},{})
            resolve.assert_not_called()
            self.retain.assert_not_called()

    def test_requires_waybill_is_rejected_even_with_no_match(self):
        with patch('backend.features.warehouse_receipts.admission.resolve_receipt',return_value={'status':'no_match','requiresWaybill':True}),self.assertRaises(HTTPException):
            require_standalone_receipt(Mock(),self.data,{},{},{})

    def test_location_only_request_checks_actual_stock_destination(self):
        data={**self.data,'project':'','location':'Clinic'}
        with patch('backend.features.warehouse_receipts.admission.resolve_receipt',return_value={'status':'no_match'}) as resolve:
            require_standalone_receipt(Mock(),data,{},{},{})
        self.assertEqual(resolve.call_args.args[1]['project'],'Clinic')
