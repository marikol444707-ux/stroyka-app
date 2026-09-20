"""Platform contract and invoice lifecycle on a disposable database."""
import os
import unittest
import uuid
from . import test_payment_commands_postgres as payment_support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class BillingChainTests(unittest.TestCase):
    api = payment_support.PlatformPaymentTests.api
    sql = payment_support.PlatformPaymentTests.sql

    @classmethod
    def setUpClass(cls):
        payment_support.PlatformPaymentTests.setUpClass.__func__(cls)

    def prepare_parties(self):
        account = self.sql('SELECT platform_account_id FROM companies WHERE id=2')[0][0]
        self.api(self.operator, 'PUT', '/system/licensor-profile', {
            'platformAccountId': account, 'legalForm':'legal_entity',
            'legalName':'ООО Тестовый лицензиар', 'inn':'2635000000', 'kpp':'263501001',
            'ogrn':'1022600000000', 'legalAddress':'Тестовый адрес',
            'phone':'+79000000000', 'email':'licensor@local.test',
            'settlementAccount':'40702810000000000001', 'bankName':'Тестовый банк',
            'bankBik':'040000002', 'correspondentAccount':'30101810000000000002',
            'signatoryName':'Тестовый директор', 'signatoryBasis':'Устав'})
        self.sql("""INSERT INTO company_requisites(company_id,full_name,inn,kpp,ogrn,legal_address,
            phone,email,rs,bank_name,bik,ks,director_name,basis)
            VALUES(2,'ООО Тестовый заказчик','2635000000','263501001','1022600000000','Тестовый адрес',
            '+79000000000','client@local.test','40702810000000000001','Тестовый банк','040000002',
            '30101810000000000002','Тестовый директор','Устав') ON CONFLICT(company_id) DO NOTHING""")
        return {'companyId':2,'idempotencyKey':str(uuid.uuid4()),'contractDate':'2026-09-20',
                'startsOn':'2026-09-20','plan':'pro','monthlyFee':'150.12','maxProjects':5,'maxUsers':10}

    def block_audit(self):
        self.sql("""CREATE OR REPLACE FUNCTION test_billing_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'test billing audit unavailable'; END $$;
            CREATE TRIGGER test_billing_reject_audit BEFORE INSERT ON platform_audit_log
            FOR EACH ROW EXECUTE FUNCTION test_billing_reject_audit()""")
        self.addCleanup(self.sql, 'DROP TRIGGER IF EXISTS test_billing_reject_audit ON platform_audit_log; DROP FUNCTION IF EXISTS test_billing_reject_audit()')

    def test_contract_create_rolls_back_when_audit_fails(self):
        payload=self.prepare_parties()
        preview=self.api(self.operator,'POST','/system/client-contracts/preview',payload)
        self.assertEqual(preview['blockers'],[])
        self.block_audit()
        with self.assertRaisesRegex(Exception,'test billing audit unavailable'):
            self.api(self.operator,'POST','/system/client-contracts',payload)
        self.assertEqual(self.sql('SELECT id FROM platform_client_contracts WHERE idempotency_key=%s',(payload['idempotencyKey'],)),[])

    def test_invoice_create_rolls_back_when_audit_fails(self):
        number='TEST-'+str(uuid.uuid4())
        self.block_audit()
        with self.assertRaisesRegex(Exception,'test billing audit unavailable'):
            self.api(self.operator,'POST','/system/billing-documents',{'companyId':2,'amount':'150.12','number':number})
        self.assertEqual(self.sql('SELECT id FROM platform_billing_documents WHERE number=%s',(number,)),[])

    def test_invoice_rejects_nonfinite_or_fractional_kopecks(self):
        for value in ('NaN','Infinity','0.001'):
            self.api(self.operator,'POST','/system/billing-documents',{'companyId':2,'amount':value},expected=422)

    def test_contract_invoice_payment_summary_and_subscription(self):
        payload=self.prepare_parties()
        created=self.api(self.operator,'POST','/system/client-contracts',payload)
        contract=created['contract']['id']
        replay=self.api(self.operator,'POST','/system/client-contracts',payload)
        self.assertEqual(replay['contract']['id'],contract)
        invoice=self.api(self.operator,'POST','/system/billing-documents',{'companyId':2,'clientContractId':contract,
            'amount':'150.12','status':'issued','periodStart':'2026-09-20','periodEnd':'2030-12-31'})['document']
        def summary():
            return next(row['billingSummary'] for row in self.api(self.operator,'GET','/system/client-contracts?companyId=2')['items'] if row['id']==contract)
        self.assertEqual((summary()['billedAmount'],summary()['paidAmount'],summary()['debtAmount']),('150.12','0.00','150.12'))
        body={'companyId':2,'clientContractId':contract,'amount':'150.12','requestId':str(uuid.uuid4()),
              'invoiceNumber':invoice['number'],'periodEnd':'2030-12-31'}
        self.api(self.operator,'POST','/system/payments',body)
        self.api(self.operator,'POST','/system/payments',body)
        self.assertEqual((summary()['paidAmount'],summary()['debtAmount'],summary()['paymentCount']),('150.12','0.00',1))
        self.assertEqual(self.sql('SELECT plan_expires_at::text FROM companies WHERE id=2'),[('2030-12-31',)])
        self.api(self.fixture['users']['director'],'GET','/system/client-contracts?companyId=2',expected=403)

    def test_closed_invoice_cannot_be_reopened_for_another_provider_credit(self):
        invoice=self.api(self.operator,'POST','/system/billing-documents',{'companyId':2,'amount':'150.12','status':'closed'})['document']
        self.api(self.operator,'PUT',f"/system/billing-documents/{invoice['id']}",{'status':'issued'},expected=409)
        self.api(self.operator,'POST',f"/system/billing-documents/{invoice['id']}/prepare-payment",{'provider':'manual'},expected=409)

    def test_invoice_update_rolls_back_with_audit(self):
        invoice=self.api(self.operator,'POST','/system/billing-documents',{'companyId':2,'amount':'150.12'})['document']
        self.block_audit()
        with self.assertRaisesRegex(Exception,'test billing audit unavailable'):
            self.api(self.operator,'PUT',f"/system/billing-documents/{invoice['id']}",{'status':'issued'})
        self.assertEqual(self.sql('SELECT status FROM platform_billing_documents WHERE id=%s',(invoice['id'],)),[('draft',)])

    def test_provider_settlement_keeps_invoice_and_payment_on_same_contract(self):
        contract=self.api(self.operator,'POST','/system/client-contracts',self.prepare_parties())['contract']['id']
        document,event=payment_support.PlatformPaymentTests.seed_event(self)
        self.api(self.operator,'PUT',f'/system/billing-documents/{document}/client-contract',{'clientContractId':contract})
        payment=self.api(self.operator,'POST',f'/system/payment-events/{event}/confirm',{})['paymentId']
        before=self.api(self.operator,'GET','/system/client-contracts?companyId=2')
        self.api(self.operator,'PUT',f'/system/billing-documents/{document}/client-contract',{'clientContractId':None},expected=409)
        self.api(self.operator,'PUT',f'/system/payments/{payment}/client-contract',{'clientContractId':None},expected=409)
        self.assertEqual(self.api(self.operator,'GET','/system/client-contracts?companyId=2'),before)
        self.assertEqual(self.sql('SELECT client_contract_id FROM platform_billing_documents WHERE id=%s',(document,)),[(contract,)])
        self.assertEqual(self.sql('SELECT client_contract_id FROM company_payments WHERE id=%s',(payment,)),[(contract,)])

    def test_expired_subscription_is_read_only_until_paid_and_admin_freeze_survives(self):
        director=self.fixture['users']['director']
        old=self.sql('SELECT plan,plan_expires_at,payment_status,suspended_at,suspended_reason FROM companies WHERE id=2')[0]
        self.sql("UPDATE companies SET plan='pro',plan_expires_at='2000-01-01',payment_status='overdue',suspended_at=NULL WHERE id=2")
        try:
            self.api(director,'GET','/projects')
            self.api(director,'POST','/projects',{'name':'Blocked expired project'},expected=403)
            body={'companyId':2,'amount':'150.12','requestId':str(uuid.uuid4()),'periodEnd':'2031-01-01'}
            self.api(self.operator,'POST','/system/payments',body)
            self.api(director,'POST','/projects',{'name':'Paid subscription project'})
            self.sql("UPDATE companies SET suspended_at=NOW(),suspended_reason='Director decision' WHERE id=2")
            self.api(self.operator,'POST','/system/payments',dict(body,requestId=str(uuid.uuid4()),periodEnd='2032-01-01'))
            self.api(director,'POST','/projects',{'name':'Blocked frozen project'},expected=403)
        finally:
            self.sql('UPDATE companies SET plan=%s,plan_expires_at=%s,payment_status=%s,suspended_at=%s,suspended_reason=%s WHERE id=2',old)

    def test_contract_pdf_is_protected_replayable_and_does_not_create_payment(self):
        payload=self.prepare_parties()
        contract=self.api(self.operator,'POST','/system/client-contracts',payload)['contract']['id']
        before=self.sql('SELECT COUNT(*) FROM company_payments')
        generated=self.api(self.operator,'POST',f'/system/client-contracts/{contract}/generate-pdf',{})
        repeated=self.api(self.operator,'POST',f'/system/client-contracts/{contract}/generate-pdf',{})
        self.assertEqual(generated['fileUrl'],repeated['fileUrl'])
        self.assertTrue(generated['fileUrl'].startswith('/tenant-files/'))
        token=self.main.create_auth_token(self.operator,two_factor_passed=True)
        pdf=self.client.get(generated['fileUrl'],headers={'Authorization':'Bearer '+token})
        self.assertEqual(pdf.status_code,200,pdf.text[:100] if pdf.status_code!=200 else '')
        self.assertTrue(pdf.content.startswith(b'%PDF-'))
        metadata_url=generated['fileUrl'].removesuffix('/content')
        self.api(self.operator,'DELETE',metadata_url,expected=409)
        self.api(self.customer,'GET',metadata_url,expected=403)
        file_id=int(metadata_url.rsplit('/',1)[1])
        self.sql("UPDATE file_ownership SET context='general' WHERE id=%s",(file_id,))
        self.api(self.operator,'GET',metadata_url,expected=403)
        self.sql("UPDATE file_ownership SET context='platform-client-contract' WHERE id=%s",(file_id,))
        self.sql('UPDATE platform_client_contracts SET generated_file_url=NULL WHERE id=%s',(contract,))
        self.api(self.operator,'GET',metadata_url,expected=403)
        self.sql('UPDATE platform_client_contracts SET generated_file_url=%s WHERE id=%s',(generated['fileUrl'],contract))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM company_payments'),before)
        self.assertEqual(self.sql('SELECT status FROM platform_client_contracts WHERE id=%s',(contract,)),[('draft',)])

    def test_invoice_pdf_has_owned_protected_download(self):
        self.prepare_parties()
        invoice=self.api(self.operator,'POST','/system/billing-documents',{'companyId':2,'amount':'150.12'})['document']
        generated=self.api(self.operator,'POST',f"/system/billing-documents/{invoice['id']}/generate-pdf",{})
        self.assertTrue(generated['fileUrl'].startswith('/tenant-files/'),generated['fileUrl'])
        repeated=self.api(self.operator,'POST',f"/system/billing-documents/{invoice['id']}/generate-pdf",{})
        self.assertEqual(repeated['fileUrl'],generated['fileUrl'])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM file_ownership WHERE context='platform-billing-document'"),[(1,)])
        token=self.main.create_auth_token(self.operator,two_factor_passed=True)
        response=self.client.get(generated['fileUrl'],headers={'Authorization':'Bearer '+token})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.content.startswith(b'%PDF-'))
