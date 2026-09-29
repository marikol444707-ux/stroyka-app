"""Legacy readers exclude supplier operations; opt-in PG uses synthetic mappings.

The deliberately minimal ledger table permits a malformed foreign-company mapping.
These tests prove reader SQL, not payment-engine writes or ledger constraints.
"""
import ast
import os
import unittest
from pathlib import Path

from backend.features.director_agent.read_tools import build_director_agent_tools, execute_director_agent_read_query
from backend.features.director_agent.result_policy import sanitize_director_agent_tool_result
from backend.features.director_daily_brief.service import build_director_daily_brief
from backend.features.director_daily_brief.test_service import valid_facts
from backend.features.supplier_access import test_postgres_chain as chain_support


NOTE = 'Платежи поставщикам и их сторно не включены; это не полная финансовая сводка.'


def chat_payment_block():
    tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
               and ast.unparse(node.test) == "payment_visibility_sql != 'FALSE'"]
    if len(matches) != 1:
        raise AssertionError('Expected exactly one legacy chat payment block')
    return tree, matches[0]


class ReaderScopeNoteTests(unittest.TestCase):
    def test_chat_query_excludes_ledger_and_context_declares_scope(self):
        tree, block = chat_payment_block()
        source = ast.unparse(block)
        self.assertIn('to_regclass', source)
        self.assertIn('NOT EXISTS', source)
        self.assertIn('project_payment_id=pp.id', source)
        self.assertNotIn('ledger.company_id', source)
        self.assertTrue(any(isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name) and node.target.id == 'context'
            and NOTE in ast.unparse(node.value) for node in ast.walk(tree)))

    def test_sanitized_finances_carries_server_scope_note(self):
        row = valid_facts()['finances'][0]
        row['paymentsScopeNote'] = 'Untrusted completeness claim'
        self.assertEqual(sanitize_director_agent_tool_result('finances', [row])[0].get('paymentsScopeNote'), NOTE)

    def test_daily_brief_carries_scope_note_even_without_projects(self):
        for empty in (False, True):
            facts = valid_facts()
            if empty:
                facts['finances'] = []
            result = build_director_daily_brief(brief_date='2026-09-18', tool_results=facts)
            self.assertEqual(result.get('paymentsScopeNote'), NOTE)

    def test_failed_schema_probe_is_not_legacy_fallback(self):
        def query(sql, params=()):
            if 'FROM projects' in sql:
                return [dict(company_id=2, name='School', budget=100, status='')]
            if 'to_regclass' in sql:
                raise RuntimeError('Synthetic probe failure')
            return []
        with self.assertRaisesRegex(RuntimeError, 'Synthetic probe failure'):
            build_director_agent_tools(query)['finances']['fn']({}, [2])


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LegacyLedgerReadersPostgresTests(unittest.TestCase):
    sql = chain_support.PostgresSupplyChainTests.sql
    api = chain_support.PostgresSupplyChainTests.api

    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def payment(self, amount, day, *, company=2, project=None, note='Legacy customer'):
        row = self.sql('''INSERT INTO project_payments(company_id,project_name,amount,note,date,created_at)
            VALUES(%s,%s,%s,%s,%s,%s::timestamp) RETURNING id''',
            (company, project or self.fixture['project'], amount, note, day, day))[0][0]
        self.addCleanup(self.sql, 'DELETE FROM project_payments WHERE id=%s', (row,))
        return row

    def ledger(self, mappings):
        self.sql('''CREATE TABLE public.supplier_payment_operations
            (id SERIAL PRIMARY KEY, company_id INTEGER, project_payment_id INTEGER UNIQUE)''')
        self.addCleanup(self.sql, 'DROP TABLE public.supplier_payment_operations')
        for company, payment in mappings:
            self.sql('INSERT INTO supplier_payment_operations(company_id,project_payment_id) VALUES(%s,%s)',
                     (company, payment))

    def events(self, **filters):
        from urllib.parse import urlencode
        return self.api('director', 'GET', '/project-events?' + urlencode(
            dict(project_name=self.fixture['project'], **filters)))

    def finances(self):
        def query(sql, params=()):
            return execute_director_agent_read_query(sql, params, connection_factory=self.main.get_db)
        return build_director_agent_tools(query)['finances']['fn']({'project': self.fixture['project']}, [2])

    def chat_payments(self):
        # Execute only the actual query block, never the route/AI client.
        _, block = chat_payment_block()
        conn = self.main.get_db()
        try:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                namespace = dict(cur2=cur, payment_visibility_sql='pp.company_id=%s AND pp.project_name=%s',
                                 payment_visibility_params=[2, self.fixture['project']])
                exec(compile(ast.Module(body=[block], type_ignores=[]), '<chat payment query>', 'exec'), namespace)
                return namespace['payments']
        finally:
            conn.close()

    def test_chat_excludes_foreign_company_mappings_before_limit(self):
        self.payment(100, '2026-09-01')
        mappings = [(3, self.payment(900, '2026-09-02', note='Private supplier')) for _ in range(12)]
        self.ledger(mappings)
        self.assertEqual(self.chat_payments(), [(self.fixture['project'], 100, 'Legacy customer')])

    def test_excludes_both_signs_and_foreign_mapping_before_limit_and_sum(self):
        legacy = self.payment(100, '2026-09-01')
        self.payment(-20, '2026-08-31')
        paid = self.payment(900, '2026-09-03', note='Private supplier payment')
        reversal = self.payment(-300, '2026-09-02', note='Private supplier reversal')
        self.ledger([(2, paid), (3, reversal)])
        result = self.events(limit=1)
        self.assertEqual([row['id'] for row in result['items']], [f'payment:{legacy}'])
        self.assertTrue(result['hasMore'])
        all_rows = self.events()['items']
        self.assertEqual(len(all_rows), 2)
        self.assertNotIn('Private supplier', str(all_rows))
        finances = self.finances()
        self.assertEqual(finances[0]['paymentsNet'], 80)
        self.assertEqual(finances[0].get('paymentsScopeNote'), NOTE)

    def test_absent_ledger_preserves_signed_legacy_values(self):
        self.payment(100, '2026-09-01')
        self.payment(-20, '2026-09-02')
        self.assertEqual(sorted(row['amount'] for row in self.events()['items']), [-20, 100])
        self.assertEqual(self.finances()[0]['paymentsNet'], 80)
        self.assertEqual(sorted(row[1] for row in self.chat_payments()), [-20, 100])

    def test_company_project_date_filters_and_existing_role_boundary_remain(self):
        keep = self.payment(100, '2026-09-02')
        self.payment(11, '2026-08-01')
        self.payment(999, '2026-09-02', company=3)
        self.payment(888, '2026-09-02', project='Other project')
        managed = self.payment(700, '2026-09-02')
        self.ledger([(2, managed)])
        rows = self.events(date_from='2026-09-01', date_to='2026-09-03')['items']
        self.assertEqual([row['id'] for row in rows], [f'payment:{keep}'])
        self.assertEqual(self.finances()[0]['paymentsNet'], 111)
        self.api('foreman', 'GET', '/project-events?project_name=' + self.fixture['project'], expected=403)

    def test_present_but_invalid_schema_never_returns_unfiltered_data(self):
        from psycopg2.errors import UndefinedColumn
        self.payment(900, '2026-09-02', note='Must not fall back')
        self.ledger([])
        self.sql('ALTER TABLE supplier_payment_operations RENAME COLUMN project_payment_id TO broken_link')
        with self.assertRaises(UndefinedColumn):
            self.events()
        with self.assertRaises(UndefinedColumn):
            self.finances()
        with self.assertRaises(UndefinedColumn):
            self.chat_payments()
