import json
import unittest
from decimal import Decimal

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.assignment_apply import (
    AssignmentApplyError,
    apply_assignment_plan,
    normalize_assignment_apply_payload,
    prepare_assignment_operations,
)
from backend.features.estimate_row_transfer.test_audit import _sections
from backend.features.estimate_row_transfer.test_storage import (
    entry_row,
    reviewed_plan,
)


def approved_stored_plan():
    plan = reviewed_plan()
    return {
        "id": 5,
        "status": "approved",
        "approvedPlanSha256": plan["planSha256"],
        "canonicalPlan": plan,
    }


def source_item(**overrides):
    row = {
        "id": 41,
        "contract_id": 7,
        "estimate_section": "Раздел",
        "description": "Старая работа",
        "work_package": "Отделка",
        "estimate_item_key": "old-row",
        "unit": "м2",
        "quantity": 10,
        "price_smeta": Decimal("850"),
        "price_brigade": Decimal("700"),
        "done_quantity": 4,
        "status": "В работе",
        "source_type": "estimate",
        "source_estimate_version_id": 71,
        "source_section_index": 0,
        "source_item_index": 0,
        "source_item_key": "old-row",
    }
    row.update(overrides)
    return row


def target_snapshot(**overrides):
    sections = _sections("new-row")
    row = {
        "id": 72,
        "estimate_id": 15,
        "sections_json": json.dumps(sections, ensure_ascii=False),
        "sections_sha256": sections_sha256(sections),
    }
    row.update(overrides)
    return row


def contract(**overrides):
    row = {
        "id": 7,
        "company_id": 1,
        "project_id": 3,
        "work_package": "Отделка",
        "total_amount": Decimal("7000"),
    }
    row.update(overrides)
    return row


def journal_rows(confirmed="4"):
    return [{
        "id": 91,
        "contract_item_id": 41,
        "quantity": Decimal(confirmed),
        "status": "Подтверждено",
    }]


def transfer_receipt(plan=None, **overrides):
    plan = plan or reviewed_plan()
    row = {
        "id": 201,
        "entry_id": 8,
        "plan_id": 5,
        "company_id": 1,
        "project_id": 3,
        "plan_sha256": plan["planSha256"],
        "source_item_id": 41,
        "target_item_id": 101,
        "transfer_quantity": Decimal("3"),
        "applied_at": "2026-08-07 12:00:00+03",
    }
    row.update(overrides)
    return row


class ApplyCursor:
    def __init__(self, *, existing_receipts=None, post_total="7000"):
        self.calls = []
        self.current = None
        self.receipt_reads = 0
        self.existing_receipts = existing_receipts
        self.post_total = Decimal(post_total)

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        lowered = compact.lower()
        self.calls.append((compact, params))
        if "from public.estimate_row_transfer_entries" in lowered:
            self.current = [entry_row(reviewed_plan())]
        elif "from public.estimate_row_assignment_transfers" in lowered:
            self.receipt_reads += 1
            if self.receipt_reads == 1:
                self.current = list(self.existing_receipts or [])
            else:
                self.current = [transfer_receipt()]
        elif "from public.brigade_contracts" in lowered and "for update" in lowered:
            self.current = [contract()]
        elif "from public.brigade_contract_items" in lowered and "for update" in lowered:
            self.current = [source_item()]
        elif "from public.work_journal" in lowered and "for update" in lowered:
            self.current = journal_rows()
        elif "from public.estimate_versions" in lowered:
            self.current = target_snapshot()
        elif lowered.startswith("update public.brigade_contract_items"):
            self.current = {"id": 41, "quantity": Decimal("7")}
        elif lowered.startswith("insert into public.brigade_contract_items"):
            self.current = {
                "id": 101,
                "quantity": Decimal("3"),
                "price_smeta": Decimal("900"),
                "price_brigade": Decimal("700"),
                "done_quantity": Decimal("0"),
            }
        elif "sum(quantity::numeric*price_brigade)" in lowered:
            self.current = [{"contract_id": 7, "contract_total": self.post_total}]
        elif lowered.startswith("update public.brigade_contracts"):
            self.current = {"id": 7, "total_amount": self.post_total}
        elif lowered.startswith("insert into public.estimate_row_assignment_transfers"):
            self.current = {"id": 201, "applied_at": "2026-08-07 12:00:00+03"}
        else:
            raise AssertionError("unexpected SQL: " + compact)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return list(self.current or [])


