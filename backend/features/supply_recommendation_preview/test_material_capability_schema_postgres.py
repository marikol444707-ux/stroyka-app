import hashlib
import os
import re
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from backend.features.supply_recommendation_preview import (
    material_capability_schema as schema,
)


RUN_POSTGRES = os.getenv("A8_4B_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("A8_4B_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    RUN_POSTGRES and TEST_DATABASE_URL,
    "set A8_4B_RUN_POSTGRES_INTEGRATION=1 and a dedicated a8_4b_* database URL",
)
class MaterialCapabilitySchemaPostgresTests(unittest.TestCase):
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
        cls._reset_parent_schema()

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
    def _reset_parent_schema(cls):
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

    def get_db(self):
        connection = psycopg2.connect(TEST_DATABASE_URL)
        connection.autocommit = True
        return connection

    def _table_exists(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT pg_catalog.to_regclass(%s) IS NOT NULL",
                ("public.supplier_material_capability_assertions",),
            )
            return cur.fetchone()[0]

    def _ensure_schema(self):
        if self._table_exists():
            return
        dry_run = schema.run_material_capability_schema_migration(self.get_db)
        schema.run_material_capability_schema_migration(
            self.get_db,
            apply=True,
            confirm=schema.APPLY_CONFIRMATION,
            expected_change_count=dry_run["changeCount"],
            expected_plan_sha256=dry_run["planSha256"],
        )

    def _fixture(
        self,
        *,
        actor_role="директор",
        membership_active=True,
        actor_active=True,
        company_active=True,
        account_active=True,
        account_status="active",
        link_status="Активный",
        supplier_status="Активный",
        supplier_user_active=True,
    ):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(active,status) "
                "VALUES (%s,%s) RETURNING id",
                (account_active, account_status),
            )
            account_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.companies(platform_account_id,active) "
                "VALUES (%s,%s) RETURNING id",
                (account_id, company_active),
            )
            company_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.users(role,active) "
                "VALUES ('поставщик',%s) RETURNING id",
                (supplier_user_active,),
            )
            supplier_user_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.suppliers(status,user_id) "
                "VALUES (%s,%s) RETURNING id",
                (supplier_status, supplier_user_id),
            )
            supplier_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.company_supplier_links
                     (company_id,supplier_id,platform_account_id,status)
                     VALUES (%s,%s,%s,%s) RETURNING id""",
                (company_id, supplier_id, account_id, link_status),
            )
            link_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.users(role,active) "
                "VALUES (%s,%s) RETURNING id",
                (actor_role, actor_active),
            )
            actor_user_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.user_company_roles
                     (user_id,company_id,platform_account_id,role,active)
                     VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (
                    actor_user_id,
                    company_id,
                    account_id,
                    actor_role,
                    membership_active,
                ),
            )
            membership_id = cur.fetchone()[0]
        material_hash = hashlib.sha256(
            ("material:" + str(company_id) + ":" + str(link_id)).encode()
        ).hexdigest()
        subject_hash = hashlib.sha256(
            ("subject:" + str(company_id) + ":" + str(link_id)).encode()
        ).hexdigest()
        return {
            "account_id": account_id,
            "company_id": company_id,
            "supplier_id": supplier_id,
            "supplier_user_id": supplier_user_id,
            "link_id": link_id,
            "actor_user_id": actor_user_id,
            "membership_id": membership_id,
            "material_hash": material_hash,
            "subject_hash": subject_hash,
        }

    def _insert_event(self, fixture, *, event_kind="confirmed", revokes=None,
                      overrides=None):
        values = {
            "confirmation_version": 1,
            "event_kind": event_kind,
            "company_id": fixture["company_id"],
            "company_supplier_link_id": fixture["link_id"],
            "supplier_id": fixture["supplier_id"],
            "material_identity_sha256": fixture["material_hash"],
            "confirmation_subject_sha256": fixture["subject_hash"],
            "actor_membership_id": fixture["membership_id"],
            "actor_user_id": fixture["actor_user_id"],
            "actor_role": "директор",
            "source_kind": "director_manual",
            "revokes_assertion_id": revokes,
        }
        values.update(overrides or {})
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO public.supplier_material_capability_assertions
                     (confirmation_version,event_kind,company_id,
                      company_supplier_link_id,supplier_id,
                      material_identity_sha256,confirmation_subject_sha256,
                      actor_membership_id,actor_user_id,actor_role,source_kind,
                      revokes_assertion_id)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     RETURNING id,confirmation_version,event_kind,company_id,
                               company_supplier_link_id,supplier_id,
                               material_identity_sha256,
                               confirmation_subject_sha256,
                               actor_membership_id,actor_user_id,actor_role,
                               source_kind,revokes_assertion_id,created_at""",
                (
                    values["confirmation_version"],
                    values["event_kind"],
                    values["company_id"],
                    values["company_supplier_link_id"],
                    values["supplier_id"],
                    values["material_identity_sha256"],
                    values["confirmation_subject_sha256"],
                    values["actor_membership_id"],
                    values["actor_user_id"],
                    values["actor_role"],
                    values["source_kind"],
                    values["revokes_assertion_id"],
                ),
            )
            return dict(cur.fetchone())

    def test_00_guarded_apply_postcheck_rollback_and_zero_change_dry_run(self):
        self._drop_capability_schema()
        dry_run = schema.run_material_capability_schema_migration(self.get_db)

        self.assertTrue(dry_run["readyForApply"])
        self.assertEqual(dry_run["changeCount"], 9)
        self.assertTrue(dry_run["readOnlyTransaction"])
        self.assertTrue(dry_run["rolledBack"])
        self.assertFalse(self._table_exists())

        wrong_hash = ("0" if dry_run["planSha256"][0] != "0" else "1") + (
            dry_run["planSha256"][1:]
        )
        with self.assertRaises(
            schema.MaterialCapabilitySchemaMigrationError
        ) as mismatch:
            schema.run_material_capability_schema_migration(
                self.get_db,
                apply=True,
                confirm=schema.APPLY_CONFIRMATION,
                expected_change_count=dry_run["changeCount"],
                expected_plan_sha256=wrong_hash,
            )
        self.assertEqual(
            mismatch.exception.code,
            "material_capability_schema_apply_guard_mismatch",
        )
        self.assertFalse(self._table_exists())

        real_collect = schema._collect_catalog
        collect_calls = 0

        def fail_only_postcheck(cur):
            nonlocal collect_calls
            collect_calls += 1
            catalog = real_collect(cur)
            if collect_calls == 2:
                catalog["triggers"] = {}
            return catalog

        with patch.object(schema, "_collect_catalog", side_effect=fail_only_postcheck):
            with self.assertRaises(
                schema.MaterialCapabilitySchemaMigrationError
            ) as postcheck:
                schema.run_material_capability_schema_migration(
                    self.get_db,
                    apply=True,
                    confirm=schema.APPLY_CONFIRMATION,
                    expected_change_count=dry_run["changeCount"],
                    expected_plan_sha256=dry_run["planSha256"],
                )
        self.assertEqual(
            postcheck.exception.code,
            "material_capability_schema_postcheck_failed",
        )
        self.assertFalse(self._table_exists())

        applied = schema.run_material_capability_schema_migration(
            self.get_db,
            apply=True,
            confirm=schema.APPLY_CONFIRMATION,
            expected_change_count=dry_run["changeCount"],
            expected_plan_sha256=dry_run["planSha256"],
        )
        self.assertTrue(applied["committed"])
        self.assertTrue(applied["complete"])
        self.assertEqual(applied["schemaWritesAttempted"], 9)
        self.assertTrue(self._table_exists())

        complete = schema.run_material_capability_schema_migration(self.get_db)
        self.assertTrue(complete["complete"])
        self.assertEqual(complete["changeCount"], 0)
        self.assertEqual(complete["schemaWritesAttempted"], 0)
        self.assertTrue(complete["readOnlyTransaction"])
        self.assertTrue(complete["rolledBack"])

    def test_exact_director_can_confirm_and_exactly_revoke_once(self):
        self._ensure_schema()
        fixture = self._fixture()

        confirmed = self._insert_event(fixture)
        self.assertEqual(confirmed["event_kind"], "confirmed")
        self.assertEqual(confirmed["company_id"], fixture["company_id"])
        self.assertEqual(confirmed["actor_role"], "директор")
        self.assertEqual(confirmed["source_kind"], "director_manual")
        self.assertIsNone(confirmed["revokes_assertion_id"])
        self.assertIsNotNone(confirmed["created_at"])

        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self._insert_event(fixture)

        revoked = self._insert_event(
            fixture, event_kind="revoked", revokes=confirmed["id"]
        )
        self.assertEqual(revoked["event_kind"], "revoked")
        self.assertEqual(revoked["revokes_assertion_id"], confirmed["id"])
        self.assertEqual(
            revoked["confirmation_subject_sha256"],
            confirmed["confirmation_subject_sha256"],
        )

        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self._insert_event(
                fixture, event_kind="revoked", revokes=confirmed["id"]
            )

    def test_revocation_survives_disabled_supplier_parents_and_ids_stay_positive(self):
        self._ensure_schema()
        fixture = self._fixture()
        confirmed = self._insert_event(fixture)

        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.platform_accounts SET active=FALSE "
                "WHERE id=%s",
                (fixture["account_id"],),
            )
            cur.execute(
                "UPDATE public.company_supplier_links SET status='Неактивный' "
                "WHERE id=%s",
                (fixture["link_id"],),
            )
            cur.execute(
                "UPDATE public.suppliers SET status='Неактивный' WHERE id=%s",
                (fixture["supplier_id"],),
            )
            cur.execute(
                "UPDATE public.users SET active=FALSE WHERE id=%s",
                (fixture["supplier_user_id"],),
            )

        revoked = self._insert_event(
            fixture, event_kind="revoked", revokes=confirmed["id"]
        )
        self.assertEqual(revoked["revokes_assertion_id"], confirmed["id"])

        fresh = self._fixture()
        source = self._insert_event(fresh)
        for invalid_id, digit in ((0, "a"), (-1, "b")):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    with self.connection.cursor() as cur:
                        cur.execute(
                            """INSERT INTO public.
                                 supplier_material_capability_assertions
                                 (id,confirmation_version,event_kind,company_id,
                                  company_supplier_link_id,supplier_id,
                                  material_identity_sha256,
                                  confirmation_subject_sha256,
                                  actor_membership_id,actor_user_id,actor_role,
                                  source_kind,revokes_assertion_id)
                                 OVERRIDING SYSTEM VALUE
                                 SELECT %s,confirmation_version,event_kind,
                                        company_id,company_supplier_link_id,
                                        supplier_id,%s,%s,actor_membership_id,
                                        actor_user_id,actor_role,source_kind,NULL
                                   FROM public.
                                     supplier_material_capability_assertions
                                  WHERE id=%s""",
                            (
                                invalid_id,
                                digit * 64,
                                ("c" if digit == "a" else "d") * 64,
                                source["id"],
                            ),
                        )

        maximum = self._fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO public.
                     supplier_material_capability_assertions
                     (id,confirmation_version,event_kind,company_id,
                      company_supplier_link_id,supplier_id,
                      material_identity_sha256,
                      confirmation_subject_sha256,actor_membership_id,
                      actor_user_id,actor_role,source_kind,
                      revokes_assertion_id)
                     OVERRIDING SYSTEM VALUE
                     VALUES (%s,1,'confirmed',%s,%s,%s,%s,%s,%s,%s,
                             'директор','director_manual',NULL)
                     RETURNING id""",
                (
                    9_223_372_036_854_775_807,
                    maximum["company_id"],
                    maximum["link_id"],
                    maximum["supplier_id"],
                    maximum["material_hash"],
                    maximum["subject_hash"],
                    maximum["membership_id"],
                    maximum["actor_user_id"],
                ),
            )
            maximum_id = cur.fetchone()[0]
        maximum_revoke = self._insert_event(
            maximum, event_kind="revoked", revokes=maximum_id
        )
        self.assertEqual(maximum_revoke["revokes_assertion_id"], maximum_id)
        self.assertLess(maximum_revoke["id"], maximum_id)

    def test_catalog_blocks_every_extra_user_trigger(self):
        self._ensure_schema()
        with self.connection.cursor() as cur:
            cur.execute(
                """CREATE TRIGGER zz_rewrite_after_guard
                     BEFORE INSERT ON public.
                       supplier_material_capability_assertions
                     FOR EACH ROW EXECUTE FUNCTION public.
                       guard_supplier_material_capability_assertion_insert()"""
            )
        try:
            audit = schema.run_material_capability_schema_migration(
                self.get_db
            )
            self.assertFalse(audit["ok"])
            self.assertFalse(audit["complete"])
            self.assertEqual(
                audit["blockers"],
                ["material_capability_schema_catalog_incomplete"],
            )
        finally:
            with self.connection.cursor() as cur:
                cur.execute(
                    """DROP TRIGGER IF EXISTS zz_rewrite_after_guard
                         ON public.supplier_material_capability_assertions"""
                )

    def test_catalog_preserves_case_sensitive_partial_index_literals(self):
        self._ensure_schema()
        cases = (
            (
                "uq_smca_confirmed_subject",
                "company_id,confirmation_subject_sha256",
                "CONFIRMED",
            ),
            (
                "uq_smca_revocation_target",
                "revokes_assertion_id",
                "REVOKED",
            ),
            (
                "uq_smca_confirmed_subject",
                "company_id,confirmation_subject_sha256",
                "con firmed",
            ),
            (
                "uq_smca_revocation_target",
                "revokes_assertion_id",
                "re voked",
            ),
        )
        for index_name, columns, literal in cases:
            with self.subTest(index_name=index_name):
                with self.connection.cursor() as cur:
                    cur.execute("DROP INDEX public." + index_name)
                    cur.execute(
                        "CREATE UNIQUE INDEX " + index_name +
                        " ON public.supplier_material_capability_assertions "
                        "USING btree (" + columns + ") WHERE event_kind=%s",
                        (literal,),
                    )
                try:
                    audit = schema.run_material_capability_schema_migration(
                        self.get_db
                    )
                    self.assertFalse(audit["ok"])
                    self.assertEqual(
                        audit["blockers"],
                        ["material_capability_schema_drift"],
                    )
                finally:
                    with self.connection.cursor() as cur:
                        cur.execute("DROP INDEX public." + index_name)
                        if index_name == "uq_smca_confirmed_subject":
                            cur.execute(
                                """CREATE UNIQUE INDEX
                                     uq_smca_confirmed_subject
                                     ON public.
                                       supplier_material_capability_assertions
                                     USING btree
                                       (company_id,
                                        confirmation_subject_sha256)
                                     WHERE event_kind='confirmed'"""
                            )
                        else:
                            cur.execute(
                                """CREATE UNIQUE INDEX
                                     uq_smca_revocation_target
                                     ON public.
                                       supplier_material_capability_assertions
                                     USING btree (revokes_assertion_id)
                                     WHERE event_kind='revoked'"""
                            )

    def test_audit_is_independent_of_caller_search_path(self):
        self._ensure_schema()

        def restricted_search_path_db():
            connection = psycopg2.connect(
                TEST_DATABASE_URL,
                options="-c search_path=pg_catalog",
            )
            connection.autocommit = True
            return connection

        result = schema.run_material_capability_schema_migration(
            restricted_search_path_db
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["blockers"], [])

    def test_preflight_blocks_same_named_standalone_table_type(self):
        self._drop_capability_schema()
        with self.connection.cursor() as cur:
            cur.execute(
                "CREATE TYPE public.supplier_material_capability_assertions "
                "AS ENUM ('x')"
            )
        try:
            audit = schema.run_material_capability_schema_migration(
                self.get_db
            )
            self.assertFalse(audit["ok"])
            self.assertFalse(audit["readyForApply"])
            self.assertEqual(
                audit["blockers"],
                ["material_capability_schema_object_collision"],
            )
        finally:
            with self.connection.cursor() as cur:
                cur.execute(
                    "DROP TYPE public."
                    "supplier_material_capability_assertions"
                )

    def test_rejects_deputy_inactive_actor_cross_tenant_and_bad_link(self):
        self._ensure_schema()
        deputy = self._fixture(actor_role="зам_директора")
        inactive_membership = self._fixture(membership_active=False)
        inactive_user = self._fixture(actor_active=False)
        first_tenant = self._fixture()
        second_tenant = self._fixture()
        shared_supplier_user = self._fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.suppliers(status,user_id) "
                "VALUES ('Активный',%s)",
                (shared_supplier_user["supplier_user_id"],),
            )

        cases = (
            (
                "deputy",
                deputy,
                {},
                "supplier_material_capability_director_invalid",
            ),
            (
                "inactive-membership",
                inactive_membership,
                {},
                "supplier_material_capability_director_invalid",
            ),
            (
                "inactive-user",
                inactive_user,
                {},
                "supplier_material_capability_director_invalid",
            ),
            (
                "cross-tenant-actor",
                first_tenant,
                {
                    "company_id": second_tenant["company_id"],
                    "company_supplier_link_id": second_tenant["link_id"],
                    "supplier_id": second_tenant["supplier_id"],
                },
                "supplier_material_capability_director_invalid",
            ),
            (
                "foreign-link-in-own-tenant",
                first_tenant,
                {
                    "company_supplier_link_id": second_tenant["link_id"],
                    "supplier_id": second_tenant["supplier_id"],
                },
                "supplier_material_capability_scope_invalid",
            ),
            (
                "missing-link",
                first_tenant,
                {"company_supplier_link_id": 2_000_000_000},
                "supplier_material_capability_scope_invalid",
            ),
            (
                "shared-supplier-user",
                shared_supplier_user,
                {},
                "supplier_material_capability_scope_invalid",
            ),
        )
        for name, fixture, overrides, expected_code in cases:
            with self.subTest(name=name):
                with self.assertRaises(psycopg2.Error) as error:
                    self._insert_event(fixture, overrides=overrides)
                self.assertIn(expected_code, str(error.exception))

    def test_update_delete_and_truncate_are_rejected_without_data_loss(self):
        self._ensure_schema()
        fixture = self._fixture()
        confirmed = self._insert_event(fixture)

        mutations = (
            (
                "update",
                "UPDATE public.supplier_material_capability_assertions "
                "SET source_kind='tampered' WHERE id=%s",
                (confirmed["id"],),
            ),
            (
                "delete",
                "DELETE FROM public.supplier_material_capability_assertions "
                "WHERE id=%s",
                (confirmed["id"],),
            ),
            (
                "truncate",
                "TRUNCATE TABLE public.supplier_material_capability_assertions",
                None,
            ),
        )
        for name, statement, params in mutations:
            with self.subTest(name=name):
                with self.assertRaises(psycopg2.Error) as error:
                    with self.connection.cursor() as cur:
                        cur.execute(statement, params)
                self.assertEqual(error.exception.pgcode, "55000")
                self.assertIn(
                    "supplier_material_capability_assertion_immutable",
                    str(error.exception),
                )

        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM "
                "public.supplier_material_capability_assertions WHERE id=%s",
                (confirmed["id"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
