import json
import unittest

from backend.features.supply_kp_comparison.source_resolver import (
    SupplyTechnicalSourceResolverError,
    resolve_supply_technical_source_rows,
    run_supply_technical_source_resolver,
)


def _request(**updates):
    row = {
        "id": 31,
        "company_id": 1,
        "project_id": 7,
        "project": "Кисловодск Лицей 4",
        "material_name": "Труба PP-R PN20 20x3,4 мм",
        "quantity": "100",
        "unit": "м",
        "category": "Трубы PP-R",
        "work_package": "ВК",
        "items_json": json.dumps(
            [
                {
                    "materialName": "Труба PP-R PN20 20x3,4 мм",
                    "quantity": 100,
                    "unit": "м",
                    "workPackage": "ВК",
                }
            ],
            ensure_ascii=False,
        ),
    }
    row.update(updates)
    return row


def _offer(**updates):
    row = {
        "id": 81,
        "company_id": 1,
        "request_id": 31,
        "source_file_ref": "/tenant-files/44/content",
        "items_kp_json": json.dumps(
            [
                {
                    "materialName": "Труба Valfex PP-R PN20 20x3,4 мм",
                    "quantity": 100,
                    "unit": "м",
                    "workPackage": "ВК",
                    "pricePerUnit": 120,
                    "totalPrice": 12000,
                }
            ],
            ensure_ascii=False,
        ),
    }
    row.update(updates)
    return row


def _invoice(**updates):
    row = {
        "id": 91,
        "company_id": 1,
        "request_id": 31,
        "offer_id": 81,
        "offer_company_id": 1,
        "offer_request_id": 31,
        "project_name": "Кисловодск Лицей 4",
        "source_file_ref": "/tenant-files/44/content",
        "items_kp_json": _offer()["items_kp_json"],
    }
    row.update(updates)
    return row


def _file(**updates):
    row = {
        "id": 44,
        "company_id": 1,
        "project_id": 7,
        "file_url": "https://s3.example/private-object",
        "storage_key": (
            "uploads/company-1-project-7-supplier-offer/2026/09/02/offer.pdf"
        ),
        "context": "supplier-offer",
        "original_name": "offer.pdf",
        "content_type": "application/pdf",
        "deletion_status": "active",
    }
    row.update(updates)
    return row


def _rows(*, source=None, file=None):
    return {
        "request": _request(),
        "source": source or _offer(),
        "file": file or _file(),
    }


def _resolve(rows=None, **updates):
    values = {
        "company_id": 1,
        "project_id": 7,
        "request_id": 31,
        "source_kind": "supplier_offer",
        "source_id": 81,
        "file_id": 44,
    }
    values.update(updates)
    return resolve_supply_technical_source_rows(rows or _rows(), **values)