class AssignmentApplyPayloadTests(unittest.TestCase):
    def test_accepts_only_exact_lowercase_plan_hash(self):
        digest = "a" * 64

        self.assertEqual(
            normalize_assignment_apply_payload({"planSha256": digest}),
            {"planSha256": digest},
        )
        invalid = (
            {},
            {"planSha256": digest, "confirm": True},
            {"planSha256": digest.upper()},
            {"planSha256": "a" * 63},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(
                    AssignmentApplyError,
                    "assignment_apply_payload_invalid",
                ):
                    normalize_assignment_apply_payload(payload)


class AssignmentApplyPreparationTests(unittest.TestCase):
    def _prepare(self, **overrides):
        stored = approved_stored_plan()
        entry = entry_row(stored["canonicalPlan"])
        values = {
            "stored": stored,
            "assignment_entries": [entry],
            "contracts": [contract()],
            "contract_items": [source_item()],
            "journal_rows": journal_rows(),
            "target_snapshot": target_snapshot(),
        }
        values.update(overrides)
        return prepare_assignment_operations(**values)

    def test_prepares_exact_split_with_target_estimate_and_source_brigade_prices(self):
        operations = self._prepare()

        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual(operation["entryId"], 8)
        self.assertEqual(operation["sourceItemId"], 41)
        self.assertEqual(operation["sourceQuantityBefore"], Decimal("10"))
        self.assertEqual(operation["sourceQuantityAfter"], Decimal("7"))
        self.assertEqual(operation["confirmedQuantity"], Decimal("4"))
        self.assertEqual(operation["transferQuantity"], Decimal("3"))
        self.assertEqual(operation["sourcePriceBrigade"], Decimal("700"))
        self.assertEqual(operation["targetPriceSmeta"], Decimal("900"))
        self.assertEqual(operation["targetPriceBrigade"], Decimal("700"))
        self.assertEqual(operation["contractTotalBefore"], Decimal("7000"))
        self.assertEqual(operation["target"]["sourceEstimateVersionId"], 72)
        self.assertEqual(operation["target"]["sourceItemKey"], "new-row")
        self.assertEqual(operation["target"]["doneQuantity"], Decimal("0"))

    def test_confirmed_journal_drift_blocks_before_operations_are_returned(self):
        with self.assertRaisesRegex(AssignmentApplyError, "assignment_plan_stale"):
            self._prepare(journal_rows=journal_rows("5"))

    def test_source_progress_cannot_exceed_the_remaining_quantity(self):
        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_source_progress_protected",
        ):
            self._prepare(contract_items=[source_item(done_quantity=Decimal("8"))])

    def test_existing_exact_target_lineage_is_a_conflict_not_a_merge(self):
        existing_target = source_item(
            id=42,
            quantity=1,
            source_estimate_version_id=72,
            source_item_key="new-row",
            estimate_item_key="new-row",
        )

        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_target_exists",
        ):
            self._prepare(
                contracts=[contract(total_amount=Decimal("7700"))],
                contract_items=[source_item(), existing_target],
            )

    def test_target_estimate_price_matches_numeric_database_scale(self):
        snapshot = target_snapshot()
        sections = json.loads(snapshot["sections_json"])
        sections[0]["items"][0]["priceWork"] = "900.005"
        snapshot["sections_json"] = json.dumps(sections, ensure_ascii=False)
        snapshot["sections_sha256"] = sections_sha256(sections)
        stored = approved_stored_plan()
        stored["canonicalPlan"]["targetSnapshot"]["sectionsSha256"] = snapshot[
            "sections_sha256"
        ]
        stored["canonicalPlan"]["entries"][0]["target"][
            "sectionsSha256"
        ] = snapshot["sections_sha256"]
        stored["canonicalPlan"]["planSha256"] = ""
        from backend.features.estimate_row_transfer.plan import calculate_plan_sha256
        stored["canonicalPlan"]["planSha256"] = calculate_plan_sha256(
            stored["canonicalPlan"]
        )
        stored["approvedPlanSha256"] = stored["canonicalPlan"]["planSha256"]

        operations = self._prepare(
            stored=stored,
            assignment_entries=[entry_row(stored["canonicalPlan"])],
            target_snapshot=snapshot,
        )

        self.assertEqual(operations[0]["targetPriceSmeta"], Decimal("900.01"))

    def test_stored_contract_total_must_match_locked_items(self):
        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_contract_total_stale",
        ):
            self._prepare(contracts=[contract(total_amount=Decimal("6999"))])

    def test_contract_total_rounding_matches_positive_postgres_numeric_round(self):
        operations = self._prepare(
            contracts=[contract(total_amount=Decimal("7000.01"))],
            contract_items=[source_item(price_brigade=Decimal("700.0005"))],
        )

        self.assertEqual(operations[0]["contractTotalBefore"], Decimal("7000.01"))

    def test_draft_plan_never_reaches_business_preparation(self):
        stored = approved_stored_plan()
        stored["status"] = "draft"
        stored["approvedPlanSha256"] = None

        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_plan_not_approved",
        ):
            self._prepare(stored=stored)

    def test_tampered_canonical_plan_is_rejected_even_when_rows_match_it(self):
        stored = approved_stored_plan()
        stored["canonicalPlan"]["entries"][0]["quantity"] = "2"
        matching_tampered_entry = entry_row(stored["canonicalPlan"])

        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_plan_integrity_invalid",
        ):
            self._prepare(
                stored=stored,
                assignment_entries=[matching_tampered_entry],
            )


