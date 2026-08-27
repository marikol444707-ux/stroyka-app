from decimal import Decimal
import re
import unittest

from backend.features.accounting_exception_checks.link_repair_plan import (
    LinkRepairPlanError,
    build_accounting_link_repair_plan,
)


def project(**overrides):
    return {
        "id": 17,
        "company_id": 4,
        "name": "ЖК Северный",
        **overrides,
    }


def supplier_invoice(**overrides):
    return {
        "id": 91,
        "company_id": 4,
        "supplier_id": 12,
        "supplier_name": "ООО Поставка",
        "project_name": "ЖК Северный",
        "amount": Decimal("1000.00"),
        "offer_id": 51,
        "request_id": 31,
        "warehouse_invoice_id": 999,
        "invoice_number": "Счёт № 14555",
        "invoice_date": "2026-08-10",
        "status": "На утверждении",
        **overrides,
    }


def warehouse_invoice(**overrides):
    return {
        "id": 44,
        "company_id": 4,
        "supplier_id": 12,
        "supplier_name": "ООО Поставка",
        "project": "ЖК Северный",
        "total_with_vat": Decimal("1000.00"),
        "total_base": Decimal("1000.00"),
        "supply_delivery_id": 71,
        "supply_request_id": 31,
        "supplier_invoice_id": None,
        "number": "14555",
        "date": "2026-08-10",
        "status": "Принята",
        **overrides,
    }


def delivery(**overrides):
    return {
        "id": 71,
        "company_id": 4,
        "offer_id": 51,
        "request_id": 31,
        "supplier_id": 12,
        "supplier_name": "ООО Поставка",
        "project": "ЖК Северный",
        "status": "Принято",
        **overrides,
    }


def build(**overrides):
    values = {
        "company_id": 4,
        "projects": [project()],
        "supplier_invoices": [supplier_invoice()],
        "warehouse_invoices": [warehouse_invoice()],
        "deliveries": [delivery()],
    }
    values.update(overrides)
    return build_accounting_link_repair_plan(**values)


