"""DDL contract checks only; these do not claim PostgreSQL execution."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

PATH = Path(__file__).resolve().parents[3] / 'migrations/versions/0045_supplier_payment_ledger.py'


def migration_statements(method='upgrade'):
    tree = ast.parse(PATH.read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
    statements = []
    namespace = {'op': SimpleNamespace(execute=statements.append)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(PATH), 'exec'), namespace)
    namespace[method]()
    return namespace, statements


class PaymentLedgerMigrationTests(unittest.TestCase):
    def test_revision_and_additive_only(self):
        namespace, statements = migration_statements()
        self.assertEqual(namespace['down_revision'], '0044_supplier_document_bindings')
        self.assertEqual(sum(sql.startswith('CREATE TABLE ') for sql in statements), 3)
        self.assertFalse(any(sql.lstrip().upper().startswith(('UPDATE ', 'DELETE ', 'INSERT ', 'ALTER TABLE ')) for sql in statements))

    def test_identity_and_money_contract(self):
        _, statements = migration_statements()
        sql = '\n'.join(statements)
        for text in ('UNIQUE(company_id,document_kind,document_id)', 'UNIQUE(company_id,request_id)',
                     'PRIMARY KEY(operation_id,document_record_id)', 'NUMERIC(14,2)',
                     'document_kind TEXT NOT NULL', 'document_id INTEGER NOT NULL',
                     'opening_paid<=amount', "kind='reversal' AND reverses_id IS NOT NULL",
                     "btrim(reason)<>''", 'project_payment_id INTEGER NOT NULL UNIQUE'):
            self.assertIn(text, sql)
        for target in ('supplier_payment_operations', 'supplier_payment_documents'):
            self.assertIn('REFERENCES public.' + target + '(id,company_id)', sql)

    def test_history_cannot_be_mutated_or_truncated(self):
        _, statements = migration_statements()
        for table in ('documents', 'operations', 'impacts'):
            self.assertTrue(any('BEFORE UPDATE OR DELETE ON public.supplier_payment_' + table in sql for sql in statements))
            self.assertTrue(any('BEFORE TRUNCATE ON public.supplier_payment_' + table in sql for sql in statements))

    def test_fixed_document_queries_and_final_integrity_guard(self):
        _, statements = migration_statements()
        sql = '\n'.join(statements)
        for text in ('FROM public.supplier_invoices', 'FROM public.warehouse_invoices',
                     'FOR UPDATE', 'IS DISTINCT FROM', 'DEFERRABLE INITIALLY DEFERRED',
                     'FROM public.project_payments', 'EXCEPT', 'NEW.delta', 'NEW.opening_paid'):
            self.assertIn(text, sql)
        self.assertNotIn('EXECUTE format', sql)

    def test_empty_only_downgrade_locks_before_check(self):
        _, statements = migration_statements('downgrade')
        self.assertTrue(statements[0].startswith('LOCK TABLE '))
        for table in ('documents', 'operations', 'impacts'):
            self.assertIn('supplier_payment_' + table, statements[0])
        self.assertIn('read committed', statements[1])
        self.assertIn('EXISTS(SELECT 1 FROM public.supplier_payment_documents)', statements[1])
        self.assertIn('EXISTS(SELECT 1 FROM public.supplier_payment_operations)', statements[1])
        self.assertTrue(statements[2].startswith('DROP TABLE '))

    def test_impact_group_is_sealed_by_database_owned_transaction_id(self):
        _, statements = migration_statements()
        sql = '\n'.join(statements)
        self.assertIn('creation_xid XID8 NOT NULL DEFAULT pg_current_xact_id()', sql)
        self.assertIn('NEW.creation_xid := pg_current_xact_id()', sql)
        self.assertIn('operation.creation_xid IS DISTINCT FROM pg_current_xact_id()', sql)
