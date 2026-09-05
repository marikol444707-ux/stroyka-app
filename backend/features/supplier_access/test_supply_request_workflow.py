import ast
import json
import unittest
from pathlib import Path

from backend.features.supplier_access.supply_request_workflow import (
    SUPPLIER_REQUEST_VISIBILITY_SQL,
    SupplyRequestWorkflowViolation,
    sanitize_supplier_request_response,
    supplier_request_visibility_params,
    validate_rfq_dispatch_role,
    validate_supply_request_transition,
)


class SupplyRequestTransitionPolicyTests(unittest.TestCase):
    def test_prorab_confirms_only_new_request(self):
        for role in ("прораб", "главный_инженер"):
            validate_supply_request_transition(
                action="confirm_prorab",
                role=role,
                current_status="Новая",
            )

        for role in (
            "мастер",
            "снабженец",
            "директор",
            "поставщик",
        ):
            with self.subTest(role=role):
                with self.assertRaises(
                    SupplyRequestWorkflowViolation
                ) as raised:
                    validate_supply_request_transition(
                        action="confirm_prorab",
                        role=role,
                        current_status="Новая",
                    )
                self.assertEqual(
                    raised.exception.status_code,
                    403,
                )

        for status in (
            "Подтверждена прорабом",
            "Утверждена",
            "КП запрошены",
            "Отклонена",
            "Отменена",
        ):
            with self.subTest(status=status):
                with self.assertRaises(
                    SupplyRequestWorkflowViolation
                ) as raised:
                    validate_supply_request_transition(
                        action="confirm_prorab",
                        role="прораб",
                        current_status=status,
                    )
                self.assertEqual(
                    raised.exception.status_code,
                    409,
                )

    def test_director_approves_only_after_prorab(self):
        for role in ("директор", "зам_директора"):
            validate_supply_request_transition(
                action="approve_director",
                role=role,
                current_status="Подтверждена прорабом",
            )

        for role in ("прораб", "снабженец", "бухгалтер"):
            with self.subTest(role=role):
                with self.assertRaises(
                    SupplyRequestWorkflowViolation
                ) as raised:
                    validate_supply_request_transition(
                        action="approve_director",
                        role=role,
                        current_status="Подтверждена прорабом",
                    )
                self.assertEqual(
                    raised.exception.status_code,
                    403,
                )

        for status in (
            None,
            "Новая",
            "Утверждена",
            "КП запрошены",
            "Отклонена",
        ):
            with self.subTest(status=status):
                with self.assertRaises(
                    SupplyRequestWorkflowViolation
                ) as raised:
                    validate_supply_request_transition(
                        action="approve_director",
                        role="директор",
                        current_status=status,
                    )
                self.assertEqual(
                    raised.exception.status_code,
                    409,
                )

    def test_only_leadership_or_supply_can_dispatch_rfq(self):
        for role in (
            "директор",
            "зам_директора",
            "снабженец",
        ):
            validate_rfq_dispatch_role(role)

        for role in (
            "прораб",
            "кладовщик",
            "бухгалтер",
            "мастер",
            "поставщик",
        ):
            with self.subTest(role=role):
                with self.assertRaises(
                    SupplyRequestWorkflowViolation
                ) as raised:
                    validate_rfq_dispatch_role(role)
                self.assertEqual(
                    raised.exception.status_code,
                    403,
                )


