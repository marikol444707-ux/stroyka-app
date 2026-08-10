from concurrent.futures import ThreadPoolExecutor, wait
import copy
import hashlib
import os
import re
import threading
import unittest
from unittest import mock

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from backend.features.supply_recommendation_preview import (
    material_capability_confirmation as confirmation,
    material_capability_proof as proof,
    material_capability_schema as schema,
    material_capability_schema_contract as schema_contract,
    material_capability_schema_probe as schema_probe,
    material_capability_writer as writer,
)
from backend.features.supply_recommendation_preview.test_rfq_content import (
    valid_report,
)
from backend.features.supply_recommendation_preview.test_material_capability_confirmation import (
    _valid_dependencies,
)


RUN_POSTGRES = os.getenv("A8_4C_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("A8_4C_TEST_DATABASE_URL", "")
SELECTED = {"requestId": 21, "requestItemIndex": 0}


def _plan_index_names(node):
    names = []
    if type(node) is dict:
        if type(node.get("Index Name")) is str:
            names.append(node["Index Name"])
        for child in node.get("Plans") or []:
            names.extend(_plan_index_names(child))
    return names


class _ObservedCursor:
    def __init__(self, cursor, observation, before_execute=None):
        self._cursor = cursor
        self._observation = observation
        self._before_execute = before_execute

    def execute(self, sql, params=None):
        sql = str(sql)
        self._observation["sql"].append((sql, tuple(params or ())))
        if self._before_execute is not None:
            self._before_execute(sql)
        return self._cursor.execute(sql, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._cursor.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _ObservedConnection:
    def __init__(self, connection, *, label=None, before_execute=None):
        self._connection = connection
        self._before_execute = before_execute
        self.observation = {
            "label": label,
            "sessions": [],
            "sql": [],
            "commits": 0,
            "rollbacks": 0,
        }

    def set_session(self, **kwargs):
        self.observation["sessions"].append(dict(kwargs))
        return self._connection.set_session(**kwargs)

    def cursor(self, *args, **kwargs):
        return _ObservedCursor(
            self._connection.cursor(*args, **kwargs),
            self.observation,
            self._before_execute,
        )

    def commit(self):
        self.observation["commits"] += 1
        return self._connection.commit()

    def rollback(self):
        self.observation["rollbacks"] += 1
        return self._connection.rollback()

    def close(self):
        return self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


@unittest.skipUnless(
    RUN_POSTGRES and TEST_DATABASE_URL,
    "set A8_4C_RUN_POSTGRES_INTEGRATION=1 and a dedicated a8_4c_* database URL",
)
class MaterialCapabilityWriterPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = parse_dsn(TEST_DATABASE_URL).get("dbname", "")
        if not re.fullmatch(r"a8_4c_[a-z0-9_]+", configured):
            raise RuntimeError(
                "A8.4c PostgreSQL tests require a dedicated a8_4c_* database"
            )

        cls.connection = psycopg2.connect(TEST_DATABASE_URL)
        cls.connection.autocommit = True
        with cls.connection.cursor() as cur:
            cur.execute("SELECT pg_catalog.current_database()")
            if cur.fetchone()[0] != configured:
                raise RuntimeError("dedicated database identity changed")

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "connection"):
            return
        cls._drop_schema()
        cls.connection.close()

    def setUp(self):
        self.writer_connections = []
        self.proof_transactions = []
        self._reset_schema()
        dry_run = schema.run_material_capability_schema_migration(
            self._migration_db
        )
        applied = schema.run_material_capability_schema_migration(
            self._migration_db,
            apply=True,
            confirm=schema.APPLY_CONFIRMATION,
            expected_change_count=dry_run["changeCount"],
            expected_plan_sha256=dry_run["planSha256"],
        )
        if applied.get("complete") is not True:
            raise RuntimeError("material capability schema was not applied")

    @classmethod
    def _drop_capability_schema(cls):
        with cls.connection.cursor() as cur:
            cur.execute(
                "DROP TABLE IF EXISTS "
                "public.supplier_material_capability_assertions CASCADE"
            )
            cur.execute(
                "DROP FUNCTION IF EXISTS public."
                "guard_supplier_material_capability_assertion_insert() CASCADE"
            )
            cur.execute(
                "DROP FUNCTION IF EXISTS public."
                "reject_supplier_material_capability_assertion_mutation() "
                "CASCADE"
            )

    @classmethod
    def _drop_schema(cls):
        cls._drop_capability_schema()
        with cls.connection.cursor() as cur:
            for table in (
                "user_sessions",
                "company_supplier_links",
                "user_company_roles",
                "suppliers",
                "users",
                "companies",
                "platform_accounts",
            ):
                cur.execute("DROP TABLE IF EXISTS public." + table + " CASCADE")

    @classmethod
    def _reset_schema(cls):
        cls._drop_schema()
        with cls.connection.cursor() as cur:
            cur.execute(
                """CREATE TABLE public.platform_accounts (
                     id SERIAL PRIMARY KEY,
                     active BOOLEAN,
                     status VARCHAR(50)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.companies (
                     id SERIAL PRIMARY KEY,
                     platform_account_id INTEGER,
                     active BOOLEAN
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.users (
                     id SERIAL PRIMARY KEY,
                     role VARCHAR(100),
                     active BOOLEAN,
                     two_factor_enabled BOOLEAN
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.user_company_roles (
                     id SERIAL PRIMARY KEY,
                     user_id INTEGER,
                     company_id INTEGER,
                     platform_account_id INTEGER,
                     role VARCHAR(100),
                     active BOOLEAN,
                     CONSTRAINT uq_a84c_membership_user_company_role
                       UNIQUE (user_id,company_id,role)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.suppliers (
                     id SERIAL PRIMARY KEY,
                     status VARCHAR(100),
                     user_id INTEGER
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.company_supplier_links (
                     id SERIAL PRIMARY KEY,
                     company_id INTEGER,
                     supplier_id INTEGER,
                     platform_account_id INTEGER,
                     status VARCHAR(50)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.user_sessions (
                     id SERIAL PRIMARY KEY,
                     user_id INTEGER,
                     session_hash VARCHAR(64),
                     expires_at TIMESTAMPTZ,
                     revoked_at TIMESTAMPTZ,
                     two_factor_passed BOOLEAN,
                     CONSTRAINT uq_a84c_user_session_hash
                       UNIQUE (session_hash)
                   )"""
            )

    @staticmethod
    def _migration_db():
        connection = psycopg2.connect(TEST_DATABASE_URL)
        connection.autocommit = True
        return connection

    def _writer_db(self):
        observed = _ObservedConnection(psycopg2.connect(TEST_DATABASE_URL))
        self.writer_connections.append(observed)
        return observed

    def _fixture(self):
        session_hash = hashlib.sha256(b"a8.4c-live-session").hexdigest()
        cross_company_hash = hashlib.sha256(
            b"a8.4c-cross-company-session"
        ).hexdigest()
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                """INSERT INTO public.users
                     (id,role,active,two_factor_enabled)
                     VALUES
                     (41,'директор',TRUE,TRUE),
                     (42,'директор',TRUE,TRUE),
                     (401,'поставщик',TRUE,FALSE)"""
            )
            cur.execute(
                """INSERT INTO public.user_company_roles
                     (id,user_id,company_id,platform_account_id,role,active)
                     VALUES
                     (51,41,4,1,'директор',TRUE),
                     (52,42,5,1,'директор',TRUE)"""
            )
            cur.execute(
                "INSERT INTO public.suppliers(id,status,user_id) "
                "VALUES (71,'Активный',401)"
            )
            cur.execute(
                """INSERT INTO public.company_supplier_links
                     (id,company_id,supplier_id,platform_account_id,status)
                     VALUES (61,4,71,1,'Активный')"""
            )
            cur.execute(
                """INSERT INTO public.user_sessions
                     (id,user_id,session_hash,expires_at,revoked_at,
                      two_factor_passed)
                     VALUES
                     (81,41,%s,clock_timestamp()+interval '1 hour',NULL,TRUE),
                     (82,42,%s,clock_timestamp()+interval '1 hour',NULL,TRUE)""",
                (session_hash, cross_company_hash),
            )
        return {
            "company_id": 4,
            "account_id": 1,
            "link_id": 61,
            "supplier_id": 71,
            "supplier_user_id": 401,
            "actor_user_id": 41,
            "membership_id": 51,
            "session_hash": session_hash,
            "cross_company_hash": cross_company_hash,
            "material_hash": "b" * 64,
            "subject_hash": "c" * 64,
        }

    def _authentication(self, fixture, session_hash=None):
        return {
            "authenticationKind": "cookie_session",
            "sessionHash": session_hash or fixture["session_hash"],
        }

    @staticmethod
    def _confirmation_command(fixture):
        return {
            "companyId": fixture["company_id"],
            "companySupplierLinkId": fixture["link_id"],
            "supplierId": fixture["supplier_id"],
            "confirmationSubjectSha256": fixture["subject_hash"],
        }

    def _collect_real_proof_snapshot(self, cur, prepared, fixture):
        cur.execute("SHOW transaction_read_only")
        read_only = cur.fetchone()["transaction_read_only"]
        cur.execute("SHOW transaction_isolation")
        isolation = cur.fetchone()["transaction_isolation"]
        self.proof_transactions.append((read_only, isolation))

        source = {
            "companyId": prepared["source"]["companyId"],
            "requestId": 21,
            "requestItemIndex": 0,
            "requestItemSha256": "1" * 64,
            "rfqContentSha256": "2" * 64,
            "supplierEligibilitySha256": "3" * 64,
            "materialIdentitySha256": fixture["material_hash"],
        }
        readiness = schema_probe.collect_material_capability_schema_readiness(
            cur
        )
        if readiness != {
            "contractVersion": 1,
            "complete": True,
            "blockers": [],
        }:
            result = proof._result(
                source=source,
                confirmation_sha256="d" * 64,
                confirmation_subject_count=0,
                state="incomplete",
                blockers=[
                    "supply_supplier_material_schema_not_ready"
                ],
            )
            return result

        subjects = [{
            "companySupplierLinkId": fixture["link_id"],
            "supplierId": fixture["supplier_id"],
            "materialIdentitySha256": fixture["material_hash"],
            "confirmationSubjectSha256": fixture["subject_hash"],
        }]
        rows = proof._read_assertions(cur, fixture["company_id"], subjects)
        proof_subjects = proof._validated_proof_subjects(
            source, subjects, rows
        )
        state, blockers = proof._state_for_subjects(proof_subjects)
        result = proof._result(
            source=source,
            confirmation_sha256="d" * 64,
            confirmation_subject_count=1,
            state=state,
            blockers=blockers,
            proof_subjects=proof_subjects,
        )
        return result

    def _confirm(self, fixture, *, session_hash=None):
        with mock.patch.object(
            writer,
            "_collect_proof",
            side_effect=lambda cur, prepared: self._collect_real_proof_snapshot(
                cur, prepared, fixture
            ),
        ):
            return self._confirmation_write(
                self._writer_db, fixture, session_hash=session_hash
            )

    def _confirmation_write(
        self, get_db, fixture, *, session_hash=None,
    ):
        return writer.run_material_capability_confirmation_write(
            get_db,
            valid_report(),
            SELECTED,
            self._authentication(fixture, session_hash),
            self._confirmation_command(fixture),
        )

    def _revoke(self, fixture, assertion_id, *, session_hash=None):
        return self._revocation_write(
            self._writer_db,
            fixture,
            assertion_id,
            session_hash=session_hash,
        )

    def _revocation_write(
        self, get_db, fixture, assertion_id, *, session_hash=None,
    ):
        return writer.run_material_capability_revocation_write(
            get_db,
            self._authentication(fixture, session_hash),
            {
                "companyId": fixture["company_id"],
                "confirmationAssertionId": assertion_id,
            },
        )

    def _assertion_count(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT pg_catalog.count(*) FROM "
                "public.supplier_material_capability_assertions"
            )
            return cur.fetchone()[0]

    def _schema_plan(self):
        return schema.run_material_capability_schema_migration(
            self._migration_db
        )

    def _apply_schema_plan(self, plan, get_db=None):
        return schema.run_material_capability_schema_migration(
            get_db or self._migration_db,
            apply=True,
            confirm=schema.APPLY_CONFIRMATION,
            expected_change_count=plan["changeCount"],
            expected_plan_sha256=plan["planSha256"],
        )

    def _explain_indexes(self, sql, params):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET enable_seqscan=off")
            cur.execute("EXPLAIN (FORMAT JSON,COSTS OFF) " + sql, params)
            plan = cur.fetchone()["QUERY PLAN"][0]["Plan"]
            return _plan_index_names(plan)

    def _assert_writer_lock_order(self, connection):
        calls = [
            " ".join(sql.split())
            for sql, _params in connection.observation["sql"]
        ]
        self.assertGreaterEqual(len(calls), 8)
        self.assertEqual(calls[:4], [
            "SET LOCAL statement_timeout='60s'",
            "SET LOCAL lock_timeout='5s'",
            "SET LOCAL idle_in_transaction_session_timeout='60s'",
            "SET LOCAL search_path=pg_catalog,public",
        ])
        self.assertEqual(
            calls[4],
            "LOCK TABLE public.companies "
            "IN SHARE UPDATE EXCLUSIVE MODE",
        )
        self.assertEqual(
            calls[5],
            "LOCK TABLE public.supplier_material_capability_assertions "
            "IN SHARE ROW EXCLUSIVE MODE",
        )
        self.assertEqual(
            calls[6],
            "SELECT pg_catalog.pg_advisory_xact_lock(%s)",
        )
        self.assertIn("FROM public.user_sessions session", calls[7])
        first_select_or_dml = next(
            index for index, sql in enumerate(calls)
            if sql.upper().startswith((
                "SELECT ", "INSERT ", "UPDATE ", "DELETE ",
            ))
        )
        self.assertLess(5, first_select_or_dml)

    def test_public_proof_collector_drives_real_confirmation_and_idempotency(self):
        fixture = self._fixture()
        content, eligibility = _valid_dependencies(candidate_count=1)
        content["readOnlyTransaction"] = False
        content["rolledBack"] = False
        eligibility["readOnlyTransaction"] = False
        eligibility["rolledBack"] = False
        readiness = (
            confirmation
            ._build_material_capability_confirmation_snapshot(
                content, eligibility,
            )
        )
        subject = readiness["confirmationSubjects"][0]
        fixture["material_hash"] = readiness["source"][
            "materialIdentitySha256"
        ]
        fixture["subject_hash"] = subject[
            "confirmationSubjectSha256"
        ]
        self.assertEqual(subject["companySupplierLinkId"], fixture["link_id"])
        self.assertEqual(subject["supplierId"], fixture["supplier_id"])

        invalid_content = copy.deepcopy(content)
        invalid_content["contentSha256"] = "0" * 64
        with mock.patch.object(
            proof,
            "collect_prepared_supply_rfq_content",
            return_value=invalid_content,
        ), mock.patch.object(
            proof,
            "collect_prepared_supply_supplier_eligibility",
            return_value=eligibility,
        ), self.assertRaises(writer.MaterialCapabilityWriterError) as error:
            self._confirmation_write(self._writer_db, fixture)
        self.assertEqual(
            error.exception.code,
            "supply_supplier_material_writer_evidence_invalid",
        )
        self.assertEqual(self._assertion_count(), 0)

        with mock.patch.object(
            proof,
            "collect_prepared_supply_rfq_content",
            return_value=content,
        ), mock.patch.object(
            proof,
            "collect_prepared_supply_supplier_eligibility",
            return_value=eligibility,
        ):
            confirmed = self._confirmation_write(self._writer_db, fixture)
            repeated = self._confirmation_write(self._writer_db, fixture)

        self.assertEqual(confirmed["state"], "confirmed")
        self.assertTrue(confirmed["committed"])
        self.assertEqual(repeated["state"], "already_confirmed")
        self.assertFalse(repeated["committed"])
        self.assertEqual(repeated["assertionId"], confirmed["assertionId"])
        self.assertEqual(self._assertion_count(), 1)

    def test_live_passed_session_confirms_revokes_and_repeats_idempotently(self):
        fixture = self._fixture()
        first_proof_reached = threading.Event()
        release_first = threading.Event()
        second_lock_attempted = threading.Event()
        concurrent_connections = {}
        connections_guard = threading.Lock()

        def writer_db(label):
            def before_execute(sql):
                if (
                    label == "second"
                    and " ".join(sql.split()).startswith(
                        "LOCK TABLE public.companies "
                    )
                ):
                    second_lock_attempted.set()

            def get_db():
                observed = _ObservedConnection(
                    psycopg2.connect(TEST_DATABASE_URL),
                    label=label,
                    before_execute=before_execute,
                )
                with connections_guard:
                    concurrent_connections[label] = observed
                    self.writer_connections.append(observed)
                return observed

            return get_db

        def collect_snapshot(cur, prepared):
            if cur._observation["label"] == "first":
                first_proof_reached.set()
                if not release_first.wait(timeout=5):
                    raise AssertionError("first writer release timed out")
            return self._collect_real_proof_snapshot(
                cur, prepared, fixture
            )

        def confirm(get_db):
            return writer.run_material_capability_confirmation_write(
                get_db,
                valid_report(),
                SELECTED,
                self._authentication(fixture),
                self._confirmation_command(fixture),
            )

        with mock.patch.object(
            writer,
            "_collect_proof",
            side_effect=collect_snapshot,
        ), ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(confirm, writer_db("first"))
            second_future = None
            try:
                self.assertTrue(first_proof_reached.wait(timeout=5))
                second_future = pool.submit(
                    confirm, writer_db("second")
                )
                self.assertTrue(second_lock_attempted.wait(timeout=5))
                done, _pending = wait([second_future], timeout=0.2)
                self.assertEqual(done, set())
                second_calls = concurrent_connections[
                    "second"
                ].observation["sql"]
                self.assertEqual(len(second_calls), 5)
                self.assertEqual(
                    " ".join(second_calls[-1][0].split()),
                    "LOCK TABLE public.companies "
                    "IN SHARE UPDATE EXCLUSIVE MODE",
                )
            finally:
                release_first.set()
            confirmed = first_future.result(timeout=10)
            repeated_confirmation = second_future.result(timeout=10)

        revoked = self._revoke(fixture, confirmed["assertionId"])
        repeated_revocation = self._revoke(fixture, confirmed["assertionId"])

        self.assertEqual(confirmed["state"], "confirmed")
        self.assertTrue(confirmed["committed"])
        self.assertEqual(confirmed["writesAttempted"], 1)
        self.assertEqual(repeated_confirmation["state"], "already_confirmed")
        self.assertFalse(repeated_confirmation["committed"])
        self.assertEqual(repeated_confirmation["assertionId"], confirmed["assertionId"])
        self.assertEqual(repeated_confirmation["writesAttempted"], 0)
        self.assertEqual(revoked["state"], "revoked")
        self.assertTrue(revoked["committed"])
        self.assertEqual(revoked["revokesAssertionId"], confirmed["assertionId"])
        self.assertEqual(repeated_revocation["state"], "already_revoked")
        self.assertFalse(repeated_revocation["committed"])
        self.assertEqual(repeated_revocation["assertionId"], revoked["assertionId"])
        self.assertEqual(self._assertion_count(), 2)

        expected_session = {
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        }
        self.assertEqual(len(self.writer_connections), 4)
        for connection in self.writer_connections:
            self.assertEqual(connection.observation["sessions"], [expected_session])
            self._assert_writer_lock_order(connection)
        self.assertEqual(
            self.proof_transactions,
            [("off", "serializable"), ("off", "serializable")],
        )

    def test_writer_and_b1_migration_share_one_deadlock_free_gate_order(self):
        fixture = self._fixture()
        self._drop_capability_schema()
        writer_first_plan = self._schema_plan()
        self.assertEqual(writer_first_plan["changeCount"], 9)
        self.assertTrue(writer_first_plan["readyForApply"])

        writer_target_attempted = threading.Event()
        release_writer = threading.Event()
        migration_parent_lock_attempted = threading.Event()
        first_connections = {}

        def writer_first_db():
            def before_execute(sql):
                if " ".join(sql.split()).startswith(
                    "LOCK TABLE public."
                    "supplier_material_capability_assertions "
                ):
                    writer_target_attempted.set()
                    if not release_writer.wait(timeout=5):
                        raise AssertionError("writer release timed out")

            observed = _ObservedConnection(
                psycopg2.connect(TEST_DATABASE_URL),
                label="writer-first",
                before_execute=before_execute,
            )
            first_connections["writer"] = observed
            self.writer_connections.append(observed)
            return observed

        def migration_after_writer_db():
            def before_execute(sql):
                if " ".join(sql.split()).startswith(
                    "LOCK TABLE public.companies,public.platform_accounts,"
                ):
                    migration_parent_lock_attempted.set()

            observed = _ObservedConnection(
                psycopg2.connect(TEST_DATABASE_URL),
                label="migration-after-writer",
                before_execute=before_execute,
            )
            first_connections["migration"] = observed
            return observed

        with ThreadPoolExecutor(max_workers=2) as pool:
            writer_future = pool.submit(
                self._confirmation_write,
                writer_first_db,
                fixture,
            )
            migration_future = None
            try:
                self.assertTrue(writer_target_attempted.wait(timeout=5))
                migration_future = pool.submit(
                    self._apply_schema_plan,
                    writer_first_plan,
                    migration_after_writer_db,
                )
                self.assertTrue(
                    migration_parent_lock_attempted.wait(timeout=5)
                )
                done, _pending = wait([migration_future], timeout=0.2)
                self.assertEqual(done, set())
                migration_calls = first_connections[
                    "migration"
                ].observation["sql"]
                self.assertTrue(
                    " ".join(migration_calls[-1][0].split()).startswith(
                        "LOCK TABLE public.companies,"
                    )
                )
                self.assertFalse(any(
                    "pg_advisory_xact_lock" in sql
                    for sql, _params in migration_calls
                ))
            finally:
                release_writer.set()

            with self.assertRaises(
                writer.MaterialCapabilityWriterError
            ) as writer_error:
                writer_future.result(timeout=10)
            self.assertEqual(
                writer_error.exception.code,
                "supply_supplier_material_writer_schema_not_ready",
            )
            writer_first_migration = migration_future.result(timeout=10)

        self.assertTrue(writer_first_migration["committed"])
        self.assertTrue(writer_first_migration["complete"])
        self.assertEqual(writer_first_migration["schemaWritesAttempted"], 9)
        failed_writer_calls = first_connections["writer"].observation["sql"]
        self.assertEqual(len(failed_writer_calls), 6)
        self.assertFalse(any(
            "pg_advisory_xact_lock" in sql
            or "FROM public.user_sessions" in sql
            for sql, _params in failed_writer_calls
        ))

        self._drop_capability_schema()
        migration_first_plan = self._schema_plan()
        self.assertEqual(migration_first_plan["changeCount"], 9)
        self.assertTrue(migration_first_plan["readyForApply"])

        migration_at_create = threading.Event()
        release_migration = threading.Event()
        writer_gate_attempted = threading.Event()
        second_connections = {}

        def migration_first_db():
            def before_execute(sql):
                normalized = " ".join(sql.split())
                if normalized.startswith(
                    "CREATE TABLE public."
                    "supplier_material_capability_assertions "
                ):
                    migration_at_create.set()
                    if not release_migration.wait(timeout=5):
                        raise AssertionError("migration release timed out")

            observed = _ObservedConnection(
                psycopg2.connect(TEST_DATABASE_URL),
                label="migration-first",
                before_execute=before_execute,
            )
            second_connections["migration"] = observed
            return observed

        def writer_after_migration_db():
            def before_execute(sql):
                if " ".join(sql.split()).startswith(
                    "LOCK TABLE public.companies "
                ):
                    writer_gate_attempted.set()

            observed = _ObservedConnection(
                psycopg2.connect(TEST_DATABASE_URL),
                label="writer-after-migration",
                before_execute=before_execute,
            )
            second_connections["writer"] = observed
            self.writer_connections.append(observed)
            return observed

        with mock.patch.object(
            writer,
            "_collect_proof",
            side_effect=lambda cur, prepared: (
                self._collect_real_proof_snapshot(cur, prepared, fixture)
            ),
        ), ThreadPoolExecutor(max_workers=2) as pool:
            migration_future = pool.submit(
                self._apply_schema_plan,
                migration_first_plan,
                migration_first_db,
            )
            writer_future = None
            try:
                self.assertTrue(migration_at_create.wait(timeout=5))
                writer_future = pool.submit(
                    self._confirmation_write,
                    writer_after_migration_db,
                    fixture,
                )
                self.assertTrue(writer_gate_attempted.wait(timeout=5))
                done, _pending = wait([writer_future], timeout=0.2)
                self.assertEqual(done, set())
                writer_calls = second_connections[
                    "writer"
                ].observation["sql"]
                self.assertEqual(len(writer_calls), 5)
                self.assertEqual(
                    " ".join(writer_calls[-1][0].split()),
                    "LOCK TABLE public.companies "
                    "IN SHARE UPDATE EXCLUSIVE MODE",
                )
            finally:
                release_migration.set()

            migration_first = migration_future.result(timeout=10)
            confirmed = writer_future.result(timeout=10)

        self.assertTrue(migration_first["committed"])
        self.assertTrue(migration_first["complete"])
        self.assertEqual(migration_first["schemaWritesAttempted"], 9)
        self.assertEqual(confirmed["state"], "confirmed")
        self.assertTrue(confirmed["committed"])
        self.assertEqual(self._assertion_count(), 1)
        self._assert_writer_lock_order(second_connections["writer"])

    def test_guard_trigger_ddl_cannot_feed_a_stale_writer_snapshot(self):
        fixture = self._fixture()
        mutations = (
            (
                "dropped",
                "DROP TRIGGER smca_assertion_insert_guard ON "
                "public.supplier_material_capability_assertions",
            ),
            (
                "disabled",
                "ALTER TABLE public.supplier_material_capability_assertions "
                "DISABLE TRIGGER smca_assertion_insert_guard",
            ),
        )
        for index, (name, mutation_sql) in enumerate(mutations):
            with self.subTest(name=name):
                ddl = psycopg2.connect(TEST_DATABASE_URL)
                ddl.set_session(autocommit=False)
                with ddl.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='5s'")
                    cur.execute(mutation_sql)

                target_lock_attempted = threading.Event()
                connection = {}

                def stale_writer_db():
                    def before_execute(sql):
                        if " ".join(sql.split()).startswith(
                            "LOCK TABLE public."
                            "supplier_material_capability_assertions "
                        ):
                            target_lock_attempted.set()

                    observed = _ObservedConnection(
                        psycopg2.connect(TEST_DATABASE_URL),
                        label="stale-" + name,
                        before_execute=before_execute,
                    )
                    connection["writer"] = observed
                    self.writer_connections.append(observed)
                    return observed

                with mock.patch.object(
                    writer,
                    "_collect_proof",
                    side_effect=lambda cur, prepared: (
                        self._collect_real_proof_snapshot(
                            cur, prepared, fixture
                        )
                    ),
                ), ThreadPoolExecutor(max_workers=1) as pool:
                    writer_future = pool.submit(
                        self._confirmation_write,
                        stale_writer_db,
                        fixture,
                    )
                    try:
                        self.assertTrue(
                            target_lock_attempted.wait(timeout=5)
                        )
                        done, _pending = wait(
                            [writer_future], timeout=0.2
                        )
                        self.assertEqual(done, set())
                        calls = connection["writer"].observation["sql"]
                        self.assertEqual(len(calls), 6)
                        self.assertFalse(any(
                            "pg_advisory_xact_lock" in sql
                            or "FROM public.user_sessions" in sql
                            or sql.lstrip().upper().startswith("INSERT ")
                            for sql, _params in calls
                        ))
                    finally:
                        try:
                            ddl.commit()
                        finally:
                            ddl.close()
                    with self.assertRaises(
                        writer.MaterialCapabilityWriterError
                    ) as raised:
                        writer_future.result(timeout=10)

                self.assertIn(raised.exception.code, {
                    "supply_supplier_material_writer_schema_not_ready",
                    "supply_supplier_material_writer_write_conflict",
                })
                self.assertEqual(self._assertion_count(), 0)
                audit = self._schema_plan()
                self.assertFalse(audit["complete"])
                self._assert_writer_lock_order(connection["writer"])

                if index == 0:
                    trigger_sql = next(
                        change["sql"]
                        for change in schema_contract.CREATE_STEPS
                        if change["name"]
                        == "create_smca_insert_guard_trigger"
                    )
                    with self.connection.cursor() as cur:
                        cur.execute(trigger_sql)
                    repaired = self._schema_plan()
                    self.assertTrue(repaired["complete"])
                    self.assertEqual(repaired["changeCount"], 0)

    def test_authentication_failures_never_insert(self):
        fixture = self._fixture()
        cases = (
            (
                "session_without_passed_2fa",
                "UPDATE public.user_sessions SET two_factor_passed=FALSE "
                "WHERE id=81",
                fixture["session_hash"],
            ),
            (
                "actor_without_enabled_2fa",
                "UPDATE public.users SET two_factor_enabled=FALSE WHERE id=41",
                fixture["session_hash"],
            ),
            (
                "expired_session",
                "UPDATE public.user_sessions SET "
                "expires_at=clock_timestamp()-interval '1 second' WHERE id=81",
                fixture["session_hash"],
            ),
            (
                "revoked_session",
                "UPDATE public.user_sessions SET revoked_at=clock_timestamp() "
                "WHERE id=81",
                fixture["session_hash"],
            ),
            (
                "cross_company_director",
                None,
                fixture["cross_company_hash"],
            ),
        )
        for name, mutation, session_hash in cases:
            with self.subTest(name=name):
                with self.connection.cursor() as cur:
                    cur.execute(
                        "UPDATE public.user_sessions SET "
                        "two_factor_passed=TRUE,"
                        "expires_at=clock_timestamp()+interval '1 hour',"
                        "revoked_at=NULL WHERE id=81"
                    )
                    cur.execute(
                        "UPDATE public.users SET two_factor_enabled=TRUE "
                        "WHERE id=41"
                    )
                    if mutation is not None:
                        cur.execute(mutation)

                with self.assertRaises(
                    writer.MaterialCapabilityWriterError
                ) as raised:
                    self._confirm(fixture, session_hash=session_hash)
                self.assertEqual(
                    raised.exception.code,
                    "supply_supplier_material_writer_authentication_required",
                )
                self.assertEqual(self._assertion_count(), 0)

    def test_revocation_survives_supplier_parent_deactivation(self):
        fixture = self._fixture()
        confirmed = self._confirm(fixture)
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.company_supplier_links "
                "SET status='Неактивный' "
                "WHERE id=61"
            )
            cur.execute(
                "UPDATE public.suppliers SET status='Неактивный' WHERE id=71"
            )
            cur.execute(
                "UPDATE public.users SET active=FALSE WHERE id=401"
            )

        revoked = self._revoke(fixture, confirmed["assertionId"])

        self.assertEqual(revoked["state"], "revoked")
        self.assertEqual(revoked["revokesAssertionId"], confirmed["assertionId"])
        self.assertTrue(revoked["committed"])
        self.assertEqual(self._assertion_count(), 2)

    def test_writer_reads_use_declared_indexes(self):
        fixture = self._fixture()
        confirmed = self._confirm(fixture)
        self._confirm(fixture)
        self._revoke(fixture, confirmed["assertionId"])
        self._revoke(fixture, confirmed["assertionId"])

        calls = [
            call
            for connection in self.writer_connections
            for call in connection.observation["sql"]
        ]
        proof_read = next(
            call for call in calls
            if "confirmation_subject_sha256=ANY" in call[0]
        )
        target_read = next(
            call for call in calls
            if "WHERE company_id=%s" in call[0]
            and "AND id=%s" in call[0]
            and "revokes_assertion_id=%s" not in call[0]
        )
        revocation_read = next(
            call for call in calls
            if "revokes_assertion_id=%s" in call[0]
        )
        authentication_read = next(
            call for call in calls
            if "FROM public.user_sessions session" in call[0]
        )

        self.assertIn(
            "idx_smca_company_subject_id",
            self._explain_indexes(*proof_read),
        )
        self.assertTrue(
            {
                "pk_smca_assertions",
                "idx_smca_company_subject_id",
            }
            & set(self._explain_indexes(*target_read)),
        )
        self.assertIn(
            "uq_smca_revocation_target",
            self._explain_indexes(*revocation_read),
        )
        authentication_indexes = self._explain_indexes(
            *authentication_read
        )
        self.assertIn(
            "uq_a84c_user_session_hash",
            authentication_indexes,
        )
        self.assertIn(
            "uq_a84c_membership_user_company_role",
            authentication_indexes,
        )


if __name__ == "__main__":
    unittest.main()
