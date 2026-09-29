"""Authenticated supply-claim lifecycle and disclosure regressions on real PG."""
import os
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import psycopg2

from .test_support import SupplyClaimCasesPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class SupplyClaimCasesPostgresTests(SupplyClaimCasesPostgresSupport, unittest.TestCase):
    def test_legacy_put_cannot_set_arbitrary_status_and_client_resolution_time(self):
        self.assert_denied_unchanged("PUT", self.legacy_path, {
            "status": "Arbitrary client status", "resolvedAt": "1900-01-01T00:00:00", "resolution": "Replaced without history"})

    def test_supplier_cannot_overwrite_the_resolution_of_a_closed_claim(self):
        self.assertEqual(self.sql("SELECT status,resolution FROM supply_claims WHERE id=%s", (self.claim_id,)),
                         [("Решена", "Director original decision")])
        self.assert_denied_unchanged("PUT", self.legacy_path, {"resolution": "Supplier erased the agreed decision"}, actor="supplier")

    test_supplier_cannot_overwrite_the_resolution_of_a_closed_claim.initial_status = "Решена"

    def body(self, actor='director', **changes):
        return dict(action='comment', text='Synthetic claim message', expectedVersion=1,
                    expectedCompanyId=2, expectedActorId=self.f['users'][actor]['id'],
                    requestId=str(uuid4()), **changes)

    def test_lifecycle_history_and_exact_replay_preserve_delivery_and_business(self):
        tables = ('supply_deliveries','supply_requests','supplier_offers','materials','warehouse_main',
                  'warehouse_history','supplier_invoices','brigade_payments')
        before = [(t,self.sql('SELECT row_to_json(t)::text FROM '+t+' t ORDER BY 1')) for t in tables]
        for version, (actor, action, status) in enumerate([
                ('director','start','В работе'), ('supplier','reply','В работе'),
                ('director','resolve','Решена'), ('director','reopen','Открыта')], 1):
            body = self.body(actor)
            body.update(action=action, expectedVersion=version, text='Message '+str(version))
            result = self.api(actor,'POST',self.path,body)
            self.assertEqual(self.api(actor,'POST',self.path,body), result)
            detail = self.api('director','GET',self.path)
            self.assertEqual(detail['claim']['status'],status)
            self.assertEqual(detail['claim']['version'],version+1)
            self.assertEqual(len(detail['history']),version)
            self.assertEqual(detail['history'][-1]['text'],body['text'])
            self.assertEqual(detail['history'][-1]['actorId'],self.f['users'][actor]['id'])
        self.assertEqual([(t,self.sql('SELECT row_to_json(t)::text FROM '+t+' t ORDER BY 1')) for t in tables],before)
        self.assertIsNone(self.api('supplier','GET',self.path)['claim']['resolvedAt'])

    def test_scope_supplier_revocation_and_replay_reauthorization(self):
        body=self.body('supplier'); body['action']='reply'
        self.api('supplier','POST',self.path,body)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE id=%s',(self.recipient_id,))
        self.assertEqual(self.api('supplier','GET','/supply-claims/cases')['items'],[])
        self.api('supplier','GET',self.path,expected=404)
        self.api('supplier','POST',self.path,body,expected=403)
        self.api('stranger','GET',self.path,expected=404)
        self.assertEqual(len(self.api('director','GET',self.path)['history']),1)

    def test_stale_version_changed_uuid_payload_and_context_pins_do_not_write(self):
        body=self.body()
        self.api('director','POST',self.path,body)
        for changes in ({'text':'changed'}, {'expectedCompanyId':3}, {'expectedActorId':999}):
            self.assert_denied_unchanged('POST',self.path,{**body,**changes})
        self.assert_denied_unchanged('POST',self.path,self.body())
        self.assert_denied_unchanged('POST',self.path,{**self.body(),'expectedVersion':2,'requestId':'bad'},expected=400)

    def test_roles_and_supplier_cannot_close_or_reply_after_resolution(self):
        self.assert_denied_unchanged('POST',self.path,{**self.body('supplier'),'action':'resolve'},actor='supplier',expected=403)
        self.assert_denied_unchanged('POST',self.path,self.body('worker'),actor='worker',expected=403)
        self.api('director','POST',self.path,{**self.body(),'action':'resolve'})
        self.assert_denied_unchanged('POST',self.path,{**self.body('supplier'),'action':'reply','expectedVersion':2},actor='supplier',expected=403)
        self.assertFalse(self.api('supplier','GET',self.path)['canReply'])
        self.assertTrue(self.api('director','GET',self.path)['canReopen'])

    def test_concurrent_exact_replay_has_one_event(self):
        body=self.body()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.api('director','POST',self.path,body),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claim_events'),[(1,)])
        self.assertEqual(self.sql('SELECT version FROM supply_claims WHERE id=%s',(self.claim_id,)),[(2,)])

    def test_event_failure_rolls_back_decision_and_operation(self):
        from backend.features.supply_claim_cases import routes
        before=self.snapshot()
        with patch.object(routes.runtime,'finish_operation',side_effect=RuntimeError('Synthetic rollback')):
            response=self.request('POST',self.path,self.body(),actor='director')
        self.assertEqual(response.status_code,500)
        self.assertEqual(self.snapshot(),before)

    def test_database_guards_original_facts_and_event_history(self):
        self.api('director','POST',self.path,self.body())
        for sql in ("UPDATE supply_claims SET description='changed',version=version+1",
                    "UPDATE supply_claim_events SET text='changed'",'DELETE FROM supply_claim_events',
                    'DELETE FROM supply_claims'):
            with self.subTest(sql=sql),self.assertRaises(psycopg2.Error):
                self.sql(sql)

    def test_reads_are_no_store_and_selected_company_is_required(self):
        for path in ('/supply-claims','/supply-claims/cases',self.path):
            response=self.request('GET',path,None,actor='director')
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn('no-store',response.headers['cache-control'])
        self.api('director','GET','/supply-claims/cases',expected=409,**{'X-Company-Mode':'all_companies'})

    def test_missing_real_membership_cannot_read_history_or_replay_through_legacy_company(self):
        body = self.body()
        body['text'] = 'Private synthetic claim history'
        self.api('director', 'POST', self.path, body)
        user_id = self.f['users']['director']['id']
        memberships = self.sql('SELECT row_to_json(m)::text FROM user_company_roles m WHERE user_id=%s',
                               (user_id,))
        self.assertTrue(memberships)
        self.addCleanup(self.sql, '''INSERT INTO user_company_roles
            SELECT * FROM json_populate_recordset(NULL::user_company_roles,%s::json)''',
            ('[' + ','.join(row[0] for row in memberships) + ']',))
        # Keep the authenticated user's legacy company/role intact. With no
        # membership rows, the shared resolver can still return legacy context.
        self.sql('DELETE FROM user_company_roles WHERE user_id=%s', (user_id,))
        before = self.snapshot()
        self.assertEqual(self.api('director', 'GET', '/supply-claims'), [])
        for path in ('/supply-claims/cases', self.path):
            self.api('director', 'GET', path, expected=403)
        self.api('director', 'POST', self.path, body, expected=403)
        fresh = self.body()
        fresh['expectedVersion'] = 2
        self.api('director', 'POST', self.path, fresh, expected=403)
        self.assertEqual(self.snapshot(), before)

    def test_supplier_billing_uses_actual_buyer_company(self):
        self.addCleanup(lambda: self.sql("UPDATE companies SET plan='trial',trial_until=NOW()+INTERVAL '30 days',plan_expires_at=NOW()+INTERVAL '30 days' WHERE id=2"))
        self.sql("UPDATE companies SET plan='trial',trial_until=NOW()-INTERVAL '1 day',plan_expires_at=NOW()-INTERVAL '1 day' WHERE id=2")
        response=self.request('POST',self.path,{**self.body('supplier'),'action':'reply'},actor='supplier')
        self.assertIn(response.status_code,(402,403),response.text)
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claim_events'),[(0,)])


if __name__ == "__main__":
    unittest.main()
