"""Compatibility with a database that has not installed ledger migration 0017."""
import os
import unittest

from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PreLedgerRoutesTests(unittest.TestCase):
    setUpClass = classmethod(chain.PostgresSupplyChainTests.setUpClass.__func__)
    api = chain.PostgresSupplyChainTests.api
    sql = chain.PostgresSupplyChainTests.sql

    def test_list_create_and_reversal_without_ledger_schema(self):
        self.assertEqual(self.sql("SELECT to_regclass('public.supplier_payment_operations')"), [(None,)])
        payload = dict(projectName=self.fixture['project'], amount=7, note='Synthetic pre-ledger', date='2026-09-18')
        first = self.api('accountant', 'POST', '/project-payments', payload)
        self.assertEqual(self.api('accountant', 'POST', '/project-payments', payload)['id'], first['id'])
        self.assertIn(first['id'], {row['id'] for row in self.api('accountant', 'GET', '/project-payments')})
        reversal = self.api('accountant', 'DELETE', '/project-payments/' + str(first['id']))
        self.assertTrue(reversal['reversed'])
        self.assertEqual(self.sql('SELECT amount FROM project_payments WHERE id=%s', (reversal['reversalId'],)), [(-7,)])
