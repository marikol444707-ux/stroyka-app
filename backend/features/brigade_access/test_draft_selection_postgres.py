"""Real SQL selection/locking on a fresh launcher-owned PostgreSQL cluster.

Exercises the automatic selector shared by create, assignment and distribution.
The small transaction writer below does not claim to exercise their HTTP routes;
explicit contract selection and manual command replay keep their own contracts.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
import unittest

from fastapi import HTTPException
import psycopg2

from .service import find_existing_brigade_contract_id

ROOT = Path(__file__).resolve().parents[3]
RUN = os.environ.get('BRIGADE_DRAFT_RUN_POSTGRES') == '1'


@unittest.skipUnless(RUN, 'Run scripts/run_brigade_draft_tests.py for an isolated database.')
class DraftSelectionPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = os.environ.get('BRIGADE_DRAFT_TEST_ROOT', '')
        if not raw:
            raise RuntimeError('Missing disposable database fixture')
        work = Path(raw).resolve()
        if work.parent != (ROOT / 'tmp').resolve() or not work.name.startswith('bg-'):
            raise RuntimeError('Not a repo-local disposable fixture')
        expected = {'kind': 'brigade-draft-test-v1', 'root': str(work),
                    'database': 'brigade_draft_test', 'user': 'brigade_test', 'port': '6547'}
        if json.loads((work / 'fixture.json').read_text()) != expected:
            raise RuntimeError('Invalid fixture marker')
        pid = (work / 'data/postmaster.pid').read_text().splitlines()
        if Path(pid[1]).resolve() != work / 'data' or pid[3] != '6547':
            raise RuntimeError('Postmaster is not owned by this fixture')
        cls.settings = dict(host=str(work), port=6547, user='brigade_test',
                            dbname='brigade_draft_test', connect_timeout=5)
        with cls.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database(),current_user,current_setting('listen_addresses')")
            if cur.fetchone() != ('brigade_draft_test', 'brigade_test', ''):
                raise RuntimeError('Not the intended socket-only database')
            cur.execute('''CREATE TABLE brigade_contracts (
                id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL, project_id INTEGER NOT NULL,
                work_package TEXT, contractor_id INTEGER, brigade_name TEXT, status TEXT,
                total_amount NUMERIC DEFAULT 0, notes TEXT
            ); CREATE TABLE brigade_contract_items (
                id SERIAL PRIMARY KEY, contract_id INTEGER REFERENCES brigade_contracts(id),
                name TEXT, amount NUMERIC
            ); CREATE TABLE draft_selection_effects (description TEXT);''')

    @classmethod
    def connect(cls):
        return psycopg2.connect(**cls.settings, options='-c statement_timeout=8000 -c lock_timeout=6000')

    def sql(self, sql, args=()):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else []

    def setUp(self):
        self.sql('TRUNCATE brigade_contract_items,brigade_contracts,draft_selection_effects RESTART IDENTITY')

    def add(self, *, company=4, project=17, package='Основная', user=9,
            name='Одинаковое имя', status='Черновик', with_item=False):
        result = self.sql('''INSERT INTO brigade_contracts
            (company_id,project_id,work_package,contractor_id,brigade_name,status,total_amount,notes)
            VALUES(%s,%s,%s,%s,%s,%s,123,'immutable original') RETURNING id''',
            (company, project, package, user, name, status))[0][0]
        if with_item:
            self.sql('INSERT INTO brigade_contract_items(contract_id,name,amount) VALUES(%s,%s,123)',
                     (result, 'Original work'))
        return result

    def select(self, *, company=4, project=17, package='Основная', user=9, name='Одинаковое имя'):
        with self.connect() as conn, conn.cursor() as cur:
            return find_existing_brigade_contract_id(cur, company, project, package, user, name)

    def snapshot(self):
        return [self.sql('SELECT to_jsonb(t) FROM ' + table + ' t ORDER BY id')
                for table in ('brigade_contracts', 'brigade_contract_items')]

    def test_signed_and_closed_contracts_are_not_automatic_targets(self):
        for status in ('Подписан', 'Закрыт', 'Завершён', 'Аннулирован', 'Удалён', 'Удален'):
            with self.subTest(status=status):
                self.setUp()
                self.add(status=status, with_item=True)
                before = self.snapshot()
                self.assertIsNone(self.select())
                self.assertEqual(self.snapshot(), before)

    def test_draft_is_selected_even_when_signed_contract_has_existing_work(self):
        draft = self.add()
        self.add(status='Подписан', with_item=True)
        before = self.snapshot()
        self.assertEqual(self.select(), draft)
        self.assertEqual(self.snapshot(), before)

    def test_new_work_goes_into_new_draft_and_preserves_signed_original(self):
        signed = self.add(status='Подписан', with_item=True)
        original = self.snapshot()
        with self.connect() as conn, conn.cursor() as cur:
            target = find_existing_brigade_contract_id(cur, 4, 17, 'Основная', 9, 'Одинаковое имя')
            if target is None:
                cur.execute('''INSERT INTO brigade_contracts
                    (company_id,project_id,work_package,contractor_id,brigade_name,status)
                    VALUES(4,17,'Основная',9,'Одинаковое имя','Черновик') RETURNING id''')
                target = cur.fetchone()[0]
            cur.execute('INSERT INTO brigade_contract_items(contract_id,name,amount) VALUES(%s,%s,10)',
                        (target, 'New work'))
        self.assertNotEqual(target, signed)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM brigade_contracts t WHERE id=%s', (signed,)), original[0])
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM brigade_contract_items t WHERE contract_id=%s ORDER BY id',
                                 (signed,)), original[1])
        self.assertEqual(self.sql('SELECT status FROM brigade_contracts WHERE id=%s', (target,)), [('Черновик',)])

    def test_ambiguous_drafts_raise_409_and_roll_back_prior_effects(self):
        self.add()
        self.add(with_item=True)
        before = self.snapshot()
        with self.assertRaises(HTTPException) as raised:
            with self.connect() as conn, conn.cursor() as cur:
                cur.execute("INSERT INTO draft_selection_effects VALUES('prior transaction effect')")
                find_existing_brigade_contract_id(cur, 4, 17, 'Основная', 9, 'Одинаковое имя')
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.sql('SELECT * FROM draft_selection_effects'), [])
        self.assertEqual(self.snapshot(), before)

    def test_company_project_package_and_exact_account_boundaries(self):
        self.add(company=5, with_item=True)
        self.add(project=18, with_item=True)
        self.add(package='Другое', with_item=True)
        self.add(user=10, with_item=True)
        self.add(user=None, with_item=True)
        self.assertIsNone(self.select())
        target = self.add(name='Новое имя того же пользователя')
        self.assertEqual(self.select(), target)

    def test_manual_name_only_selects_unlinked_identity_in_exact_scope(self):
        self.add(with_item=True)
        self.add(user=None, company=5, with_item=True)
        target = self.add(user=None, name='  Бригада Север  ')
        self.assertEqual(self.select(user=None, name=' Бригада Север '), target)
        self.assertIsNone(self.select(user=9, name='Бригада Север', project=99))

    def test_ambiguous_manual_drafts_are_not_guessed(self):
        self.add(user=None, name='Бригада Север')
        self.add(user=None, name=' Бригада Север ', with_item=True)
        with self.assertRaises(HTTPException) as raised:
            self.select(user=None, name='Бригада Север')
        self.assertEqual(raised.exception.status_code, 409)

    def test_null_and_empty_legacy_status_are_drafts(self):
        for status in (None, ''):
            with self.subTest(status=status):
                self.setUp()
                target = self.add(status=status)
                self.assertEqual(self.select(), target)

    def test_empty_package_uses_existing_default_package_draft(self):
        for stored in (None, '', 'Основная'):
            with self.subTest(stored=stored):
                self.setUp()
                target = self.add(package=stored)
                self.assertEqual(self.select(package=''), target)

    def test_two_concurrent_first_writers_reuse_one_draft(self):
        barrier = threading.Barrier(2)
        def write():
            with self.connect() as conn, conn.cursor() as cur:
                barrier.wait(timeout=5)
                target = find_existing_brigade_contract_id(cur, 4, 17, 'Основная', 9, 'Одинаковое имя')
                if target is None:
                    cur.execute('''INSERT INTO brigade_contracts
                        (company_id,project_id,work_package,contractor_id,brigade_name,status)
                        VALUES(4,17,'Основная',9,'Одинаковое имя','Черновик') RETURNING id''')
                    target = cur.fetchone()[0]
                cur.execute('INSERT INTO brigade_contract_items(contract_id,name,amount) VALUES(%s,%s,10)',
                            (target, 'Concurrent work'))
                return target
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = list(pool.map(lambda _: write(), range(2)))
        self.assertEqual(a, b)
        self.assertEqual(self.sql('SELECT count(*) FROM brigade_contracts'), [(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM brigade_contract_items WHERE contract_id=%s', (a,)), [(2,)])
