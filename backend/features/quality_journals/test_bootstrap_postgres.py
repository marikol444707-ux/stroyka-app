from copy import deepcopy
from unittest.mock import patch
from types import SimpleNamespace

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .bootstrap import make_plan, apply_plan, digest, TABLES
from .test_owner_stock_postgres import OwnerStockPostgresTests
from .test_owner_migration import load_migration


class OwnershipBootstrapPostgresTests(OwnerStockPostgresTests):
    def setUp(self):
        super().setUp()
        self.invoice=self.sql('''INSERT INTO warehouse_invoices(company_id,project,location,
            warehouse_target,items) VALUES(2,%s,%s,'object',%s) RETURNING id''',
            (self.f['project'],self.f['project'],Json([dict(name='Historical cable',quantity=2,unit='уп')])))[0][0]
        self.journal_ids={}
        for table in TABLES[1:]:
            self.journal_ids[table]=[self.sql('INSERT INTO '+table+'(project_name,invoice_id) VALUES(%s,%s) RETURNING id',
                                            (self.f['project'],self.invoice))[0][0]]
        # Content anomalies are independent from confirmed ownership: preserve
        # duplicates and non-metre historical cable observations without repair.
        self.journal_ids['cable_journal'].append(self.sql('''INSERT INTO cable_journal
            (project_name,source_type,length_received,normatives) VALUES(%s,'project_stock',123,'Original finding') RETURNING id''',
            (self.f['project'],))[0][0])
        self.plan=self.transaction(lambda cur: make_plan(cur,company_id=2,project_id=self.f['projectId'],
            journal_ids=self.journal_ids,confirmation='Synthetic owner confirmation of the exact historical inventory'))

    def transaction(self, operation):
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
                return operation(cur)
        finally:
            conn.close()

    def snapshot(self):
        return [self.sql('SELECT to_jsonb(t)-\'company_id\'-\'project_id\' FROM '+table+' t ORDER BY id') for table in TABLES]

    def test_explicit_transfer_changes_only_owners_and_replays_once(self):
        before=self.snapshot()
        first=self.transaction(lambda cur:apply_plan(cur,self.plan,digest(self.plan)))
        self.assertFalse(first['alreadyApplied'])
        self.assertEqual(self.snapshot(),before)
        self.assertTrue(self.transaction(lambda cur:apply_plan(cur,self.plan,digest(self.plan)))['alreadyApplied'])
        self.assertEqual(self.sql('SELECT count(*) FROM quality_owner_bootstraps WHERE plan_digest=%s',(digest(self.plan),)),[(1,)])
        for table,ids in self.journal_ids.items():
            self.assertEqual(self.sql('SELECT company_id,project_id FROM '+table+' WHERE id=ANY(%s)',(ids,)),[(2,self.f['projectId'])]*len(ids))

    def test_changed_source_blocks_every_assignment(self):
        self.sql("UPDATE warehouse_invoices SET number='Changed after confirmation' WHERE id=%s",(self.invoice,))
        with self.assertRaisesRegex(ValueError,'changed after review'):
            self.transaction(lambda cur:apply_plan(cur,self.plan,digest(self.plan)))
        self.assertEqual(self.sql('SELECT project_id FROM warehouse_invoices WHERE id=%s',(self.invoice,)),[(None,)])
        self.assertEqual(self.sql('SELECT count(*) FROM quality_owner_bootstraps WHERE plan_digest=%s',(digest(self.plan),)),[(0,)])

    def test_changed_digest_is_rejected(self):
        changed=deepcopy(self.plan);changed['confirmation']='Unconfirmed replacement'
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            self.transaction(lambda cur:apply_plan(cur,changed,digest(self.plan)))

    def test_cross_company_source_is_rejected(self):
        self.sql('UPDATE warehouse_invoices SET company_id=3 WHERE id=%s',(self.invoice,))
        with self.assertRaisesRegex(ValueError,'different owner'):
            self.transaction(lambda cur:make_plan(cur,company_id=2,project_id=self.f['projectId'],
                journal_ids=self.journal_ids,confirmation=self.plan['confirmation']))

    def test_owner_and_confirmation_audit_cannot_be_rewritten(self):
        self.transaction(lambda cur:apply_plan(cur,self.plan,digest(self.plan)))
        for table in TABLES:
            row_id=self.plan['entries'][table][0]['id']
            with self.assertRaises(psycopg2.errors.CheckViolation):
                self.sql('UPDATE '+table+' SET project_id=NULL WHERE id=%s',(row_id,))
        for statement in ('DELETE FROM quality_owner_bootstraps','UPDATE quality_owner_bootstraps SET result=result','TRUNCATE quality_owner_bootstraps'):
            with self.assertRaises(psycopg2.errors.CheckViolation):
                self.sql(statement)
        migration=load_migration()
        def downgrade(cur):
            with patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade()
        with self.assertRaises(psycopg2.errors.RaiseException):
            self.transaction(downgrade)

    def test_composite_owner_and_complete_pair_are_enforced(self):
        for table in TABLES[1:]:
            with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                self.sql('INSERT INTO '+table+'(company_id,project_id) VALUES(3,%s)',(self.f['projectId'],))
            with self.assertRaises(psycopg2.errors.CheckViolation):
                self.sql('INSERT INTO '+table+'(company_id) VALUES(2)')
