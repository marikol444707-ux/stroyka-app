"""Authenticated work consumption/return conservation on guarded socket-only PG.

No balance, stock, authorization or contract mocks. A temporary trigger pauses
the real work write after its balance check to force the dangerous interleaving.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest

from backend.features.material_traceability import test_transfer_workflow_postgres as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Requires fresh explicitly provisioned PostgreSQL database')
class WorkConsumptionPostgresTests(unittest.TestCase):
    sql = support.TransferWorkflowPostgresTests.sql
    api = support.TransferWorkflowPostgresTests.api
    payload = support.TransferWorkflowPostgresTests.payload
    balance = support.TransferWorkflowPostgresTests.balance

    @classmethod
    def setUpClass(cls):
        support.TransferWorkflowPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        support.TransferWorkflowPostgresTests.setUp(self)
        self.sql('DELETE FROM room_works')
        sections = json.loads(self.sql('SELECT sections_json FROM estimates WHERE id=%s',
                                      (self.f['estimateId'],))[0][0])
        sections[0]['items'][0]['quantity'] = 20
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s',
                 (json.dumps(sections), self.f['estimateId']))
        worker = self.f['users']['worker']
        contract = self.sql('''INSERT INTO brigade_contracts(company_id,project_id,project_name,
            brigade_name,contractor_id,status) VALUES(2,%s,%s,%s,%s,'Подписан') RETURNING id''',
            (self.f['projectId'], self.f['project'], worker['name'], worker['id']))[0][0]
        self.contract_item = self.sql('''INSERT INTO brigade_contract_items(contract_id,
            description,unit,quantity,price_brigade,work_package)
            VALUES(%s,'Synthetic work','шт',100,10,%s) RETURNING id''',
            (contract, self.f['workPackage']))[0][0]
        tid = self.api('foreman', 'POST', '/material-transfers', self.payload(2))['id']
        self.api('worker', 'PUT', f'/material-transfers/{tid}/sign')

    def work_payload(self, quantity=2):
        worker = self.f['users']['worker']
        return dict(masterId=worker['id'], masterName=worker['name'],
            project=self.f['project'], description='Synthetic work', unit='шт', quantity=1,
            date='2026-09-18', workPackage=self.f['workPackage'], contractItemId=self.contract_item,
            materialsUsed=[dict(name=self.f['materialName'], unit=self.f['unit'], quantity=quantity)]
                          if quantity else [])

    def request(self, method, path, payload, actor='worker'):
        from fastapi.testclient import TestClient
        token = self.main.create_auth_token(self.f['users'][actor], two_factor_passed=True)
        with TestClient(self.main.app, raise_server_exceptions=False) as client:
            return client.request(method, path, json=payload,
                                  headers={'Authorization': 'Bearer '+token})

    def race_work_with_return(self, method, path, payload):
        self.sql('''CREATE FUNCTION work_consumption_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.type='расход (работа мастера)' THEN
              PERFORM pg_advisory_xact_lock(914227,1); END IF; RETURN NEW; END $$''')
        self.sql('''CREATE TRIGGER work_consumption_pause BEFORE INSERT ON warehouse_history
            FOR EACH ROW EXECUTE FUNCTION work_consumption_pause()''')
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(914227,1)')
            with ThreadPoolExecutor(max_workers=2) as pool:
                work = pool.submit(self.request, method, path, payload)
                try:
                    deadline = time.monotonic()+3
                    while time.monotonic() < deadline:
                        waiting = self.sql("""SELECT count(*) FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event='advisory'
                            AND query LIKE 'INSERT INTO warehouse_history%%'""")[0][0]
                        if waiting:
                            break
                        if work.done():
                            self.fail('Work did not reach its stock mutation: '+work.result().text)
                        time.sleep(.02)
                    self.assertEqual(waiting, 1, 'Real work handler must pause after balance read')
                    returned = pool.submit(self.request, 'POST', '/material-transfers/return', self.payload(2))
                    deadline = time.monotonic()+3
                    while not returned.done() and time.monotonic() < deadline:
                        waiting = self.sql("""SELECT count(*) FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock'
                            AND query LIKE 'LOCK TABLE materials, warehouse_main, projects%%'""")[0][0]
                        if waiting:
                            break
                        time.sleep(.02)
                finally:
                    blocker.rollback()
                responses = [work.result(timeout=20), returned.result(timeout=20)]
        finally:
            blocker.close()
            self.sql('DROP TRIGGER work_consumption_pause ON warehouse_history')
            self.sql('DROP FUNCTION work_consumption_pause()')
        self.assertEqual([r.status_code for r in responses], [200, 400],
                         [(r.status_code,r.text) for r in responses])
        self.assertEqual(self.balance(), dict(issued=2, used=2, returned=0, available=0))
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(0,)])

    def test_create_consumption_and_return_cannot_spend_the_same_personal_stock(self):
        self.race_work_with_return('POST', '/work-journal', self.work_payload())

    def test_update_consumption_and_return_cannot_spend_the_same_personal_stock(self):
        journal = self.api('worker', 'POST', '/work-journal', self.work_payload(0))
        self.race_work_with_return('PUT', '/work-journal/'+str(journal['id']),
                                  {'materialsUsed': self.work_payload()['materialsUsed']})

    def test_two_same_name_workers_keep_distinct_return_balances(self):
        worker, other = self.f['users']['worker'], self.f['users']['other_worker']
        self.sql('UPDATE users SET name=%s WHERE id=%s', (worker['name'], other['id']))
        original_name = other['name']
        other['name'] = worker['name']
        self.addCleanup(other.update, name=original_name)
        self.addCleanup(self.sql, 'UPDATE users SET name=%s WHERE id=%s', (original_name, other['id']))
        self.sql('UPDATE materials SET quantity=2 WHERE company_id=2')
        transfer = self.api('foreman', 'POST', '/material-transfers',
                            self.payload(2, toUserId=other['id'], toPerson=other['name']))['id']
        self.api('other_worker', 'PUT', f'/material-transfers/{transfer}/sign')
        self.api('worker', 'POST', '/material-transfers/return', self.payload(2))
        self.assertEqual(self.balance('other_worker'), dict(issued=2,used=0,returned=0,available=2))
        self.api('other_worker', 'POST', '/material-transfers/return', self.payload(2))
        self.assertEqual(self.balance('worker'), dict(issued=2,used=0,returned=2,available=0))
        self.assertEqual(self.balance('other_worker'), dict(issued=2,used=0,returned=2,available=0))
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(4,)])

    def test_renaming_worker_does_not_restore_already_returned_stock(self):
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1))
        worker = self.f['users']['worker']
        old_name = worker['name']
        worker['name'] = old_name+' renamed'
        self.sql('UPDATE users SET name=%s WHERE id=%s', (worker['name'],worker['id']))
        self.addCleanup(worker.update, name=old_name)
        self.addCleanup(self.sql, 'UPDATE users SET name=%s WHERE id=%s', (old_name,worker['id']))
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=1,available=1))
        self.api('worker', 'POST', '/material-transfers/return', self.payload(2), expected=400)

    def test_repeated_material_rows_cannot_overconsume_within_one_journal(self):
        payload = self.work_payload(2)
        payload['materialsUsed'] *= 2
        self.api('worker', 'POST', '/work-journal', payload, expected=400)
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=0,available=2))
        self.assertEqual(self.sql('SELECT count(*) FROM work_journal'), [(0,)])

    def test_historical_name_only_return_is_preserved(self):
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1))
        self.sql("UPDATE warehouse_history SET source_type=NULL,source_id=NULL WHERE type='возврат от мастера'")
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=1,available=1))
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1))
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=2,available=0))
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(2,)])

    def test_ambiguous_historical_name_only_return_blocks_without_changing_stock(self):
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1))
        self.sql("UPDATE warehouse_history SET source_type=NULL,source_id=NULL WHERE type='возврат от мастера'")
        other = self.f['users']['other_worker']
        self.sql('UPDATE users SET name=%s WHERE id=%s', (self.f['users']['worker']['name'],other['id']))
        self.addCleanup(self.sql, 'UPDATE users SET name=%s WHERE id=%s', (other['name'],other['id']))
        before = self.sql('SELECT * FROM warehouse_history ORDER BY id')
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1), expected=409)
        self.assertEqual(self.sql('SELECT * FROM warehouse_history ORDER BY id'), before)
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(1,)])

    def test_cancelling_work_releases_personal_materials_exactly_once(self):
        journal = self.api('worker', 'POST', '/work-journal', self.work_payload())
        self.assertEqual(self.balance(), dict(issued=2,used=2,returned=0,available=0))
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1), expected=400)
        self.api('director', 'DELETE', '/work-journal/'+str(journal['id']))
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=0,available=2))
        self.api('worker', 'POST', '/material-transfers/return', self.payload(2))
        self.api('director', 'DELETE', '/work-journal/'+str(journal['id']))
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=2,available=0))
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(2,)])

    def test_nonfinite_historical_balance_blocks_return_without_changing_stock(self):
        self.sql("UPDATE material_transfers SET quantity='NaN'::float WHERE company_id=2")
        before = self.sql('SELECT * FROM warehouse_history ORDER BY id')
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1), expected=409)
        self.assertEqual(self.sql('SELECT * FROM warehouse_history ORDER BY id'), before)
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(0,)])

    def test_nonfinite_requested_work_material_is_rejected(self):
        self.api('worker', 'POST', '/work-journal', self.work_payload('NaN'), expected=400)
        journal = self.api('worker', 'POST', '/work-journal', self.work_payload(0))
        self.api('worker', 'PUT', '/work-journal/'+str(journal['id']),
                 {'materialsUsed': self.work_payload('NaN')['materialsUsed']}, expected=400)
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=0,available=2))

    def test_name_only_issue_rejects_two_active_same_name_workers(self):
        worker, other = self.f['users']['worker'], self.f['users']['other_worker']
        self.sql('UPDATE users SET name=%s WHERE id=%s', (worker['name'],other['id']))
        self.addCleanup(self.sql, 'UPDATE users SET name=%s WHERE id=%s', (other['name'],other['id']))
        self.sql('UPDATE materials SET quantity=2 WHERE company_id=2')
        before = self.sql('SELECT * FROM material_transfers ORDER BY id')
        self.api('foreman', 'POST', '/material-transfers', self.payload(1, toUserId=None), expected=409)
        self.assertEqual(self.sql('SELECT * FROM material_transfers ORDER BY id'), before)
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(2,)])

    def test_name_only_issue_resolves_unique_company_member(self):
        self.sql('UPDATE materials SET quantity=2 WHERE company_id=2')
        transfer = self.api('foreman', 'POST', '/material-transfers', self.payload(1, toUserId=None))['id']
        self.assertEqual(self.sql('SELECT to_user_id FROM material_transfers WHERE id=%s', (transfer,)),
                         [(self.f['users']['worker']['id'],)])

    def cancelled_work(self):
        journal = self.api('worker', 'POST', '/work-journal', self.work_payload())
        path = '/work-journal/'+str(journal['id'])
        self.api('director', 'DELETE', path)
        return journal['id'], path

    def test_reactivation_after_full_return_cannot_consume_the_returned_material_again(self):
        journal_id, path = self.cancelled_work()
        self.api('worker', 'POST', '/material-transfers/return', self.payload(2))
        before = self.sql('SELECT * FROM warehouse_history ORDER BY id')
        self.api('director', 'PUT', path, {'status': 'На проверке'}, expected=400)
        self.assertEqual(self.sql('SELECT status FROM work_journal WHERE id=%s', (journal_id,)), [('Отклонено',)])
        self.assertEqual(self.sql('SELECT * FROM warehouse_history ORDER BY id'), before)
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=2,available=0))
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2'), [(2,)])

    def test_reactivation_with_available_material_records_consumption_and_can_be_cancelled_again(self):
        journal_id, path = self.cancelled_work()
        self.api('director', 'PUT', path, {'status': 'На проверке'})
        self.assertEqual(self.balance(), dict(issued=2,used=2,returned=0,available=0))
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_history WHERE type='расход (работа мастера)' ORDER BY id"),
                         [(2,),(2,)])
        before = self.sql('SELECT * FROM warehouse_history ORDER BY id')
        self.api('director', 'PUT', path, {'status': 'На проверке'})
        self.assertEqual(self.sql('SELECT * FROM warehouse_history ORDER BY id'), before)
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1), expected=400)
        self.api('director', 'DELETE', path)
        self.assertEqual(self.sql('SELECT status FROM work_journal WHERE id=%s', (journal_id,)), [('Отклонено',)])
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=0,available=2))

    def test_reactivation_validates_and_records_full_reduced_material_quantity(self):
        _, path = self.cancelled_work()
        self.api('worker', 'POST', '/material-transfers/return', self.payload(1))
        self.api('director', 'PUT', path, {'status':'На проверке',
                 'materialsUsed': self.work_payload(3)['materialsUsed']}, expected=403)
        self.api('director', 'PUT', path, {'status':'На проверке',
                 'materialsUsed': self.work_payload(1)['materialsUsed']})
        self.assertEqual(self.balance(), dict(issued=2,used=1,returned=1,available=0))
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_history WHERE type='расход (работа мастера)' ORDER BY id"),
                         [(2,),(1,)])

    def test_editing_rejected_materials_does_not_consume_until_reactivation(self):
        _, path = self.cancelled_work()
        self.api('worker', 'POST', '/material-transfers/return', self.payload(2))
        before = self.sql('SELECT * FROM warehouse_history ORDER BY id')
        self.api('worker', 'PUT', path, {'materialsUsed': self.work_payload(3)['materialsUsed']})
        self.assertEqual(self.sql('SELECT * FROM warehouse_history ORDER BY id'), before)
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=2,available=0))
        self.api('director', 'PUT', path, {'status':'На проверке'}, expected=400)

    def test_annulled_status_also_requires_full_balance_on_reactivation(self):
        journal = self.api('worker', 'POST', '/work-journal', self.work_payload())
        path = '/work-journal/'+str(journal['id'])
        self.api('director', 'PUT', path, {'status':'Аннулировано'})
        self.api('worker', 'POST', '/material-transfers/return', self.payload(2))
        self.api('director', 'PUT', path, {'status':'На проверке'}, expected=400)
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=2,available=0))

    def test_worker_cannot_create_work_with_own_name_but_another_user_id(self):
        payload = self.work_payload()
        payload['masterId'] = self.f['users']['other_worker']['id']
        before = self.sql('SELECT * FROM warehouse_history ORDER BY id')
        self.api('worker', 'POST', '/work-journal', payload, expected=403)
        self.assertEqual(self.sql('SELECT count(*) FROM work_journal'), [(0,)])
        self.assertEqual(self.sql('SELECT * FROM warehouse_history ORDER BY id'), before)
        self.assertEqual(self.balance(), dict(issued=2,used=0,returned=0,available=2))

    def test_worker_name_only_create_is_pinned_to_authenticated_identity(self):
        payload = self.work_payload()
        payload['masterId'] = 0
        journal = self.api('worker', 'POST', '/work-journal', payload)
        worker = self.f['users']['worker']
        self.assertEqual((journal['master_id'],journal['master_name']), (worker['id'],worker['name']))
        self.assertEqual(self.balance(), dict(issued=2,used=2,returned=0,available=0))
        # Existing historic name-only rows retain their narrow update fallback.
        self.sql('UPDATE work_journal SET master_id=0 WHERE id=%s', (journal['id'],))
        self.api('worker', 'PUT', '/work-journal/'+str(journal['id']), {'comment':'Legacy own row'})

    def test_worker_create_uses_current_name_for_matching_authenticated_id(self):
        payload = self.work_payload()
        payload['masterName'] = 'Stale or supplied display name'
        journal = self.api('worker', 'POST', '/work-journal', payload)
        self.assertEqual(journal['master_name'], self.f['users']['worker']['name'])
        self.assertEqual(self.balance(), dict(issued=2,used=2,returned=0,available=0))

    def test_stored_worker_id_takes_precedence_over_matching_name_on_update(self):
        journal = self.api('worker', 'POST', '/work-journal', self.work_payload())
        self.sql('UPDATE work_journal SET master_id=%s WHERE id=%s',
                 (self.f['users']['other_worker']['id'],journal['id']))
        self.api('worker', 'PUT', '/work-journal/'+str(journal['id']), {'comment':'Not my row'}, expected=403)
        self.assertEqual(self.sql('SELECT comment FROM work_journal WHERE id=%s', (journal['id'],)), [('',)])


if __name__ == '__main__':
    unittest.main()