class SourceResolverRowsTest(unittest.TestCase):
    def test_offer_resolves_one_exact_scoped_comparison_without_exposing_storage_url(self):
        result = _resolve()

        self.assertIs(result["ok"], True)
        self.assertIs(result["dryRun"], True)
        self.assertEqual(result["sourceKind"], "supplier_offer")
        self.assertEqual(result["requestedLineCount"], 1)
        self.assertEqual(result["offeredLineCount"], 1)
        self.assertEqual(result["comparisonCount"], 1)
        self.assertIs(result["comparisons"][0]["result"]["automaticApprovalAllowed"], False)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(result["modelCalls"], 0)
        self.assertEqual(
            result["file"],
            {
                "id": 44,
                "contentUrl": "/tenant-files/44/content",
                "context": "supplier-offer",
                "originalName": "offer.pdf",
                "contentType": "application/pdf",
            },
        )
        self.assertNotIn("storage_key", json.dumps(result))
        self.assertNotIn("s3.example", json.dumps(result))

    def test_invoice_must_be_linked_to_an_offer_in_the_same_request_scope(self):
        result = _resolve(
            rows=_rows(source=_invoice()),
            source_kind="supplier_invoice",
            source_id=91,
        )
        self.assertEqual(result["sourceKind"], "supplier_invoice")
        self.assertEqual(result["comparisonCount"], 1)

        with self.assertRaises(SupplyTechnicalSourceResolverError):
            _resolve(
                rows=_rows(source=_invoice(offer_request_id=32)),
                source_kind="supplier_invoice",
                source_id=91,
            )

    def test_invalid_or_cross_scope_identifiers_fail_closed(self):
        cases = [
            ({"company_id": True}, None),
            ({"project_id": 8}, None),
            ({"request_id": 32}, None),
            ({"source_id": 82}, None),
            ({"file_id": 45}, None),
            ({}, _rows(file=_file(company_id=2))),
            ({}, _rows(file=_file(project_id=8))),
            ({}, _rows(file=_file(deletion_status="pending"))),
        ]
        for updates, rows in cases:
            with self.subTest(updates=updates, rows=rows):
                with self.assertRaises(SupplyTechnicalSourceResolverError) as caught:
                    _resolve(rows=rows, **updates)
                self.assertEqual(
                    caught.exception.code,
                    "supply_technical_source_resolver_invalid",
                )

    def test_source_reference_must_name_the_selected_protected_file(self):
        with self.assertRaises(SupplyTechnicalSourceResolverError):
            _resolve(rows=_rows(source=_offer(source_file_ref="/tenant-files/99/content")))

    def test_storage_key_must_belong_to_the_selected_company_and_project(self):
        foreign_key = (
            "uploads/company-2-project-7-supplier-offer/2026/09/02/offer.pdf"
        )
        with self.assertRaises(SupplyTechnicalSourceResolverError) as caught:
            _resolve(rows=_rows(file=_file(storage_key=foreign_key)))
        self.assertEqual(
            caught.exception.code,
            "supply_technical_source_resolver_invalid",
        )

    def test_line_count_mismatch_is_not_guessed_or_partially_compared(self):
        two_lines = json.dumps(
            [
                {
                    "materialName": "Труба Valfex PP-R PN20 20x3,4 мм",
                    "quantity": 50,
                    "unit": "м",
                },
                {
                    "materialName": "Муфта PP-R 20 мм",
                    "quantity": 2,
                    "unit": "шт",
                },
            ],
            ensure_ascii=False,
        )
        with self.assertRaises(SupplyTechnicalSourceResolverError):
            _resolve(rows=_rows(source=_offer(items_kp_json=two_lines)))

    def test_equivalent_decimal_quantity_formats_do_not_create_a_false_mismatch(self):
        request_items = json.dumps(
            [{"materialName": "Труба", "quantity": 100.0, "unit": "м", "workPackage": "ВК"}],
            ensure_ascii=False,
        )
        offer_items = json.dumps(
            [{"materialName": "Труба", "quantity": "100.000", "unit": "м", "workPackage": "ВК"}],
            ensure_ascii=False,
        )
        rows = _rows(source=_offer(items_kp_json=offer_items))
        rows["request"] = _request(items_json=request_items)
        result = _resolve(rows=rows)
        self.assertEqual(result["comparisons"][0]["required"]["quantity"], "100")
        self.assertEqual(result["comparisons"][0]["offered"]["quantity"], "100")

    def test_same_evidence_produces_the_same_result_hash(self):
        first = _resolve()
        second = _resolve()
        self.assertEqual(first["resultSha256"], second["resultSha256"])

    def test_unbounded_json_is_rejected_before_comparison(self):
        with self.assertRaises(SupplyTechnicalSourceResolverError):
            _resolve(rows=_rows(source=_offer(items_kp_json="[" + " " * 600_000 + "]")))

    def test_extreme_decimal_exponent_is_rejected_before_string_expansion(self):
        hostile_items = json.dumps(
            [
                {
                    "materialName": "Труба",
                    "quantity": "1e999999999",
                    "unit": "м",
                    "workPackage": "ВК",
                }
            ],
            ensure_ascii=False,
        )
        with self.assertRaises(SupplyTechnicalSourceResolverError):
            _resolve(rows=_rows(source=_offer(items_kp_json=hostile_items)))


