"""Schema admission is read-only and fails closed; isolated PostgreSQL only."""
import os
import unittest

from fastapi import HTTPException
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from .allocation_schema import require_allocation_schema, REQUIRED_TRIGGERS
from . import test_allocation_store_postgres as base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AllocationSchemaTests(unittest.TestCase):
    sql = base.AllocationStorePostgresTests.sql
    api = base.AllocationStorePostgresTests.api
    create_offer = base.AllocationStorePostgresTests.create_offer
    check_contract = base.AllocationStorePostgresTests.check_contract

    @classmethod
    def setUpClass(cls):
        base.AllocationStorePostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)

    def unavailable(self):
        with self.assertRaises(HTTPException) as caught:
            require_allocation_schema(self.cur)
        self.assertEqual(caught.exception.status_code, 503)

    def test_intact_schema_is_ready_without_financial_writes(self):
        self.cur.execute('SELECT COUNT(*) n FROM supplier_payment_allocation_revisions')
        before = self.cur.fetchone()['n']
        require_allocation_schema(self.cur)
        self.cur.execute('SELECT COUNT(*) n FROM supplier_payment_allocation_revisions')
        self.assertEqual(self.cur.fetchone()['n'], before)

    def test_each_allocation_guard_must_exist_and_be_enabled(self):
        for table, trigger in REQUIRED_TRIGGERS:
            with self.subTest(table=table, trigger=trigger):
                self.cur.execute('SAVEPOINT guard_check')
                self.cur.execute(sql.SQL('ALTER TABLE {} DISABLE TRIGGER {}').format(
                    sql.Identifier(table), sql.Identifier(trigger)))
                self.unavailable()
                self.cur.execute('ROLLBACK TO SAVEPOINT guard_check')
                self.cur.execute(sql.SQL('DROP TRIGGER {} ON {}').format(
                    sql.Identifier(trigger), sql.Identifier(table)))
                self.unavailable()
                self.cur.execute('ROLLBACK TO SAVEPOINT guard_check')
                self.cur.execute('RELEASE SAVEPOINT guard_check')

    def test_missing_relation_table_is_not_recreated(self):
        self.cur.execute('ALTER TABLE supplier_payment_allocation_rows RENAME TO synthetic_unavailable_rows')
        self.unavailable()
        self.cur.execute("SELECT to_regclass('public.supplier_payment_allocation_rows') name")
        self.assertIsNone(self.cur.fetchone()['name'])

    def test_base_payment_guards_are_also_required(self):
        self.cur.execute('ALTER TABLE supplier_payment_operations DISABLE TRIGGER supplier_payment_complete')
        self.unavailable()

    def test_cancellation_guards_are_required(self):
        self.cur.execute('ALTER TABLE supplier_payment_request_cancellations DISABLE TRIGGER supplier_payment_cancellation_immutable')
        self.unavailable()

    def test_base_no_truncate_guards_cannot_be_disabled_or_dropped(self):
        guards = [(table, 'supplier_payment_no_truncate') for table in (
            'supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts')]
        guards.append(('supplier_payment_attachments', 'supplier_payment_attachment_no_truncate'))
        for table, trigger in guards:
            for action in ('disable', 'drop'):
                with self.subTest(table=table, action=action):
                    self.cur.execute('SAVEPOINT base_guard')
                    statement = ('ALTER TABLE {} DISABLE TRIGGER {}' if action == 'disable'
                                 else 'DROP TRIGGER {1} ON {0}')
                    self.cur.execute(sql.SQL(statement).format(sql.Identifier(table), sql.Identifier(trigger)))
                    self.unavailable()
                    self.cur.execute('ROLLBACK TO SAVEPOINT base_guard')
                    self.cur.execute('RELEASE SAVEPOINT base_guard')
