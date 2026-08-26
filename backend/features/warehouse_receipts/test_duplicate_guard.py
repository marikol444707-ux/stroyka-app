import unittest

from .duplicate_guard import (
    build_invoice_number_lookup_keys,
    build_supplier_invoice_lock_keys,
    build_warehouse_invoice_lock_keys,
    match_supplier_invoice_duplicate,
    match_warehouse_invoice_duplicate,
    normalize_invoice_number,
)


class WarehouseInvoiceDuplicateGuardTests(unittest.TestCase):
    def test_normalizes_common_invoice_number_formatting(self):
        self.assertEqual(normalize_invoice_number("№ 323/3091032"), "3233091032")
        self.assertEqual(normalize_invoice_number("323-3091032"), "3233091032")
        self.assertEqual(normalize_invoice_number("накладная № 323 3091032"), "3233091032")

    def test_generated_scan_number_is_not_treated_as_document_number(self):
        self.assertEqual(normalize_invoice_number("SCAN-20260826-1430"), "")

    def test_oversized_document_number_is_not_used_for_lookup_or_locking(self):
        oversized = "№" + ("1" * 513)

        self.assertEqual(normalize_invoice_number(oversized), "")
        self.assertEqual(build_invoice_number_lookup_keys(oversized), tuple())

    def test_builds_bounded_database_lookup_variants(self):
        keys = build_invoice_number_lookup_keys("накладная № 14555")

        self.assertIn("14555", keys)
        self.assertIn("NO14555", keys)
        self.assertIn("НАКЛАДНАЯ14555", keys)
        self.assertEqual(build_invoice_number_lookup_keys("SCAN-20260826-1430"), tuple())

    def test_same_document_matches_even_when_project_changes(self):
        match = match_warehouse_invoice_duplicate(
            incoming_number="№ 14555",
            incoming_date="2026-08-10",
            incoming_total=94380,
            incoming_items_signature="штукатурка|шт|270.0000|336.00|90720.00",
            candidate_number="14555",
            candidate_date="2026-08-10",
            candidate_total=94380,
            candidate_items_signature="штукатурка|шт|270.0000|336.00|90720.00",
            same_supplier=True,
        )

        self.assertEqual(match, "number_date")

    def test_same_number_and_date_matches_when_ocr_supplier_name_changes(self):
        match = match_warehouse_invoice_duplicate(
            incoming_number="94/2026",
            incoming_date="10.08.2026",
            incoming_total=11800,
            incoming_items_signature="кабель|м|100.0000|118.00|11800.00",
            candidate_number="94-2026",
            candidate_date="2026-08-10",
            candidate_total=11800,
            candidate_items_signature="кабель|м|100.0000|118.00|11800.00",
            same_supplier=False,
        )

        self.assertEqual(match, "number_date")

    def test_scan_draft_requires_same_supplier_date_total_and_items(self):
        common = {
            "incoming_number": "SCAN-20260826-1430",
            "incoming_date": "2026-08-10",
            "incoming_total": 11800,
            "incoming_items_signature": "кабель|м|100.0000|118.00|11800.00",
            "candidate_number": "SCAN-20260826-1515",
            "candidate_date": "2026-08-10",
            "candidate_total": 11800,
            "candidate_items_signature": "кабель|м|100.0000|118.00|11800.00",
        }

        self.assertEqual(
            match_warehouse_invoice_duplicate(**common, same_supplier=True),
            "content",
        )
        self.assertIsNone(
            match_warehouse_invoice_duplicate(**common, same_supplier=False),
        )

    def test_different_real_numbers_are_not_duplicates(self):
        match = match_warehouse_invoice_duplicate(
            incoming_number="101",
            incoming_date="2026-08-10",
            incoming_total=11800,
            incoming_items_signature="кабель|м|100.0000|118.00|11800.00",
            candidate_number="102",
            candidate_date="2026-08-10",
            candidate_total=11800,
            candidate_items_signature="кабель|м|100.0000|118.00|11800.00",
            same_supplier=True,
        )

        self.assertIsNone(match)

    def test_same_number_and_date_does_not_merge_different_supplier_content(self):
        match = match_warehouse_invoice_duplicate(
            incoming_number="101",
            incoming_date="2026-08-10",
            incoming_total=11800,
            incoming_items_signature="кабель|м|100.0000|118.00|11800.00",
            candidate_number="№ 101",
            candidate_date="2026-08-10",
            candidate_total=11800,
            candidate_items_signature="штукатурка|шт|20.0000|590.00|11800.00",
            same_supplier=False,
        )

        self.assertIsNone(match)

    def test_lock_keys_are_stable_for_formatting_and_scan_drafts(self):
        first = build_warehouse_invoice_lock_keys(
            company_id=1,
            invoice_number="№ 14555",
            invoice_date="10.08.2026",
            total_with_vat=11800,
            items_signature="кабель|м|100.0000|118.00|11800.00",
        )
        second = build_warehouse_invoice_lock_keys(
            company_id=1,
            invoice_number="14555",
            invoice_date="2026-08-10",
            total_with_vat="11800.00",
            items_signature="кабель|м|100.0000|118.00|11800.00",
        )
        draft = build_warehouse_invoice_lock_keys(
            company_id=1,
            invoice_number="SCAN-20260826-1430",
            invoice_date="2026-08-10",
            total_with_vat=11800,
            items_signature="кабель|м|100.0000|118.00|11800.00",
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(draft), 1)

    def test_supplier_invoice_matches_the_same_supplier_document_across_number_formatting(self):
        match = match_supplier_invoice_duplicate(
            incoming_number="счёт № 14555",
            incoming_date="10.08.2026",
            candidate_number="14555",
            candidate_date="2026-08-10",
            same_supplier=True,
            same_offer=False,
            same_request=False,
        )

        self.assertEqual(match, "number_date_supplier")

    def test_supplier_invoice_does_not_match_by_amount_or_number_without_supplier_proof(self):
        match = match_supplier_invoice_duplicate(
            incoming_number="14555",
            incoming_date="2026-08-10",
            candidate_number="№ 14555",
            candidate_date="2026-08-10",
            same_supplier=False,
            same_offer=False,
            same_request=False,
        )

        self.assertIsNone(match)

    def test_supplier_invoice_accepts_an_exact_offer_even_if_display_name_changed(self):
        match = match_supplier_invoice_duplicate(
            incoming_number="14555",
            incoming_date="2026-08-10",
            candidate_number="счёт № 14555",
            candidate_date="10.08.2026",
            same_supplier=False,
            same_offer=True,
            same_request=True,
        )

        self.assertEqual(match, "number_date_offer")

    def test_supplier_invoice_request_requires_supplier_proof(self):
        without_supplier = match_supplier_invoice_duplicate(
            incoming_number="14555",
            incoming_date="2026-08-10",
            candidate_number="14555",
            candidate_date="2026-08-10",
            same_supplier=False,
            same_offer=False,
            same_request=True,
        )
        with_supplier = match_supplier_invoice_duplicate(
            incoming_number="14555",
            incoming_date="2026-08-10",
            candidate_number="14555",
            candidate_date="2026-08-10",
            same_supplier=True,
            same_offer=False,
            same_request=True,
        )

        self.assertIsNone(without_supplier)
        self.assertEqual(with_supplier, "number_date_supplier")

    def test_supplier_invoice_lock_keys_are_canonical_and_company_scoped(self):
        first = build_supplier_invoice_lock_keys(
            company_id=1,
            invoice_number="счёт № 14555",
            invoice_date="10.08.2026",
            supplier_identity="ids:150",
            offer_id=21,
            request_id=9,
            warehouse_invoice_id=163,
        )
        second = build_supplier_invoice_lock_keys(
            company_id=1,
            invoice_number="14555",
            invoice_date="2026-08-10",
            supplier_identity="ids:150",
            offer_id=21,
            request_id=9,
            warehouse_invoice_id=163,
        )
        foreign_company = build_supplier_invoice_lock_keys(
            company_id=2,
            invoice_number="14555",
            invoice_date="2026-08-10",
            supplier_identity="ids:150",
            offer_id=21,
            request_id=9,
            warehouse_invoice_id=163,
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, foreign_company)
        self.assertEqual(len(first), 4)


if __name__ == "__main__":
    unittest.main()