class ScriptedCursor:
    def __init__(self, rows):
        self.rows = rows
        self.current = None
        self.executed = []
        self.closed = False

    def execute(self, sql, params):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if "FROM supply_requests" in normalized:
            self.current = self.rows["request"]
        elif "FROM supplier_invoices" in normalized:
            self.current = self.rows["source"]
        elif "FROM supplier_offers" in normalized:
            self.current = self.rows["source"]
        elif "FROM file_ownership" in normalized:
            self.current = self.rows["file"]
        else:
            raise AssertionError("unexpected SQL: " + normalized)

    def fetchone(self):
        return self.current

    def close(self):
        self.closed = True


class ReadOnlyConnection:
    def __init__(self, rows):
        self.cursor_value = ScriptedCursor(rows)
        self.session_values = None
        self.rollback_count = 0
        self.commit_count = 0

    def set_session(self, **values):
        self.session_values = values

    def cursor(self, **_values):
        return self.cursor_value

    def rollback(self):
        self.rollback_count += 1

    def commit(self):
        self.commit_count += 1


class SourceResolverRuntimeTest(unittest.TestCase):
    def test_database_runner_is_repeatable_read_readonly_and_always_rolls_back(self):
        connection = ReadOnlyConnection(_rows())
        result = run_supply_technical_source_resolver(
            connection,
            company_id=1,
            project_id=7,
            request_id=31,
            source_kind="supplier_offer",
            source_id=81,
            file_id=44,
        )

        self.assertIs(result["rolledBack"], True)
        self.assertEqual(
            connection.session_values,
            {
                "readonly": True,
                "autocommit": False,
                "isolation_level": "REPEATABLE READ",
            },
        )
        self.assertEqual(connection.rollback_count, 1)
        self.assertEqual(connection.commit_count, 0)
        self.assertIs(connection.cursor_value.closed, True)
        sql = " ".join(query for query, _params in connection.cursor_value.executed).upper()
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", " FOR UPDATE", "LOCK "):
            self.assertNotIn(forbidden, sql)

    def test_database_runner_loads_an_invoice_through_its_exact_offer_scope(self):
        connection = ReadOnlyConnection(_rows(source=_invoice()))
        result = run_supply_technical_source_resolver(
            connection,
            company_id=1,
            project_id=7,
            request_id=31,
            source_kind="supplier_invoice",
            source_id=91,
            file_id=44,
        )

        self.assertEqual(result["sourceKind"], "supplier_invoice")
        self.assertEqual(result["comparisonCount"], 1)
        self.assertEqual(connection.rollback_count, 1)
        source_query, source_params = connection.cursor_value.executed[1]
        self.assertIn("FROM supplier_invoices", source_query)
        self.assertIn("JOIN supplier_offers", source_query)
        self.assertEqual(source_params, (91, 31, 1))

    def test_database_runner_rolls_back_when_resolution_fails(self):
        connection = ReadOnlyConnection(_rows(file=_file(company_id=2)))
        with self.assertRaises(SupplyTechnicalSourceResolverError):
            run_supply_technical_source_resolver(
                connection,
                company_id=1,
                project_id=7,
                request_id=31,
                source_kind="supplier_offer",
                source_id=81,
                file_id=44,
            )
        self.assertEqual(connection.rollback_count, 1)
        self.assertEqual(connection.commit_count, 0)
        self.assertIs(connection.cursor_value.closed, True)

    def test_invalid_selector_is_rejected_before_any_query_and_still_rolls_back(self):
        connection = ReadOnlyConnection(_rows())
        with self.assertRaises(SupplyTechnicalSourceResolverError):
            run_supply_technical_source_resolver(
                connection,
                company_id=True,
                project_id=7,
                request_id=31,
                source_kind="supplier_offer",
                source_id=81,
                file_id=44,
            )
        self.assertEqual(connection.cursor_value.executed, [])
        self.assertEqual(connection.rollback_count, 1)
        self.assertEqual(connection.commit_count, 0)


if __name__ == "__main__":
    unittest.main()