class AccountingLinkRepairPlanTests(unittest.TestCase):
    def test_uses_unique_exact_document_identity_when_lineage_is_absent(self):
        plan = build(
            supplier_invoices=[supplier_invoice(
                offer_id=None,
                request_id=None,
                invoice_number="Счёт № 14555",
                invoice_date="2026-08-10",
            )],
            warehouse_invoices=[warehouse_invoice(
                supply_delivery_id=None,
                supply_request_id=None,
                number="14555",
                date="10.08.2026",
            )],
            deliveries=[],
        )

        self.assertEqual(plan.state, "ready")
        self.assertEqual(plan.unresolved_count, 0)
        self.assertEqual(len(plan.repairs), 1)
        self.assertEqual(plan.repairs[0].proof, "identity")

    def test_refuses_incomplete_mismatched_or_ambiguous_document_identity(self):
        unsafe_cases = (
            (
                [supplier_invoice(
                    offer_id=None, request_id=None, invoice_number="",
                )],
                [warehouse_invoice(
                    supply_delivery_id=None, supply_request_id=None,
                )],
            ),
            (
                [supplier_invoice(
                    offer_id=None, request_id=None, invoice_date="неизвестно",
                )],
                [warehouse_invoice(
                    supply_delivery_id=None, supply_request_id=None,
                    date="неизвестно",
                )],
            ),
            (
                [supplier_invoice(
                    offer_id=None, request_id=None, amount=Decimal("999.00"),
                )],
                [warehouse_invoice(
                    supply_delivery_id=None, supply_request_id=None,
                )],
            ),
            (
                [supplier_invoice(offer_id=None, request_id=None)],
                [
                    warehouse_invoice(
                        supply_delivery_id=None, supply_request_id=None,
                    ),
                    warehouse_invoice(
                        id=45, supply_delivery_id=None, supply_request_id=None,
                    ),
                ],
            ),
        )

        for suppliers, warehouses in unsafe_cases:
            with self.subTest(suppliers=suppliers, warehouses=warehouses):
                plan = build(
                    supplier_invoices=suppliers,
                    warehouse_invoices=warehouses,
                    deliveries=[],
                )
                self.assertEqual(plan.state, "clear")
                self.assertEqual(plan.repairs, ())
                self.assertEqual(plan.unresolved_count, 1)

    def test_prefers_a_missing_reciprocal_link_over_documentary_inference(self):
        plan = build(
            supplier_invoices=[supplier_invoice(warehouse_invoice_id=44)],
        )

        self.assertEqual(plan.state, "ready")
        self.assertEqual(plan.unresolved_count, 0)
        self.assertEqual(len(plan.repairs), 1)
        self.assertEqual(plan.repairs[0].proof, "reciprocal")
        self.assertEqual(plan.repairs[0].supplier_invoice_id, 91)
        self.assertEqual(plan.repairs[0].warehouse_invoice_id, 44)

    def test_repairs_the_other_missing_reciprocal_direction(self):
        plan = build(
            supplier_invoices=[supplier_invoice(
                warehouse_invoice_id=None,
                offer_id=None,
                request_id=None,
            )],
            warehouse_invoices=[warehouse_invoice(
                supplier_invoice_id=91,
                supply_delivery_id=None,
                supply_request_id=None,
            )],
            deliveries=[],
        )

        self.assertEqual(plan.state, "ready")
        self.assertEqual(len(plan.repairs), 1)
        self.assertEqual(plan.repairs[0].proof, "reciprocal")

    def test_uses_the_exact_delivery_chain_when_the_stored_link_is_dangling(self):
        plan = build()

        self.assertEqual(plan.state, "ready")
        self.assertEqual(plan.proof_counts, {
            "reciprocal": 0,
            "delivery": 1,
            "request": 0,
            "identity": 0,
        })
        self.assertEqual(plan.public_result(), {
            "version": "accounting-exception-link-repair-v2",
            "companyId": 4,
            "state": "ready",
            "repairCount": 1,
            "unresolvedCount": 0,
            "proofCounts": {
                "reciprocal": 0,
                "delivery": 1,
                "request": 0,
                "identity": 0,
            },
            "planSha256": plan.plan_sha256,
            "blockers": [],
        })
        self.assertRegex(plan.plan_sha256, re.compile(r"^[0-9a-f]{64}$"))

    def test_refuses_an_annulled_delivery_as_documentary_proof(self):
        plan = build(
            supplier_invoices=[supplier_invoice(
                request_id=None,
                invoice_number="",
                invoice_date="",
            )],
            warehouse_invoices=[warehouse_invoice(supply_request_id=None)],
            deliveries=[delivery(request_id=None, status="Аннулировано")],
        )

        self.assertEqual(plan.state, "clear")
        self.assertEqual(plan.repairs, ())
        self.assertEqual(plan.unresolved_count, 1)

    def test_uses_a_unique_request_chain_without_names_as_authority(self):
        plan = build(
            supplier_invoices=[supplier_invoice(
                supplier_id=12,
                supplier_name="Непохожее отображаемое имя",
                offer_id=None,
            )],
            warehouse_invoices=[warehouse_invoice(
                supplier_id=12,
                supplier_name="Другое отображаемое имя",
                supply_delivery_id=None,
            )],
            deliveries=[],
        )

        self.assertEqual(len(plan.repairs), 1)
        self.assertEqual(plan.repairs[0].proof, "request")

    def test_refuses_ambiguous_request_candidates_and_keeps_them_unresolved(self):
        plan = build(
            supplier_invoices=[supplier_invoice(offer_id=None)],
            warehouse_invoices=[
                warehouse_invoice(supply_delivery_id=None),
                warehouse_invoice(id=45, supply_delivery_id=None),
            ],
            deliveries=[],
        )

        self.assertEqual(plan.state, "clear")
        self.assertEqual(plan.repairs, ())
        self.assertEqual(plan.unresolved_count, 1)

    def test_refuses_cross_tenant_project_annulled_and_live_conflicting_rows(self):
        unsafe_warehouses = [
            warehouse_invoice(id=44, company_id=5),
            warehouse_invoice(id=45, project="Другой объект"),
            warehouse_invoice(id=46, status="Аннулирована"),
            warehouse_invoice(id=47, supplier_invoice_id=777),
        ]
        plan = build(
            supplier_invoices=[
                supplier_invoice(),
                supplier_invoice(
                    id=777,
                    warehouse_invoice_id=47,
                    request_id=99,
                    offer_id=None,
                ),
            ],
            warehouse_invoices=unsafe_warehouses,
            deliveries=[delivery(id=72)],
        )

        self.assertEqual(plan.repairs, ())
        self.assertEqual(plan.unresolved_count, 1)

    def test_accepts_a_normalized_supplier_name_only_when_both_ids_are_absent(self):
        plan = build(
            supplier_invoices=[supplier_invoice(
                supplier_id=None,
                supplier_name=' ООО  "Поставка" ',
            )],
            warehouse_invoices=[warehouse_invoice(
                supplier_id=None,
                supplier_name="ооо поставка",
            )],
            deliveries=[delivery(supplier_id=None, supplier_name="ООО Поставка")],
        )

        self.assertEqual(len(plan.repairs), 1)
        self.assertEqual(plan.repairs[0].proof, "delivery")

    def test_plan_order_and_sha_are_stable_for_permuted_inputs(self):
        suppliers = [
            supplier_invoice(),
            supplier_invoice(
                id=92,
                offer_id=52,
                request_id=32,
                warehouse_invoice_id=998,
            ),
        ]
        warehouses = [
            warehouse_invoice(),
            warehouse_invoice(
                id=45,
                supply_delivery_id=72,
                supply_request_id=32,
            ),
        ]
        deliveries = [
            delivery(),
            delivery(id=72, offer_id=52, request_id=32),
        ]

        first = build(
            supplier_invoices=suppliers,
            warehouse_invoices=warehouses,
            deliveries=deliveries,
        )
        second = build(
            projects=[project()],
            supplier_invoices=list(reversed(suppliers)),
            warehouse_invoices=list(reversed(warehouses)),
            deliveries=list(reversed(deliveries)),
        )

        self.assertEqual(first.repairs, second.repairs)
        self.assertEqual(first.plan_sha256, second.plan_sha256)

    def test_rejects_malformed_or_oversized_inputs_instead_of_guessing(self):
        with self.assertRaisesRegex(
            LinkRepairPlanError,
            "accounting_link_repair_plan_input_invalid",
        ):
            build(company_id=True)
        with self.assertRaisesRegex(
            LinkRepairPlanError,
            "accounting_link_repair_plan_limit_exceeded",
        ):
            build(supplier_invoices=[
                supplier_invoice(id=index + 1)
                for index in range(1001)
            ])


if __name__ == "__main__":
    unittest.main()
