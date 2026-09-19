"""Read-only notification evidence across real tenant boundaries."""
import os
import unittest
from backend.features.supplier_access import test_postgres_chain as chain
from backend.features.supplier_offers import test_response_postgres as response


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class DeliveryEvidencePostgresTests(unittest.TestCase):
    setUpClass = classmethod(chain.PostgresSupplyChainTests.setUpClass.__func__)
    api = chain.PostgresSupplyChainTests.api
    sql = chain.PostgresSupplyChainTests.sql
    quote = response.SupplierResponsePostgresTests.quote

    def test_scoped_evidence_is_read_only_and_mismatched_queue_is_unconfirmed(self):
        from backend.features.messenger.schema import ensure_messenger_schema
        ensure_messenger_schema(self.main.get_db)
        offer, _, _ = self.quote()
        request_id = offer['requestId']
        user_id = self.fixture['users']['supplier']['id']
        queue_id = self.sql("""INSERT INTO messenger_outbox
            (owner_scope,company_id,provider,user_id,event_type,entity_type,entity_id,status,attempts,failed_at)
            VALUES ('company',2,'max',%s,'supplier_kp_requested','supply_request',%s,'failed',2,NOW()) RETURNING id""",
            (user_id, request_id))[0][0]
        self.sql("UPDATE supply_request_recipients SET max_outbox_id=%s,max_notification_status='В очереди MAX' WHERE request_id=%s", (queue_id, request_id))
        path = f'/supply-requests/{request_id}/recipients'
        def snapshot():
            return [self.sql('SELECT row_to_json(t)::text FROM ' + table + ' t ORDER BY id')
                    for table in ('supplier_offers', 'supply_request_recipients', 'messenger_outbox')]
        before = snapshot()
        rows = self.api('director', 'GET', path)
        self.assertEqual(rows[0]['actualMaxQueueStatus'], 'failed')
        self.assertEqual(rows[0]['maxQueueEvidence'], 'matched')
        self.assertEqual(rows[0]['maxFailedAttempts'], 2)
        self.assertIsNotNone(rows[0]['maxFailedAt'])
        self.assertIsNone(rows[0]['maxSentAt'])
        self.assertEqual(snapshot(), before)
        self.api('stranger', 'GET', path, expected=403)
        self.api('stranger_supplier', 'GET', path, expected=403)
        for update in ("company_id=3", "company_id=2,owner_scope=NULL", "owner_scope='company',user_id=NULL"):
            self.sql('UPDATE messenger_outbox SET ' + update + ' WHERE id=%s', (queue_id,))
            row = self.api('director', 'GET', path)[0]
            self.assertEqual(row['maxQueueEvidence'], 'unconfirmed')
            self.assertEqual(row['actualMaxQueueStatus'], 'unknown')
            self.assertIsNone(row['maxFailedAttempts'])
        self.sql('DELETE FROM messenger_outbox WHERE id=%s', (queue_id,))
        before = snapshot()
        self.assertEqual(self.api('director', 'GET', path)[0]['maxQueueEvidence'], 'unconfirmed')
        self.assertEqual(snapshot(), before)
