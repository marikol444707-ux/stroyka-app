import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
)
from backend.features.supply_recommendation_preview import rfq_content
from backend.features.supply_recommendation_preview import supplier_eligibility
from backend.features.supply_recommendation_preview.test_rfq_content import (
    baseline_report,
    current_supply_report,
    full_collector_result_sets,
    request_row,
    valid_report,
    valid_result_sets,
)


def supplier_schema_rows():
    return tuple(
        {"table_name": table, "column_name": column}
        for table, columns in supplier_eligibility.REQUIRED_COLUMNS.items()
        for column in columns
    )


def linked_supplier_row(**overrides):
    row = {
        "company_id": 4,
        "company_account_id": 7,
        "company_active": True,
        "account_id": 7,
        "account_active": True,
        "account_status": "active",
        "link_id": 61,
        "link_company_id": 4,
        "supplier_id": 71,
        "link_account_id": 7,
        "link_status": "Активный",
        "supplier_parent_id": 71,
        "supplier_status": "Активный",
        "supplier_user_link_id": 81,
        "supplier_user_id": 81,
        "supplier_user_role": "поставщик",
        "supplier_user_active": True,
    }
    row.update(overrides)
    return row


def direct_user_row(**overrides):
    row = {"supplier_id": 71, "supplier_user_id": 81}
    row.update(overrides)
    return row


def supporting_index_row():
    return {"index_ready": True}


def run_case(
    *, report=None, selection=None, rfq_result_sets=None, supplier_sets=None,
):
    report = report or valid_report()
    supplier_sets = supplier_sets or (
        supplier_schema_rows(),
        (supporting_index_row(),),
        (linked_supplier_row(),),
        (supporting_index_row(),),
        (direct_user_row(),),
    )
    cursor = FakeCursor(
        (rfq_result_sets or valid_result_sets()) + tuple(supplier_sets)
    )
    connection = FakeConnection(cursor)
    current = current_supply_report(report)
    current.update(copy.deepcopy(baseline_report(report)))
    with mock.patch.object(
        rfq_content,
        "collect_supply_warehouse_impact_audit",
        return_value=current,
    ):
        result = supplier_eligibility.run_supply_supplier_eligibility_preview(
            lambda: connection,
            report,
            selection or {"requestId": 21, "requestItemIndex": 0},
        )
    return result, connection, cursor


class RollbackFails(FakeConnection):
    def rollback(self):
        self.rollbacks += 1
        raise RuntimeError("private rollback detail")


class CloseFailsCursor(FakeCursor):
    def close(self):
        self.closed = True
        raise RuntimeError("private close detail")


