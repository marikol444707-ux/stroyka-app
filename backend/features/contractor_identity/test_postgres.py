"""Exact legacy identities on an explicitly empty, socket-only PostgreSQL DB."""
from contextlib import redirect_stdout
import io
import json
import os
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extras import Json

from .report import main, run_audit
from .test_report import frozen, candidate
from ..supplier_access.test_postgres_chain_support import connection_settings, _assert_empty_database


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ContractorIdentityPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = connection_settings(os.environ)
        cls.db = psycopg2.connect(**cls.settings)
        cls.addClassCleanup(cls.db.close)
        _assert_empty_database(cls.db, cls.settings)
        cls.db.rollback()
        cls.db.autocommit = True
        with cls.db.cursor() as cur:
            cur.execute('''CREATE TABLE companies(id INT PRIMARY KEY,platform_account_id INT,active BOOLEAN);
                CREATE TABLE projects(id INT PRIMARY KEY,company_id INT,name TEXT);
                CREATE TABLE users(id INT PRIMARY KEY,active BOOLEAN,name TEXT,email TEXT);
                CREATE TABLE staff(id INT PRIMARY KEY,company_id INT,name TEXT,email_work TEXT);
                CREATE TABLE user_company_roles(id SERIAL PRIMARY KEY,user_id INT,company_id INT,
                    staff_id INT,role TEXT,active BOOLEAN);
                CREATE TABLE brigade_contracts(id SERIAL PRIMARY KEY,company_id INT,project_id INT,
                    contractor_id INT,status TEXT,party_snapshot_json JSONB,party_snapshot_hash TEXT,
                    total_amount NUMERIC,notes TEXT);
            ''')

    def sql(self, query, params=None):
        with self.db.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall() if cur.description else []

    def setUp(self):
        self.sql('''TRUNCATE companies,projects,users,staff,user_company_roles,brigade_contracts RESTART IDENTITY;
            INSERT INTO companies VALUES(2,1,TRUE),(3,99,TRUE);
            INSERT INTO projects VALUES(17,2,'Same project'),(18,3,'Same project');
            INSERT INTO users VALUES(23,TRUE,'Same person','private@local.invalid'),
                (41,TRUE,'Same person','private@local.invalid');
            INSERT INTO user_company_roles(user_id,company_id,role,active)
                VALUES(23,2,'субподрядчик',TRUE),(41,3,'субподрядчик',TRUE);
            INSERT INTO brigade_contracts(id,company_id,project_id,contractor_id,status,total_amount,notes)
                VALUES(71,2,17,23,'Черновик',123.45,'private bank/contract information'),
                      (72,3,18,41,'Черновик',999,'other buyer private information');''')

    def connect(self):
        return psycopg2.connect(**self.settings)

    def report(self, company=2, **page):
        return run_audit(self.connect, company, **page)

    def original_rows(self):
        return [(table, self.sql('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id'))
                for table in ('companies','projects','users','staff','user_company_roles','brigade_contracts')]

    def test_report_preserves_all_rows_and_discloses_no_contacts_money_or_other_buyer(self):
        before = self.original_rows()
        report = self.report()
        self.assertEqual([item['contractId'] for item in report['items']], [71])
        self.assertEqual(report['items'][0]['reference'], {'type':'user','id':23})
        self.assertFalse(report['canApply'])
        self.assertFalse(report['accessGranted'])
        self.assertTrue(report['readOnlyTransaction'])
        self.assertTrue(report['rolledBack'])
        for forbidden in ('private','123.45','999','Same person','72', 'bankAccount'):
            # IDs can coincidentally occur inside the evidence hash.
            public = dict(report, evidenceSha256='')
            self.assertNotIn(forbidden, json.dumps(public))
        self.assertEqual(before, self.original_rows())

    def test_colliding_staff_id_cannot_select_another_user_by_name_or_email(self):
        self.sql("INSERT INTO staff VALUES(23,2,'Same person','private@local.invalid')")
        self.sql("INSERT INTO user_company_roles(user_id,company_id,staff_id,role,active) VALUES(41,2,23,'мастер',TRUE)")
        report = self.report()
        self.assertEqual(report['items'][0]['reason'], 'AMBIGUOUS_USER_STAFF_ID')
        self.assertIsNone(report['items'][0]['reference'])
        row = frozen(candidate())
        self.sql('UPDATE brigade_contracts SET status=%s,party_snapshot_json=%s,party_snapshot_hash=%s WHERE id=71',
                 (row['status'], Json(row['party_snapshot_json']), row['party_snapshot_hash']))
        self.assertEqual(self.report()['items'][0]['reason'], 'FROZEN_USER_REFERENCE')
        self.sql("UPDATE brigade_contracts SET party_snapshot_json=jsonb_set(party_snapshot_json,'{contractor,userId}','41') WHERE id=71")
        self.assertEqual(self.report()['items'][0]['reason'], 'FROZEN_IDENTITY_UNVERIFIED')

    def test_revocation_changes_evidence_and_never_creates_a_replacement_membership(self):
        initial = self.report()
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=23')
        before = self.original_rows()
        revoked = self.report()
        self.assertNotEqual(initial['evidenceSha256'], revoked['evidenceSha256'])
        self.assertEqual(revoked['items'][0]['reason'], 'COMPANY_MEMBERSHIP_UNVERIFIED')
        self.assertEqual(before, self.original_rows())
        self.assertEqual(self.sql('SELECT count(*) FROM user_company_roles'), [(2,)])

    def test_wrong_project_owner_missing_membership_and_unknown_company_fail_closed(self):
        self.sql('UPDATE brigade_contracts SET project_id=18 WHERE id=71')
        self.assertEqual(self.report()['items'][0]['reason'], 'PROJECT_OWNER_UNVERIFIED')
        with self.assertRaisesRegex(ValueError, 'COMPANY_UNAVAILABLE'):
            self.report(999)
        self.sql('UPDATE companies SET active=FALSE WHERE id=2')
        self.assertIn('COMPANY_INACTIVE', self.report()['blockers'])
        self.sql('UPDATE companies SET active=TRUE,platform_account_id=NULL WHERE id=2')
        self.assertIn('COMPANY_ACCOUNT_UNVERIFIED', self.report()['blockers'])

    def test_fifty_buyers_keep_one_user_without_cross_company_results(self):
        self.sql('TRUNCATE companies,projects,user_company_roles,brigade_contracts RESTART IDENTITY')
        for cid in range(1,51):
            self.sql('INSERT INTO companies VALUES(%s,%s,TRUE)', (cid, 1 if cid < 26 else 99))
            self.sql("INSERT INTO projects VALUES(%s,%s,'Same project')", (cid,cid))
            self.sql("INSERT INTO user_company_roles(user_id,company_id,role,active) VALUES(23,%s,'субподрядчик',TRUE)", (cid,))
            self.sql("INSERT INTO brigade_contracts(company_id,project_id,contractor_id,status) VALUES(%s,%s,23,'Черновик')", (cid,cid))
        before = self.original_rows()
        for cid in (1,25,26,50):
            report = self.report(cid)
            self.assertEqual([item['contractId'] for item in report['items']], [cid])
            self.assertEqual(report['items'][0]['reference'], {'type':'user','id':23})
        self.assertEqual(before, self.original_rows())

    def test_pages_are_stable_separate_and_never_claim_complete_inventory(self):
        self.sql("INSERT INTO brigade_contracts(company_id,project_id,contractor_id,status) VALUES(2,17,23,'Черновик'),(2,17,23,'Черновик')")
        first = self.report(limit=1)
        second = self.report(limit=1, offset=1)
        self.assertTrue(first['hasMore'])
        self.assertIn('PAGE_INCOMPLETE', first['blockers'])
        self.assertNotEqual(first['items'][0]['contractId'], second['items'][0]['contractId'])
        self.assertEqual(first['evidenceSha256'], self.report(limit=1)['evidenceSha256'])
        self.assertNotEqual(first['evidenceSha256'], second['evidenceSha256'])
        self.assertEqual(second['scope'], 'company_page_only')
        self.assertFalse(second['canApply'])

    def test_read_only_database_transaction_blocks_even_an_accidental_writer(self):
        before = self.original_rows()
        def accidental_writer(cur, *_args, **_kwargs):
            cur.execute('UPDATE brigade_contracts SET contractor_id=41 WHERE id=71')
        with patch('backend.features.contractor_identity.report.collect_report', side_effect=accidental_writer):
            with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
                self.report()
        self.assertEqual(before, self.original_rows())

    def test_report_works_with_select_only_database_permissions(self):
        self.sql('CREATE ROLE contractor_identity_reader NOLOGIN')
        conn = None
        try:
            self.sql('''GRANT USAGE ON SCHEMA public TO contractor_identity_reader;
                GRANT SELECT ON companies,projects,users,staff,user_company_roles,brigade_contracts
                TO contractor_identity_reader''')
            def reader():
                nonlocal conn
                conn = self.connect()
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute('SET ROLE contractor_identity_reader')
                conn.autocommit = False
                return conn
            before = self.original_rows()
            report = run_audit(reader, 2)
            self.assertEqual(report['items'][0]['reason'], 'CANDIDATE_USER_REFERENCE')
            self.assertFalse(report['accessGranted'])
            self.assertEqual(before, self.original_rows())
        finally:
            if conn is not None and not conn.closed:
                conn.close()
            self.sql('DROP OWNED BY contractor_identity_reader')
            self.sql('DROP ROLE contractor_identity_reader')

    def test_cli_uses_explicit_socket_dsn_and_returns_only_the_selected_company(self):
        dsn = psycopg2.extensions.make_dsn(**self.settings)
        output = io.StringIO()
        with patch.dict(os.environ, {'CONTRACTOR_IDENTITY_AUDIT_DSN':dsn}), redirect_stdout(output):
            result = main(['--company-id','2','--read-only'])
        self.assertEqual(result,0)
        self.assertEqual(json.loads(output.getvalue())['companyId'],2)
        self.assertNotIn(self.settings['dbname'],output.getvalue())


if __name__ == '__main__':
    unittest.main()
