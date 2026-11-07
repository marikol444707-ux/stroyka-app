"""Manual brigades through authenticated APIs on a disposable migrated database."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import unittest
from uuid import uuid4

from fastapi import HTTPException
import psycopg2

from . import test_selection_postgres as support
from .manual_schema import DOWNGRADE_SQL


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ManualBrigadePostgresTests(unittest.TestCase):
    sql = support.TypedContractorSelectionPostgresTests.sql
    api = support.TypedContractorSelectionPostgresTests.api
    request = support.TypedContractorSelectionPostgresTests.request
    setUp = support.TypedContractorSelectionPostgresTests.setUp

    @classmethod
    def setUpClass(cls):
        support.TypedContractorSelectionPostgresTests.setUpClass.__func__(cls)

    def state(self):
        return support.TypedContractorSelectionPostgresTests.state(self) + [
            ('manual_origins', self.sql('SELECT to_jsonb(o) FROM manual_brigade_contract_origins o ORDER BY contract_id'))]

    def manual_payload(self):
        return {**self.contract, 'contractorId': None,
                'contractorRef': {'type':'manual','requestId':str(uuid4())}}

    def create(self, payload=None, expected=200):
        return self.api('director','POST','/brigade-contracts',payload or self.manual_payload(),expected=expected)

    def assignment(self, reference):
        key = 'manual-work-' + self.tag
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s', (json.dumps([
            {'name':'Manual section','items':[{'name':'Manual work','unit':'м','type':'work',
                'quantity':5,'priceWork':100,'estimateItemKey':key}]}]), self.f['estimateId']))
        return {'assignee':{'contractorRef':reference,'contractorId':None,'brigadeName':self.name},
                'priceMode':'coefficient','coefficient':0.6,
                'items':[{'sectionIndex':0,'itemIndex':0,'estimateItemKey':key}]}

    def assign(self, payload, expected=200):
        return self.api('director','POST',f"/estimates/{self.f['estimateId']}/work-assignment",payload,expected=expected)

    def test_same_name_account_gets_no_contract_items_execution_scope_or_membership_change(self):
        identities = self.sql('SELECT to_jsonb(u) FROM users u ORDER BY id')
        memberships = self.sql('SELECT to_jsonb(m) FROM user_company_roles m ORDER BY id')
        selected = self.create()['id']
        item = self.api('director','POST','/brigade-contract-items',{'contractId':selected,
            'name':'Manual work','unit':'м','quantity':5,'priceSmeta':100,'priceBrigade':60})
        self.assertEqual(self.sql('SELECT contractor_id FROM brigade_contracts WHERE id=%s',(selected,)),[(None,)])
        self.assertEqual(identities,self.sql('SELECT to_jsonb(u) FROM users u ORDER BY id'))
        self.assertEqual(memberships,self.sql('SELECT to_jsonb(m) FROM user_company_roles m ORDER BY id'))
        self.assertNotIn(selected,[c['id'] for c in self.api('typed_collision','GET','/brigade-contracts')])
        self.assertEqual(self.api('typed_collision','GET',f'/brigade-contract-items/{selected}'),[])
        user = self.f['users']['typed_collision']
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                self.assertEqual(self.main._worker_contract_scope_pairs(cur,user),[])
                self.assertEqual(self.main._worker_allowed_estimate_items_for_scopes(cur,user,
                    [(self.f['project'],self.f['workPackage'])]),{})
                with self.assertRaises(HTTPException) as raised:
                    self.main._worker_contract_item_for_work(cur,user,self.f['project'],'Manual work',
                        contract_item_id=item['id'],work_package=self.f['workPackage'])
                self.assertEqual(raised.exception.status_code,403)
        finally:
            conn.rollback()
            conn.close()

    def test_same_name_new_commands_are_distinct_and_exact_retry_does_not_change_state(self):
        payload = self.manual_payload()
        first = self.create(payload)
        before = self.state()
        retry = self.create(payload)
        self.assertEqual((retry['id'],retry['reused']),(first['id'],True))
        self.assertEqual(before,self.state())
        second = self.create()
        self.assertNotEqual(first['id'],second['id'])
        before = self.state()
        self.create({**payload,'brigadeName':'Changed after uncertain result'},expected=409)
        self.create({**payload,'contractorId':self.collision},expected=400)
        self.assertEqual(before,self.state())

    def test_assignment_retry_and_explicit_manual_contract_reuse_preserve_item_prices(self):
        reference = {'type':'manual','requestId':str(uuid4())}
        payload = self.assignment(reference)
        result = self.assign(payload)
        selected = result['contractId']
        before = self.state()
        retry = self.assign(payload)
        self.assertEqual((retry['contractId'],retry['inserted'],retry['reused']),(selected,0,1))
        self.assertEqual(before,self.state())
        self.assign({**payload,'coefficient':0.9},expected=409)
        self.assertEqual(before,self.state())
        exact = {**payload,'coefficient':0.9,'assignee':{**payload['assignee'],
            'contractorRef':{'type':'contract','id':selected}}}
        reused = self.assign(exact)
        self.assertEqual((reused['contractId'],reused['inserted']),(selected,0))
        self.assertEqual(before,self.state())

    def test_real_user_selection_never_adopts_same_name_manual_or_legacy_unlinked_contract(self):
        manual = self.create()['id']
        legacy = self.sql('''INSERT INTO brigade_contracts(company_id,project_id,project_name,work_package,
            brigade_name,contractor_type,status) VALUES(2,%s,%s,%s,%s,'Мастер','Черновик') RETURNING id''',
            (self.f['projectId'],self.f['project'],self.f['workPackage'],self.name))[0][0]
        before = self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=ANY(%s) ORDER BY id',([manual,legacy],))
        actual = self.create({**self.contract,'contractorId':self.collision,
            'contractorRef':{'type':'user','id':self.collision}})['id']
        self.assertNotIn(actual,[manual,legacy])
        self.assertEqual(before,self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=ANY(%s) ORDER BY id',([manual,legacy],)))
        self.create({**self.contract,'contractorRef':{'type':'contract','id':legacy}},expected=409)

    def test_manual_origin_and_identity_cannot_be_rewritten_and_downgrade_preserves_used_history(self):
        selected = self.create()['id']
        before = self.state()
        for sql,args in (
            ('UPDATE brigade_contracts SET contractor_id=%s WHERE id=%s',(self.collision,selected)),
            ('UPDATE brigade_contracts SET company_id=3 WHERE id=%s',(selected,)),
            ('UPDATE manual_brigade_contract_origins SET created_by=%s WHERE contract_id=%s',(self.collision,selected)),
            ('DELETE FROM manual_brigade_contract_origins WHERE contract_id=%s',(selected,)),
            (DOWNGRADE_SQL,()),
        ):
            with self.subTest(sql=sql),self.assertRaises(psycopg2.errors.RaiseException):
                self.sql(sql,args)
            self.assertEqual(before,self.state())

    def test_parallel_retries_share_one_manual_contract(self):
        payload = self.manual_payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.create(payload),range(2)))
        self.assertEqual(responses[0]['id'],responses[1]['id'])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM manual_brigade_contract_origins WHERE company_id=2 AND request_id=%s',
            (payload['contractorRef']['requestId'],)),[(1,)])

    def test_retry_and_exact_selection_reject_a_signed_manual_record_without_rewriting_it(self):
        payload = self.manual_payload()
        selected = self.create(payload)['id']
        # Synthetic imported status; the ordinary signing API needs a verified party.
        self.sql("UPDATE brigade_contracts SET status='Подписан' WHERE id=%s",(selected,))
        assignment = self.assignment({'type':'contract','id':selected})
        before = self.state()
        self.create(payload,expected=409)
        self.assign(assignment,expected=409)
        self.assertEqual(before,self.state())
