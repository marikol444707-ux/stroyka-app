import hashlib
import os
import re
import unittest

import psycopg2
from psycopg2.errors import ReadOnlySqlTransaction
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from backend.features.supply_recommendation_preview import (
    material_capability_proof as proof,
    material_capability_schema as schema,
    material_capability_schema_probe as schema_probe,
)


RUN_POSTGRES = os.getenv("A8_4B_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("A8_4B_TEST_DATABASE_URL", "")


class _RecordingCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self.cursor.execute(sql, params)

    def fetchall(self):
        return self.cursor.fetchall()


def _plan_index_names(node):
    names = []
    if type(node) is dict:
        if type(node.get("Index Name")) is str:
            names.append(node["Index Name"])
        for child in node.get("Plans") or []:
            names.extend(_plan_index_names(child))
    return names


@unittest.skipUnless(
    RUN_POSTGRES and TEST_DATABASE_URL,
    "set A8_4B_RUN_POSTGRES_INTEGRATION=1 and a dedicated a8_4b_* database URL",
)
class MaterialCapabilityProofPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = parse_dsn(TEST_DATABASE_URL).get("dbname", "")
        if not re.fullmatch(r"a8_4b_[a-z0-9_]+", configured):
            raise RuntimeError(
                "A8.4b PostgreSQL tests require a dedicated a8_4b_* database"
            )

        cls.connection = psycopg2.connect(TEST_DATABASE_URL)
        cls.connection.autocommit = True
        with cls.connection.cursor() as cur:
            cur.execute("SELECT pg_catalog.current_database()")
            if cur.fetchone()[0] != configured:
                raise RuntimeError("dedicated database identity changed")
        cls._reset_schema()
        dry_run = schema.run_material_capability_schema_migration(cls.get_db)
        applied = schema.run_material_capability_schema_migration(
            cls.get_db,
            apply=True,
            confirm=schema.APPLY_CONFIRMATION,
            expected_change_count=dry_run["changeCount"],
            expected_plan_sha256=dry_run["planSha256"],
        )
        if applied.get("complete") is not True:
            raise RuntimeError("material capability schema was not applied")

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "connection"):
            return
        cls._drop_capability_schema()
        with cls.connection.cursor() as cur:
            for table in (
                "company_supplier_links",
                "user_company_roles",
                "suppliers",
                "users",
                "companies",
                "platform_accounts",
            ):
                cur.execute("DROP TABLE IF EXISTS public." + table + " CASCADE")
        cls.connection.close()

    @classmethod
    def get_db(cls):
        connection = psycopg2.connect(TEST_DATABASE_URL)
        connection.autocommit = True
        return connection

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
    def _reset_schema(cls):
        cls._drop_capability_schema()
        with cls.connection.cursor() as cur:
            for table in (
                "company_supplier_links",
                "user_company_roles",
                "suppliers",
                "users",
                "companies",
                "platform_accounts",
            ):
                cur.execute("DROP TABLE IF EXISTS public." + table + " CASCADE")
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
                     active BOOLEAN
                   )"""
            )
            cur.execute(
                """CREATE TABLE public.user_company_roles (
                     id SERIAL PRIMARY KEY,
                     user_id INTEGER,
                     company_id INTEGER,
                     platform_account_id INTEGER,
                     role VARCHAR(100),
                     active BOOLEAN
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

    @classmethod
    def _fixture(cls):
        with cls.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(active,status) "
                "VALUES (TRUE,'active') RETURNING id"
            )
            account_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.companies(platform_account_id,active) "
                "VALUES (%s,TRUE) RETURNING id",
                (account_id,),
            )
            company_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.users(role,active) "
                "VALUES ('поставщик',TRUE) RETURNING id"
            )
            supplier_user_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.suppliers(status,user_id) "
                "VALUES ('Активный',%s) RETURNING id",
                (supplier_user_id,),
            )
            supplier_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.company_supplier_links
                     (company_id,supplier_id,platform_account_id,status)
                     VALUES (%s,%s,%s,'Активный') RETURNING id""",
                (company_id, supplier_id, account_id),
            )
            link_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.users(role,active) "
                "VALUES ('директор',TRUE) RETURNING id"
            )
            actor_user_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.user_company_roles
                     (user_id,company_id,platform_account_id,role,active)
                     VALUES (%s,%s,%s,'директор',TRUE) RETURNING id""",
                (actor_user_id, company_id, account_id),
            )
            membership_id = cur.fetchone()[0]
        return {
            "company_id": company_id,
            "supplier_id": supplier_id,
            "link_id": link_id,
            "actor_user_id": actor_user_id,
            "membership_id": membership_id,
            "material_hash": hashlib.sha256(
                ("material:" + str(company_id)).encode()
            ).hexdigest(),
            "subject_hash": hashlib.sha256(
                ("subject:" + str(company_id)).encode()
            ).hexdigest(),
        }

    @classmethod
    def _insert_confirmation(cls, fixture, *, subject_hash=None):
        subject_hash = subject_hash or fixture["subject_hash"]
        with cls.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO public.supplier_material_capability_assertions
                     (confirmation_version,event_kind,company_id,
                      company_supplier_link_id,supplier_id,
                      material_identity_sha256,confirmation_subject_sha256,
                      actor_membership_id,actor_user_id,actor_role,source_kind,
                      revokes_assertion_id)
                     VALUES (1,'confirmed',%s,%s,%s,%s,%s,%s,%s,
                             'директор','director_manual',NULL)
                     RETURNING id""",
                (
                    fixture["company_id"],
                    fixture["link_id"],
                    fixture["supplier_id"],
                    fixture["material_hash"],
                    subject_hash,
                    fixture["membership_id"],
                    fixture["actor_user_id"],
                ),
            )
            return cur.fetchone()[0]

    @staticmethod
    def _subject(fixture, subject_hash=None):
        return {
            "companySupplierLinkId": fixture["link_id"],
            "supplierId": fixture["supplier_id"],
            "confirmationSubjectSha256": (
                subject_hash or fixture["subject_hash"]
            ),
        }

    def test_exact_reader_query_is_served_by_company_subject_id_index(self):
        fixture = self._fixture()
        assertion_id = self._insert_confirmation(fixture)
        absent_hash = hashlib.sha256(b"absent-proof-subject").hexdigest()
        subjects = [
            self._subject(fixture, absent_hash),
            self._subject(fixture),
        ]

        connection = self.get_db()
        connection.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        try:
            real_cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor = _RecordingCursor(real_cursor)
            rows = proof._read_assertions(
                cursor, fixture["company_id"], subjects,
            )
            self.assertEqual([row["id"] for row in rows], [assertion_id])

            sql, params = cursor.calls[-1]
            self.assertEqual(params, (
                fixture["company_id"],
                sorted((absent_hash, fixture["subject_hash"])),
                5,
            ))
            self.assertEqual(
                " ".join(sql.split()),
                "SELECT id,confirmation_version,event_kind,company_id, "
                "company_supplier_link_id,supplier_id, "
                "material_identity_sha256,confirmation_subject_sha256, "
                "actor_membership_id,actor_user_id,actor_role,source_kind, "
                "revokes_assertion_id FROM "
                "public.supplier_material_capability_assertions WHERE "
                "company_id=%s AND "
                "confirmation_subject_sha256=ANY(%s::varchar[]) ORDER BY "
                "confirmation_subject_sha256,id LIMIT %s",
            )

            real_cursor.execute("SET LOCAL enable_seqscan=off")
            real_cursor.execute(
                "EXPLAIN (FORMAT JSON, COSTS OFF) " + sql,
                params,
            )
            plan = real_cursor.fetchone()["QUERY PLAN"][0]["Plan"]
            self.assertIn(
                "idx_smca_company_subject_id",
                _plan_index_names(plan),
            )
        finally:
            connection.rollback()
            connection.close()

    def test_repeatable_read_snapshot_requires_a_new_transaction_to_see_commit(self):
        fixture = self._fixture()
        subject = [self._subject(fixture)]
        reader = self.get_db()
        reader.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        try:
            with reader.cursor(cursor_factory=RealDictCursor) as cur:
                self.assertEqual(
                    proof._read_assertions(
                        cur, fixture["company_id"], subject,
                    ),
                    [],
                )
                assertion_id = self._insert_confirmation(fixture)
                self.assertEqual(
                    proof._read_assertions(
                        cur, fixture["company_id"], subject,
                    ),
                    [],
                )

            reader.rollback()
            with reader.cursor(cursor_factory=RealDictCursor) as cur:
                visible = proof._read_assertions(
                    cur, fixture["company_id"], subject,
                )
            self.assertEqual([row["id"] for row in visible], [assertion_id])
        finally:
            reader.rollback()
            reader.close()

    def test_proof_style_reader_cannot_write_and_leaves_no_persistent_mutation(self):
        fixture = self._fixture()
        assertion_id = self._insert_confirmation(fixture)
        subject = [self._subject(fixture)]
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT pg_catalog.count(*) FROM "
                "public.supplier_material_capability_assertions"
            )
            count_before = cur.fetchone()[0]
            cur.execute(
                "SELECT last_value,is_called FROM public.smca_assertion_id_seq"
            )
            sequence_before = cur.fetchone()
            cur.execute(
                "SELECT pg_catalog.count(*) FROM public.platform_accounts"
            )
            account_count_before = cur.fetchone()[0]

        reader = self.get_db()
        reader.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        try:
            with reader.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SHOW transaction_read_only")
                self.assertEqual(cur.fetchone()["transaction_read_only"], "on")
                cur.execute("SHOW transaction_isolation")
                self.assertEqual(
                    cur.fetchone()["transaction_isolation"],
                    "repeatable read",
                )
                readiness = schema_probe.collect_material_capability_schema_readiness(
                    cur
                )
                self.assertEqual(readiness, {
                    "contractVersion": 1,
                    "complete": True,
                    "blockers": [],
                })
                rows = proof._read_assertions(
                    cur, fixture["company_id"], subject,
                )
                self.assertEqual([row["id"] for row in rows], [assertion_id])
                with self.assertRaises(ReadOnlySqlTransaction) as error:
                    cur.execute(
                        "INSERT INTO public.platform_accounts(active,status) "
                        "VALUES (TRUE,'active')"
                    )
                self.assertEqual(error.exception.pgcode, "25006")
        finally:
            reader.rollback()
            reader.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT pg_catalog.count(*) FROM "
                "public.supplier_material_capability_assertions"
            )
            self.assertEqual(cur.fetchone()[0], count_before)
            cur.execute(
                "SELECT last_value,is_called FROM public.smca_assertion_id_seq"
            )
            self.assertEqual(cur.fetchone(), sequence_before)
            cur.execute(
                "SELECT pg_catalog.count(*) FROM public.platform_accounts"
            )
            self.assertEqual(cur.fetchone()[0], account_count_before)


if __name__ == "__main__":
    unittest.main()
