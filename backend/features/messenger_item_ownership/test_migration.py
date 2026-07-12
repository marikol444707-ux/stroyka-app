import unittest
from unittest.mock import patch

from . import migration as migration_module
from .migration import _plan_sha256, build_report, classify_item, run_migration


OWNER_COLUMNS = {"owner_scope", "company_id", "project_id"}


def owner_result(status="verified", reason="verified_project_or_entity_owner", company_id=1, project_id=None):
    return {
        "status": status,
        "reason": reason,
        "companyId": company_id if status == "verified" else None,
        "projectId": project_id if status == "verified" else None,
        "recipientCompanyIds": [],
    }


class FakeCursor:
    def __init__(self, file_updates=0, outbox_updates=0):
        self.calls = []
        self.rowcount = 0
        self.file_updates = file_updates
        self.outbox_updates = outbox_updates
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if compact.startswith("UPDATE messenger_files f SET owner_scope"):
            self.rowcount = self.file_updates
        elif compact.startswith("UPDATE messenger_outbox o SET owner_scope"):
            self.rowcount = self.outbox_updates

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.session_calls = []
        self.committed = False
        self.rolled_back = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class MessengerItemOwnershipMigrationTests(unittest.TestCase):
    def test_verified_outbox_inherits_company_owner(self):
        result = classify_item(
            "messenger_outbox", {"id": 26, "status": "sent"}, owner_result(company_id=1), set()
        )
        self.assertEqual((result["status"], result["proposedScope"]), ("ready", "company"))
        self.assertEqual(result["proposedCompanyId"], 1)

    def test_explicit_failed_orphan_can_be_preserved_as_legacy(self):
        result = classify_item(
            "messenger_outbox",
            {"id": 30, "status": "failed"},
            owner_result(status="unresolved", reason="entity_parent_not_found"),
            {30},
        )
        self.assertEqual((result["status"], result["proposedScope"]), ("ready", "legacy"))
        self.assertIsNone(result["proposedCompanyId"])

    def test_failed_orphan_requires_explicit_operator_selection(self):
        result = classify_item(
            "messenger_outbox",
            {"id": 30, "status": "failed"},
            owner_result(status="unresolved", reason="entity_parent_not_found"),
            set(),
        )
        self.assertEqual((result["status"], result["reason"]), ("unresolved", "entity_parent_not_found"))

    def test_non_terminal_outbox_cannot_be_marked_legacy(self):
        result = classify_item(
            "messenger_outbox",
            {"id": 30, "status": "queued"},
            owner_result(status="unresolved", reason="entity_parent_not_found"),
            {30},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "legacy_outbox_not_terminal"))

    def test_orphan_with_recipient_company_cannot_be_marked_legacy(self):
        evidence = owner_result(status="unresolved", reason="entity_parent_not_found")
        evidence["recipientCompanyIds"] = [1]
        result = classify_item(
            "messenger_outbox", {"id": 30, "status": "failed"}, evidence, {30}
        )
        self.assertEqual(
            (result["status"], result["reason"]),
            ("mismatched", "legacy_outbox_has_recipient_owner"),
        )

    def test_stored_legacy_is_revalidated_without_operator_argument(self):
        result = classify_item(
            "messenger_outbox",
            {"id": 30, "status": "failed", "stored_scope": "legacy"},
            owner_result(status="unresolved", reason="entity_parent_not_found"),
            set(),
        )
        self.assertEqual((result["status"], result["reason"]), ("stored", "stored_owner_verified"))

    def test_stored_legacy_with_new_recipient_evidence_requires_review(self):
        evidence = owner_result(status="unresolved", reason="entity_parent_not_found")
        evidence["recipientCompanyIds"] = [1]
        result = classify_item(
            "messenger_outbox",
            {"id": 30, "status": "failed", "stored_scope": "legacy"},
            evidence,
            set(),
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "stored_owner_invalid"))

    def test_stored_company_owner_mismatch_is_blocked(self):
        result = classify_item(
            "messenger_outbox",
            {"id": 26, "status": "sent", "stored_scope": "company", "stored_company_id": 2},
            owner_result(company_id=1),
            set(),
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "stored_owner_mismatch"))

    def test_unknown_explicit_legacy_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown outbox IDs"):
            build_report(OWNER_COLUMNS, OWNER_COLUMNS, [], requested_legacy_ids={99}, seen_outbox_ids={30})

    def test_strict_ready_requires_columns_and_no_pending_rows(self):
        ready = classify_item(
            "messenger_outbox", {"id": 26, "status": "sent"}, owner_result(), set()
        )
        self.assertFalse(build_report(set(), set(), [ready])["readyForStrictRuntime"])
        stored = {**ready, "status": "stored", "reason": "stored_owner_verified"}
        self.assertTrue(build_report(OWNER_COLUMNS, OWNER_COLUMNS, [stored])["readyForStrictRuntime"])

    def test_dry_run_is_read_only(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        ready = classify_item("messenger_outbox", {"id": 26, "status": "sent"}, owner_result(), set())
        with patch.object(
            migration_module, "collect_ownership", return_value=(set(), set(), [ready], {26})
        ):
            result = run_migration(connection, legacy_outbox_ids=set(), apply=False)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)

    def test_apply_updates_rows_and_commits_after_clean_postcheck(self):
        cursor = FakeCursor(outbox_updates=2)
        connection = FakeConnection(cursor)
        company = classify_item("messenger_outbox", {"id": 26, "status": "sent"}, owner_result(), {30})
        legacy = classify_item(
            "messenger_outbox",
            {"id": 30, "status": "failed"},
            owner_result(status="unresolved", reason="entity_parent_not_found"),
            {30},
        )
        stored = [
            {**company, "status": "stored", "reason": "stored_owner_verified"},
            {**legacy, "status": "stored", "reason": "stored_owner_verified"},
        ]
        with patch.object(
            migration_module,
            "collect_ownership",
            side_effect=[(set(), set(), [company, legacy], {26, 30}), (OWNER_COLUMNS, OWNER_COLUMNS, stored, {26, 30})],
        ):
            result = run_migration(connection, {30}, True, 2, _plan_sha256([company, legacy]))
        self.assertTrue(result["complete"])
        self.assertEqual(result["updatedOutbox"], 2)
        self.assertTrue(connection.committed)

    def test_schema_prevents_legacy_row_from_becoming_queued(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch.object(
            migration_module,
            "collect_ownership",
            side_effect=[(set(), set(), [], set()), (OWNER_COLUMNS, OWNER_COLUMNS, [], set())],
        ):
            run_migration(connection, set(), True, 0, _plan_sha256([]))
        constraints = "\n".join(sql for sql, _params in cursor.calls if "ADD CONSTRAINT" in sql)
        self.assertIn("owner_scope IS DISTINCT FROM 'legacy' OR status IN ('failed','skipped')", constraints)


if __name__ == "__main__":
    unittest.main()
