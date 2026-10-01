import json
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.features.supplier_access.rfq_requester_snapshot import (
    RfqRequesterSnapshotError,
    build_rfq_requester_snapshot,
    freeze_rfq_requester_snapshot,
    requester_snapshot_identity,
    validate_rfq_requester_snapshot,
)


class RfqRequesterSnapshotTests(unittest.TestCase):
    def test_supply_request_model_can_be_defined_from_declared_imports(self):
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))
        selected = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in {"pydantic", "typing"}:
                selected.append(node)
            if isinstance(node, ast.ClassDef) and node.name == "SupplyRequestModel":
                selected.append(node)
        namespace = {}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(main_path), "exec"), namespace)
        self.assertTrue(issubclass(namespace["SupplyRequestModel"], namespace["BaseModel"]))

    def test_builds_bounded_server_owned_requester_and_delivery_snapshot(self):
        snapshot = build_rfq_requester_snapshot(
            request_id=81,
            company_id=17,
            project_id=31,
            project_name="  Лицей №4  ",
            delivery_address="  г. Кисловодск, ул. Школьная, 4  ",
            company={
                "full_name": "ООО АльянсПромСтрой",
                "short_name": "Альянс",
                "email": " office@example.test ",
                "phone": "+7 900 000-00-00",
            },
            actor={
                "id": 71,
                "name": "Иван Петров",
                "email": " buyer@example.test ",
                "phone": "+7 911 000-00-00",
            },
            frozen_at="2026-10-01T12:00:00Z",
        )

        self.assertEqual(snapshot, {
            "version": 1,
            "requestId": 81,
            "companyId": 17,
            "companyName": "Альянс",
            "companyEmail": "office@example.test",
            "companyPhone": "+7 900 000-00-00",
            "contactUserId": 71,
            "contactName": "Иван Петров",
            "contactEmail": "buyer@example.test",
            "contactPhone": "+7 911 000-00-00",
            "projectId": 31,
            "projectName": "Лицей №4",
            "deliveryAddress": "г. Кисловодск, ул. Школьная, 4",
            "frozenAt": "2026-10-01T12:00:00Z",
        })

    def test_validates_exact_request_company_and_project_without_current_profile(self):
        raw = json.dumps(build_rfq_requester_snapshot(
            request_id=81,
            company_id=17,
            project_id=31,
            project_name="Лицей №4",
            delivery_address="Адрес",
            company={"full_name": "Старое подтверждённое название"},
            actor={"id": 71, "name": "Контакт"},
            frozen_at="2026-10-01T12:00:00Z",
        ), ensure_ascii=False)

        snapshot = validate_rfq_requester_snapshot(
            raw, request_id=81, company_id=17, project_name="Лицей №4",
        )

        self.assertEqual(snapshot["companyName"], "Старое подтверждённое название")
        self.assertEqual(
            requester_snapshot_identity(snapshot),
            {
                "companyName": "Старое подтверждённое название", "companyEmail": "",
                "companyPhone": "", "contactName": "Контакт", "contactEmail": "",
                "contactPhone": "", "project": "Лицей №4", "deliveryAddress": "Адрес",
            },
        )

    def test_rejects_foreign_or_drifted_snapshot(self):
        snapshot = build_rfq_requester_snapshot(
            request_id=81, company_id=17, project_id=31,
            project_name="Лицей №4", delivery_address="Адрес",
            company={"full_name": "Компания"}, actor={"id": 71},
            frozen_at="2026-10-01T12:00:00Z",
        )
        for request_id, company_id, project_name in (
            (82, 17, "Лицей №4"),
            (81, 18, "Лицей №4"),
            (81, 17, "Другой объект"),
        ):
            with self.subTest(request_id=request_id, company_id=company_id, project=project_name):
                with self.assertRaises(RfqRequesterSnapshotError):
                    validate_rfq_requester_snapshot(
                        snapshot,
                        request_id=request_id,
                        company_id=company_id,
                        project_name=project_name,
                    )

    def test_does_not_accept_client_claimed_identity_fields(self):
        with self.assertRaises(TypeError):
            build_rfq_requester_snapshot(
                request_id=81, company_id=17, project_id=31,
                project_name="Лицей №4", delivery_address="Адрес",
                company={"full_name": "Компания"}, actor={"id": 71},
                frozen_at="2026-10-01T12:00:00Z",
                companyName="Подмена",
            )

    def test_existing_snapshot_is_reused_without_reading_mutable_profiles(self):
        snapshot = build_rfq_requester_snapshot(
            request_id=81, company_id=17, project_id=31,
            project_name="Лицей №4", delivery_address="Старый адрес",
            company={"full_name": "Старое название"}, actor={"id": 71},
            frozen_at="2026-10-01T12:00:00Z",
        )
        cursor = Mock()

        result = freeze_rfq_requester_snapshot(
            cursor,
            {
                "id": 81, "company_id": 17, "project": "Лицей №4",
                "delivery_address": "Новый адрес, который нельзя применить",
                "requester_snapshot_json": snapshot,
            },
            {"id": 71, "name": "Новый контакт"},
        )

        self.assertEqual(result["companyName"], "Старое название")
        self.assertEqual(result["deliveryAddress"], "Старый адрес")
        cursor.execute.assert_not_called()

    def test_first_dispatch_resolves_exact_project_and_freezes_current_profiles(self):
        cursor = Mock()
        cursor.rowcount = 1
        cursor.fetchall.return_value = [{"id": 31}]
        cursor.fetchone.return_value = {
            "name": "Карточка компании",
            "full_name": "ООО АльянсПромСтрой",
            "short_name": "Альянс",
            "email": "office@example.test",
            "phone": "+7 900 000-00-00",
            "contact_email": "fallback@example.test",
            "contact_phone": "",
        }

        result = freeze_rfq_requester_snapshot(
            cursor,
            {
                "id": 81, "company_id": 17, "project": "Лицей №4",
                "delivery_address": "Адрес доставки", "requester_snapshot_json": None,
            },
            {"id": 71, "name": "Иван", "email": "ivan@example.test", "phone": "+7 911"},
            frozen_at="2026-10-01T12:00:00Z",
        )

        self.assertEqual(result["projectId"], 31)
        self.assertEqual(result["companyName"], "Альянс")
        self.assertEqual(result["contactName"], "Иван")
        update = [call for call in cursor.execute.call_args_list if "UPDATE supply_requests" in call.args[0]]
        self.assertEqual(len(update), 1)
        stored = json.loads(update[0].args[1][0])
        self.assertEqual(stored, result)
        self.assertEqual(update[0].args[1][1:], (81, 17))

    def test_ambiguous_project_does_not_freeze_a_snapshot(self):
        cursor = Mock()
        cursor.fetchall.return_value = [{"id": 31}, {"id": 32}]

        with self.assertRaises(RfqRequesterSnapshotError):
            freeze_rfq_requester_snapshot(
                cursor,
                {
                    "id": 81, "company_id": 17, "project": "Лицей №4",
                    "delivery_address": "Адрес", "requester_snapshot_json": None,
                },
                {"id": 71},
                frozen_at="2026-10-01T12:00:00Z",
            )

        self.assertFalse(any("UPDATE supply_requests" in call.args[0] for call in cursor.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
