"""Actual Alembic release path on a populated, disposable 0051 fixture only."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

from . import test_allocation_store_postgres as base
from .test_cancellations_postgres import migration
from ..supplier_access.test_postgres_chain_support import connection_settings


class ReleaseRevisionGraphTests(unittest.TestCase):
    def test_single_release_head_and_all_ids_fit_alembic_version(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        root = Path(__file__).resolve().parents[3]
        config = Config(str(root / 'alembic.ini'))
        config.set_main_option('script_location', str(root / 'migrations'))
        graph = ScriptDirectory.from_config(config)
        self.assertEqual(graph.get_heads(), ['0070_approved_legacy_binding'])
        for revision in graph.walk_revisions():
            self.assertLessEqual(len(revision.revision), 32, revision.revision)


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupplierReleaseUpgradeTests(unittest.TestCase):
    sql = base.AllocationStorePostgresTests.sql
    api = base.AllocationStorePostgresTests.api
    create_offer = base.AllocationStorePostgresTests.create_offer
    check_contract = base.AllocationStorePostgresTests.check_contract
    seed_receipt = base.AllocationStorePostgresTests.seed_receipt
    pay = base.AllocationStorePostgresTests.pay
    replace = base.AllocationStorePostgresTests.replace
    read = base.AllocationStorePostgresTests.read
    snapshot = base.AllocationStorePostgresTests.snapshot
    synthetic_current_group_authorizer = base.AllocationStorePostgresTests.synthetic_current_group_authorizer

    @classmethod
    def setUpClass(cls):
        cls.test_settings = connection_settings(os.environ)
        base.AllocationStorePostgresTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, '0027_work_material_accounting.py')
                migration(cur, '0033_supply_claim_cases.py')
                migration(cur, '0050_supplier_invoice_line_specs.py')
                migration(cur, '0051_supplier_offer_item_scopes.py')
        finally:
            conn.close()

    def alembic(self, *args):
        settings = self.test_settings  # Validated before fixture isolates the environment.
        env = dict(os.environ, DB_HOST=settings['host'], DB_PORT=settings['port'],
                   DB_NAME=settings['dbname'], DB_USER=settings['user'], DB_PASSWORD='',
                   PGOPTIONS='-c lock_timeout=5000 -c statement_timeout=60000')
        result = subprocess.run([sys.executable, '-m', 'alembic', *args],
            cwd=Path(__file__).resolve().parents[3], env=env, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_populated_0051_upgrade_preserves_finances_and_rollback_then_replay(self):
        base.AllocationStorePostgresTests.setUp(self)
        self.replace(dict(requestId=str(uuid4()), groupId=self.group, expectedVersion=0,
            reason='Release rehearsal existing distribution', rows=[
                dict(paymentId=self.payment, receiptId=self.receipts[0]['id'], amount='40.00'),
                dict(paymentId=self.second_payment, receiptId=self.receipts[1]['id'], amount='20.00')]))
        from .engine import execute
        from .policy import validate_new_payment
        body = dict(requestId=str(uuid4()), kind='payment', documentKind='invoice',
                    documentId=self.invoice, amount='10.00', paidAt='2026-09-28', reason='Before upgrade')
        original = execute(self.main.get_db, self.payment_resolver, self.actor, 2, body,
                           validate_new=validate_new_payment)
        before = self.snapshot(), self.snapshot(allocations=True)
        # The fixture actually applies the schema through 0051 above. Only its
        # disposable Alembic version metadata needs initializing; never stamp
        # a deployed database or use stamping as a substitute for an upgrade.
        self.alembic('stamp', '0051_supplier_offer_item_scopes')
        result = self.alembic('upgrade', '0061_supplier_mixed_bindings')
        for number in range(52, 62):
            self.assertIn(f'00{number}_', result.stderr)
        self.assertEqual(self.sql('SELECT version_num FROM alembic_version'),
                         [('0061_supplier_mixed_bindings',)])
        self.assertEqual((self.snapshot(), self.snapshot(allocations=True)), before)
        for table in ('supplier_receipt_line_proofs', 'supplier_opening_confirmations',
                      'supplier_payment_refund_links', 'supplier_mixed_scope_reviews', 'supplier_mixed_opening_bindings'):
            self.assertEqual(self.sql(f'SELECT count(*) FROM {table}'), [(0,)])
        self.alembic('downgrade', '0051_supplier_offer_item_scopes')
        self.assertEqual((self.snapshot(), self.snapshot(allocations=True)), before)
        self.alembic('upgrade', '0061_supplier_mixed_bindings')
        replay = execute(self.main.get_db, self.payment_resolver, self.actor, 2, body,
                         validate_new=validate_new_payment)
        self.assertEqual(replay, original)
        self.assertEqual((self.snapshot(), self.snapshot(allocations=True)), before)
        view = self.read()
        self.assertEqual((view['paid'], view['allocated'], view['unallocatedPayments']),
                         ('100.00', '60.00', '40.00'))
        self.pay('5.00')
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(105,)])
        before_binding_release = self.snapshot(), self.snapshot(allocations=True)
        self.alembic('upgrade', '0062_supplier_legacy_binding')
        self.assertEqual(self.sql('SELECT version_num FROM alembic_version'), [('0062_supplier_legacy_binding',)])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_legacy_contract_bindings'), [(0,)])
        self.assertEqual((self.snapshot(), self.snapshot(allocations=True)), before_binding_release)
        self.assertEqual(execute(self.main.get_db, self.payment_resolver, self.actor, 2, body,
                                validate_new=validate_new_payment), original)

        before_lines_release = self.snapshot(), self.snapshot(allocations=True)
        self.alembic('upgrade', '0063_supplier_legacy_lines')
        self.assertEqual(self.sql('SELECT version_num FROM alembic_version'), [('0063_supplier_legacy_lines',)])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_legacy_line_reviews'), [(0,)])
        self.assertEqual((self.snapshot(), self.snapshot(allocations=True)), before_lines_release)
        self.assertEqual(execute(self.main.get_db, self.payment_resolver, self.actor, 2, body,
                                validate_new=validate_new_payment), original)