class SupplierRequestDisclosureTests(unittest.TestCase):
    def test_supplier_receives_only_safe_request_fields(self):
        row = {
            "id": 81,
            "materialName": "Труба PP-R PN20",
            "quantity": 100,
            "unit": "м",
            "project": "Объект №7",
            "companyId": 17,
            "workPackage": "Водоснабжение",
            "date": "2026-09-03",
            "status": "КП запрошены",
            "urgency": "Обычная",
            "category": "Сантехника",
            "createdAt": "2026-09-03T10:00:00",
            "notes": "Внутренний комментарий",
            "createdBy": "Мастер Иванов",
            "selectedSuppliers": [4, 9],
            "requestedByRole": "мастер",
            "requestedById": 501,
            "prorabId": 601,
            "prorabName": "Прораб Петров",
            "prorabConfirmedAt": "2026-09-03T11:00:00",
            "directorId": 701,
            "directorName": "Директор Сидоров",
            "directorApprovedAt": "2026-09-03T12:00:00",
            "rejectReason": "Не показывать",
            "itemsJson": json.dumps(
                [{
                    "materialName": "Труба PP-R PN20",
                    "quantity": 100,
                    "unit": "м",
                    "workPackage": "Водоснабжение",
                    "characteristics": {
                        "diameter": "20 мм",
                        "pressureClass": "PN20",
                        "companyId": 17,
                    },
                    "estimateControl": {
                        "plannedSum": 120000,
                    },
                    "estimateLineage": {
                        "estimateId": 44,
                    },
                    "plannedSum": 120000,
                    "price": 1200,
                }],
                ensure_ascii=False,
            ),
        }

        result = sanitize_supplier_request_response(row)

        self.assertEqual(set(result), {
            "id",
            "materialName",
            "quantity",
            "unit",
            "project",
            "companyId",
            "workPackage",
            "date",
            "status",
            "urgency",
            "category",
            "itemsJson",
            "createdAt",
        })

        item = json.loads(result["itemsJson"])[0]
        self.assertEqual(
            item["characteristics"]["diameter"],
            "20 мм",
        )
        self.assertEqual(
            item["characteristics"]["pressureClass"],
            "PN20",
        )
        self.assertNotIn(
            "companyId",
            item["characteristics"],
        )
        self.assertNotIn("estimateControl", item)
        self.assertNotIn("estimateLineage", item)
        self.assertNotIn("plannedSum", item)
        self.assertNotIn("price", item)

    def test_malformed_items_fail_closed(self):
        result = sanitize_supplier_request_response({
            "id": 1,
            "itemsJson": "{broken",
        })
        self.assertEqual(result["itemsJson"], "[]")

    def test_visibility_is_recipient_first_and_company_scoped(self):
        sql = " ".join(
            SUPPLIER_REQUEST_VISIBILITY_SQL.split()
        )

        self.assertIn(
            "recipient.visible_to_supplier=TRUE",
            sql,
        )
        self.assertIn(
            "recipient.company_id="
            "supply_requests.company_id",
            sql,
        )
        self.assertIn(
            "supply_requests.prorab_confirmed_at "
            "IS NOT NULL",
            sql,
        )
        self.assertIn(
            "supply_requests.director_approved_at "
            "IS NOT NULL",
            sql,
        )
        self.assertIn(
            "NOT EXISTS",
            sql,
        )
        self.assertIn(
            "supply_requests.selected_suppliers",
            sql,
        )

        self.assertEqual(
            supplier_request_visibility_params(
                [9, 4, 9]
            ),
            [[4, 9], [4, 9], [4, 9], [4, 9]],
        )


class SupplyRequestRuntimeWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_path = (
            Path(__file__).resolve().parents[2]
            / "main.py"
        )
        cls.source = cls.main_path.read_text(
            encoding="utf-8"
        )
        cls.tree = ast.parse(
            cls.source,
            filename=str(cls.main_path),
        )

    @classmethod
    def function_source(cls, *, name=None, contains=None):
        matches = []

        for node in ast.walk(cls.tree):
            if not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue

            segment = ast.get_source_segment(
                cls.source,
                node,
            ) or ""

            if name is not None and node.name != name:
                continue
            if (
                contains is not None
                and contains not in segment
            ):
                continue

            matches.append((
                node.end_lineno - node.lineno,
                segment,
            ))

        if not matches:
            raise AssertionError(
                f"Runtime function not found: "
                f"name={name!r}, contains={contains!r}"
            )

        return min(matches, key=lambda item: item[0])[1]

    def test_transition_policy_is_wired_into_update_route(self):
        function = self.function_source(
            contains="confirm_prorab",
        )
        self.assertIn(
            "validate_supply_request_transition(",
            function,
        )
        self.assertIn(
            "COALESCE(status,'Новая')='Новая'",
            function,
        )
        self.assertIn(
            "status='Подтверждена прорабом'",
            function,
        )

    def test_dispatch_policy_is_wired_into_request_kp(self):
        function = self.function_source(
            name="request_kp_from_suppliers",
        )
        self.assertIn(
            "validate_rfq_dispatch_role(",
            function,
        )
        self.assertIn(
            '("Утверждена", "КП запрошены")',
            function,
        )

    def test_supplier_visibility_policy_is_wired_into_list(self):
        function = self.function_source(
            name="get_supply_requests",
        )
        self.assertIn(
            "SUPPLIER_REQUEST_VISIBILITY_SQL",
            function,
        )
        self.assertIn(
            "supplier_request_visibility_params(",
            function,
        )

    def test_supplier_sanitizer_is_wired_into_response(self):
        function = self.function_source(
            name="_supply_response_for_role",
        )
        self.assertIn(
            'role == "поставщик"',
            function,
        )
        self.assertIn(
            "sanitize_supplier_request_response(data)",
            function,
        )


if __name__ == "__main__":
    unittest.main()
