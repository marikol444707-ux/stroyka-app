"""Main-coordinated fresh Unix-socket DB only; real OwnerStock runtime/auth/helpers."""
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from . import test_owner_stock_postgres as support
from ..material_traceability import test_stock_chain_postgres as stock_support
from ..warehouse_distribution.test_postgres_support import migration



class DistributionQualityPostgresTests(support.OwnerStockPostgresTests):
    prepare_lot = stock_support.StockChainPostgresTests.prepare_lot
    distribution = stock_support.StockChainPostgresTests.distribution
    chain_snapshot = stock_support.StockChainPostgresTests.chain_snapshot

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, 'upgrade')
        finally:
            conn.close()
        flag = patch.dict(os.environ, {'WAREHOUSE_DISTRIBUTION_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def setUp(self):
        super().setUp()
        # Do not change flag policy of inherited stock regression scenarios.
        if self._testMethodName.startswith('test_distribution_quality_'):
            flag = patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '1'})
            flag.start()
            self.addCleanup(flag.stop)

    def quality_issue(self, quantity='2'):
        lot = self.prepare_lot()
        payload = self.distribution(lot)
        payload['rows'][0]['quantity'] = quantity
        return payload, self.api('director', 'POST', '/warehouse-distributions', payload)

    def quality_return(self, allocation, quantity='1', expected=200, payload=None):
        body = payload or dict(companyId=2, requestId=str(uuid4()), quantity=quantity, reason='Physical return')
        return body, self.api('director', 'POST', f"/warehouse-distributions/{allocation['id']}/returns", body, expected=expected)

    def test_distribution_quality_exact_history_owner_and_no_upstream_stamp(self):
        command, result = self.quality_issue()
        allocation = result['items'][0]
        proof = result['ownedQuality'][0]
        self.assertEqual(self.sql('SELECT project_id FROM warehouse_invoices WHERE id=%s',
                                 (allocation['warehouseInvoiceId'],)), [(None,)])
        self.assertEqual(self.sql('''SELECT company_id,project_id,warehouse_history_id,source_type,source_id,
            source_item_key,invoice_id,delivery_id,quantity FROM material_inspection_journal WHERE id=%s''',
            (proof['inspectionId'],)), [(2,self.f['projectId'],proof['historyId'],'warehouse_history',
                proof['historyId'],'allocation:'+str(allocation['id']),None,None,2)])
        before = self.chain_snapshot()
        self.assertEqual(self.api('director', 'POST', '/warehouse-distributions', command), result)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_return_preserves_inspection_and_stamps_outbound_only(self):
        _, result = self.quality_issue()
        allocation = result['items'][0]
        original = self.sql('SELECT * FROM material_inspection_journal WHERE id=%s', (result['ownedQuality'][0]['inspectionId'],))
        command, returned = self.quality_return(allocation)
        proof = returned['ownedQuality'][0]
        self.assertEqual(self.sql('SELECT project_id,type FROM warehouse_history WHERE id=%s',
            (proof['returnHistoryId'],)), [(self.f['projectId'],'перемещение: списание')])
        self.assertEqual(self.sql('SELECT * FROM material_inspection_journal WHERE id=%s',
                                 (proof['inspectionId'],)), original)
        self.assertEqual(self.quality_return(allocation, payload=command)[1], returned)
        with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '0'}):
            self.quality_return(allocation)
        self.assertEqual(self.sql('SELECT * FROM material_inspection_journal WHERE id=%s',
                                 (proof['inspectionId'],)), original)

    def test_distribution_quality_missing_record_is_not_recreated_on_replay_or_return(self):
        command, result = self.quality_issue()
        self.sql('DELETE FROM material_inspection_journal WHERE id=%s', (result['ownedQuality'][0]['inspectionId'],))
        before = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        self.quality_return(result['items'][0], expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_does_not_adopt_historical_allocation(self):
        with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '0'}):
            command, result = self.quality_issue()
        before = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        self.quality_return(result['items'][0], expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_excess_precision_rolls_back_whole_issue(self):
        lot = self.prepare_lot()
        command = self.distribution(lot)
        command['rows'][0]['quantity'] = '0.00001'
        before = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_conflicting_journal_quantity_blocks_return(self):
        _, result = self.quality_issue()
        self.sql('UPDATE material_inspection_journal SET quantity=1 WHERE id=%s',
                 (result['ownedQuality'][0]['inspectionId'],))
        before = self.chain_snapshot()
        self.quality_return(result['items'][0], expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_cable_has_two_exact_records_and_no_rounding(self):
        payload = self.receipt_payload()
        payload['items'][0].update(name='ВВГнг 3х2,5', materialName='ВВГнг 3х2,5', unit='м')
        receipt = self.api('director', 'POST', '/warehouse-invoices', payload)
        lot = self.sql('SELECT id FROM warehouse_receipt_lots WHERE warehouse_invoice_id=%s AND company_id=2',
                       (receipt['id'],))[0][0]
        command = self.distribution(lot)
        command['rows'][0]['quantity'] = '1.234'
        before = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        self.assertEqual(self.chain_snapshot(), before)
        command['rows'][0]['quantity'] = '1.23'
        result = self.api('director', 'POST', '/warehouse-distributions', command)
        proof = result['ownedQuality'][0]
        self.assertIsNotNone(proof['cableId'])
        records = [self.sql('SELECT * FROM '+table+' WHERE id=%s', (proof[key],))
                   for table, key in [('material_inspection_journal','inspectionId'), ('cable_journal','cableId')]]
        self.quality_return(result['items'][0], quantity='0.23')
        self.assertEqual([self.sql('SELECT * FROM '+table+' WHERE id=%s', (proof[key],))
                   for table, key in [('material_inspection_journal','inspectionId'), ('cable_journal','cableId')]], records)

    def test_distribution_quality_wrong_history_identity_rejected_on_replay(self):
        command, result = self.quality_issue()
        self.sql("UPDATE warehouse_history SET material='Wrong history material' WHERE id=%s",
                 (result['ownedQuality'][0]['historyId'],))
        before = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        self.quality_return(result['items'][0], expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_concurrent_replay_creates_one_record(self):
        command = self.distribution(self.prepare_lot())
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request, 'POST', '/warehouse-distributions', command) for _ in range(2)]
            responses = [f.result(timeout=20) for f in futures]
        self.assertEqual([r.status_code for r in responses], [200,200], [r.text for r in responses])
        self.assertEqual(responses[0].json(), responses[1].json())
        proof = responses[0].json()['ownedQuality'][0]
        self.assertEqual(self.sql('SELECT count(*) FROM material_inspection_journal WHERE warehouse_history_id=%s',
                                 (proof['historyId'],)), [(1,)])

    def test_distribution_quality_readback_failure_rolls_back_stock_and_quality(self):
        command = self.distribution(self.prepare_lot())
        command['rows'][0]['quantity'] = '1.2345'
        before = self.chain_snapshot()
        self.sql('''CREATE FUNCTION distribution_quality_test_round() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN NEW.quantity=1; RETURN NEW; END $$''')
        self.sql('''CREATE TRIGGER distribution_quality_test_round BEFORE INSERT ON material_inspection_journal
            FOR EACH ROW EXECUTE FUNCTION distribution_quality_test_round()''')
        try:
            self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        finally:
            self.sql('DROP TRIGGER distribution_quality_test_round ON material_inspection_journal')
            self.sql('DROP FUNCTION distribution_quality_test_round()')
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_source_lot_project_conflict_blocks_replay(self):
        command, result = self.quality_issue()
        self.sql('UPDATE warehouse_receipt_lots SET project_id=%s WHERE id=%s',
                 (self.f['projectId'], result['items'][0]['lotId']))
        before = self.chain_snapshot()
        self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def corrupt_saved_quality(self, request_id, proofs):
        """Privileged corruption injection in this isolated test DB only.

        Normal SQL cannot alter finalized results: restore the immutable trigger
        in the same transaction, including rollback on any injection failure.
        """
        from psycopg2.extras import Json
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor() as cur:
                cur.execute('ALTER TABLE warehouse_distribution_operations DISABLE TRIGGER warehouse_distribution_operations_immutable')
                cur.execute('''UPDATE warehouse_distribution_operations
                    SET result=jsonb_set(result,'{ownedQuality}',%s::jsonb)
                    WHERE company_id=2 AND request_id=%s''', (Json(proofs), request_id))
                self.assertEqual(cur.rowcount, 1)
                cur.execute('ALTER TABLE warehouse_distribution_operations ENABLE TRIGGER warehouse_distribution_operations_immutable')
        finally:
            conn.close()

    def test_distribution_quality_flag_off_corrupt_issue_proof_denies_replay_and_return(self):
        command, result = self.quality_issue()
        proof = {**result['ownedQuality'][0], 'inspectionId': -1}
        self.corrupt_saved_quality(command['requestId'], [proof])
        before = self.chain_snapshot()
        with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '0'}):
            self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
            self.quality_return(result['items'][0], expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_flag_off_corrupt_return_proof_denies_replay(self):
        _, result = self.quality_issue()
        allocation = result['items'][0]
        command, returned = self.quality_return(allocation)
        proof = {**returned['ownedQuality'][0], 'returnHistoryId': -1}
        self.corrupt_saved_quality(command['requestId'], [proof])
        before = self.chain_snapshot()
        with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '0'}):
            self.quality_return(allocation, payload=command, expected=409)
        self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_flag_off_empty_proof_denies_replay_and_return(self):
        command, result = self.quality_issue()
        for invalid_proof in ([], None):
            self.corrupt_saved_quality(command['requestId'], invalid_proof)
            before = self.chain_snapshot()
            with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '0'}):
                self.api('director', 'POST', '/warehouse-distributions', command, expected=409)
                self.quality_return(result['items'][0], expected=409)
            self.assertEqual(self.chain_snapshot(), before)

    def test_distribution_quality_replay_vs_cancellation_real_lock_queue(self):
        command, result = self.quality_issue()
        receipt_id = result['items'][0]['warehouseInvoiceId']
        before = self.chain_snapshot()
        # Queue both real HTTP transactions behind a third connection. Observing
        # pg_stat_activity proves overlapping SQL, not just concurrent futures.
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('LOCK TABLE materials IN SHARE ROW EXCLUSIVE MODE')
            with ThreadPoolExecutor(max_workers=2) as pool:
                try:
                    replay = pool.submit(self.request, 'POST', '/warehouse-distributions', command)
                    self.wait_blocked('LOCK TABLE materials')
                    cancel = pool.submit(self.request, 'DELETE', f'/warehouse-invoices/{receipt_id}', None)
                    self.wait_blocked('LOCK TABLE materials', count=2)
                finally:
                    blocker.rollback()
                replay_response, cancel_response = replay.result(timeout=20), cancel.result(timeout=20)
        finally:
            blocker.close()
        self.assertEqual(replay_response.status_code, 200, replay_response.text)
        self.assertEqual(replay_response.json(), result)
        self.assertEqual(cancel_response.status_code, 409, cancel_response.text)
        self.assertEqual(self.chain_snapshot(), before)