class SupplySupplierEligibilityPreviewTests(unittest.TestCase):
    def test_builds_deterministic_id_only_company_link_review_candidate(self):
        first, connection, cursor = run_case()
        second, _, _ = run_case()

        self.assertEqual(first, second)
        self.assertEqual(first["eligibilityVersion"], 1)
        self.assertEqual(first["state"], "review_ready")
        self.assertTrue(first["readyForHumanSupplierReview"])
        self.assertFalse(first["materialEligibilityProven"])
        self.assertFalse(first["rankingApplied"])
        self.assertFalse(first["selectionAllowed"])
        self.assertFalse(first["sendAllowed"])
        self.assertEqual(first["supplierIds"], [])
        self.assertEqual(first["candidateKind"], "company_link_account_ready")
        self.assertEqual(first["candidateSupplierLinks"], [{
            "companySupplierLinkId": 61,
            "supplierId": 71,
            "evidence": [
                "company_link_exact",
                "supplier_card_active",
                "supplier_portal_user_direct_active",
            ],
        }])
        self.assertEqual(first["candidateCount"], 1)
        self.assertEqual(first["blockers"], [])
        self.assertEqual(first["source"]["companyId"], 4)
        self.assertEqual(first["source"]["requestId"], 21)
        self.assertEqual(first["source"]["requestItemIndex"], 0)
        self.assertRegex(first["source"]["requestItemSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(first["source"]["rfqContentSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(first["eligibilitySha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(first["readOnlyTransaction"])
        self.assertTrue(first["rolledBack"])
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

        serialized = json.dumps(first, ensure_ascii=False)
        for forbidden in (
            "Private material", "PRIVATE MATERIAL", "Private project",
            "кг", "5.000000", "email", "phone", "rating", "price",
        ):
            self.assertNotIn(forbidden, serialized)

        self.assertEqual(
            first["eligibilitySha256"],
            supplier_eligibility.calculate_eligibility_sha256(first),
        )
        self.assertEqual(len(cursor.calls), 12)

    def test_sorts_complete_candidates_without_ranking_or_selection(self):
        second_link = linked_supplier_row(
            link_id=62,
            supplier_id=72,
            supplier_parent_id=72,
            supplier_user_link_id=82,
            supplier_user_id=82,
        )
        result, _, _ = run_case(supplier_sets=(
            supplier_schema_rows(),
            (supporting_index_row(),),
            (second_link, linked_supplier_row()),
            (supporting_index_row(),),
            (
                direct_user_row(supplier_id=72, supplier_user_id=82),
                direct_user_row(),
            ),
        ))

        self.assertEqual(
            [row["supplierId"] for row in result["candidateSupplierLinks"]],
            [71, 72],
        )
        self.assertEqual(result["candidateCount"], 2)
        self.assertFalse(result["rankingApplied"])
        self.assertEqual(result["supplierIds"], [])

    def test_empty_or_inactive_company_links_return_no_candidates(self):
        empty_link = linked_supplier_row(
            link_id=None,
            link_company_id=None,
            supplier_id=None,
            link_account_id=None,
            link_status=None,
            supplier_parent_id=None,
            supplier_status=None,
            supplier_user_link_id=None,
            supplier_user_id=None,
            supplier_user_role=None,
            supplier_user_active=None,
        )
        for rows in (
            (empty_link,),
            (linked_supplier_row(link_status="Архивный"),),
        ):
            with self.subTest(rows=rows):
                result, _, cursor = run_case(supplier_sets=(
                    supplier_schema_rows(),
                    (supporting_index_row(),),
                    rows,
                ))

                self.assertEqual(result["state"], "no_candidates")
                self.assertFalse(result["readyForHumanSupplierReview"])
                self.assertEqual(result["candidateSupplierLinks"], [])
                self.assertEqual(result["supplierIds"], [])
                self.assertEqual(result["blockers"], [
                    "supply_supplier_no_active_company_links",
                ])
                self.assertEqual(len(cursor.calls), 10)

    def test_ambiguous_or_broken_active_links_fail_without_partial_candidates(self):
        cases = {
            "account_mismatch": (
                (linked_supplier_row(link_account_id=8),),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "zero_account_is_not_null": (
                (linked_supplier_row(link_account_id=0),),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "negative_account_is_not_null": (
                (linked_supplier_row(link_account_id=-1),),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "missing_supplier_parent": (
                (linked_supplier_row(supplier_parent_id=None),),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "inactive_supplier": (
                (linked_supplier_row(supplier_status="Архивный"),),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "wrong_user_role": (
                (linked_supplier_row(supplier_user_role="снабженец"),),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "duplicate_supplier_link": (
                (
                    linked_supplier_row(),
                    linked_supplier_row(link_id=62),
                ),
                (),
                "supply_supplier_link_ambiguous",
            ),
            "shared_direct_user": (
                (linked_supplier_row(),),
                (
                    direct_user_row(),
                    direct_user_row(supplier_id=72),
                ),
                "supply_supplier_user_link_ambiguous",
            ),
        }
        for name, (links, users, blocker) in cases.items():
            with self.subTest(name=name):
                supplier_sets = [
                    supplier_schema_rows(),
                    (supporting_index_row(),),
                    links,
                ]
                if users:
                    supplier_sets.append((supporting_index_row(),))
                    supplier_sets.append(users)
                result, _, _ = run_case(supplier_sets=tuple(supplier_sets))

                self.assertEqual(result["state"], "needs_review")
                self.assertFalse(result["readyForHumanSupplierReview"])
                self.assertEqual(result["candidateCount"], 0)
                self.assertEqual(result["candidateSupplierLinks"], [])
                self.assertEqual(result["blockers"], [blocker])

    def test_missing_schema_index_or_bounded_scan_overflow_is_incomplete(self):
        link_overflow = tuple(
            linked_supplier_row(
                link_id=1000 + index,
                supplier_id=2000 + index,
                supplier_parent_id=2000 + index,
                supplier_user_link_id=3000 + index,
                supplier_user_id=3000 + index,
            )
            for index in range(supplier_eligibility.MAX_COMPANY_LINKS + 1)
        )
        user_overflow = tuple(
            direct_user_row(supplier_id=4000 + index)
            for index in range(
                supplier_eligibility.MAX_DIRECT_USER_LINKS + 1
            )
        )
        cases = {
            "schema": (
                ((),),
                "supply_supplier_schema_not_ready",
            ),
            "schema_overflow": (
                (
                    supplier_schema_rows() + ({
                        "table_name": "companies",
                        "column_name": "id",
                    },),
                ),
                "supply_supplier_schema_not_ready",
            ),
            "company_index_missing": (
                (
                    supplier_schema_rows(),
                    (),
                ),
                "supply_supplier_company_link_index_not_ready",
            ),
            "link_overflow": (
                (
                    supplier_schema_rows(),
                    (supporting_index_row(),),
                    link_overflow,
                ),
                "supply_supplier_link_scan_incomplete",
            ),
            "user_index_missing": (
                (
                    supplier_schema_rows(),
                    (supporting_index_row(),),
                    (linked_supplier_row(),),
                    (),
                ),
                "supply_supplier_user_index_not_ready",
            ),
            "user_overflow": (
                (
                    supplier_schema_rows(),
                    (supporting_index_row(),),
                    (linked_supplier_row(),),
                    (supporting_index_row(),),
                    user_overflow,
                ),
                "supply_supplier_user_scan_incomplete",
            ),
        }
        for name, (supplier_sets, blocker) in cases.items():
            with self.subTest(name=name):
                result, _, _ = run_case(supplier_sets=supplier_sets)

                self.assertEqual(result["state"], "incomplete")
                self.assertEqual(result["candidateSupplierLinks"], [])
                self.assertEqual(result["blockers"], [blocker])

    def test_missing_or_inactive_company_parents_need_review(self):
        cases = {
            "missing_company": (),
            "inactive_company": (
                linked_supplier_row(company_active=False),
            ),
            "missing_platform_account": (
                linked_supplier_row(
                    company_account_id=None,
                    account_id=None,
                    link_account_id=None,
                ),
            ),
            "inactive_platform_account": (
                linked_supplier_row(account_active=False),
            ),
            "platform_account_status": (
                linked_supplier_row(account_status="suspended"),
            ),
        }
        for name, rows in cases.items():
            with self.subTest(name=name):
                result, _, _ = run_case(supplier_sets=(
                    supplier_schema_rows(),
                    (supporting_index_row(),),
                    rows,
                ))

                self.assertEqual(result["state"], "needs_review")
                self.assertEqual(result["candidateSupplierLinks"], [])
                self.assertEqual(result["blockers"], [
                    "supply_supplier_company_scope_invalid",
                ])

    def test_invalid_source_or_selection_is_rejected_before_database_access(self):
        report = valid_report()
        report["source"]["companyId"] = 404
        get_db = mock.Mock()

        with self.assertRaises(
            supplier_eligibility.SupplySupplierEligibilityError
        ) as error:
            supplier_eligibility.run_supply_supplier_eligibility_preview(
                get_db,
                report,
                {"requestId": 21, "requestItemIndex": 0},
            )

        self.assertEqual(error.exception.code, "supply_supplier_input_invalid")
        get_db.assert_not_called()

        get_db.reset_mock()
        with mock.patch.object(
            supplier_eligibility,
            "prepare_supply_rfq_content",
            side_effect=RuntimeError("private input detail"),
        ):
            with self.assertRaises(
                supplier_eligibility.SupplySupplierEligibilityError
            ) as error:
                supplier_eligibility.run_supply_supplier_eligibility_preview(
                    get_db,
                    valid_report(),
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_supplier_input_invalid")
        self.assertNotIn("private input detail", str(error.exception))
        get_db.assert_not_called()

    def test_non_ready_current_rfq_content_stops_before_supplier_scan(self):
        result, _, cursor = run_case(rfq_result_sets=valid_result_sets(
            requests=(request_row(request_status="Новая"),),
        ))

        self.assertEqual(result["state"], "no_action")
        self.assertEqual(result["candidateSupplierLinks"], [])
        self.assertEqual(result["blockers"], [
            "supply_rfq_request_status_ineligible",
        ])
        sql = " ".join(call[0] for call in cursor.calls).lower()
        self.assertNotIn("company_supplier_links", sql)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("Private material", serialized)
        self.assertNotIn("PRIVATE MATERIAL", serialized)

    def test_rejects_unknown_dependency_blocker_without_exposing_it(self):
        prepared = supplier_eligibility.prepare_supply_rfq_content(
            valid_report(), {"requestId": 21, "requestItemIndex": 0},
        )
        dependency_result = {
            "contentVersion": rfq_content.RFQ_CONTENT_VERSION,
            "ok": True,
            "dryRun": True,
            "writesAttempted": 0,
            "state": "no_action",
            "source": copy.deepcopy(prepared["source"]),
            "candidate": copy.deepcopy(prepared["candidate"]),
            "readyForRfqDraft": False,
            "blockers": ["private_email_alice"],
            "request": None,
            "balance": None,
            "rfqDraft": None,
            "requestItemSha256": "a" * 64,
            "contentSha256": "b" * 64,
            "readOnlyTransaction": False,
            "rolledBack": False,
        }
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)
        with mock.patch.object(
            supplier_eligibility,
            "collect_prepared_supply_rfq_content",
            return_value=dependency_result,
        ):
            result = (
                supplier_eligibility.run_supply_supplier_eligibility_preview(
                    lambda: connection,
                    valid_report(),
                    {"requestId": 21, "requestItemIndex": 0},
                )
            )

        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["blockers"], [
            "supply_supplier_rfq_content_invalid",
        ])
        self.assertNotIn("private_email_alice", json.dumps(result))
        self.assertIsNone(result["source"]["requestItemSha256"])
        self.assertIsNone(result["source"]["rfqContentSha256"])

    def test_runner_normalizes_read_rollback_and_cleanup_failures(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)
        with mock.patch.object(
            supplier_eligibility,
            "_collect",
            side_effect=RuntimeError("private read detail"),
        ):
            with self.assertRaises(
                supplier_eligibility.SupplySupplierEligibilityError
            ) as error:
                supplier_eligibility.run_supply_supplier_eligibility_preview(
                    lambda: connection,
                    valid_report(),
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_supplier_read_failed")
        self.assertNotIn("private read detail", str(error.exception))
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

        rollback_cursor = FakeCursor(())
        rollback_connection = RollbackFails(rollback_cursor)
        with mock.patch.object(
            supplier_eligibility,
            "_collect",
            side_effect=RuntimeError("private read detail"),
        ):
            with self.assertRaises(
                supplier_eligibility.SupplySupplierEligibilityError
            ) as error:
                supplier_eligibility.run_supply_supplier_eligibility_preview(
                    lambda: rollback_connection,
                    valid_report(),
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(
            error.exception.code, "supply_supplier_rollback_failed"
        )
        self.assertNotIn("private rollback detail", str(error.exception))
        self.assertTrue(rollback_cursor.closed)
        self.assertTrue(rollback_connection.closed)

        close_cursor = CloseFailsCursor(())
        close_connection = FakeConnection(close_cursor)
        with mock.patch.object(
            supplier_eligibility,
            "_collect",
            return_value={
                "readOnlyTransaction": False,
                "rolledBack": False,
            },
        ):
            with self.assertRaises(
                supplier_eligibility.SupplySupplierEligibilityError
            ) as error:
                supplier_eligibility.run_supply_supplier_eligibility_preview(
                    lambda: close_connection,
                    valid_report(),
                    {"requestId": 21, "requestItemIndex": 0},
                )
        self.assertEqual(error.exception.code, "supply_supplier_cleanup_failed")
        self.assertNotIn("private close detail", str(error.exception))
        self.assertEqual(close_connection.rollbacks, 1)
        self.assertTrue(close_connection.closed)

    def test_static_boundary_is_select_only_bounded_and_inert(self):
        result, _, cursor = run_case()
        self.assertEqual(result["state"], "review_ready")
        for sql, _params in cursor.calls:
            self.assertTrue(sql.upper().startswith("SELECT "))
            for forbidden in (
                " INSERT ", " UPDATE ", " DELETE ", " ALTER ",
                " CREATE ", " FOR UPDATE", " LOCK ", " NOTIFY ",
            ):
                self.assertNotIn(forbidden, " " + sql.upper())
        schema_calls = [
            call for call in cursor.calls
            if "jsonb_to_recordset" in call[0]
            and "pg_catalog.pg_attribute" in call[0]
        ]
        self.assertEqual(len(schema_calls), 2)
        for sql, params in schema_calls:
            self.assertIn("jsonb_to_recordset", sql)
            self.assertNotIn("information_schema", sql)
            self.assertIn("LIMIT %s", sql)
            self.assertIsInstance(params[-1], int)
        index_calls = [
            call for call in cursor.calls if "pg_catalog.pg_index" in call[0]
        ]
        self.assertEqual(len(index_calls), 2)
        for sql, _params in index_calls:
            self.assertIn("LIMIT %s", sql)
            self.assertIn("indcheckxmin IS FALSE", sql)
        supplier_sql = " ".join(call[0] for call in cursor.calls[-5:])
        for relation in (
            "public.companies", "public.platform_accounts",
            "public.company_supplier_links", "public.suppliers",
            "public.users",
        ):
            self.assertIn(relation, supplier_sql)
        self.assertIn("ORDER BY link.supplier_id", supplier_sql)
        self.assertIn("ORDER BY user_id", supplier_sql)
        self.assertNotIn("ORDER BY user_id,id", supplier_sql)

        real_cursor = FakeCursor((
            *full_collector_result_sets(),
            *valid_result_sets(),
            supplier_schema_rows(),
            (supporting_index_row(),),
            (linked_supplier_row(),),
            (supporting_index_row(),),
            (direct_user_row(),),
        ))
        real_connection = FakeConnection(real_cursor)
        real_result = (
            supplier_eligibility.run_supply_supplier_eligibility_preview(
                lambda: real_connection,
                valid_report(),
                {"requestId": 21, "requestItemIndex": 0},
            )
        )
        self.assertEqual(real_result["state"], "review_ready")
        self.assertEqual(len(real_cursor.calls), 26)
        real_schema_calls = [
            call for call in real_cursor.calls
            if "jsonb_to_recordset" in call[0]
            and "pg_catalog.pg_attribute" in call[0]
        ]
        self.assertEqual(len(real_schema_calls), 4)
        for sql, params in real_schema_calls:
            self.assertIn("jsonb_to_recordset", sql)
            self.assertNotIn("information_schema", sql)
            self.assertIn("LIMIT %s", sql)
            self.assertIsInstance(params[-1], int)

        root = Path(__file__).resolve().parents[3]
        source_text = (
            root
            / "backend/features/supply_recommendation_preview/supplier_eligibility.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "backend.main", "supplier_catalog", "supply_history",
            "supplier_offers", "supply_request_recipients",
            "suggest_suppliers", "_send_email", "log_audit",
            "from backend.db import", "commit(", "FOR UPDATE",
            "INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE ",
            "email", "phone", "rating", "price", "material_name",
        ):
            self.assertNotIn(forbidden, source_text)
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "package.json",
        ):
            self.assertNotIn(
                "supply_recommendation_preview.supplier_eligibility",
                (root / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
