"""VAT invoice -> unpaid partial receipt -> cash settlement on isolated PostgreSQL."""
import os
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
from . import test_unpaid_receipts_postgres as unpaid
from . import test_settlements_postgres as settlements
from . import test_invoice_line_creation_postgres as invoices
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class ReceiptVatTests(unittest.TestCase):
    sql=unpaid.UnpaidReceiptTests.sql
    api=unpaid.UnpaidReceiptTests.api
    create_offer=unpaid.UnpaidReceiptTests.create_offer
    check_contract=unpaid.UnpaidReceiptTests.check_contract
    raw_sources=unpaid.UnpaidReceiptTests.raw_sources
    ship=unpaid.UnpaidReceiptTests.ship
    receive=unpaid.UnpaidReceiptTests.receive
    pay=unpaid.UnpaidReceiptTests.pay

    @classmethod
    def setUpClass(cls):
        settlements.SettlementTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0056_supplier_receipt_vat.py')
                migration(cur,'0056_supplier_receipt_vat.py',method='downgrade')
                migration(cur,'0056_supplier_receipt_vat.py')
        finally: conn.close()

    def create(self,payload=None,**kw):
        self.sql('UPDATE supplier_offers SET vat_included=TRUE WHERE id=%s',(self.offer_id,))
        data={**self.payload,'vatAmount':'34.00'} if payload is None else payload
        return invoices.InvoiceLineCreationPostgresTests.create(self,data,**kw)

    def setUp(self):
        flags=patch.dict(os.environ,SUPPLIER_VAT_RECEIPTS_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)
        unpaid.UnpaidReceiptTests.setUp(self)

    def test_partial_receipts_preserve_declared_vat_without_second_debt(self):
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        warehouses=[]
        for _ in range(2):
            did=self.ship();result=self.receive(did);warehouses.append(result['invoiceId'])
            self.assertTrue(self.receive(did)['alreadyReceived'])
        self.assertEqual(self.sql('SELECT total_base,total_vat,total_with_vat,supplier_invoice_id FROM warehouse_invoices WHERE id=ANY(%s) ORDER BY id',(warehouses,)),[(83,17,100,None),(83,17,100,None)])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT sum(p.amount),sum(p.vat_amount) FROM supplier_receipt_line_proofs p JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id WHERE s.invoice_id=%s',(self.invoice,)),[(200,34)])
        self.pay('200.00')
        self.assertEqual(self.sql('SELECT amount,vat_amount,paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(200,34,200)])

    def test_vat_flag_off_rejects_receipt_without_warehouse_or_stock_write(self):
        did=self.ship()
        with patch.dict(os.environ,SUPPLIER_VAT_RECEIPTS_ENABLED='0'):
            self.receive(did,expected=409)
        self.assertEqual(self.sql('SELECT id FROM warehouse_invoices WHERE supply_delivery_id=%s',(did,)),[])

    def test_rejected_vat_goods_do_not_consume_accepted_line_tax(self):
        did=self.ship()
        result=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'))
        self.assertEqual(self.sql('SELECT total_base,total_vat,total_with_vat FROM warehouse_invoices WHERE id=%s',(result['invoiceId'],)),[(83,17,100)])
        self.assertEqual(self.sql('SELECT p.receipt_relation_id FROM supplier_receipt_line_proofs p JOIN supplier_payment_receipt_relations r ON r.id=p.receipt_relation_id WHERE r.warehouse_invoice_id=%s',(result['invoiceId'],)),[])

    def test_database_rejects_wrong_tax_and_rolls_back_receipt(self):
        did=self.ship()
        before=self.sql('SELECT count(*),sum(quantity) FROM materials WHERE company_id=2')
        with patch('backend.features.supplier_payments.receipt_vat_runtime.receipt_tax_slice',
                   return_value=dict(amount='100.00',baseAmount='84.00',vatAmount='16.00')):
            self.receive(did,expected=409)
        self.assertEqual(self.sql('SELECT id FROM warehouse_invoices WHERE supply_delivery_id=%s',(did,)),[])
        self.assertEqual(self.sql('SELECT count(*),sum(quantity) FROM materials WHERE company_id=2'),before)

    def test_repeat_does_not_silently_change_tax(self):
        self.assertEqual(self.create()['id'],self.invoice)
        self.create({**self.payload,'vatAmount':'35.00'},expected=409)
        self.assertEqual(self.sql('SELECT vat_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(34,)])

    def test_tax_evidence_is_immutable_and_cannot_be_downgraded(self):
        from psycopg2 import Error
        with self.assertRaises(Error):
            self.sql('UPDATE supplier_invoice_lines SET vat_amount=0 WHERE spec_id=(SELECT id FROM supplier_invoice_line_specs WHERE invoice_id=%s)',(self.invoice,))
        conn=self.main.get_db()
        try:
            with self.assertRaises(Error),conn,conn.cursor() as cur:
                migration(cur,'0056_supplier_receipt_vat.py',method='downgrade')
        finally: conn.close()

    def test_mixed_tax_lines_keep_their_own_amounts(self):
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        first={**self.request_items[0],'quantity':'1'}
        second={**first,'materialName':'Synthetic VAT-free material'}
        sections=json.loads(self.sql('SELECT sections_json FROM estimates WHERE id=%s',(self.fixture['estimateId'],))[0][0])
        sections[0]['items'].append({**sections[0]['items'][0],'id':'vat-free-material','name':second['materialName']})
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s',(json.dumps(sections),self.fixture['estimateId']))
        self.raw_sources([first,second],[{**first,'pricePerUnit':'100','totalPrice':'100'},
                                        {**second,'pricePerUnit':'100','totalPrice':'100'}])
        payload={**self.payload,'vatAmount':'17.00','lineTaxes':[
            dict(sourceOfferPosition=0,vatAmount='17.00'),dict(sourceOfferPosition=1,vatAmount='0.00')]}
        self.invoice=self.create(payload)['id']
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        result=self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedItems=[{**first,'shippedQuantity':'1'},{**second,'shippedQuantity':'1'}]))
        for delivery in result['deliveries']:
            self.receive(delivery['id'])
        self.assertEqual(self.sql('''SELECT l.material_name,p.amount,p.vat_amount FROM supplier_receipt_line_proofs p
            JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id
            WHERE s.invoice_id=%s ORDER BY l.line_no''',(self.invoice,)),[(first['materialName'],100,17),(second['materialName'],100,0)])
        self.create({**payload,'lineTaxes':[dict(sourceOfferPosition=0,vatAmount='0'),dict(sourceOfferPosition=1,vatAmount='17')]},expected=409)

    def test_zero_declared_tax_is_not_relabelled_as_exempt(self):
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        self.invoice=self.create({**self.payload,'vatAmount':'0.00'})['id']
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        result=self.receive(self.ship())
        self.assertEqual(self.sql('SELECT vat,total_vat FROM warehouse_invoices WHERE id=%s',(result['invoiceId'],)),[('НДС по строке счёта',0)])
