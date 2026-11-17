"""Personal transfer drafts and stock conservation on disposable PostgreSQL only."""
import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from . import transfers
from .test_postgres_support import Fixture
from .test_transfers_postgres import migrate_transfers


PATH = '/warehouse-distributions/transfer-draft'
HEADER = 'X-Warehouse-Transfer-Draft-Revision'


def empty():
    return dict(kind=None, allocationId=None, transferId=None, toProjectId=None,
                quantity='', expectedQuantity='', reason='')


@skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class TransferDraftPostgresTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        with self.fixture.get_db() as conn, conn.cursor() as cur:
            migrate_transfers(cur)
            cur.execute(importlib.import_module('migrations.versions.0113_warehouse_transfer_drafts').SCHEMA_SQL)
        conn.close()
        os.environ['WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED'] = '1'
        self.client = TestClient(self.fixture.app)
        self.addCleanup(self.client.close)
        response = self.client.post('/warehouse-distributions', json=dict(
            companyId=2, requestId=str(uuid4()), reason='Seed allocation',
            rows=[dict(lotId=1, projectId=1, quantity='6')]))
        self.assertEqual(response.status_code, 200, response.text)
        self.allocation = response.json()['items'][0]['id']

    def dispatch_doc(self, quantity='2', **changes):
        return {**empty(), 'kind': 'dispatch', 'allocationId': self.allocation,
                'toProjectId': 2, 'quantity': quantity, 'reason': 'Dispatch materials', **changes}

    def receipt_doc(self, transfer, quantity='1', **changes):
        return {**empty(), 'kind': 'receipt', 'transferId': transfer,
                'quantity': quantity, 'expectedQuantity': '2', 'reason': 'Receive materials', **changes}

    def save(self, document, revision=0, headers=None, company=2):
        return self.client.put(PATH, json=dict(companyId=company, expectedRevision=revision,
            requestId=str(uuid4()), document=document), headers=headers or {})

    def current(self, headers=None):
        result = self.client.get(PATH, headers=headers or {})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def body(self, document):
        body = dict(companyId=2, requestId=str(uuid4()), quantity=document['quantity'], reason=document['reason'])
        if document['kind'] == 'dispatch':
            body.update(allocationId=document['allocationId'], toProjectId=document['toProjectId'])
        else:
            body['expectedQuantity'] = document['expectedQuantity']
        return body

    def perform(self, document, revision=1, body=None, headers=None):
        path = '/warehouse-distributions/transfers'
        if document['kind'] == 'receipt':
            path += f"/{document['transferId']}/receipts"
        return self.client.post(path, json=body or self.body(document),
            headers={**({HEADER: str(revision)} if revision is not None else {}), **(headers or {})})

    def transfer(self):
        response = self.perform(self.dispatch_doc('4'), revision=None)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['item']['id']

    def facts(self):
        tables = ('warehouse_main', 'materials', 'warehouse_receipt_lots', 'warehouse_movements',
                  'warehouse_history', 'warehouse_lot_movements', 'warehouse_invoices',
                  'warehouse_distribution_operations', 'warehouse_distribution_allocations',
                  'warehouse_distribution_transfers', 'warehouse_distribution_transfer_receipts')
        return {table: self.fixture.query('SELECT * FROM '+table+' ORDER BY id') for table in tables}

    def test_personal_transfer_draft_is_available_after_reopening(self):
        self.assertEqual(self.current()['document'], empty())
        self.assertEqual(self.current()['revision'], 0)
        self.assertIsNone(self.current()['source'])

    def test_incomplete_dispatch_survives_another_device_without_stock_changes(self):
        before = self.facts()
        document = self.dispatch_doc('2.', toProjectId=None, reason='unfinished reason ')
        saved = self.save(document)
        self.assertEqual(saved.status_code, 200, saved.text)
        with TestClient(self.fixture.app) as other_device:
            result = other_device.get(PATH).json()
        self.assertEqual(result['document'], document)
        self.assertEqual(result['source']['id'], self.allocation)
        self.assertEqual(result['companyId'], 2)
        self.assertEqual(result['userId'], 1)
        self.assertEqual(self.facts(), before)

    def test_incomplete_receipt_survives_another_device_without_stock_changes(self):
        transfer = self.transfer()
        before = self.facts()
        document = self.receipt_doc(transfer, '0.', expectedQuantity='')
        saved = self.save(document)
        self.assertEqual(saved.status_code, 200, saved.text)
        with TestClient(self.fixture.app) as other_device:
            result = other_device.get(PATH).json()
        self.assertEqual(result['document'], document)
        self.assertEqual(result['source']['id'], transfer)
        self.assertEqual(result['source']['sourceAllocationId'], self.allocation)
        self.assertEqual(self.facts(), before)

    def test_competing_saves_do_not_overwrite_winning_revision(self):
        barrier = Barrier(2)
        def write(quantity):
            barrier.wait()
            return self.save(self.dispatch_doc(quantity))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(write, ['1', '3']))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        winner = next(r.json()['document'] for r in responses if r.status_code == 200)
        self.assertEqual(self.current()['document'], winner)
        self.assertEqual(self.current()['revision'], 1)

    def test_save_replay_recovers_lost_response_but_rejects_later_overwrite(self):
        first = dict(companyId=2, expectedRevision=0, requestId=str(uuid4()), document=self.dispatch_doc())
        response = self.client.put(PATH, json=first)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.put(PATH, json=first).json(), response.json())
        self.assertEqual(self.save(self.dispatch_doc('3'), revision=1).status_code, 200)
        self.assertEqual(self.client.put(PATH, json=first).status_code, 409)
        self.assertEqual(self.current()['document'], self.dispatch_doc('3'))
        changed_replay = {**first, 'document': self.dispatch_doc('1')}
        self.assertEqual(self.client.put(PATH, json=changed_replay).status_code, 409)

    def test_concurrent_edit_and_dispatch_cannot_both_commit_the_same_revision(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        before = self.facts()
        barrier = Barrier(2)
        def edit():
            barrier.wait()
            return self.save(self.dispatch_doc('3'), revision=1)
        def dispatch():
            barrier.wait()
            return self.perform(document)
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit_future, dispatch_future = pool.submit(edit), pool.submit(dispatch)
            edited, dispatched = edit_future.result(), dispatch_future.result()
        self.assertEqual(sorted([edited.status_code, dispatched.status_code]), [200, 409])
        current = self.current()
        self.assertEqual(current['revision'], 2)
        if edited.status_code == 200:
            self.assertEqual(current['document'], self.dispatch_doc('3'))
            self.assertEqual(self.facts(), before)
        else:
            self.assertEqual(current['document'], empty())
            self.assertEqual(len(self.fixture.query('SELECT id FROM warehouse_distribution_transfers')), 1)

    def test_dispatch_consumes_snapshot_atomically_and_replay_preserves_next_draft(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        body = self.body(document)
        result = self.perform(document, body=body)
        self.assertEqual(result.status_code, 200, result.text)
        current = self.current()
        self.assertEqual(current['document'], empty())
        self.assertEqual(current['revision'], 2)
        self.assertEqual(current['lastOperation']['requestId'], body['requestId'])
        self.assertTrue(current['lastOperation']['operationId'] > 0)
        self.assertEqual(self.save(self.dispatch_doc('1'), revision=2).status_code, 200)
        before = self.facts()
        self.assertEqual(self.perform(document, body=body).json(), result.json())
        self.assertEqual(self.facts(), before)
        self.assertEqual(self.current()['document'], self.dispatch_doc('1'))
        self.assertEqual(self.current()['revision'], 3)

    def test_receipt_consumes_snapshot_atomically_and_replay_preserves_next_draft(self):
        transfer = self.transfer()
        document = self.receipt_doc(transfer)
        self.assertEqual(self.save(document).status_code, 200)
        body = self.body(document)
        result = self.perform(document, body=body)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['item']['receivedQuantity'], '1')
        self.assertEqual(result.json()['item']['inTransitQuantity'], '3')
        self.assertEqual(result.json()['item']['status'], 'discrepancy')
        self.assertEqual(self.current()['document'], empty())
        self.assertEqual(self.current()['revision'], 2)
        self.assertEqual(self.current()['lastOperation']['requestId'], body['requestId'])
        child = self.fixture.query('SELECT * FROM warehouse_distribution_allocations WHERE project_id=2')[0]
        self.assertEqual((child['lot_id'], child['receipt_id'], child['quantity']), (1, 1, 1))
        self.assertEqual(self.save(self.receipt_doc(transfer, '2'), revision=2).status_code, 200)
        before = self.facts()
        self.assertEqual(self.perform(document, body=body).json(), result.json())
        self.assertEqual(self.facts(), before)
        self.assertEqual(self.current()['document'], self.receipt_doc(transfer, '2'))

    def test_two_dispatch_commands_with_same_draft_consume_once(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        barrier = Barrier(2)
        def perform(_):
            barrier.wait()
            return self.perform(document)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(perform, range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        self.assertEqual(len(self.fixture.query('SELECT id FROM warehouse_distribution_transfers')), 1)
        self.assertEqual(self.fixture.query("SELECT quantity FROM materials WHERE project='Alpha'")[0]['quantity'], 4)
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]['available_quantity'], 4)
        self.assertEqual(self.current()['revision'], 2)

    def test_two_receipt_commands_with_same_draft_consume_once(self):
        transfer = self.transfer()
        document = self.receipt_doc(transfer)
        self.assertEqual(self.save(document).status_code, 200)
        barrier = Barrier(2)
        def perform(_):
            barrier.wait()
            return self.perform(document)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(perform, range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        self.assertEqual(len(self.fixture.query('SELECT id FROM warehouse_distribution_transfer_receipts')), 1)
        self.assertEqual(self.fixture.query("SELECT quantity FROM materials WHERE project='Beta'")[0]['quantity'], 1)
        self.assertEqual(self.current()['revision'], 2)

    def test_saved_snapshot_must_match_command_payload_identity_and_revision(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        before = self.facts()
        for changed in (self.dispatch_doc('1'), self.dispatch_doc(allocationId=self.allocation+500),
                        self.dispatch_doc(toProjectId=1), self.dispatch_doc(reason='Changed')):
            with self.subTest(document=changed):
                self.assertEqual(self.perform(changed).status_code, 409)
        self.assertEqual(self.perform(document, revision=2).status_code, 409)
        self.assertEqual(self.facts(), before)
        self.assertEqual(self.current()['document'], document)

    def test_receipt_snapshot_cannot_be_used_for_other_transfer_or_dispatch(self):
        transfer = self.transfer()
        document = self.receipt_doc(transfer)
        self.assertEqual(self.save(document).status_code, 200)
        before = self.facts()
        self.assertEqual(self.perform(self.receipt_doc(transfer+500)).status_code, 409)
        self.assertEqual(self.perform(self.receipt_doc(transfer, expectedQuantity='1')).status_code, 409)
        self.assertEqual(self.perform(self.dispatch_doc()).status_code, 409)
        self.assertEqual(self.facts(), before)
        self.assertEqual(self.current()['document'], document)

    def test_failed_dispatch_rolls_back_stock_history_and_preserves_draft(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        before = self.facts()
        original = transfers.movement_leg
        def fail_after_movement(*args, **kwargs):
            original(*args, **kwargs)
            raise HTTPException(409, 'Synthetic failure after stock and movement writes')
        with patch.object(transfers, 'movement_leg', fail_after_movement):
            result = self.perform(document)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self.facts(), before)
        self.assertEqual(self.current()['document'], document)
        self.assertEqual(self.current()['revision'], 1)

    def test_failed_receipt_rolls_back_stock_history_and_preserves_draft(self):
        transfer = self.transfer()
        document = self.receipt_doc(transfer)
        self.assertEqual(self.save(document).status_code, 200)
        before = self.facts()
        original = transfers.movement_leg
        def fail_after_movement(*args, **kwargs):
            original(*args, **kwargs)
            raise HTTPException(409, 'Synthetic failure after stock and movement writes')
        with patch.object(transfers, 'movement_leg', fail_after_movement):
            result = self.perform(document)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self.facts(), before)
        self.assertEqual(self.current()['document'], document)

    def test_zero_receipt_records_discrepancy_once_without_receiving_stock(self):
        transfer = self.transfer()
        document = self.receipt_doc(transfer, '0')
        self.assertEqual(self.save(document).status_code, 200)
        before = self.fixture.query('SELECT * FROM materials ORDER BY id')
        result = self.perform(document)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['item']['inTransitQuantity'], '4')
        self.assertEqual(result.json()['item']['status'], 'discrepancy')
        self.assertEqual(self.fixture.query('SELECT * FROM materials ORDER BY id'), before)
        self.assertEqual(self.current()['document'], empty())

    def test_personal_and_company_scopes_do_not_share_drafts_or_sources(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        self.fixture.query("INSERT INTO user_company_roles(user_id,company_id,role) VALUES(1,3,'директор') RETURNING id")
        for headers in ({'X-Test-Role': 'deputy'}, {'X-Company-Id': '3', 'X-Company-Mode': 'company'}):
            result = self.current(headers)
            self.assertEqual(result['document'], empty())
            self.assertEqual(result['revision'], 0)
            self.assertIsNone(result['source'])
        self.assertEqual(self.perform(document, headers={'X-Test-Role': 'deputy'}).status_code, 409)
        headers = {'X-Company-Id': '3', 'X-Company-Mode': 'company'}
        self.assertEqual(self.save(document, company=3, headers=headers).status_code, 404)
        self.assertEqual(self.save(self.dispatch_doc(toProjectId=3), revision=1).status_code, 404)
        self.assertEqual(self.current()['document'], document)

    def test_receipt_cannot_reference_another_company_transfer(self):
        transfer = self.transfer()
        self.fixture.query("INSERT INTO user_company_roles(user_id,company_id,role) VALUES(1,3,'директор') RETURNING id")
        result = self.save(self.receipt_doc(transfer), company=3,
            headers={'X-Company-Id': '3', 'X-Company-Mode': 'company'})
        self.assertEqual(result.status_code, 404, result.text)

    def test_readers_and_unassigned_roles_cannot_read_or_write_personal_draft(self):
        before = self.facts()
        for role in ('accountant', 'foreman', 'supplier'):
            with self.subTest(role=role):
                headers = {'X-Test-Role': role}
                self.assertEqual(self.client.get(PATH, headers=headers).status_code, 403)
                self.assertEqual(self.save(self.dispatch_doc(), headers=headers).status_code, 403)
        self.assertEqual(self.facts(), before)

    def test_revocation_denies_read_save_and_completed_command_replay(self):
        document = self.dispatch_doc()
        self.assertEqual(self.save(document).status_code, 200)
        body = self.body(document)
        self.assertEqual(self.perform(document, body=body).status_code, 200)
        self.fixture.query('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=1 RETURNING id')
        self.assertEqual(self.client.get(PATH).status_code, 403)
        self.assertEqual(self.save(document, revision=2).status_code, 403)
        self.assertEqual(self.perform(document, body=body).status_code, 403)

    def test_missing_migration_is_explicit_and_legacy_command_still_works(self):
        self.fixture.query('DROP TABLE warehouse_transfer_drafts')
        self.assertEqual(self.client.get(PATH).status_code, 503)
        self.assertEqual(self.save(self.dispatch_doc()).status_code, 503)
        self.assertEqual(self.perform(self.dispatch_doc()).status_code, 503)
        result = self.perform(self.dispatch_doc(), revision=None)
        self.assertEqual(result.status_code, 200, result.text)

    def test_disabled_transfer_feature_blocks_new_draft_endpoints(self):
        os.environ['WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED'] = '0'
        self.assertEqual(self.client.get(PATH).status_code, 404)
        self.assertEqual(self.save(self.dispatch_doc()).status_code, 404)

    def test_invalid_documents_and_missing_revision_never_change_draft(self):
        invalid = [self.dispatch_doc(confirmed=True), self.dispatch_doc('\x00'),
                   self.dispatch_doc(expectedQuantity='2'), self.dispatch_doc(transferId=5),
                   self.dispatch_doc(allocationId=True), self.dispatch_doc(kind='invented'),
                   {**empty(), 'quantity': '1'}, self.receipt_doc(None),
                   self.receipt_doc(1, allocationId=self.allocation)]
        for document in invalid:
            with self.subTest(document=document):
                self.assertEqual(self.save(document).status_code, 422)
        self.assertEqual(self.save(self.dispatch_doc(), revision=True).status_code, 422)
        response = self.client.put(PATH, json=dict(companyId=2, requestId=str(uuid4()), document=self.dispatch_doc()))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.current()['revision'], 0)

    def test_explicit_clear_changes_only_the_personal_draft(self):
        self.assertEqual(self.save(self.dispatch_doc()).status_code, 200)
        before = self.facts()
        response = self.save(empty(), revision=1)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.current()['document'], empty())
        self.assertEqual(self.current()['revision'], 2)
        self.assertEqual(self.facts(), before)
