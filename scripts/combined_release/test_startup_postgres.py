"""Real PG16 tests: synthetic fixtures only, in a private disposable native cluster."""
import contextlib
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import sys
import importlib.util
import psycopg2
from psycopg2 import sql
SPEC=importlib.util.spec_from_file_location('_startup_fixture_probe',Path(__file__).with_name('server-readonly-check.py'))
probe=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(probe)
runner=probe.startup_module()

ROOT = Path(os.environ.get('STROYKA_TEST_SOURCE_ROOT',str(Path(__file__).resolve().parents[2])))
PG_BIN = Path(os.environ.get('STROYKA_TEST_PG_BIN','/usr/lib/postgresql/16/bin'))

class StartupPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if __import__('socket').gethostname().split('.')[0]=='msk-1-vm-zh4n':
            raise RuntimeError('Synthetic startup fixture must never run on production')
        if not (PG_BIN/'initdb').is_file():raise RuntimeError('Native PostgreSQL 16 initdb is required')
        cls.temp = Path(tempfile.mkdtemp(prefix='startup-pg16-'))
        cls.data = cls.temp/'data'
        cls.env = dict(os.environ, DB_HOST=str(cls.temp), DB_PORT='6547', DB_USER='chain_test', DB_NAME='stroyka', DB_PASSWORD='', AUTH_SECRET=__import__('secrets').token_urlsafe(48))
        try:
            subprocess.run([PG_BIN/'initdb','-D',cls.data,'-A','trust','-U','chain_test','--no-locale','-E','UTF8'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run([PG_BIN/'pg_ctl','-D',cls.data,'-l',cls.temp/'postgres.log','-o',f"-F -h '' -k {cls.temp} -p 6547",'-w','start'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run([PG_BIN/'createdb','-h',cls.temp,'-p','6547','-U','chain_test','stroyka'],check=True)
            cls.settings = dict(host=str(cls.temp), port=6547,user='chain_test',dbname='stroyka')
            tree = ast.parse((ROOT/'backend/main.py').read_text())
            fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='init_db')
            ddl = ast.literal_eval(next(n.value.args[0] for n in fn.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='execute'))
            with contextlib.closing(psycopg2.connect(**cls.settings)) as conn, conn:
                with conn.cursor() as cur:
                    # Current production startup expects these tables to exist. This
                    # fixture creates them from their exact source definitions; no
                    # startup code is edited or disabled.
                    for name in ('estimates','warehouse_main','work_journal','interim_acts','hidden_works_acts'):
                        cur.execute(re.search(r'CREATE TABLE IF NOT EXISTS '+name+r' \(.*?\n        \);',ddl,re.S)[0])
                    cur.execute(ddl)
                    cur.execute('CREATE TABLE alembic_version (version_num varchar(64) NOT NULL)')
                    cur.execute("INSERT INTO alembic_version VALUES ('0102_job_candidates')")
            result=subprocess.run([sys.executable,'-B','-c','import backend.main'],cwd=ROOT,env=cls.env,capture_output=True,text=True,timeout=60)
            if result.returncode: raise RuntimeError(result.stderr[-2500:])
            # Fresh bootstrap seeds users after the membership insert. A second
            # synthetic startup establishes existing memberships before no-op tests.
            result=subprocess.run([sys.executable,'-B','-c','import backend.main'],cwd=ROOT,env=cls.env,capture_output=True,text=True,timeout=60)
            if result.returncode: raise RuntimeError(result.stderr[-2500:])
        except BaseException:
            cls.tearDownClass();raise
    @classmethod
    def tearDownClass(cls):
        if (cls.data/'postmaster.pid').exists():
            subprocess.run([PG_BIN/'pg_ctl','-D',cls.data,'-m','fast','-w','stop'],stdout=subprocess.DEVNULL,check=True)
        shutil.rmtree(cls.temp)
    def inspect(self,plan=None):
        conn=psycopg2.connect(**self.settings)
        try:return runner.inspect_connection(conn,plan or runner.load_plan())
        finally:conn.close()
    def fingerprint(self, dbname=None):
        settings=dict(self.settings)
        if dbname: settings['dbname']=dbname
        with contextlib.closing(psycopg2.connect(**settings)) as conn, conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
                values={}
                for (table,) in cur.fetchall():
                    cur.execute(sql.SQL("SELECT md5(coalesce(string_agg(row_to_json(t)::text,'|' ORDER BY row_to_json(t)::text),'')) FROM public.{} t").format(sql.Identifier(table)))
                    values[table]=cur.fetchone()[0]
                cur.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
                return values,cur.fetchall()
    def test_clean_snapshot_runs_all_guards_without_row_or_sequence_changes(self):
        before=self.fingerprint();report=self.inspect()
        self.assertEqual(len(report['counts']),31)
        self.assertTrue(report['business_guards_satisfied'],report['counts'])
        self.assertFalse(report['maintenance_boundary_proven'])
        self.assertEqual(before,self.fingerprint())
        (self.temp/'startup-clean-report.json').write_text(json.dumps(report,indent=2))
    def test_real_custom_backup_can_restore_in_disposable_database(self):
        backup=self.temp/'synthetic-fixture.dump'
        common=['-h',str(self.temp),'-p','6547','-U','chain_test']
        before=self.fingerprint()
        subprocess.run([PG_BIN/'pg_dump',*common,'--format=custom','--file',backup,'stroyka'],check=True)
        subprocess.run([PG_BIN/'pg_restore','--list',backup],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([PG_BIN/'createdb',*common,'stroyka_backup_restore_test'],check=True)
        subprocess.run([PG_BIN/'pg_restore',*common,'--exit-on-error','--dbname=stroyka_backup_restore_test',backup],check=True)
        self.assertEqual(before,self.fingerprint('stroyka_backup_restore_test'))

    def test_real_postgres_rejects_mutating_query(self):
        plan=copy.deepcopy(runner.load_plan());plan['guards'][0]['sql']='UPDATE public.users SET active=false RETURNING id'
        with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):self.inspect(plan)
    def test_nonzero_user_repair_is_not_accepted(self):
        with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
            with conn.cursor() as cur:cur.execute('UPDATE public.users SET active=NULL WHERE id=(SELECT min(id) FROM public.users)')
        try:self.assertFalse(self.inspect()['business_guards_satisfied'])
        finally:
            with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
                with conn.cursor() as cur:cur.execute('UPDATE public.users SET active=true WHERE active IS NULL')
    def test_estimate_json_repair_is_not_accepted(self):
        with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO public.estimates (name,sections_json,company_id) VALUES (%s,%s,1) RETURNING id',('Synthetic test',json.dumps([{'items':[{'itemType':'material','quantity':-1}]}])))
                key=cur.fetchone()[0]
        try:
            result=self.inspect();self.assertFalse(result['business_guards_satisfied']);self.assertEqual(result['estimate_json']['would_update'],1)
        finally:
            with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
                with conn.cursor() as cur:cur.execute('DELETE FROM public.estimates WHERE id=%s',(key,))


    def test_large_document_matches_observed_size_without_writes(self):
        with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO estimates (name,sections_json) VALUES ('synthetic-size-test',%s) RETURNING id",(' '*(1107980-2)+'[]',))
                identity=cur.fetchone()[0]
        try:
            before=self.fingerprint();report=self.inspect()
            self.assertEqual(report['estimate_json']['would_update'],0)
            self.assertEqual(report['estimate_json']['startup_error'],0)
            self.assertEqual(before,self.fingerprint())
        finally:
            with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
                with conn.cursor() as cur:cur.execute('DELETE FROM estimates WHERE id=%s',(identity,))
    def test_oversize_document_is_refused(self):
        with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO estimates (name,sections_json) VALUES ('synthetic-rejection-test',%s) RETURNING id",(' '* (runner.MAX_JSON_VALUE_BYTES-1)+'[]',))
                identity=cur.fetchone()[0]
        try:
            before=self.fingerprint()
            with self.assertRaises(runner.CheckError):self.inspect()
            self.assertEqual(before,self.fingerprint())
        finally:
            with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
                with conn.cursor() as cur:cur.execute('DELETE FROM estimates WHERE id=%s',(identity,))
    def test_reviewed_trigger_and_actual_startup_preserve_business_rows(self):
        import maintenance
        tree=ast.parse((ROOT/'migrations/versions/0038_supplier_customer_team.py').read_text())
        ddl=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMA_SQL' for t in n.targets)).split('CREATE TABLE supplier_customer_assignments')[0]
        with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
            with conn.cursor() as cur:cur.execute(ddl)
        try:
            report=self.inspect()
            trigger=next(t for t in report['catalog']['triggers'] if t['name']=='supplier_team_epoch_change')
            self.assertEqual(trigger['definition_sha256'],'9d0453060a7d107addbde23cffe202a164dfa0b7296d103adb75557960dad9b2')
            maintenance.require_clean_snapshot(report)
            before=self.fingerprint()
            result=subprocess.run([sys.executable,'-B','-c','import backend.main'],cwd=ROOT,env=self.env,capture_output=True,timeout=60)
            self.assertEqual(result.returncode,0,'Synthetic application startup failed')
            after=self.fingerprint()
            self.assertEqual(before[0],after[0], 'Startup changed logical business rows')
            before_sequences=dict(before[1]);after_sequences=dict(after[1])
            changed={name for name in before_sequences if before_sequences[name]!=after_sequences[name]}
            self.assertTrue(changed)
            self.assertLessEqual(changed,{'users_id_seq','site_price_rules_id_seq','material_norms_id_seq','user_company_roles_id_seq'})
            maintenance.require_clean_snapshot(self.inspect())
        finally:
            with contextlib.closing(psycopg2.connect(**self.settings)) as conn, conn:
                with conn.cursor() as cur:cur.execute('DROP TRIGGER supplier_team_epoch_change ON users; DROP FUNCTION advance_supplier_team_epoch(); ALTER TABLE users DROP COLUMN supplier_team_epoch')

if __name__=='__main__':unittest.main(verbosity=2)
