"""Recovery under fresh authorization acknowledges original committed commands."""
import json
import os
import unittest
from uuid import uuid4

from . import test_manual_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ManualRecoveryPostgresTests(unittest.TestCase):
    sql = support.ManualBrigadePostgresTests.sql
    api = support.ManualBrigadePostgresTests.api
    request = support.ManualBrigadePostgresTests.request
    setUp = support.ManualBrigadePostgresTests.setUp
    state = support.ManualBrigadePostgresTests.state
    manual_payload = support.ManualBrigadePostgresTests.manual_payload
    create = support.ManualBrigadePostgresTests.create
    assignment = support.ManualBrigadePostgresTests.assignment
    assign = support.ManualBrigadePostgresTests.assign

    @classmethod
    def setUpClass(cls):
        support.ManualBrigadePostgresTests.setUpClass.__func__(cls)

    def pinned(self, payload):
        return {**payload,'expectedCompanyId':2,'expectedActorId':self.f['users']['director']['id']}

    def work(self):
        payload=self.assignment({'type':'manual','requestId':str(uuid4())})
        payload['items'][0]['expectedSource']={'name':'Manual work','unit':'м','quantity':5,'priceSmeta':100}
        return self.pinned(payload)

    def test_lost_response_retry_after_estimate_change_does_not_issue_a_new_snapshot_or_more_work(self):
        payload=self.work()
        original=self.assign(payload)
        self.assertEqual(original['manualRequestId'],payload['assignee']['contractorRef']['requestId'])
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s',(json.dumps([
            {'name':'Changed section','items':[{'name':'Changed work','unit':'м','quantity':20,'priceWork':900,
                'estimateItemKey':payload['items'][0]['estimateItemKey']}]}]),self.f['estimateId']))
        before=self.state()
        retried=self.assign(payload)
        self.assertEqual((retried['contractId'],retried['inserted'],retried['reused']),
                         (original['contractId'],0,1))
        self.assertEqual(before,self.state())
        self.assertEqual(self.sql('SELECT quantity,price_smeta,price_brigade FROM brigade_contract_items WHERE contract_id=%s',
            (original['contractId'],)),[(5,100,60)])

    def test_uncommitted_original_with_changed_source_is_rejected_without_creating_anything(self):
        payload=self.work()
        payload['items'][0]['expectedSource']['priceSmeta']=99
        before=self.state()
        self.assign(payload,expected=409)
        self.assertEqual(before,self.state())

    def test_recovery_cannot_run_as_another_actor_or_company_and_keeps_original_receipt(self):
        payload=self.pinned(self.manual_payload())
        original=self.create(payload)
        self.assertEqual(original['manualRequestId'],payload['contractorRef']['requestId'])
        before=self.state()
        for changes in ({'expectedCompanyId':3},{'expectedActorId':self.collision},{'expectedActorId':True}):
            self.create({**payload,**changes},expected=403)
        self.api('typed_collision','POST','/brigade-contracts',payload,expected=403)
        self.assertEqual(before,self.state())
        self.assertEqual(self.create(payload)['id'],original['id'])

    def test_assignment_recovery_still_requires_current_leadership_permission(self):
        payload=self.work()
        original=self.assign(payload)
        before=self.state()
        self.api('typed_collision','POST',f"/estimates/{self.f['estimateId']}/work-assignment",payload,expected=403)
        self.assertEqual(before,self.state())
        self.assertEqual(self.assign(payload)['contractId'],original['contractId'])
