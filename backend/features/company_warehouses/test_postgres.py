"""Tenant boundaries for the warehouse directory through real authenticated HTTP."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from .test_support import CompanyWarehousesPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class CompanyWarehousesPostgresTests(CompanyWarehousesPostgresSupport, unittest.TestCase):
    def test_unattributed_legacy_warehouses_are_not_visible_in_selected_company(self):
        before = self.snapshot()
        rows = self.api("director", "GET", "/warehouses", **self.own_headers())
        self.assertNotIn(self.legacy_id, [row["id"] for row in rows],
                         "Historical records without verified company ownership must not become global directory entries")
        self.assertEqual(self.snapshot(), before)

    def test_director_cannot_rewrite_an_unattributed_legacy_warehouse(self):
        self.assert_denied_unchanged("PUT", f"/warehouses/{self.legacy_id}", self.warehouse_payload(name="Hijacked historical row"))

    def test_director_cannot_delete_an_unattributed_legacy_warehouse(self):
        self.assert_denied_unchanged("DELETE", f"/warehouses/{self.legacy_id}")

    def test_legacy_create_cannot_add_another_globally_shared_warehouse(self):
        self.assert_denied_unchanged("POST", "/warehouses", self.warehouse_payload())

    def test_warehouse_created_by_other_company_is_not_visible_or_mutable(self):
        created, _ = self.create_card(actor="stranger", name="Company3 private warehouse")
        foreign_id = created["warehouseId"]
        before = self.snapshot()
        rows = self.api("director", "GET", "/warehouses", **self.own_headers())
        with self.subTest(action="read"):
            self.assertNotIn(foreign_id, [row["id"] for row in rows], "Selected company2 must never disclose company3 warehouse details")
        self.assertEqual(self.snapshot(), before)
        with self.subTest(action="update"):
            self.assert_denied_unchanged("PUT", f"/warehouses/{foreign_id}", self.warehouse_payload(name="Cross-company overwrite"))
        with self.subTest(action="delete"):
            self.assert_denied_unchanged("DELETE", f"/warehouses/{foreign_id}")

    def test_create_records_authenticated_company_and_author_and_leaves_legacy_owner_null(self):
        created, _ = self.create_card(name="  Северный   склад  ")
        detail = self.detail()
        card = detail["warehouse"]
        self.assertEqual(card["id"], created["warehouseId"])
        self.assertEqual(card["companyId"], 2)
        self.assertEqual(card["name"], "Северный склад")
        self.assertEqual(card["version"], 1)
        self.assertFalse(card["archived"])
        self.assertTrue(detail["canManage"])
        self.assertTrue(detail["canArchive"])
        self.assertEqual(len(detail["history"]), 1)
        self.assertEqual(self.sql("SELECT company_id FROM warehouses WHERE id=%s", (self.legacy_id,)), [(None,)])
        events = self.sql("""SELECT company_id,actor_id,action,before_card,after_card
            FROM warehouse_directory_events WHERE warehouse_id=%s""", (created["warehouseId"],))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][:3], (2, self.f["users"]["director"]["id"], "create"))
        self.assertEqual(events[0][4]["name"], "Северный склад")

    def test_create_and_update_replays_return_same_event_without_extra_card_or_version(self):
        created, create_payload = self.create_card()
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", "/warehouses/directory", create_payload), created)
        self.assertEqual(self.snapshot(), before)
        self.assert_denied_unchanged("POST", "/warehouses/directory", {**create_payload, "name": "Changed replay"})
        update = self.update_payload(address="Corrected address")
        updated = self.api("director", "POST", self.path, update)
        self.assertEqual(self.detail()["warehouse"]["version"], 2)
        self.assertEqual(self.detail()["warehouse"]["address"], "Corrected address")
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.path, update), updated)
        self.assertEqual(self.snapshot(), before)
        self.assert_denied_unchanged("POST", self.path, {**update, "notes": "Different same UUID"})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM warehouse_directory_events WHERE warehouse_id=%s", (self.warehouse_id,)), [(2,)])

    def test_stale_update_cannot_overwrite_a_saved_edit(self):
        self.create_card()
        stale = self.update_payload(notes="Old form contents")
        self.api("director", "POST", self.path, self.update_payload(notes="Saved newer contents"))
        self.assert_denied_unchanged("POST", self.path, stale)
        self.assertEqual(self.detail()["warehouse"]["notes"], "Saved newer contents")

    def test_active_names_are_unique_only_within_the_same_company(self):
        self.create_card(name="Северный склад")
        self.assert_denied_unchanged("POST", "/warehouses/directory", {
            "action": "create", "requestId": str(uuid4()), **self.warehouse_payload(name="  северный   СКЛАД ")})
        foreign, _ = self.create_card(actor="stranger", name="Северный склад")
        self.assertEqual(self.sql("SELECT company_id FROM warehouses WHERE id=%s", (foreign["warehouseId"],)), [(3,)])

    def test_update_cannot_adopt_another_active_name_with_different_cyrillic_case(self):
        self.create_card(name="Северный склад")
        self.create_card(name="Южный склад")
        self.assert_denied_unchanged("POST", self.path, self.update_payload(name="северный СКЛАД"))
        self.assertEqual(self.detail()["warehouse"]["name"], "Южный склад")

    def test_restore_cannot_duplicate_the_active_replacement_name(self):
        first, _ = self.create_card(name="Северный склад")
        self.api("director", "POST", self.path, self.command_payload("archive", reason="Temporary closure"))
        replacement, _ = self.create_card(name="северный СКЛАД")
        old_path = f"/warehouses/{first['warehouseId']}/directory"
        self.assert_denied_unchanged("POST", old_path, {
            "action": "restore", "requestId": str(uuid4()), "expectedVersion": 2, "reason": "Reopen original"})
        self.assertEqual(self.sql("SELECT archived FROM warehouses WHERE id=%s", (first["warehouseId"],)), [(True,)])
        self.assertEqual([row["id"] for row in self.api("director", "GET", "/warehouses", **self.own_headers())],
                         [replacement["warehouseId"]])

    def test_archive_restore_preserves_card_and_history_and_active_legacy_projection(self):
        self.create_card()
        for action in ("archive", "restore"):
            self.assert_denied_unchanged("POST", self.path, self.command_payload(action, reason=""), expected=400)
            payload = self.command_payload(action, reason="Warehouse temporarily closed" if action == "archive" else "Warehouse reopened")
            result = self.api("director", "POST", self.path, payload)
            archived = action == "archive"
            self.assertEqual(self.detail()["warehouse"]["archived"], archived)
            active_ids = [row["id"] for row in self.api("director", "GET", "/warehouses", **self.own_headers())]
            self.assertEqual(self.warehouse_id in active_ids, not archived)
            directory = self.api("director", "GET", "/warehouses/directory")
            self.assertIn(self.warehouse_id, [row["id"] for row in directory["items"]])
            before = self.snapshot()
            self.assertEqual(self.api("director", "POST", self.path, payload), result)
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.detail()["warehouse"]["version"], 3)
        self.assertEqual(len(self.detail()["history"]), 3)

    def test_new_detail_and_commands_hide_foreign_and_unowned_rows(self):
        foreign, _ = self.create_card(actor="stranger")
        for warehouse_id in (self.legacy_id, foreign["warehouseId"]):
            with self.subTest(warehouse_id=warehouse_id):
                self.assert_denied_unchanged("GET", f"/warehouses/{warehouse_id}/directory", expected=404)
                self.assert_denied_unchanged("POST", f"/warehouses/{warehouse_id}/directory", {
                    "action": "archive", "requestId": str(uuid4()), "expectedVersion": 1, "reason": "Wrong company"}, expected=404)

    def test_all_company_mode_and_selected_secondary_membership_never_use_primary_role(self):
        own, _ = self.create_card(name="Company2 private")
        foreign, _ = self.create_card(actor="stranger", name="Company3 private")
        director_id = self.f["users"]["director"]["id"]
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default)
            VALUES(%s,3,1,'бухгалтер',TRUE,FALSE)""", (director_id,))
        self.addCleanup(self.sql, "DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3", (director_id,))
        global_headers = {"X-Company-Mode": "all_companies"}
        self.assertEqual(self.api("director", "GET", "/warehouses", **global_headers), [])
        other_headers = {"X-Company-Mode": "company", "X-Company-Id": "3"}
        listing = self.api("director", "GET", "/warehouses/directory", **other_headers)
        self.assertEqual([row["id"] for row in listing["items"]], [foreign["warehouseId"]])
        self.assertNotIn(own["warehouseId"], [row["id"] for row in listing["items"]])
        self.assertFalse(listing["canManage"])
        self.assertFalse(listing["canArchive"])
        before = self.snapshot()
        self.api("director", "POST", "/warehouses/directory", {
            "action": "create", "requestId": str(uuid4()), **self.warehouse_payload()}, expected=403, **other_headers)
        self.assertEqual(self.snapshot(), before)

    def test_accountant_is_readonly_and_foreman_and_worker_cannot_read_the_directory(self):
        self.create_card()
        readonly = self.detail(actor="accountant")
        self.assertFalse(readonly["canManage"])
        self.assertFalse(readonly["canArchive"])
        payload = self.update_payload(notes="Unauthorized edit")
        before = self.snapshot()
        for actor in ("accountant", "foreman", "worker"):
            with self.subTest(actor=actor):
                self.api(actor, "POST", self.path, payload, expected=403)
                if actor != "accountant":
                    self.api(actor, "GET", "/warehouses/directory", expected=403)
                    self.api(actor, "GET", self.path, expected=403)
                self.assertEqual(self.snapshot(), before)

    def test_storekeeper_can_edit_but_only_director_can_archive_or_restore(self):
        actor_id = self.f["users"]["accountant"]["id"]
        self.sql("UPDATE user_company_roles SET role='кладовщик' WHERE user_id=%s AND company_id=2", (actor_id,))
        self.addCleanup(self.sql, "UPDATE user_company_roles SET role='бухгалтер' WHERE user_id=%s AND company_id=2", (actor_id,))
        self.create_card(actor="accountant", name="Created by storekeeper")
        rights = self.detail(actor="accountant")
        self.assertTrue(rights["canManage"])
        self.assertFalse(rights["canArchive"])
        self.api("accountant", "POST", self.path, self.update_payload(address="Verified by storekeeper"))
        before = self.snapshot()
        self.api("accountant", "POST", self.path, self.command_payload("archive", reason="Not a director"), expected=403)
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", self.path, self.command_payload("archive", reason="Approved closure"))
        before = self.snapshot()
        self.api("accountant", "POST", self.path, self.command_payload("restore", reason="Not a director"), expected=403)
        self.assertEqual(self.snapshot(), before)

    def test_fields_are_strict_and_owner_or_client_author_cannot_be_supplied(self):
        for invalid in ({"name": "   "}, {"name": 123}, {"city": []}, {"address": True}, {"notes": {}},
                        {"name": "X" * 10001}, {"companyId": 3}, {"createdBy": "Other director"}, {"archived": True}):
            with self.subTest(invalid=invalid):
                payload = {"action": "create", "requestId": str(uuid4()), **self.warehouse_payload(), **invalid}
                self.assert_denied_unchanged("POST", "/warehouses/directory", payload, expected=400)
        self.create_card()
        for invalid in ({"name": False}, {"city": None}, {"companyId": 3}, {"version": 999}):
            with self.subTest(update=invalid):
                self.assert_denied_unchanged("POST", self.path, {**self.update_payload(), **invalid}, expected=400)

    def test_stale_actor_and_company_context_reject_commands_without_creating_history(self):
        self.create_card()
        for context in ({"expectedCompanyId": 3}, {"expectedActorId": self.f["users"]["foreman"]["id"]}):
            with self.subTest(context=context):
                self.assert_denied_unchanged("POST", self.path, {**self.update_payload(), **context})
                self.assert_denied_unchanged("POST", "/warehouses/directory", {
                    "action": "create", "requestId": str(uuid4()), **self.warehouse_payload(name="Pinned new card"), **context})

    def test_disabled_flag_closes_new_commands_but_never_reopens_legacy_mutations(self):
        self.create_card()
        update = self.update_payload(notes="Unavailable while disabled")
        before = self.snapshot()
        with patch.dict(os.environ, {"WAREHOUSE_DIRECTORY_ENABLED": "0"}):
            self.assert_denied_unchanged("POST", self.path, update, expected=409)
            for actor in ("director", "accountant", "worker"):
                for method, path, data in (("POST", "/warehouses", self.warehouse_payload()),
                                           ("PUT", f"/warehouses/{self.warehouse_id}", self.warehouse_payload()),
                                           ("DELETE", f"/warehouses/{self.warehouse_id}", None)):
                    with self.subTest(actor=actor, method=method):
                        self.api(actor, method, path, data, expected=409)
                        self.assertEqual(self.snapshot(), before)
            rows = self.api("director", "GET", "/warehouses", **self.own_headers())
            self.assertEqual([row["id"] for row in rows], [self.warehouse_id])

    def test_event_insert_failure_rolls_back_card_version_and_command_then_same_uuid_retries(self):
        self.create_card()
        payload = self.update_payload(notes="Atomic change")
        self.sql("""CREATE FUNCTION company_warehouse_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic directory event failure'; END $$""")
        self.sql("""CREATE TRIGGER company_warehouse_test_failure AFTER INSERT ON warehouse_directory_events
            FOR EACH ROW EXECUTE FUNCTION company_warehouse_test_failure()""")
        before = self.snapshot()
        try:
            response = self.request("POST", self.path, payload, actor="director")
            self.assertEqual(response.status_code, 500, response.text)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql("DROP TRIGGER company_warehouse_test_failure ON warehouse_directory_events")
            self.sql("DROP FUNCTION company_warehouse_test_failure()")
        self.api("director", "POST", self.path, payload)
        self.assertEqual(self.detail()["warehouse"]["version"], 2)
        self.assertEqual(self.detail()["warehouse"]["notes"], "Atomic change")

    def test_event_history_is_immutable_at_database_boundary(self):
        import psycopg2
        result, _ = self.create_card()
        for statement in ("UPDATE warehouse_directory_events SET reason='Rewritten reason' WHERE id=%s",
                          "DELETE FROM warehouse_directory_events WHERE id=%s"):
            with self.subTest(statement=statement):
                before = self.snapshot()
                with self.assertRaises(psycopg2.Error) as caught:
                    self.sql(statement, (result["eventId"],))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(caught.exception.pgcode, "P0001", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
