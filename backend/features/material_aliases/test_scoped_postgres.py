"""Company alias storage/auth contract on a fresh guarded local PostgreSQL DB."""
import importlib.util
import os
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor
import psycopg2

from . import test_postgres_support as support
from backend.features.material_aliases.scoped import (
    require_alias_actor, save_alias, deactivate_alias, list_aliases, resolve_alias,
)


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Fresh isolated PostgreSQL required')
class ScopedAliasPostgresTests(unittest.TestCase):
    sql = support.AliasPostgresFixture.sql

    @classmethod
    def setUpClass(cls):
        support.AliasPostgresFixture.setUpClass.__func__(cls)
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0024_company_material_aliases.py'
        spec = importlib.util.spec_from_file_location('alias_test_migration', path)
        cls.migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType('alembic')
        alembic.op = None
        with patch.dict(sys.modules, {'alembic': alembic}):
            spec.loader.exec_module(cls.migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                with patch.object(cls.migration, 'op', SimpleNamespace(execute=cur.execute)):
                    cls.migration.upgrade()
        finally:
            conn.close()

    def setUp(self):
        self.sql('DELETE FROM company_material_aliases')
        self.sql('DELETE FROM material_aliases')
        self.sql("INSERT INTO material_aliases(alias_name,canonical_name,project_name) VALUES('Brand','Legacy shared','')")
        self.legacy = self.sql('SELECT * FROM material_aliases')
        self.addCleanup(lambda: self.assertEqual(self.sql('SELECT * FROM material_aliases'), self.legacy))

    def call(self, fn, *, actor='director', company=2, write=False, fail_after=False, **kwargs):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                access = require_alias_actor(cur, self.fixture['users'][actor],
                    company_id=company, allowed_roles=('директор', 'прораб'), write=write,
                    full_project_roles=('директор',), platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
                    client_account_roles=self.main.CLIENT_ACCOUNT_ROLES)
                result = fn(cur, access, **kwargs)
                if fail_after:
                    raise RuntimeError('synthetic late failure')
                return result
        finally:
            conn.close()

    def save(self, **kwargs):
        return self.call(save_alias, write=True, alias_name='Brand', canonical_name='Cement', **kwargs)

    def resolve(self, company=2, project=None):
        conn = self.main.get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                return resolve_alias(cur, company_id=company, project_id=project, name='(Brand)')
        finally:
            conn.close()

    def test_company_wide_matching_does_not_use_legacy_or_other_company(self):
        self.assertIsNone(self.resolve())
        own = self.save()
        self.assertEqual(self.resolve()['id'], own['id'])
        self.assertIsNone(self.resolve(company=3))
        other = self.save(actor='stranger', company=3)
        self.assertEqual(self.resolve(company=3)['id'], other['id'])
        self.assertEqual([r['id'] for r in self.call(list_aliases)], [own['id']])

    def test_project_rule_has_precedence_over_company_rule(self):
        common = self.save()
        exact = self.call(save_alias, write=True, project_id=self.fixture['projectId'],
                          alias_name='BRAND', canonical_name='Exact project')
        self.assertEqual(self.resolve(project=self.fixture['projectId'])['id'], exact['id'])
        self.assertEqual(self.resolve()['id'], common['id'])

    def test_replacement_preserves_history_and_normalized_key(self):
        old = self.save()
        new = self.call(save_alias, write=True, alias_name=' (Brand) ', canonical_name='New material')
        self.assertEqual(new['previous_id'], old['id'])
        self.assertEqual(self.sql('SELECT active FROM company_material_aliases WHERE id=%s', (old['id'],)), [(False,)])
        self.assertEqual(self.resolve()['id'], new['id'])

    def test_late_failure_rolls_back_replacement(self):
        old = self.save()
        before = self.sql('SELECT * FROM company_material_aliases ORDER BY id')
        with self.assertRaises(RuntimeError):
            self.save(fail_after=True)
        self.assertEqual(self.sql('SELECT * FROM company_material_aliases ORDER BY id'), before)
        self.assertEqual(self.resolve()['id'], old['id'])

    def test_foreign_direct_id_cannot_be_deactivated(self):
        foreign = self.save(actor='stranger', company=3)
        with self.assertRaises(HTTPException) as error:
            self.call(deactivate_alias, write=True, alias_id=foreign['id'])
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(self.resolve(company=3)['id'], foreign['id'])

    def test_deactivation_is_idempotent_and_audited(self):
        row = self.save()
        for _ in range(2):
            self.call(deactivate_alias, write=True, alias_id=row['id'])
        self.assertIsNone(self.resolve())
        self.assertEqual(self.sql('SELECT deactivated_by_id FROM company_material_aliases WHERE id=%s', (row['id'],)),
                         [(self.fixture['users']['director']['id'],)])

    def test_project_company_fk_and_resolver_reject_foreign_project(self):
        foreign_project = self.sql("INSERT INTO projects(company_id,name) VALUES(3,'Foreign') RETURNING id")[0][0]
        with self.assertRaises(HTTPException) as error:
            self.save(project_id=foreign_project)
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException):
            self.resolve(project=foreign_project)
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            self.sql('''INSERT INTO company_material_aliases(company_id,project_id,alias_name,alias_key,
                canonical_name,created_by_id) VALUES(2,%s,'A','a','B',%s)''',
                (foreign_project, self.fixture['users']['director']['id']))

    def test_missing_membership_and_read_only_capability_reject_writes(self):
        with self.assertRaises(HTTPException):
            self.save(company=3)
        with self.assertRaises(HTTPException) as error:
            self.call(save_alias, alias_name='A', canonical_name='B')
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(0,)])

    def test_project_assignment_applies_to_listing_and_writing(self):
        project = self.sql("INSERT INTO projects(company_id,name) VALUES(2,'Unassigned') RETURNING id")[0][0]
        for fn, kwargs in ((save_alias, dict(alias_name='A', canonical_name='B')), (list_aliases, {})):
            with self.assertRaises(HTTPException) as error:
                self.call(fn, actor='foreman', write=fn is save_alias, project_id=project, **kwargs)
            self.assertEqual(error.exception.status_code, 403)
        self.save(actor='foreman', project_id=self.fixture['projectId'])

    def test_concurrent_replacements_leave_one_active_version(self):
        gate = Barrier(2)
        def save():
            gate.wait(timeout=5)
            return self.save()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(save) for _ in range(2)]
            rows = [future.result(timeout=20) for future in futures]
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases WHERE active'), [(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(2,)])
        self.assertIn(self.resolve()['id'], [r['id'] for r in rows])

    def test_downgrade_refuses_to_delete_history(self):
        self.save()
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with self.assertRaises(psycopg2.errors.RaiseException):
                with conn, conn.cursor() as cur:
                    with patch.object(self.migration, 'op', SimpleNamespace(execute=cur.execute)):
                        self.migration.downgrade()
        finally:
            conn.close()
        self.assertIsNotNone(self.resolve())

    def test_empty_downgrade_is_transactionally_reversible(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                with patch.object(self.migration, 'op', SimpleNamespace(execute=cur.execute)):
                    self.migration.downgrade()
                cur.execute("SELECT to_regclass('public.company_material_aliases')")
                self.assertIsNone(cur.fetchone()[0])
            conn.rollback()
        finally:
            conn.close()
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(0,)])

    def test_revoked_last_membership_does_not_fall_back_to_profile(self):
        uid = self.fixture['users']['director']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (uid,))
        self.addCleanup(self.sql, 'UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (uid,))
        with self.assertRaises(HTTPException) as error:
            self.save()
        self.assertEqual(error.exception.status_code, 403)

    def test_effective_role_not_global_profile_controls_access(self):
        uid = self.fixture['users']['director']['id']
        self.sql("UPDATE user_company_roles SET role='мастер' WHERE user_id=%s AND company_id=2", (uid,))
        self.addCleanup(self.sql, "UPDATE user_company_roles SET role='директор' WHERE user_id=%s AND company_id=2", (uid,))
        with self.assertRaises(HTTPException) as error:
            self.save()
        self.assertEqual(error.exception.status_code, 403)

    def test_repeatable_read_write_requires_explicit_retry_policy(self):
        conn = self.main.get_db()
        try:
            conn.set_session(autocommit=False, isolation_level='REPEATABLE READ')
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                access = require_alias_actor(cur, self.fixture['users']['director'],
                    company_id=2, allowed_roles=('директор',), write=True)
                with self.assertRaisesRegex(RuntimeError, 'READ COMMITTED'):
                    save_alias(cur, access, alias_name='A', canonical_name='B')
        finally:
            conn.close()
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(0,)])

    def test_downgrade_rejects_a_stale_snapshot_isolation(self):
        conn = self.main.get_db()
        try:
            conn.set_session(autocommit=False, isolation_level='REPEATABLE READ')
            with self.assertRaises(psycopg2.errors.RaiseException):
                with conn, conn.cursor() as cur:
                    with patch.object(self.migration, 'op', SimpleNamespace(execute=cur.execute)):
                        self.migration.downgrade()
        finally:
            conn.close()
        self.assertEqual(self.sql('SELECT count(*) FROM company_material_aliases'), [(0,)])

    def test_downgrade_waits_for_writer_then_refuses_to_delete_committed_history(self):
        writer = self.main.get_db()
        writer.autocommit = False
        def downgrade():
            conn = self.main.get_db()
            conn.autocommit = False
            try:
                with conn, conn.cursor() as cur:
                    with patch.object(self.migration, 'op', SimpleNamespace(execute=cur.execute)):
                        self.migration.downgrade()
            finally:
                conn.close()
        try:
            with writer.cursor(cursor_factory=RealDictCursor) as cur:
                access = require_alias_actor(cur, self.fixture['users']['director'],
                    company_id=2, allowed_roles=('директор',), write=True)
                save_alias(cur, access, alias_name='Brand', canonical_name='Preserved')
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(downgrade)
                try:
                    deadline = time.monotonic() + 3
                    blocked = []
                    while time.monotonic() < deadline:
                        blocked = self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock'
                              AND query LIKE %s""", ('LOCK TABLE company_material_aliases%',))
                        if blocked:
                            break
                        time.sleep(.02)
                    self.assertTrue(blocked, 'Downgrade must lock before checking emptiness')
                finally:
                    writer.commit()
                with self.assertRaises(psycopg2.errors.RaiseException):
                    future.result(timeout=10)
        finally:
            writer.close()
        self.assertEqual(self.resolve()['canonical_name'], 'Preserved')
