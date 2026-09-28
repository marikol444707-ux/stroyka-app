"""Real HTTP rejected receipt -> return/replacement -> owned acceptance, isolated DB."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from . import test_partial_receipt_runtime_postgres as base
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class ClaimFulfilmentTests(unittest.TestCase):
    sql = base.PartialReceiptRuntimeTests.sql
    api = base.PartialReceiptRuntimeTests.api
    create_offer = base.PartialReceiptRuntimeTests.create_offer
    check_contract = base.PartialReceiptRuntimeTests.check_contract
    raw_sources = base.PartialReceiptRuntimeTests.raw_sources
    create = base.PartialReceiptRuntimeTests.create
    pay = base.PartialReceiptRuntimeTests.pay
    ship = base.PartialReceiptRuntimeTests.ship
    receive = base.PartialReceiptRuntimeTests.receive

    @classmethod
    def setUpClass(cls):
        base.PartialReceiptRuntimeTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                for table,name in (('work_material_operations','0027_work_material_accounting.py'),
                                   ('supply_claim_events','0033_supply_claim_cases.py')):
                    cur.execute('SELECT to_regclass(%s)',(table,))
                    if not cur.fetchone()[0]:
                        migration(cur,name)
                migration(cur,'0054_supply_claim_fulfilment.py')
                migration(cur,'0054_supply_claim_fulfilment.py',method='downgrade')
                migration(cur,'0054_supply_claim_fulfilment.py')
        finally:
            conn.close()

    def setUp(self):
        base.PartialReceiptRuntimeTests.setUp(self)
        flags=patch.dict(os.environ,SUPPLY_CLAIMS_ENABLED='1',SUPPLY_CLAIM_FULFILMENT_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)

    def problem(self,quantity=1,quality='Брак'):
        did=self.ship()
        result=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',
                        dict(receivedQuantity=quantity,qualityStatus=quality))
        return result['claimId']

    def action(self,claim,action,quantity,actor='director',expected=200,body=None):
        path=f'/supply-claims/{claim}/case'
        if body is None:
            card=self.api(actor,'GET',path)
            body=dict(action=action,quantity=str(quantity),text='Synthetic physical claim action',
                expectedVersion=card['claim']['version'],expectedCompanyId=2,
                expectedActorId=self.fixture['users'][actor]['id'],requestId=str(uuid4()))
        return self.api(actor,'POST',path,body,expected=expected),body

    def test_rejected_return_then_replacement_and_original_balance_no_new_debt(self):
        claim=self.problem()
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        returned,body=self.action(claim,'return',1)
        self.assertEqual(self.action(claim,'return',1,body=body)[0],returned)
        replaced,body=self.action(claim,'replace',1,'supplier')
        self.assertEqual(self.action(claim,'replace',1,'supplier',body=body)[0],replaced)
        replacement=replaced['replacementDeliveryId']
        self.receive(replacement)
        # A replacement must not consume the unshipped original order quantity.
        self.receive(self.ship())
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM supplier_invoices WHERE offer_id=%s',(self.offer_id,)),[(1,200)])
        self.assertEqual(self.sql('SELECT sum(p.quantity),sum(p.amount) FROM supplier_receipt_line_proofs p JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id WHERE s.invoice_id=%s',(self.invoice,)),[(2,200)])
        self.action(claim,'return',1,expected=409)
        self.action(claim,'replace',1,'supplier',expected=409)
        card=self.api('director','GET',f'/supply-claims/{claim}/case')
        self.api('director','POST',f'/supply-claims/{claim}/case',dict(action='resolve',text='Return and replacement completed',
            expectedVersion=card['claim']['version'],expectedCompanyId=2,
            expectedActorId=self.fixture['users']['director']['id'],requestId=str(uuid4())))
        self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s',(self.request_id,)),[('Поставлено',)])
        listed={row['id']:row for row in self.api('supplier','GET','/supply-deliveries')}
        self.assertEqual(listed[replacement]['replacementClaimId'],claim)
        self.assertTrue(any(row.get('claimId')==claim and row.get('claimResolved') for row in listed.values()))

    def test_shortage_can_be_replaced_but_cannot_be_physically_returned(self):
        claim=self.problem(.5,'Недостача')
        self.action(claim,'return',.5,expected=409)
        replacement,_=self.action(claim,'replace',.5,'supplier')
        self.api('foreman','PUT',f"/supply-deliveries/{replacement['replacementDeliveryId']}/receive",
                 dict(receivedQuantity=.5,qualityStatus='Принято'))
        self.receive(self.ship())
        self.assertEqual(self.sql('SELECT sum(p.amount) FROM supplier_receipt_line_proofs p JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id WHERE s.invoice_id=%s',(self.invoice,)),[(200,)])

    def test_roles_and_quantities(self):
        claim=self.problem()
        self.action(claim,'return',1,'supplier',expected=403)
        self.action(claim,'replace',1,'director',expected=403)
        self.action(claim,'return',2,expected=409)
        for invalid in ('NaN','Infinity','0','-1','0.00001','10000000000'):
            self.action(claim,'return',invalid,expected=400)
        self.api('stranger','GET',f'/supply-claims/{claim}/case',expected=404)
        returned,body=self.action(claim,'return',.5)
        self.action(claim,'return',.6,body={**body,'quantity':'.6'},expected=409)
        self.api('stranger','POST',f'/supply-claims/{claim}/case',body,expected=404)

    def test_flag_off_and_closed_claim_have_no_physical_actions(self):
        claim=self.problem()
        with patch.dict(os.environ,SUPPLY_CLAIM_FULFILMENT_ENABLED='0'):
            self.action(claim,'return',1,expected=409)
        path=f'/supply-claims/{claim}/case'
        self.api('director','POST',path,dict(action='resolve',text='Synthetic resolution',expectedVersion=1,
            expectedCompanyId=2,expectedActorId=self.fixture['users']['director']['id'],requestId=str(uuid4())))
        self.action(claim,'replace',1,'supplier',expected=409)

    def test_late_failure_rolls_back_replacement_event_and_version(self):
        from fastapi import HTTPException
        claim=self.problem()
        before=self.sql('SELECT count(*) FROM supply_deliveries')
        with patch('backend.features.supply_claim_cases.fulfilment.record',side_effect=HTTPException(409,'Synthetic late failure')):
            self.action(claim,'replace',1,'supplier',expected=409)
        self.assertEqual(self.sql('SELECT count(*) FROM supply_deliveries'),before)
        self.assertEqual(self.sql('SELECT version FROM supply_claims WHERE id=%s',(claim,)),[(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claim_events WHERE claim_id=%s',(claim,)),[(0,)])

    def test_replacement_identity_is_immutable(self):
        import psycopg2
        claim=self.problem()
        replacement,_=self.action(claim,'replace',1,'supplier')
        with self.assertRaises(psycopg2.Error):
            self.sql('UPDATE supply_deliveries SET shipped_quantity=2 WHERE id=%s',(replacement['replacementDeliveryId'],))
        with self.assertRaises(psycopg2.Error):
            self.sql('DELETE FROM supply_claim_fulfilments WHERE claim_id=%s',(claim,))
        self.receive(replacement['replacementDeliveryId'])

    def test_database_rejection_is_http_conflict_and_rolls_back_event(self):
        from backend.features.supply_claim_cases import fulfilment
        claim=self.problem()
        original=fulfilment.record
        def invalid(cur,claim,action,event_id,result):
            return original(cur,claim,action,event_id,{**result,'quantity':'2'})
        with patch.object(fulfilment,'record',side_effect=invalid):
            self.action(claim,'return',1,expected=409)
        self.assertEqual(self.sql('SELECT version FROM supply_claims WHERE id=%s',(claim,)),[(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claim_events WHERE claim_id=%s',(claim,)),[(0,)])

    def test_competing_returns_cannot_exceed_claim_quantity(self):
        from concurrent.futures import ThreadPoolExecutor
        claim=self.problem()
        def attempt(_):
            token=self.main.create_auth_token(self.fixture['users']['director'],two_factor_passed=True)
            return self.client.post(f'/supply-claims/{claim}/case',headers={
                'Authorization':'Bearer '+token,'X-Company-Id':'2','X-Company-Mode':'company'},json=dict(
                    action='return',quantity='1',text='Synthetic competing return',expectedVersion=1,
                    expectedCompanyId=2,expectedActorId=self.fixture['users']['director']['id'],requestId=str(uuid4()))).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt,range(2))),[200,409])
        self.assertEqual(self.sql("SELECT sum(quantity) FROM supply_claim_fulfilments WHERE claim_id=%s AND action='return'",(claim,)),[(1,)])

    def test_zero_receipt_replacement_and_rejected_replacement_new_claim(self):
        claim=self.problem(0,'Недостача')
        first,_=self.action(claim,'replace',1,'supplier')
        rejected=self.api('foreman','PUT',f"/supply-deliveries/{first['replacementDeliveryId']}/receive",
            dict(receivedQuantity=1,qualityStatus='Брак'))
        second,_=self.action(rejected['claimId'],'replace',1,'supplier')
        self.receive(second['replacementDeliveryId'])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_invoices WHERE offer_id=%s',(self.offer_id,)),[(1,)])

    def test_database_rejects_excess_return_and_downgrade_with_evidence(self):
        import psycopg2
        claim=self.problem()
        result,_=self.action(claim,'return',.5)
        with self.assertRaises(psycopg2.Error) as error:
            self.sql("INSERT INTO supply_claim_fulfilments(event_id,claim_id,company_id,action,quantity) VALUES(%s,%s,2,'return',1)",
                (result['eventId'],claim))
        self.assertEqual(error.exception.pgcode,'23514')
        conn=self.main.get_db()
        try:
            with self.assertRaises(psycopg2.Error),conn,conn.cursor() as cur:
                migration(cur,'0054_supply_claim_fulfilment.py',method='downgrade')
        finally:
            conn.close()
