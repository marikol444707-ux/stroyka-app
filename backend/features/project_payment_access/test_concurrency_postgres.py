"""Real HTTP/SQL project-payment races in the disposable supply-chain fixture."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest
from uuid import uuid4

from backend.features.supplier_access.test_postgres_chain import PostgresSupplyChainTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ProjectPaymentConcurrencyTests(unittest.TestCase):
    setUpClass = classmethod(PostgresSupplyChainTests.setUpClass.__func__)
    api = PostgresSupplyChainTests.api
    sql = PostgresSupplyChainTests.sql

    def payload(self, **changes):
        return dict(dict(companyId=2, projectName=self.fixture['project'], amount=25,
                         note='Payment race '+uuid4().hex, date='2026-11-09', addedBy='Synthetic'), **changes)

    def wait_for_locks(self, count, query):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            rows = self.sql("""SELECT pid FROM pg_stat_activity WHERE datname=current_database()
                AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query ~ %s""", (query,))
            if len(rows) >= count:
                return
            time.sleep(.02)
        self.fail('Expected concurrent requests waiting inside PostgreSQL')

    def hold(self, sql, params=()):
        conn = self.main.get_db()
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(sql, params)
        self.addCleanup(conn.close)
        return conn

    def test_concurrent_identical_requests_create_one_actual_row_and_total(self):
        payload = self.payload()
        # Pause the real INSERT so both HTTP requests overlap deterministically.
        # Before the fix both pass the duplicate SELECT; after it the second
        # waits for the company's transaction before reading the committed row.
        self.sql('''CREATE FUNCTION payment_test_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(734927, 1); RETURN NEW; END $$''')
        self.sql('''CREATE TRIGGER payment_test_pause BEFORE INSERT ON project_payments
            FOR EACH ROW EXECUTE FUNCTION payment_test_pause()''')
        self.addCleanup(self.sql, 'DROP FUNCTION payment_test_pause() CASCADE')
        control = self.hold('SELECT pg_advisory_xact_lock(734927, 1)')
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.api, 'accountant', 'POST', '/project-payments', payload)
                       for _ in range(2)]
            try:
                self.wait_for_locks(2, r'INSERT INTO project_payments|SELECT pg_advisory_xact_lock')
            finally:
                control.rollback()
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(len({row['id'] for row in results}), 1)
        self.assertEqual(sum(bool(row.get('duplicate')) for row in results), 1)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments WHERE note=%s',
                                  (payload['note'],)), [(1, 25)])
        visible = [row for row in self.api('accountant', 'GET', '/project-payments')
                   if row['note'] == payload['note']]
        self.assertEqual([row['id'] for row in visible], [results[0]['id']])

    def foreign_project(self):
        name = 'Same project '+uuid4().hex
        self.sql('INSERT INTO projects(name,company_id) VALUES(%s,2),(%s,3)', (name,name))
        return name

    def test_company_lock_does_not_block_another_company_with_the_same_project_name(self):
        name = self.foreign_project()
        payload = self.payload(projectName=name)
        control = self.hold('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', ('project-payments:2',))
        with ThreadPoolExecutor(max_workers=2) as pool:
            own = pool.submit(self.api, 'director', 'POST', '/project-payments', payload)
            try:
                self.wait_for_locks(1, r'SELECT pg_advisory_xact_lock')
                foreign = pool.submit(self.api, 'stranger', 'POST', '/project-payments',
                                      {**payload,'companyId':3}).result(timeout=5)
                self.assertEqual(foreign['companyId'], 3)
            finally:
                control.rollback()
            own = own.result(timeout=15)
        self.assertNotEqual(own['id'], foreign['id'])
        self.assertEqual(self.sql('SELECT company_id,count(*),sum(amount) FROM project_payments WHERE note=%s GROUP BY company_id ORDER BY company_id',
                                  (payload['note'],)), [(2,1,25),(3,1,25)])

    def test_denied_company_is_rejected_before_locking_or_reusing_its_payment(self):
        name = self.foreign_project()
        payload = self.payload(projectName=name,companyId=3)
        foreign = self.api('stranger','POST','/project-payments',payload)
        before = self.sql('SELECT count(*),sum(amount) FROM project_payments')
        control = self.hold('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', ('project-payments:3',))
        with ThreadPoolExecutor(max_workers=1) as pool:
            try:
                denied = pool.submit(self.api,'director','POST','/project-payments',payload,403).result(timeout=5)
                self.assertNotIn('id',denied)
            finally:
                control.rollback()
        self.api('director','DELETE','/project-payments/'+str(foreign['id']),expected=403)
        self.assertNotIn(foreign['id'], {r['id'] for r in self.api('director','GET','/project-payments')})
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)

    def test_header_company_mismatch_and_non_finance_role_cannot_write(self):
        payload = self.payload()
        before = self.sql('SELECT count(*) FROM project_payments')
        self.api('director','POST','/project-payments',payload,expected=403,**{'X-Company-Id':'3'})
        self.api('foreman','POST','/project-payments',payload,expected=403)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'),before)

    def test_existing_identity_keeps_distinct_payments_and_empty_notes(self):
        payload = self.payload()
        saved = self.api('accountant','POST','/project-payments',payload)
        self.assertEqual(self.api('accountant','POST','/project-payments',payload)['id'],saved['id'])
        ids = {saved['id']}
        for change in ({'date':'2026-11-10'},{'amount':26},{'addedBy':'Other synthetic'}, {'note':payload['note']+' changed'}):
            ids.add(self.api('accountant','POST','/project-payments',{**payload,**change})['id'])
        self.assertEqual(len(ids),5)
        first = self.api('accountant','POST','/project-payments',{**payload,'note':''})
        second = self.api('accountant','POST','/project-payments',{**payload,'note':''})
        self.assertNotEqual(first['id'],second['id'])

    def test_revoked_company_membership_cannot_reuse_a_known_duplicate(self):
        payload=self.payload()
        saved=self.api('accountant','POST','/project-payments',payload)
        actor=self.fixture['users']['accountant']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(actor,))
        try:
            denied=self.api('accountant','POST','/project-payments',payload,expected=403)
            self.assertNotIn('id',denied)
            self.assertEqual(self.sql('SELECT id FROM project_payments WHERE note=%s',(payload['note'],)),[(saved['id'],)])
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(actor,))

    def test_failed_insert_releases_transaction_and_retry_can_save_once(self):
        payload = self.payload()
        self.sql('''CREATE FUNCTION payment_test_reject() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic payment rejection'; END $$''')
        self.sql('''CREATE TRIGGER payment_test_reject BEFORE INSERT ON project_payments
            FOR EACH ROW EXECUTE FUNCTION payment_test_reject()''')
        try:
            token = self.main.create_auth_token(self.fixture['users']['accountant'],two_factor_passed=True)
            from fastapi.testclient import TestClient
            with TestClient(self.main.app,raise_server_exceptions=False) as client:
                response=client.post('/project-payments',json=payload,headers={'Authorization':'Bearer '+token})
            self.assertEqual(response.status_code,500)
            self.assertEqual(self.sql('SELECT count(*) FROM project_payments WHERE note=%s',(payload['note'],)),[(0,)])
        finally:
            self.sql('DROP FUNCTION payment_test_reject() CASCADE')
        saved=self.api('accountant','POST','/project-payments',payload)
        self.assertEqual(self.api('accountant','POST','/project-payments',payload)['id'],saved['id'])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments WHERE note=%s',(payload['note'],)),[(1,25)])


if __name__ == '__main__':
    unittest.main()
