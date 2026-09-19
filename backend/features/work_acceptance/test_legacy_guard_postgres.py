"""Acceptance boundary regressions through authenticated HTTP and real PG.

Uses only the explicitly provisioned disposable socket database. Shared fixture
methods are borrowed without inheriting the material-accounting test suite.
"""
import os
import unittest

from backend.features.work_material_accounting import test_postgres as support


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class LegacyWorkAcceptancePostgresTests(unittest.TestCase):
    sql = support.WorkMaterialAccountingPostgresTests.sql
    api = support.WorkMaterialAccountingPostgresTests.api
    payload = support.WorkMaterialAccountingPostgresTests.payload
    balance = support.WorkMaterialAccountingPostgresTests.balance
    work_payload = support.WorkMaterialAccountingPostgresTests.work_payload
    request = support.WorkMaterialAccountingPostgresTests.request
    consumption_payload = support.WorkMaterialAccountingPostgresTests.consumption_payload
    create_consumption = support.WorkMaterialAccountingPostgresTests.create_consumption
    stock_quantity = support.WorkMaterialAccountingPostgresTests.stock_quantity

    @classmethod
    def setUpClass(cls):
        support.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        support.WorkMaterialAccountingPostgresTests.setUp(self)
        journal, self.submission = self.create_consumption(
            personal=1, warehouse=1, roomName="Synthetic acceptance room",
            photoUrl="/uploads/synthetic-submitted-work.jpg", comment="Submitted for review")
        self.journal_id = journal["id"]
        self.path = "/work-journal/" + str(self.journal_id)
        self.assertEqual(self.submission["quantity"], 1)

    def snapshot(self):
        # Includes immutable material/act ledgers from migration 0027, personal
        # and warehouse balances, work and contract totals, and legacy finance.
        tables = ("brigade_contracts", "brigade_acts", "brigade_payments",
                  "project_payments", "interim_acts", "piecework")
        return support.WorkMaterialAccountingPostgresTests.snapshot(self) + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in tables)

    def confirm(self, quantity=1):
        self.api("director", "PUT", self.path,
                 {"status": "Подтверждено", "quantity": quantity})
        self.assertEqual(self.sql("SELECT status,quantity FROM work_journal WHERE id=%s",
                                  (self.journal_id,)), [("Подтверждено", quantity)])

    def assert_rejected_unchanged(self, actor, payload, statuses):
        before = self.snapshot()
        response = self.request("PUT", self.path, payload, actor=actor)
        stored = self.sql("""SELECT status,quantity,photo_url,comment,execution_total
            FROM work_journal WHERE id=%s""", (self.journal_id,))
        self.assertIn(response.status_code, statuses,
                      f"{actor}: {response.text}; persisted work={stored!r}")
        self.assertEqual(self.snapshot(), before)

    def test_worker_cannot_change_accepted_quantity(self):
        self.confirm()
        self.assert_rejected_unchanged("worker", {"quantity": 0.5}, {409})

    def test_worker_cannot_replace_accepted_photo(self):
        self.confirm()
        self.assert_rejected_unchanged(
            "worker", {"photoUrl": "/uploads/synthetic-replaced-after-acceptance.jpg"}, {409})

    def test_worker_cannot_rewrite_accepted_comment(self):
        self.confirm()
        self.assert_rejected_unchanged("worker", {"comment": "Edited after acceptance"}, {409})

    def test_reviewer_cannot_accept_negative_quantity(self):
        self.assert_rejected_unchanged(
            "director", {"status": "Подтверждено", "quantity": -1}, {400, 422})

    def test_reviewer_cannot_accept_zero_quantity(self):
        self.assert_rejected_unchanged(
            "foreman", {"status": "Подтверждено", "quantity": 0}, {400, 422})

    def test_reviewer_cannot_accept_more_than_submitted_quantity(self):
        # Two units fit the contract's 100-unit limit, but this submission is
        # only one unit. Contract capacity must not substitute for review scope.
        self.assert_rejected_unchanged(
            "director", {"status": "Подтверждено", "quantity": 2}, {400, 422})

    def test_repeat_acceptance_without_expected_state_cannot_overwrite_accepted_quantity(self):
        self.confirm(quantity=0.5)
        self.assert_rejected_unchanged(
            "director", {"status": "Подтверждено", "quantity": 0.75}, {409})

    def test_accountant_cannot_raw_reject_without_confirmed_by(self):
        self.assertEqual(self.f["users"]["accountant"]["role"], "бухгалтер")
        # No confirmedBy/confirmedAt: do not rely on their separate role guard.
        self.assert_rejected_unchanged("accountant", {"status": "Отклонено"}, {403})


if __name__ == "__main__":
    unittest.main()
