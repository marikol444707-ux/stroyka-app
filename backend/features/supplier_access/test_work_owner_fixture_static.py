"""Offline fixture regression checks: no application, HTTP or PostgreSQL startup."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from . import test_postgres_chain_support as fixture


class WorkOwnerFixtureStaticTests(unittest.TestCase):
    def test_reuses_complete_owner_upgrades_and_exact_project_key(self):
        statements = fixture._work_owner_statements()
        self.assertEqual(statements[0],
            'CREATE UNIQUE INDEX quality_projects_id_company_idx ON projects(id,company_id)')
        expected = [sql for name in fixture.WORK_OWNER_MIGRATIONS
                    for sql in fixture._migration_statements(name)]
        self.assertEqual(statements[1:], expected)
        for table in ('room_works', 'interim_acts', 'document_versions'):
            self.assertTrue(any(f'ALTER TABLE {table} ADD CONSTRAINT {table}_owner_fk '
                'FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)' == sql
                for sql in statements))
            self.assertTrue(any(f'{table}_owner_pair CHECK (' in sql for sql in statements))
        self.assertFalse(any('UPDATE ' in sql or 'alembic_version' in sql for sql in statements))

    def test_changed_project_prerequisite_fails_closed(self):
        with patch.object(fixture, '_migration_statements', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'prerequisite changed'):
                fixture._work_owner_statements()

    def cursor(self, *, missing=None, invalid_fk=False, invalid_check=False, bad_index=False):
        cur = Mock()
        def execute(sql, params=()):
            if 'information_schema.columns' in sql:
                table = params[0]
                columns = {'company_id', 'project_id', 'owner_scope'}
                if table == missing:
                    columns.remove('company_id')
                rows = [{'column_name': name} for name in columns]
            elif 'pg_indexes' in sql:
                rows = [{'indexdef': 'CREATE ' + ('' if bad_index else 'UNIQUE ') +
                    'INDEX quality_projects_id_company_idx ON public.projects USING btree (id, company_id)'}]
            else:
                table = params[0].split('.')[1]
                names = [('ck_api_errors_owner_scope', 'c')] if table == 'api_errors' else [
                    ('rooms_exact_project_owner' if table == 'rooms' else table + '_owner_fk', 'f'),
                    (table + '_owner_pair', 'c')]
                rows = [dict(conname=name, contype=kind,
                    convalidated=not (invalid_check and kind == 'c'),
                    definition='FOREIGN KEY (project_id, company_id) REFERENCES projects (id, company_id)'
                    if not invalid_fk else 'FOREIGN KEY (project_id) REFERENCES projects (id)')
                    for name, kind in names]
            cur.fetchall.return_value = rows
        cur.execute.side_effect = execute
        return cur

    def test_readiness_accepts_complete_catalog(self):
        fixture._assert_work_owner_schema(self.cursor())

    def test_readiness_rejects_missing_columns(self):
        for table in ('room_works', 'interim_acts', 'document_versions', 'api_errors'):
            with self.subTest(table=table), self.assertRaisesRegex(RuntimeError, table + ' missing'):
                fixture._assert_work_owner_schema(self.cursor(missing=table))

    def test_readiness_rejects_wrong_fk_unvalidated_check_and_nonunique_key(self):
        for kwargs in ({'invalid_fk': True}, {'invalid_check': True}, {'bad_index': True}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(RuntimeError, 'not ready'):
                fixture._assert_work_owner_schema(self.cursor(**kwargs))

    def test_preparation_reuses_logger_schema_and_propagates_transaction_error(self):
        runtime = Mock()
        # Model the connection transaction/context protocol only; no driver connection.
        from unittest.mock import MagicMock
        conn = MagicMock()
        runtime.get_db.return_value = conn
        cur = conn.cursor.return_value.__enter__.return_value
        with patch.object(fixture, '_work_owner_statements', return_value=['DDL']), \
             patch('backend.features.api_error_ownership.migration._ensure_schema') as logger, \
             patch.object(fixture, '_assert_work_owner_schema', side_effect=RuntimeError('not ready')):
            with self.assertRaisesRegex(RuntimeError, 'not ready'):
                fixture._initialize_work_owners(runtime)
        cur.execute.assert_called_once_with('DDL')
        logger.assert_called_once_with(cur)
        from psycopg2.extras import RealDictCursor
        conn.cursor.assert_called_once_with(cursor_factory=RealDictCursor)
        self.assertIs(conn.__exit__.call_args.args[0], RuntimeError)
        conn.close.assert_called_once()

    def test_profile_is_opt_in_and_precedes_seed_and_runtime_import(self):
        import inspect
        self.assertFalse(inspect.signature(fixture.build_fixture).parameters['work_owners'].default)
        source = inspect.getsource(fixture._build_isolated_fixture)
        self.assertLess(source.index('prerequisites = _initialize_schema'), source.index('_initialize_work_owners(schema_runtime)'))
        self.assertLess(source.index('_initialize_work_owners(schema_runtime)'), source.index('fixture = _seed(main)'))
        self.assertLess(source.index('_initialize_work_owners(schema_runtime)'), source.index('main = _module_from_source'))
        root = Path(fixture.__file__).resolve().parents[3]
        for name in ('material_traceability/test_transfer_workflow_postgres.py',
                     'contractor_contract_parties/test_postgres.py'):
            self.assertIn('build_fixture(work_owners=True)', (root / 'backend/features' / name).read_text())