class AssignmentApplyTransactionTests(unittest.TestCase):
    actor = {
        "id": 2,
        "companyId": 1,
        "name": "Директор",
        "role": "директор",
    }

    def test_first_apply_writes_only_exact_assignment_split_and_receipt(self):
        cursor = ApplyCursor()

        result = apply_assignment_plan(
            cursor,
            stored=approved_stored_plan(),
            actor=self.actor,
        )

        self.assertFalse(result["idempotent"])
        self.assertEqual(result["assignmentCount"], 1)
        self.assertEqual(result["transfers"], [{
            "entryId": 8,
            "sourceItemId": 41,
            "targetItemId": 101,
            "quantity": "3",
        }])
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("UPDATE public.brigade_contract_items SET quantity=%s", sql)
        self.assertIn("INSERT INTO public.brigade_contract_items", sql)
        self.assertIn("UPDATE public.brigade_contracts", sql)
        self.assertIn("INSERT INTO public.estimate_row_assignment_transfers", sql)
        self.assertNotIn("UPDATE public.work_journal", sql)
        self.assertNotIn("brigade_acts SET", sql)
        self.assertNotIn("brigade_payments SET", sql)
        self.assertNotIn("supply_requests SET", sql)

    def test_repeated_exact_apply_returns_receipt_without_business_writes(self):
        cursor = ApplyCursor(existing_receipts=[transfer_receipt()])

        result = apply_assignment_plan(
            cursor,
            stored=approved_stored_plan(),
            actor=self.actor,
        )

        self.assertTrue(result["idempotent"])
        self.assertEqual(result["assignmentCount"], 1)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertNotIn("UPDATE public.brigade_contract_items", sql)
        self.assertNotIn("INSERT INTO public.brigade_contract_items", sql)
        self.assertNotIn("UPDATE public.brigade_contracts", sql)
        self.assertNotIn("INSERT INTO public.estimate_row_assignment_transfers", sql)

    def test_mismatched_existing_receipt_fails_closed_before_business_writes(self):
        cursor = ApplyCursor(existing_receipts=[transfer_receipt(entry_id=999)])

        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_apply_partial_state",
        ):
            apply_assignment_plan(
                cursor,
                stored=approved_stored_plan(),
                actor=self.actor,
            )

        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertNotIn("UPDATE public.brigade_contract_items", sql)

    def test_contract_total_drift_rolls_back_before_receipt(self):
        cursor = ApplyCursor(post_total="6999")

        with self.assertRaisesRegex(
            AssignmentApplyError,
            "assignment_contract_total_changed",
        ):
            apply_assignment_plan(
                cursor,
                stored=approved_stored_plan(),
                actor=self.actor,
            )

        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertNotIn("INSERT INTO public.estimate_row_assignment_transfers", sql)


if __name__ == "__main__":
    unittest.main()
