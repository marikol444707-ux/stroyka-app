import unittest

from fastapi import HTTPException

from .outbox_worker_access import (
    WORKER_OUTBOX_SCOPE_SQL,
    assert_worker_outbox_owner,
    dispatch_outbox_lock_clause,
)


class MessengerOutboxWorkerAccessTests(unittest.TestCase):
    def test_company_owned_row_is_dispatchable(self):
        owner = assert_worker_outbox_owner({
            "id": 17,
            "owner_scope": "company",
            "company_id": 4,
            "project_id": 21,
        })

        self.assertEqual(owner, {"companyId": 4, "projectId": 21})

    def test_legacy_row_is_not_dispatchable(self):
        with self.assertRaisesRegex(HTTPException, "не привязана к компании"):
            assert_worker_outbox_owner({
                "id": 17,
                "owner_scope": "legacy",
                "company_id": None,
            })

    def test_ownerless_row_is_not_dispatchable(self):
        with self.assertRaisesRegex(HTTPException, "не привязана к компании"):
            assert_worker_outbox_owner({"id": 17})

    def test_worker_scope_requires_stored_company_owner(self):
        self.assertEqual(
            WORKER_OUTBOX_SCOPE_SQL,
            "owner_scope='company' AND company_id IS NOT NULL",
        )

    def test_real_dispatch_locks_selected_rows(self):
        self.assertEqual(dispatch_outbox_lock_clause(dry_run=False), " FOR UPDATE SKIP LOCKED")

    def test_dry_run_does_not_lock_rows(self):
        self.assertEqual(dispatch_outbox_lock_clause(dry_run=True), "")


if __name__ == "__main__":
    unittest.main()
