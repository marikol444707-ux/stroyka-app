import copy
import hashlib
import json
import os
import re
import unittest
from unittest import mock

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import Json, RealDictCursor

from backend.features.agent_jobs.schema import ensure_agent_jobs_schema
from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
)
from backend.features.supply_recommendation_preview import (
    material_capability_confirmation as confirmation,
    material_capability_proof as proof,
    material_capability_runtime as runtime,
    material_capability_schema as schema,
    material_capability_source_resolver as source_resolver,
    rfq_content,
    supplier_eligibility,
)
from backend.features.supply_recommendation_preview.test_material_capability_confirmation import (
    _valid_dependencies,
)
from backend.features.supply_recommendation_preview.test_rfq_content import (
    request_item,
    sections,
    target_sections,
    valid_report,
)


RUN_POSTGRES = os.getenv("A8_4C2_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("A8_4C2_TEST_DATABASE_URL", "")
AUTHENTICATION_REQUIRED = (
    "supply_supplier_material_runtime_authentication_required"
)
SELECTORS = {
    "companyId": 4,
    "requestId": 21,
    "requestItemIndex": 0,
}


def _plan_index_names(node):
    names = []
    if type(node) is dict:
        if type(node.get("Index Name")) is str:
            names.append(node["Index Name"])
        for child in node.get("Plans") or []:
            names.extend(_plan_index_names(child))
    return names


class _ObservedCursor:
    def __init__(self, cursor, connection):
        self._cursor = cursor
        self._connection = connection

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        parameters = tuple(params or ())
        self._connection.observation["sql"].append(
            (normalized, parameters)
        )
        self._connection.observe_snapshot(normalized)
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
    def __init__(self, connection):
        self._connection = connection
        self.observation = {
            "sessions": [],
            "sql": [],
            "snapshots": [],
            "commits": 0,
            "rollbacks": 0,
        }
        self._observed_phases = set()

    @staticmethod
    def _phase(sql):
        if "FROM public.user_sessions session" in sql:
            return "authentication"
        if "FROM public.supply_requests request" in sql:
            return "request_source"
        if "FROM public.estimate_reconciliations reconciliation" in sql:
            return "target_source"
        if "FROM public.agent_jobs" in sql:
            return "agent_job"
        if (
            "FROM public.supplier_material_capability_assertions" in sql
            and "confirmation_subject_sha256=ANY" in sql
        ):
            return "proof_assertions"
        return None

    def observe_snapshot(self, sql):
        phase = self._phase(sql)
        if phase is None or phase in self._observed_phases:
            return
        self._observed_phases.add(phase)
        with self._connection.cursor() as cur:
            cur.execute("SHOW transaction_read_only")
            read_only = cur.fetchone()[0]
            cur.execute("SHOW transaction_isolation")
            isolation = cur.fetchone()[0]
            cur.execute(
                "SELECT pg_catalog.pg_backend_pid(), "
                "pg_catalog.txid_current_snapshot()::text"
            )
            backend_pid, snapshot = cur.fetchone()
        self.observation["snapshots"].append({
            "phase": phase,
            "readOnly": read_only,
            "isolation": isolation,
            "backendPid": backend_pid,
            "snapshot": snapshot,
        })

    def set_session(self, **kwargs):
        self.observation["sessions"].append(dict(kwargs))
        return self._connection.set_session(**kwargs)

    def cursor(self, *args, **kwargs):
        return _ObservedCursor(
            self._connection.cursor(*args, **kwargs), self,
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
    "set A8_4C2_RUN_POSTGRES_INTEGRATION=1 and a dedicated "
    "a8_4c2_* database URL",
)
class MaterialCapabilityRuntimePostgresTests(unittest.TestCase):
    _SNAPSHOT_TABLES = (
        "platform_accounts",
        "companies",
        "users",
        "user_company_roles",
        "user_sessions",
        "suppliers",
        "company_supplier_links",
        "projects",
        "estimates",
        "estimate_reconciliations",
        "supply_requests",
        "agent_jobs",
        "supplier_material_capability_assertions",
        "a8_4c2_unrelated_guard",
    )

    @classmethod
    def setUpClass(cls):
        configured = parse_dsn(TEST_DATABASE_URL).get("dbname", "")
        if not re.fullmatch(r"a8_4c2_[a-z0-9_]+", configured):
            raise RuntimeError(
                "A8.4c2 PostgreSQL tests require a dedicated "
                "a8_4c2_* database"
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
        self.runtime_connections = []
        self._reset_schema()
        self._apply_material_capability_schema()
        self.report = valid_report()
        self.content, self.eligibility = self._dependency_snapshots(
            self.report
        )
        self.fixture = self._seed_fixture(
            self.report, self.content, self.eligibility,
        )

    @classmethod
    def _drop_schema(cls):
        with cls.connection.cursor() as cur:
            cur.execute(
                "DROP TABLE IF EXISTS "
                "public.supplier_material_capability_assertions CASCADE"
            )
            cur.execute(
                "DROP FUNCTION IF EXISTS public."
                "guard_supplier_material_capability_assertion_insert() "
                "CASCADE"
            )
            cur.execute(
                "DROP FUNCTION IF EXISTS public."
                "reject_supplier_material_capability_assertion_mutation() "
                "CASCADE"
            )
            for table in (
                "agent_jobs",
                "supply_requests",
                "estimate_reconciliations",
                "estimates",
                "projects",
                "user_sessions",
                "company_supplier_links",
                "user_company_roles",
                "suppliers",
                "users",
                "companies",
                "platform_accounts",
                "a8_4c2_unrelated_guard",
            ):
                cur.execute(
                    "DROP TABLE IF EXISTS public." + table + " CASCADE"
                )

    @classmethod
    def _reset_schema(cls):
        cls._drop_schema()
        with cls.connection.cursor() as cur:
            cur.execute(
                """CREATE TABLE public.platform_accounts (
                     id INTEGER PRIMARY KEY,
                     active BOOLEAN NOT NULL,
                     status VARCHAR(50) NOT NULL
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.companies (
                     id INTEGER PRIMARY KEY,
                     platform_account_id INTEGER NOT NULL,
                     active BOOLEAN NOT NULL
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.users (
                     id INTEGER PRIMARY KEY,
                     role VARCHAR(100) NOT NULL,
                     active BOOLEAN NOT NULL,
                     two_factor_enabled BOOLEAN NOT NULL
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.user_company_roles (
                     id INTEGER PRIMARY KEY,
                     user_id INTEGER NOT NULL,
                     company_id INTEGER NOT NULL,
                     platform_account_id INTEGER NOT NULL,
                     role VARCHAR(100) NOT NULL,
                     active BOOLEAN NOT NULL,
                     CONSTRAINT uq_a84c2_membership_user_company_role
                       UNIQUE (user_id,company_id,role)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.user_sessions (
                     id INTEGER PRIMARY KEY,
                     user_id INTEGER NOT NULL,
                     session_hash VARCHAR(64) NOT NULL,
                     expires_at TIMESTAMPTZ NOT NULL,
                     revoked_at TIMESTAMPTZ,
                     two_factor_passed BOOLEAN NOT NULL,
                     CONSTRAINT uq_a84c2_user_session_hash
                       UNIQUE (session_hash)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.suppliers (
                     id INTEGER PRIMARY KEY,
                     status VARCHAR(100) NOT NULL,
                     user_id INTEGER NOT NULL
                   )"""
            )
            cur.execute(
                "CREATE INDEX idx_suppliers_user_id_id "
                "ON public.suppliers(user_id,id)"
            )
            cur.execute(
                """CREATE TABLE public.company_supplier_links (
                     id INTEGER PRIMARY KEY,
                     company_id INTEGER NOT NULL,
                     supplier_id INTEGER NOT NULL,
                     platform_account_id INTEGER,
                     status VARCHAR(50) NOT NULL
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.projects (
                     id INTEGER PRIMARY KEY,
                     company_id INTEGER NOT NULL,
                     name VARCHAR(1000) NOT NULL,
                     CONSTRAINT uq_a84c2_projects_company_name
                       UNIQUE (company_id,name)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.estimates (
                     id INTEGER PRIMARY KEY,
                     company_id INTEGER NOT NULL,
                     project_id INTEGER NOT NULL,
                     version VARCHAR(100),
                     sections_json JSONB,
                     status VARCHAR(100),
                     is_template BOOLEAN,
                     smeta_type VARCHAR(100),
                     work_package VARCHAR(100)
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.estimate_reconciliations (
                     id INTEGER PRIMARY KEY,
                     base_estimate_id INTEGER NOT NULL,
                     next_estimate_id INTEGER NOT NULL,
                     status VARCHAR(100),
                     smeta_type VARCHAR(100),
                     work_package VARCHAR(100)
                   )"""
            )
            cur.execute(
                "CREATE INDEX idx_a84c2_reconciliation_base "
                "ON public.estimate_reconciliations"
                "(base_estimate_id,id DESC)"
            )
            cur.execute(
                """CREATE TABLE public.supply_requests (
                     id INTEGER PRIMARY KEY,
                     company_id INTEGER NOT NULL,
                     project VARCHAR(1000) NOT NULL,
                     work_package VARCHAR(100),
                     status VARCHAR(100),
                     items_json TEXT
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.a8_4c2_unrelated_guard (
                     id INTEGER PRIMARY KEY,
                     payload JSONB NOT NULL
                   )"""
            )

        ensure_agent_jobs_schema(cls._agent_jobs_db)

    @staticmethod
    def _agent_jobs_db():
        return psycopg2.connect(TEST_DATABASE_URL)

    @staticmethod
    def _migration_db():
        connection = psycopg2.connect(TEST_DATABASE_URL)
        connection.autocommit = True
        return connection

    def _apply_material_capability_schema(self):
        plan = schema.run_material_capability_schema_migration(
            self._migration_db
        )
        applied = schema.run_material_capability_schema_migration(
            self._migration_db,
            apply=True,
            confirm=schema.APPLY_CONFIRMATION,
            expected_change_count=plan["changeCount"],
            expected_plan_sha256=plan["planSha256"],
        )
        self.assertTrue(applied["complete"])
        self.assertTrue(applied["committed"])

    @staticmethod
    def _session_hash(label):
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    @staticmethod
    def _dependency_snapshots(report):
        content, eligibility = _valid_dependencies(candidate_count=1)
        content = copy.deepcopy(content)
        eligibility = copy.deepcopy(eligibility)

        content["source"]["sourceRevision"] = report["source"][
            "sourceRevision"
        ]
        content["source"]["impactEvidenceSha256"] = report[
            "evidenceSha256"
        ]
        content["balance"]["unit"] = "кг"
        content["rfqDraft"]["items"][0]["materialName"] = (
            "Private material"
        )
        content["rfqDraft"]["items"][0]["unit"] = "кг"
        content["readOnlyTransaction"] = False
        content["rolledBack"] = False
        content["contentSha256"] = rfq_content.calculate_content_sha256(
            content
        )

        eligibility["source"].update({
            "companyId": content["source"]["companyId"],
            "requestId": content["candidate"]["requestId"],
            "requestItemIndex": content["candidate"][
                "requestItemIndex"
            ],
            "requestItemSha256": content["requestItemSha256"],
            "rfqContentSha256": content["contentSha256"],
        })
        eligibility["readOnlyTransaction"] = False
        eligibility["rolledBack"] = False
        eligibility["eligibilitySha256"] = (
            supplier_eligibility.calculate_eligibility_sha256(
                eligibility
            )
        )
        return content, eligibility

    @classmethod
    def _seed_fixture(cls, report, content, eligibility):
        sessions = {
            "live": cls._session_hash("a8.4c2-live-director"),
            "expired": cls._session_hash("a8.4c2-expired-director"),
            "non_2fa": cls._session_hash("a8.4c2-non-2fa-director"),
            "deputy": cls._session_hash("a8.4c2-deputy"),
        }
        source = build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=target_sections(),
        )
        plan = build_estimate_revision_impact_job_plan(source)
        readiness = (
            confirmation
            ._build_material_capability_confirmation_snapshot(
                content, eligibility,
            )
        )
        subject = readiness["confirmationSubjects"][0]
        proof_source = readiness["source"]

        with cls.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies"
                "(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                """INSERT INTO public.users
                     (id,role,active,two_factor_enabled)
                     VALUES
                     (41,'директор',TRUE,TRUE),
                     (42,'директор',TRUE,TRUE),
                     (43,'директор',TRUE,TRUE),
                     (44,'заместитель',TRUE,TRUE),
                     (401,'поставщик',TRUE,FALSE)"""
            )
            cur.execute(
                """INSERT INTO public.user_company_roles
                     (id,user_id,company_id,platform_account_id,role,active)
                     VALUES
                     (51,41,4,1,'директор',TRUE),
                     (52,42,4,1,'директор',TRUE),
                     (53,43,4,1,'директор',TRUE),
                     (54,44,4,1,'заместитель',TRUE)"""
            )
            cur.execute(
                "INSERT INTO public.user_sessions"
                "(id,user_id,session_hash,expires_at,revoked_at,"
                "two_factor_passed) VALUES "
                "(81,41,%s,clock_timestamp()+interval '1 hour',NULL,TRUE),"
                "(82,42,%s,clock_timestamp()-interval '1 hour',NULL,TRUE),"
                "(83,43,%s,clock_timestamp()+interval '1 hour',NULL,FALSE),"
                "(84,44,%s,clock_timestamp()+interval '1 hour',NULL,TRUE)",
                (
                    sessions["live"], sessions["expired"],
                    sessions["non_2fa"], sessions["deputy"],
                ),
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
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (17,4,'Private project')"
            )
            cur.execute(
                """INSERT INTO public.estimates
                     (id,company_id,project_id,version,sections_json,status,
                      is_template,smeta_type,work_package)
                     VALUES
                     (51,4,17,'v1.0',%s,'Архивная',FALSE,'Заказчик',
                      'Основная'),
                     (52,4,17,'v2.0',%s,'Активная',FALSE,'Заказчик',
                      'Основная')""",
                (Json(sections(quantity="10")), Json(target_sections())),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,smeta_type,
                      work_package)
                     VALUES (91,51,52,'Черновик','Заказчик','Основная')"""
            )
            cur.execute(
                """INSERT INTO public.supply_requests
                     (id,company_id,project,work_package,status,items_json)
                     VALUES (21,4,'Private project','Основная','Утверждена',%s)""",
                (json.dumps([request_item()], ensure_ascii=False),),
            )
            cur.execute(
                """INSERT INTO public.agent_jobs
                     (owner_scope,company_id,project_id,
                      requested_by_user_id,requested_by_role,job_type,
                      idempotency_key,correlation_id,payload_json,result_json,
                      status)
                     SELECT 'company',4,17,NULL,'system',%s,
                            'unrelated:' || series.value::text,
                            'unrelated:' || series.value::text,
                            '{"private":"must-not-be-selected"}'::jsonb,
                            '{"private":"must-not-be-selected"}'::jsonb,
                            'failed'
                       FROM pg_catalog.generate_series(1,32) AS series(value)""",
                (plan.job_type,),
            )
            cur.execute(
                """INSERT INTO public.agent_jobs
                     (owner_scope,company_id,project_id,
                      requested_by_user_id,requested_by_role,job_type,
                      idempotency_key,correlation_id,payload_json,result_json,
                      status)
                     VALUES
                     ('company',4,17,NULL,%s,%s,%s,%s,%s,%s,'succeeded')
                     """,
                (
                    plan.requested_by_role,
                    plan.job_type,
                    plan.idempotency_key,
                    plan.correlation_id,
                    Json(dict(plan.payload)),
                    Json(report),
                ),
            )
            cur.execute(
                """INSERT INTO public.
                     supplier_material_capability_assertions
                     (confirmation_version,event_kind,company_id,
                      company_supplier_link_id,supplier_id,
                      material_identity_sha256,
                      confirmation_subject_sha256,actor_membership_id,
                      actor_user_id,actor_role,source_kind,
                      revokes_assertion_id)
                     VALUES
                     (1,'confirmed',4,61,71,%s,%s,51,41,
                      'директор','director_manual',NULL)
                     RETURNING id""",
                (
                    proof_source["materialIdentitySha256"],
                    subject["confirmationSubjectSha256"],
                ),
            )
            assertion_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.a8_4c2_unrelated_guard(id,payload) "
                "VALUES (1,%s)",
                (Json({"private": "unchanged"}),),
            )
        return {
            "sessions": sessions,
            "jobPlan": plan,
            "assertionId": assertion_id,
        }

    def _runtime_db(self):
        observed = _ObservedConnection(
            psycopg2.connect(TEST_DATABASE_URL)
        )
        self.runtime_connections.append(observed)
        return observed

    @staticmethod
    def _authentication(session_hash):
        return {
            "authenticationKind": "cookie_session",
            "sessionHash": session_hash,
        }

    def _database_snapshot(self):
        result = {}
        with self.connection.cursor() as cur:
            for table in self._SNAPSHOT_TABLES:
                cur.execute(
                    "SELECT pg_catalog.md5(COALESCE("
                    "pg_catalog.jsonb_agg(pg_catalog.to_jsonb(row_value) "
                    "ORDER BY row_value.id)::text,'[]')) "
                    "FROM public." + table + " row_value"
                )
                result[table] = cur.fetchone()[0]
        return result

    def _patched_dependencies(self):
        content = copy.deepcopy(self.content)
        eligibility = copy.deepcopy(self.eligibility)

        def collect_content(cur, prepared):
            self.assertIsInstance(cur, _ObservedCursor)
            self.assertEqual(prepared["source"]["companyId"], 4)
            self.assertEqual(prepared["source"]["projectId"], 17)
            self.assertEqual(prepared["source"]["estimateId"], 52)
            self.assertEqual(
                prepared["source"]["sourceRevision"],
                self.report["source"]["sourceRevision"],
            )
            return copy.deepcopy(content)

        def collect_eligibility(cur, prepared, received_content):
            self.assertIsInstance(cur, _ObservedCursor)
            self.assertEqual(received_content, content)
            self.assertEqual(prepared["candidate"]["requestId"], 21)
            self.assertEqual(
                prepared["candidate"]["requestItemIndex"], 0,
            )
            return copy.deepcopy(eligibility)

        return (
            mock.patch.object(
                proof,
                "collect_prepared_supply_rfq_content",
                side_effect=collect_content,
            ),
            mock.patch.object(
                proof,
                "collect_prepared_supply_supplier_eligibility",
                side_effect=collect_eligibility,
            ),
        )

    @staticmethod
    def _source_calls(connection):
        calls = connection.observation["sql"]
        needles = (
            "FROM public.supply_requests request",
            "FROM public.estimate_reconciliations reconciliation",
            "FROM public.agent_jobs",
        )
        return [
            (sql, params) for sql, params in calls
            if any(needle in sql for needle in needles)
        ]

    def _explain_indexes(self, sql, params):
        connection = psycopg2.connect(TEST_DATABASE_URL)
        connection.autocommit = True
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("ANALYZE public.agent_jobs")
                cur.execute("SET enable_seqscan=off")
                cur.execute(
                    "EXPLAIN (FORMAT JSON,COSTS OFF) " + sql, params,
                )
                plan = cur.fetchone()["QUERY PLAN"][0]["Plan"]
                return set(_plan_index_names(plan))
        finally:
            connection.close()

    @staticmethod
    def _one_call(connection, needle):
        matches = [
            call for call in connection.observation["sql"]
            if needle in call[0]
        ]
        if len(matches) != 1:
            raise AssertionError(
                "expected one SQL call containing " + needle
            )
        return matches[0]

    def test_one_real_snapshot_resolves_job_and_reads_confirmed_proof(self):
        before = self._database_snapshot()
        content_patch, eligibility_patch = self._patched_dependencies()
        with content_patch as collect_content, eligibility_patch as collect_eligibility:
            bundle = runtime.run_material_capability_runtime_read(
                self._runtime_db,
                self._authentication(self.fixture["sessions"]["live"]),
                dict(SELECTORS),
            )
        after = self._database_snapshot()

        self.assertEqual(after, before)
        self.assertEqual(len(self.runtime_connections), 1)
        connection = self.runtime_connections[0]
        self.assertEqual(connection.observation["sessions"], [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.observation["commits"], 0)
        self.assertEqual(connection.observation["rollbacks"], 1)

        snapshots = connection.observation["snapshots"]
        self.assertEqual([item["phase"] for item in snapshots], [
            "authentication",
            "request_source",
            "target_source",
            "agent_job",
            "proof_assertions",
        ])
        self.assertEqual(
            {item["readOnly"] for item in snapshots}, {"on"},
        )
        self.assertEqual(
            {item["isolation"] for item in snapshots},
            {"repeatable read"},
        )
        self.assertEqual(
            len({item["backendPid"] for item in snapshots}), 1,
        )
        self.assertEqual(
            len({item["snapshot"] for item in snapshots}), 1,
        )

        self.assertEqual(len(self._source_calls(connection)), 3)
        _job_sql, job_params = self._one_call(
            connection, "FROM public.agent_jobs",
        )
        job_plan = self.fixture["jobPlan"]
        self.assertEqual(job_params, (
            source_resolver.MAX_JOB_PAYLOAD_BYTES,
            source_resolver.MAX_JOB_RESULT_BYTES,
            4,
            17,
            job_plan.job_type,
            job_plan.idempotency_key,
            2,
        ))
        collect_content.assert_called_once()
        collect_eligibility.assert_called_once()
        self.assertEqual(bundle["combinedReport"], self.report)
        self.assertEqual(bundle["selected"], {
            "requestId": 21,
            "requestItemIndex": 0,
        })
        result = bundle["proof"]
        self.assertEqual(result["state"], "proof_complete")
        self.assertTrue(result["materialEligibilityProven"])
        self.assertTrue(result["readOnlyTransaction"])
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["provenSubjectCount"], 1)
        self.assertEqual(result["proofSubjects"][0]["proofState"], "confirmed")
        self.assertEqual(
            result["proofSubjects"][0]["evidence"][0]["assertionId"],
            self.fixture["assertionId"],
        )
        self.assertEqual(
            result["proofSha256"], proof.calculate_proof_sha256(result),
        )

    def test_exact_runtime_reads_use_bounded_supporting_indexes(self):
        content_patch, eligibility_patch = self._patched_dependencies()
        with content_patch, eligibility_patch:
            runtime.run_material_capability_runtime_read(
                self._runtime_db,
                self._authentication(self.fixture["sessions"]["live"]),
                dict(SELECTORS),
            )
        connection = self.runtime_connections[0]

        expected = (
            (
                "FROM public.user_sessions session",
                {"uq_a84c2_user_session_hash",
                 "uq_a84c2_membership_user_company_role"},
            ),
            (
                "FROM public.supply_requests request",
                {"supply_requests_pkey",
                 "uq_a84c2_projects_company_name"},
            ),
            (
                "FROM public.estimate_reconciliations reconciliation",
                {"idx_a84c2_reconciliation_base", "estimates_pkey"},
            ),
            (
                "FROM public.agent_jobs",
                {"uq_agent_jobs_idempotency"},
            ),
            (
                "confirmation_subject_sha256=ANY",
                {"idx_smca_company_subject_id"},
            ),
        )
        for needle, required_indexes in expected:
            with self.subTest(read=needle):
                sql, params = self._one_call(connection, needle)
                indexes = self._explain_indexes(sql, params)
                self.assertTrue(
                    required_indexes.issubset(indexes),
                    (required_indexes, indexes),
                )

    def test_invalid_authentication_stops_before_tenant_source_reads(self):
        before = self._database_snapshot()
        cases = (
            ("expired", self.fixture["sessions"]["expired"], 4),
            ("non_2fa", self.fixture["sessions"]["non_2fa"], 4),
            ("deputy", self.fixture["sessions"]["deputy"], 4),
            ("cross_company", self.fixture["sessions"]["live"], 5),
        )
        for name, session_hash, company_id in cases:
            with self.subTest(case=name), self.assertRaises(
                runtime.MaterialCapabilityRuntimeError
            ) as raised:
                runtime.run_material_capability_runtime_read(
                    self._runtime_db,
                    self._authentication(session_hash),
                    {
                        "companyId": company_id,
                        "requestId": 21,
                        "requestItemIndex": 0,
                    },
                )
            self.assertEqual(raised.exception.code, AUTHENTICATION_REQUIRED)

        after = self._database_snapshot()
        self.assertEqual(after, before)
        self.assertEqual(len(self.runtime_connections), len(cases))
        for connection in self.runtime_connections:
            self.assertEqual(len(connection.observation["sql"]), 5)
            self.assertEqual(self._source_calls(connection), [])
            sql = " ".join(
                statement
                for statement, _params in connection.observation["sql"]
            )
            self.assertNotIn("Private project", sql)
            self.assertNotIn("FROM public.agent_jobs", sql)
            self.assertEqual(connection.observation["commits"], 0)
            self.assertEqual(connection.observation["rollbacks"], 1)
            self.assertEqual(
                [item["phase"] for item in connection.observation[
                    "snapshots"
                ]],
                ["authentication"],
            )


if __name__ == "__main__":
    unittest.main()
