import os, threading, unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from backend.features.supplier_access import test_delivery_evidence_postgres as support
from backend.features.supplier_offers import test_response_postgres as response
from fastapi import HTTPException
from .supplier_dispatch import dispatch_supplier_message
from .schema import ensure_messenger_schema

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Requires isolated PostgreSQL')
class SupplierDispatchPostgresTests(unittest.TestCase):
    setUpClass=classmethod(response.SupplierResponsePostgresTests.setUpClass.__func__)
    api=support.DeliveryEvidencePostgresTests.api
    sql=support.DeliveryEvidencePostgresTests.sql
    quote=support.DeliveryEvidencePostgresTests.quote

    def queued(self):
        ensure_messenger_schema(self.main.get_db)
        offer,_,_=self.quote();rid=offer['requestId']
        mid=self.sql("""INSERT INTO messenger_outbox
          (owner_scope,company_id,provider,user_id,event_type,entity_type,entity_id,status)
          VALUES ('company',2,'max',%s,'supplier_kp_requested','supply_request',%s,'queued') RETURNING id""",
          (self.fixture['users']['supplier']['id'],rid))[0][0]
        account=self.sql('''INSERT INTO messenger_accounts(provider,user_id,external_user_id)
            VALUES ('max',%s,'synthetic') RETURNING id''',(self.fixture['users']['supplier']['id'],))[0][0]
        self.sql("UPDATE messenger_outbox SET messenger_account_id=%s,external_user_id='synthetic' WHERE id=%s",(account,mid))
        self.sql('UPDATE supply_request_recipients SET max_outbox_id=%s WHERE request_id=%s',(mid,rid))
        return mid,rid

    def test_concurrent_senders_commit_before_provider_and_send_once(self):
        mid,_=self.queued();entered=threading.Event();release=threading.Event()
        def send(row):
            self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(mid,)),[('sending',)])
            entered.set();self.assertTrue(release.wait(10));return {},'synthetic',{}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(dispatch_supplier_message,self.main.get_db,mid,send)
            self.assertTrue(entered.wait(10))
            try:self.assertIsNone(pool.submit(dispatch_supplier_message,self.main.get_db,mid,send).result(10))
            finally:release.set()
            self.assertEqual(first.result(10)['status'],'sent')
        self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(mid,)),[('sent',)])

    def test_uncertain_result_never_resends(self):
        mid,_=self.queued();send=Mock(side_effect=TimeoutError())
        self.assertEqual(dispatch_supplier_message(self.main.get_db,mid,send)['status'],'unconfirmed')
        self.assertIsNone(dispatch_supplier_message(self.main.get_db,mid,send))
        self.assertEqual(send.call_count,1)

    def test_foreign_company_and_revoked_recipient_never_send(self):
        for update in ("company_id=3", "status='sent'"):
            mid,_=self.queued();self.sql('UPDATE messenger_outbox SET '+update+' WHERE id=%s',(mid,))
            send=Mock();self.assertIsNone(dispatch_supplier_message(self.main.get_db,mid,send));send.assert_not_called()
        mid,rid=self.queued();self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s',(rid,))
        send=Mock();self.assertIsNone(dispatch_supplier_message(self.main.get_db,mid,send));send.assert_not_called()

    def test_legacy_worker_cannot_list_or_requeue_supplier_notifications(self):
        mid,_=self.queued()
        endpoints={r.path:r.endpoint for r in self.main.app.routes if hasattr(r,'endpoint')}
        listed=endpoints['/max/outbox'](limit=100,status='all',_bot={})
        self.assertNotIn(mid,[r['id'] for r in listed['items']])
        for state in ('queued','sent','failed','skipped'):
            with self.assertRaises(HTTPException) as exc:
                endpoints['/max/outbox/{message_id}/status'](mid,{'status':state},_bot={})
            self.assertEqual(exc.exception.status_code,404)
        self.assertEqual(self.sql('SELECT status FROM messenger_outbox WHERE id=%s',(mid,)),[('queued',)])

    def test_missing_ack_is_unconfirmed(self):
        mid,_=self.queued();send=Mock(return_value=({},'',{}))
        self.assertEqual(dispatch_supplier_message(self.main.get_db,mid,send)['status'],'unconfirmed')
        self.assertIsNone(dispatch_supplier_message(self.main.get_db,mid,send))
        self.assertEqual(send.call_count,1)

    def test_invalid_candidates_do_not_fill_dispatch_batch(self):
        from .supplier_dispatch import SUPPLIER_MESSAGE_ELIGIBLE_SQL
        mid,_=self.queued()
        self.sql("UPDATE messenger_outbox SET status='sent' WHERE id=%s",(mid,))
        self.sql("""INSERT INTO messenger_outbox(owner_scope,company_id,provider,user_id,event_type,entity_type,entity_id,status)
            SELECT 'company',2,'max',NULL,'supplier_kp_requested','supply_request',NULL,'queued'
            FROM generate_series(1,25)""")
        valid,_=self.queued()
        rows=self.sql("SELECT id FROM messenger_outbox o WHERE status='queued' AND (COALESCE(event_type,'')<>'supplier_kp_requested' OR "+SUPPLIER_MESSAGE_ELIGIBLE_SQL+") ORDER BY id LIMIT 1")
        self.assertEqual(rows,[(valid,)])
        self.sql("UPDATE messenger_outbox SET status='sent' WHERE id=%s",(valid,))

    def test_revoke_while_claim_waits_prevents_network(self):
        import time
        mid,rid=self.queued();held=self.main.get_db();held.autocommit=False
        cur=held.cursor();cur.execute('SELECT id FROM supply_request_recipients WHERE request_id=%s FOR UPDATE',(rid,))
        user=self.fixture['users']['supplier']['id'];send=Mock()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                task=pool.submit(dispatch_supplier_message,self.main.get_db,mid,send)
                try:
                    deadline=time.monotonic()+10
                    while time.monotonic()<deadline:
                        waiting=self.sql("SELECT query FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock'")
                        if any('SELECT supplier_user_id' in q for (q,) in waiting):break
                        time.sleep(.025)
                    else:self.fail('claim did not wait for recipient')
                    self.sql('UPDATE users SET active=FALSE WHERE id=%s',(user,))
                finally:held.commit()
                self.assertIsNone(task.result(10))
            send.assert_not_called()
        finally:
            held.rollback();cur.close();held.close()
            self.sql('UPDATE users SET active=TRUE WHERE id=%s',(user,))
