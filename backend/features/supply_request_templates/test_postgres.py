"""Company supply template contract through authenticated HTTP/PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from .test_support import SupplyTemplatesPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class SupplyTemplatesPostgresTests(SupplyTemplatesPostgresSupport, unittest.TestCase):
    def test_unowned_legacy_template_is_hidden_in_selected_company(self):
        before = self.snapshot()
        rows = self.api("director", "GET", "/supply-request-templates", **self.own_headers())
        self.assertNotIn(self.legacy_id, [row["id"] for row in rows],
                         "Unknown legacy ownership must not expose private request sets to every company")
        self.assertEqual(self.snapshot(), before)

    def test_template_created_by_other_company_is_not_globally_visible(self):
        foreign, _ = self.create_template(actor="stranger", name="Company3 private template")
        before = self.snapshot()
        rows = self.api("director", "GET", "/supply-request-templates", **self.own_headers())
        self.assertNotIn(foreign["id"], [row["id"] for row in rows],
                         "An authenticated company3 submission must never leak into company2 reusable requests")
        self.assertEqual(self.snapshot(), before)

    def test_create_records_real_owner_author_and_exact_content_without_submitting_request(self):
        result, _ = self.create_template(actor="foreman", name="  Кабельный   набор  ", category="К" * 100,
            items=[self.item(quantity="0.000001"), self.item(materialName="Second material", quantity="99999999.999999")])
        rows = self.catalog("foreman")["items"]
        self.assertEqual([row["id"] for row in rows], [result["id"]])
        row = rows[0]
        self.assertEqual(row["name"], "Кабельный набор")
        self.assertEqual(row["category"], "К" * 100)
        self.assertEqual(row["companyId"], 2)
        self.assertEqual(row["version"], 1)
        self.assertEqual(row["createdById"], self.f["users"]["foreman"]["id"])
        self.assertEqual(row["createdBy"], self.f["users"]["foreman"]["name"])
        self.assertEqual([Decimal(str(item["quantity"])) for item in row["items"]],
                         [Decimal("0.000001"), Decimal("99999999.999999")])
        self.assertEqual(self.sql("SELECT company_id FROM supply_request_templates WHERE id=%s", (self.legacy_id,)), [(None,)])
        self.assertEqual(self.sql("SELECT company_id,actor_id,action FROM supply_template_events WHERE id=%s", (result["eventId"],)),
                         [(2, self.f["users"]["foreman"]["id"], "create")])

    def test_malformed_or_nonfinite_row_rejects_the_whole_template_instead_of_dropping_it(self):
        invalid = [None, "bad row", [], self.item(materialName=" "), self.item(materialName=12),
            self.item(unit=""), self.item(unit=False), self.item(workPackage=[]), self.item(quantity=True),
            self.item(quantity="NaN"), self.item(quantity="Infinity"), self.item(quantity="-Infinity"),
            self.item(quantity="0"), self.item(quantity="-1"), self.item(quantity="100000000"),
            self.item(quantity="0.0000001"), self.item(quantity="not a number"),
            {**self.item(), "companyId": 3}, {**self.item(), "work_package": "Hidden legacy alias"}]
        for row in invalid:
            with self.subTest(row=row):
                self.assert_denied_unchanged("POST", "/supply-request-templates",
                    self.template_payload(items=[self.item(), row]))

    def test_header_fields_items_shape_and_server_author_fields_are_strict(self):
        invalid = [{"name": " "}, {"name": False}, {"category": []}, {"name": "x" * 256},
            {"category": "x" * 101}, {"items": []}, {"items": {}}, {"items": "bad"},
            {"items": [self.item(materialName="x" * 501)]}, {"items": [self.item(unit="x" * 41)]},
            {"items": [self.item(workPackage="x" * 256)]}, {"items": [self.item()] * 201},
            {"createdBy": "Forged director"}, {"createdById": self.f["users"]["stranger"]["id"]},
            {"companyId": 3}, {"archived": False}, {"requestId": "not-a-uuid"}]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assert_denied_unchanged("POST", "/supply-request-templates", self.template_payload(**changes))
        self.create_template(items=[self.item(materialName=f"Material {index}") for index in range(200)])
        self.assertEqual(len(self.catalog()["items"][0]["items"]), 200)

    def test_actor_and_company_pins_are_mandatory_strict_positive_integers(self):
        for field in ("expectedActorId", "expectedCompanyId"):
            for value in (None, True, "2", 2.0, 0, -1):
                with self.subTest(field=field, value=value):
                    self.assert_denied_unchanged("POST", "/supply-request-templates", self.template_payload(**{field: value}))
            payload = self.template_payload()
            del payload[field]
            self.assert_denied_unchanged("POST", "/supply-request-templates", payload)
        for changes in ({"expectedCompanyId": 3}, {"expectedActorId": self.f["users"]["foreman"]["id"]}):
            self.assert_denied_unchanged("POST", "/supply-request-templates", self.template_payload(**changes), expected=409)

    def test_active_name_uniqueness_is_unicode_casefolded_within_company(self):
        self.create_template(name="Кабельный набор")
        self.assert_denied_unchanged("POST", "/supply-request-templates",
            self.template_payload(name="  кабельный   НАБОР  "), expected=409)
        foreign, _ = self.create_template(actor="stranger", name="Кабельный набор")
        self.assertEqual(self.sql("SELECT company_id FROM supply_request_templates WHERE id=%s", (foreign["id"],)), [(3,)])

    def test_internal_roles_read_but_accountant_cannot_create_and_supplier_has_no_access(self):
        self.create_template()
        for actor in ("director", "foreman", "worker", "accountant"):
            with self.subTest(actor=actor):
                result = self.catalog(actor)
                self.assertEqual([row["id"] for row in result["items"]], [self.template_id])
                self.assertEqual(result["canCreate"], actor != "accountant")
                self.assertEqual(result["canArchive"], actor == "director")
        self.assert_denied_unchanged("POST", "/supply-request-templates",
                                    self.template_payload(actor="accountant"), actor="accountant", expected=403)
        for path in ("/supply-request-templates", "/supply-request-templates/catalog"):
            self.assert_denied_unchanged("GET", path, actor="supplier", expected=403)
        self.create_template(actor="worker", name="Master reusable set")

    def test_secondary_membership_and_global_mode_do_not_expose_primary_company_templates(self):
        own, _ = self.create_template()
        foreign, _ = self.create_template(actor="stranger")
        actor_id = self.f["users"]["director"]["id"]
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default)
            VALUES(%s,3,1,'бухгалтер',TRUE,FALSE)""", (actor_id,))
        self.addCleanup(self.sql, "DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3", (actor_id,))
        self.assertEqual(self.api("director", "GET", "/supply-request-templates", **{"X-Company-Mode": "all_companies"}), [])
        headers = {"X-Company-Id": "3", "X-Company-Mode": "company"}
        catalog = self.catalog(**headers)
        self.assertEqual([row["id"] for row in catalog["items"]], [foreign["id"]])
        self.assertNotIn(own["id"], [row["id"] for row in catalog["items"]])
        self.assertFalse(catalog["canCreate"])
        self.assertFalse(catalog["canArchive"])
        self.assert_denied_unchanged("POST", "/supply-request-templates",
            self.template_payload(expectedCompanyId=3), expected=403, **headers)

    def test_archive_hides_card_without_deleting_content_and_replay_is_exact(self):
        created, create_payload = self.create_template()
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", "/supply-request-templates", create_payload), created)
        self.assertEqual(self.snapshot(), before)
        stored = self.sql("SELECT name,category,items_json,created_by,created_by_id FROM supply_request_templates WHERE id=%s", (self.template_id,))
        archived = self.api("director", "POST", self.path, self.archive_payload())
        self.assertTrue(archived["ok"])
        self.assertEqual(archived["id"], self.template_id)
        self.assertEqual(self.catalog()["items"], [])
        self.assertEqual(self.api("director", "GET", "/supply-request-templates"), [])
        self.assertEqual(self.sql("SELECT archived,version FROM supply_request_templates WHERE id=%s", (self.template_id,)), [(True, 2)])
        self.assertEqual(self.sql("SELECT name,category,items_json,created_by,created_by_id FROM supply_request_templates WHERE id=%s", (self.template_id,)), stored)
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", "/supply-request-templates", create_payload), created,
                         "Retry of an earlier create returns its saved result even after later archival")
        self.assertEqual(self.snapshot(), before)

    def test_archive_requires_director_current_version_and_exact_tenant(self):
        self.create_template()
        for actor in ("foreman", "worker", "accountant"):
            self.assert_denied_unchanged("POST", self.path, self.archive_payload(actor=actor), expected=403, actor=actor)
        self.assert_denied_unchanged("POST", self.path, self.archive_payload(expectedVersion=999), expected=409)
        for field in ("expectedCompanyId", "expectedActorId"):
            payload = self.archive_payload()
            del payload[field]
            self.assert_denied_unchanged("POST", self.path, payload)
        self.assert_denied_unchanged("POST", f"/supply-request-templates/{self.legacy_id}/archive", self.archive_payload(), expected=404)
        foreign, _ = self.create_template(actor="stranger", name="Foreign archive boundary")
        self.assert_denied_unchanged("POST", f"/supply-request-templates/{foreign['id']}/archive", self.archive_payload(), expected=404)

    def test_reusing_uuid_with_changed_content_rejects_and_archive_retry_has_one_event(self):
        _, payload = self.create_template()
        self.assert_denied_unchanged("POST", "/supply-request-templates", {**payload, "name": "Changed same command"}, expected=409)
        archive = self.archive_payload()
        result = self.api("director", "POST", self.path, archive)
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.path, archive), result)
        self.assertEqual(self.snapshot(), before)
        self.assert_denied_unchanged("POST", self.path, {**archive, "expectedVersion": 2}, expected=409)
        self.assertEqual(self.sql("SELECT action FROM supply_template_events ORDER BY id"), [("create",), ("archive",)])

    def test_writes_stay_closed_when_disabled_and_legacy_delete_never_reopens(self):
        self.create_template()
        with patch.dict(os.environ, {"SUPPLY_TEMPLATES_ENABLED": "0"}):
            self.assert_denied_unchanged("POST", "/supply-request-templates", self.template_payload(name="Disabled create"), expected=409)
            self.assert_denied_unchanged("POST", self.path, self.archive_payload(), expected=409)
            self.assertEqual([row["id"] for row in self.catalog()["items"]], [self.template_id])
            self.assertFalse(self.catalog()["canCreate"])
            self.assertFalse(self.catalog()["canArchive"])
            for actor in ("director", "accountant", "worker"):
                self.assert_denied_unchanged("DELETE", f"/supply-request-templates/{self.template_id}", actor=actor, expected=409)
        self.assert_denied_unchanged("DELETE", f"/supply-request-templates/{self.template_id}", expected=409)

    def test_create_event_failure_rolls_back_template_and_operation_then_same_uuid_retries(self):
        payload = self.template_payload()
        self.sql("""CREATE FUNCTION template_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic template audit failure'; END $$""")
        self.sql("""CREATE TRIGGER template_test_failure AFTER INSERT ON supply_template_events
            FOR EACH ROW EXECUTE FUNCTION template_test_failure()""")
        before = self.snapshot()
        try:
            response = self.request("POST", "/supply-request-templates", payload, actor="director")
            self.assertEqual(response.status_code, 500, response.text)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql("DROP TRIGGER template_test_failure ON supply_template_events")
            self.sql("DROP FUNCTION template_test_failure()")
        result = self.api("director", "POST", "/supply-request-templates", payload)
        self.assertTrue(result["eventId"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supply_template_events"), [(1,)])

    def test_owned_template_content_and_audit_are_database_immutable(self):
        import psycopg2
        result, _ = self.create_template()
        statements = [
            ("UPDATE supply_request_templates SET name='Rewritten',version=version+1 WHERE id=%s", self.template_id),
            ("UPDATE supply_request_templates SET items_json='[]',version=version+1 WHERE id=%s", self.template_id),
            ("UPDATE supply_request_templates SET company_id=3,version=version+1 WHERE id=%s", self.template_id),
            ("UPDATE supply_request_templates SET created_by='Other person',version=version+1 WHERE id=%s", self.template_id),
            ("DELETE FROM supply_request_templates WHERE id=%s", self.template_id),
            ("UPDATE supply_template_events SET reason='Rewritten' WHERE id=%s", result["eventId"]),
            ("DELETE FROM supply_template_events WHERE id=%s", result["eventId"]),
        ]
        for statement, key in statements:
            with self.subTest(statement=statement):
                before = self.snapshot()
                with self.assertRaises(psycopg2.Error) as caught:
                    self.sql(statement, (key,))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(caught.exception.pgcode, "P0001", str(caught.exception))

    def wait_for_lock(self, prefix, future):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            count = self.sql("""SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database()
                AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE %s""", (prefix + "%",))[0][0]
            if count or future.done():
                return count
            time.sleep(0.02)
        return 0

    def race_commands(self, path, first_payload, second_payload, action):
        self.sql("""CREATE FUNCTION pause_template_test_command() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(914263,1); RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER pause_template_test_command BEFORE INSERT ON supply_template_events
            FOR EACH ROW EXECUTE FUNCTION pause_template_test_command()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(914263,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", path, first_payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("INSERT INTO supply_template_events", first), 1,
                                     f"First {action} must pause before its real audit insert")
                    second = pool.submit(self.request, "POST", path, second_payload, "director")
                    self.assertEqual(self.wait_for_lock("SELECT pg_advisory_xact_lock(", second), 1,
                                     f"Second {action} must wait on company serialization")
                finally:
                    blocker.rollback()
                return first.result(timeout=20), second.result(timeout=20)
        finally:
            blocker.close()
            self.sql("DROP TRIGGER pause_template_test_command ON supply_template_events")
            self.sql("DROP FUNCTION pause_template_test_command()")

    def test_concurrent_create_replay_returns_one_template_and_one_audit_event(self):
        payload = self.template_payload()
        first, second = self.race_commands("/supply-request-templates", payload, payload, "create")
        self.assertEqual([first.status_code, second.status_code], [200, 200], [first.text, second.text])
        self.assertEqual(first.json(), second.json())
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supply_request_templates WHERE company_id=2"), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supply_template_events"), [(1,)])

    def test_two_concurrent_archives_with_different_uuids_cannot_duplicate_history(self):
        self.create_template()
        first_payload = self.archive_payload()
        first, second = self.race_commands(self.path, first_payload, {**first_payload, "requestId": str(uuid4())}, "archive")
        self.assertEqual([first.status_code, second.status_code], [200, 409], [first.text, second.text])
        self.assertEqual(self.sql("SELECT archived,version FROM supply_request_templates WHERE id=%s", (self.template_id,)), [(True, 2)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supply_template_events WHERE action='archive'"), [(1,)])

    def test_revocation_committed_while_actor_pin_waits_rejects_pending_create(self):
        payload = self.template_payload(actor="worker")
        actor_id = self.f["users"]["worker"]["id"]
        restore = "UPDATE user_company_roles SET active=TRUE WHERE company_id=2 AND user_id=%s"
        self.addCleanup(self.sql, restore, (actor_id,))
        before = self.snapshot()
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s", (actor_id,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self.request, "POST", "/supply-request-templates", payload, "worker")
                try:
                    self.assertEqual(self.wait_for_lock("SELECT role,assigned_projects,assigned_packages FROM user_company_roles", pending), 1)
                    blocker.commit()
                finally:
                    blocker.rollback()
                response = pending.result(timeout=20)
        finally:
            blocker.close()
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.snapshot(), before)
        self.sql(restore, (actor_id,))
        self.api("worker", "POST", "/supply-request-templates", payload)

    def test_successful_command_replay_rechecks_current_membership_role(self):
        _, payload = self.create_template(actor="worker")
        actor_id = self.f["users"]["worker"]["id"]
        self.sql("UPDATE user_company_roles SET role='бухгалтер' WHERE company_id=2 AND user_id=%s", (actor_id,))
        self.addCleanup(self.sql, "UPDATE user_company_roles SET role='мастер' WHERE company_id=2 AND user_id=%s", (actor_id,))
        self.assert_denied_unchanged("POST", "/supply-request-templates", payload, actor="worker", expected=403)


if __name__ == "__main__":
    unittest.main()
