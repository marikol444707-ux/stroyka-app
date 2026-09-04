import unittest
from datetime import date

from backend.features.platform_admin.client_contracts import (
    build_client_contract_preview,
    build_contract_number,
    build_contract_status_transition,
    can_transition_contract_status,
    find_overlapping_active_contracts,
    normalize_legal_party,
)


def _complete_licensor():
    return {
        "id": 7,
        "platform_account_id": 1,
        "legal_form": "individual_entrepreneur",
        "legal_name": "ИП Буцькин Николай Сергеевич",
        "inn": "261103507630",
        "ogrnip": "309264413800022",
        "legal_address": "Ставропольский край",
        "settlement_account": "40802810000000000001",
        "bank_name": "Тестовый банк",
        "bank_bik": "040000001",
        "correspondent_account": "30101810000000000001",
        "signatory_name": "Буцькин Николай Сергеевич",
        "signatory_basis": "действует на основании регистрации ИП",
    }


def _complete_company():
    return {
        "id": 42,
        "platform_account_id": 1,
        "name": "ООО Клиент",
        "short_name": "ООО Клиент",
        "inn": "2635000000",
        "kpp": "263501001",
        "ogrn": "1022600000000",
        "legal_address": "г. Ставрополь",
        "contact_name": "Иванов Иван Иванович",
        "contact_phone": "+7 900 000-00-00",
        "contact_email": "director@example.test",
        "settlement_account": "40702810000000000001",
        "bank_name": "Банк клиента",
        "bank_bik": "040000002",
        "correspondent_account": "30101810000000000002",
        "signatory_name": "Иванов Иван Иванович",
        "signatory_basis": "Устав",
        "plan": "pro",
        "monthly_fee": "15000.00",
        "max_projects": 10,
        "max_users": 50,
    }


def _payload(**overrides):
    payload = {
        "platformAccountId": 1,
        "companyId": 42,
        "licensorProfileId": 7,
        "idempotencyKey": "contract-create-42-2026",
        "contractType": "platform_license",
        "contractDate": "2026-09-01",
        "startsOn": "2026-09-01",
        "endsOn": "2027-08-31",
        "plan": "pro",
        "monthlyFee": "15000.00",
        "currency": "RUB",
        "maxProjects": 10,
        "maxUsers": 50,
        "status": "draft",
        "termsVersion": "2026-09-01",
    }
    payload.update(overrides)
    return payload


class ClientContractDomainTests(unittest.TestCase):
    def test_normalizes_legal_identifiers_and_contact_values(self):
        normalized = normalize_legal_party({
            "legalForm": " individual_entrepreneur ",
            "legalName": "  ИП   Буцькин Николай Сергеевич  ",
            "inn": "26 110 350 7630",
            "ogrnip": "30926-44138-00022",
            "phone": "8 (909) 763-85-05",
            "email": " OWNER@EXAMPLE.TEST ",
            "bankBik": "04 000 0001",
            "settlementAccount": "40802 810 0 00000000001",
        })

        self.assertEqual(normalized["legalForm"], "individual_entrepreneur")
        self.assertEqual(normalized["legalName"], "ИП Буцькин Николай Сергеевич")
        self.assertEqual(normalized["inn"], "261103507630")
        self.assertEqual(normalized["ogrnip"], "309264413800022")
        self.assertEqual(normalized["phone"], "+79097638505")
        self.assertEqual(normalized["email"], "owner@example.test")
        self.assertEqual(normalized["bankBik"], "040000001")
        self.assertEqual(
            normalized["settlementAccount"],
            "40802810000000000001",
        )

    def test_maps_legacy_ogrn_field_to_ogrnip_for_individual_entrepreneur(self):
        normalized = normalize_legal_party({
            "name": "Индивидуальный предприниматель Буцькин Николай Сергеевич",
            "inn": "261103507630",
            "ogrn": "309264413800022",
        })

        self.assertEqual(normalized["legalForm"], "individual_entrepreneur")
        self.assertEqual(normalized["ogrnip"], "309264413800022")
        self.assertEqual(normalized["ogrn"], "")

    def test_accepts_canonical_company_requisites_shape(self):
        normalized = normalize_legal_party({
            "fullName": "ООО Канонический клиент",
            "inn": "2635000000",
            "kpp": "263501001",
            "ogrn": "1022600000000",
            "legalAddress": "г. Ставрополь",
            "directorName": "Иванов Иван Иванович",
            "basis": "Устава",
            "bankName": "Банк клиента",
            "bik": "040000002",
            "rs": "40702810000000000001",
            "ks": "30101810000000000002",
        })

        self.assertEqual(normalized["legalName"], "ООО Канонический клиент")
        self.assertEqual(normalized["signatoryName"], "Иванов Иван Иванович")
        self.assertEqual(normalized["signatoryBasis"], "Устава")
        self.assertEqual(normalized["settlementAccount"], "40702810000000000001")
        self.assertEqual(normalized["correspondentAccount"], "30101810000000000002")

    def test_preview_returns_human_blockers_without_writes(self):
        preview = build_client_contract_preview(
            _payload(),
            company={"id": 42, "platform_account_id": 1, "name": "ООО Клиент"},
            licensor={
                "id": 7,
                "platform_account_id": 1,
                "legal_name": "ИП Буцькин Николай Сергеевич",
            },
        )

        codes = {blocker["code"] for blocker in preview["blockers"]}
        self.assertIn("licensor_inn_required", codes)
        self.assertIn("client_inn_required", codes)
        self.assertIn("licensor_bank_details_required", codes)
        self.assertIn("client_signatory_required", codes)
        self.assertEqual(preview["writesAttempted"], 0)
        self.assertTrue(preview["dryRun"])

    def test_complete_preview_freezes_parties_and_terms(self):
        company = _complete_company()
        licensor = _complete_licensor()
        preview = build_client_contract_preview(
            _payload(),
            company=company,
            licensor=licensor,
        )

        self.assertEqual(preview["blockers"], [])
        self.assertTrue(preview["readyForDraft"])
        self.assertTrue(preview["readyForActivation"])
        self.assertEqual(
            preview["contract"]["licensorSnapshot"]["legalName"],
            "ИП Буцькин Николай Сергеевич",
        )
        self.assertEqual(
            preview["contract"]["clientSnapshot"]["legalName"],
            "ООО Клиент",
        )
        self.assertEqual(preview["contract"]["termsSnapshot"]["monthlyFee"], "15000.00")
        company["name"] = "Подмена после preview"
        self.assertEqual(
            preview["contract"]["clientSnapshot"]["legalName"],
            "ООО Клиент",
        )

    def test_preview_rejects_cross_account_ownership_and_invalid_terms(self):
        preview = build_client_contract_preview(
            _payload(
                endsOn="2026-08-31",
                monthlyFee="NaN",
                currency="rub",
            ),
            company={**_complete_company(), "platform_account_id": 2},
            licensor=_complete_licensor(),
        )

        codes = {blocker["code"] for blocker in preview["blockers"]}
        self.assertIn("company_platform_account_mismatch", codes)
        self.assertIn("contract_period_invalid", codes)
        self.assertIn("monthly_fee_invalid", codes)
        self.assertIn("currency_invalid", codes)

    def test_same_idempotency_key_returns_existing_contract(self):
        preview = build_client_contract_preview(
            _payload(),
            company=_complete_company(),
            licensor=_complete_licensor(),
            existing_contracts=[{
                "id": 91,
                "platformAccountId": 1,
                "companyId": 42,
                "idempotencyKey": "contract-create-42-2026",
                "status": "draft",
            }],
        )

        self.assertEqual(preview["blockers"], [])
        self.assertEqual(preview["idempotentContractId"], 91)
        self.assertFalse(preview["shouldCreate"])

    def test_idempotency_key_cannot_be_reused_for_another_company(self):
        preview = build_client_contract_preview(
            _payload(),
            company=_complete_company(),
            licensor=_complete_licensor(),
            existing_contracts=[{
                "id": 92,
                "platformAccountId": 1,
                "companyId": 99,
                "idempotencyKey": "contract-create-42-2026",
                "status": "draft",
            }],
        )

        self.assertIn(
            "idempotency_key_conflict",
            {blocker["code"] for blocker in preview["blockers"]},
        )
        self.assertTrue(preview["shouldCreate"] is False)

    def test_finds_only_overlapping_active_contracts_of_same_company_and_type(self):
        conflicts = find_overlapping_active_contracts(
            existing_contracts=[
                {
                    "id": 1,
                    "companyId": 42,
                    "contractType": "platform_license",
                    "status": "active",
                    "startsOn": "2026-01-01",
                    "endsOn": "2026-12-31",
                },
                {
                    "id": 2,
                    "companyId": 42,
                    "contractType": "support",
                    "status": "active",
                    "startsOn": "2026-01-01",
                    "endsOn": None,
                },
                {
                    "id": 3,
                    "companyId": 99,
                    "contractType": "platform_license",
                    "status": "active",
                    "startsOn": "2026-01-01",
                    "endsOn": None,
                },
                {
                    "id": 4,
                    "companyId": 42,
                    "contractType": "platform_license",
                    "status": "terminated",
                    "startsOn": "2026-01-01",
                    "endsOn": None,
                },
            ],
            company_id=42,
            contract_type="platform_license",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 8, 31),
        )

        self.assertEqual([contract["id"] for contract in conflicts], [1])

    def test_contract_number_and_status_transitions_are_deterministic(self):
        self.assertEqual(build_contract_number(2026, 1), "STK-2026-0001")
        self.assertEqual(build_contract_number(2026, 12345), "STK-2026-12345")
        with self.assertRaises(ValueError):
            build_contract_number(2026, 0)

        self.assertTrue(can_transition_contract_status("draft", "issued"))
        self.assertTrue(can_transition_contract_status("issued", "active"))
        self.assertTrue(can_transition_contract_status("active", "terminated"))
        self.assertTrue(can_transition_contract_status("active", "expired"))
        self.assertTrue(can_transition_contract_status("active", "active"))
        self.assertFalse(can_transition_contract_status("draft", "active"))
        self.assertFalse(can_transition_contract_status("terminated", "active"))
        self.assertFalse(can_transition_contract_status("unknown", "draft"))

    def test_status_transition_requires_document_chain_before_activation(self):
        contract = {
            "id": 101,
            "company_id": 42,
            "contract_type": "platform_license",
            "status": "draft",
            "starts_on": "2026-09-01",
            "ends_on": "2027-08-31",
            "licensor_snapshot_json": normalize_legal_party(_complete_licensor()),
            "client_snapshot_json": normalize_legal_party(_complete_company()),
            "terms_snapshot_json": {
                "plan": "pro",
                "monthlyFee": "15000.00",
                "currency": "RUB",
                "maxProjects": 10,
                "maxUsers": 50,
                "startsOn": "2026-09-01",
                "endsOn": "2027-08-31",
            },
        }

        missing_pdf = build_contract_status_transition(contract, "issued")
        self.assertIn(
            "generated_contract_pdf_required",
            {item["code"] for item in missing_pdf["blockers"]},
        )

        issued = {**contract, "status": "issued", "generated_file_url": "/tenant-files/1/content"}
        missing_signature = build_contract_status_transition(issued, "active")
        self.assertIn(
            "signed_contract_pdf_required",
            {item["code"] for item in missing_signature["blockers"]},
        )

        active = build_contract_status_transition(
            {**issued, "signed_file_url": "/tenant-files/2/content"},
            "active",
        )
        self.assertEqual(active["blockers"], [])
        self.assertTrue(active["changed"])

    def test_status_transition_rejects_overlap_and_is_idempotent(self):
        contract = {
            "id": 101,
            "company_id": 42,
            "contract_type": "platform_license",
            "status": "issued",
            "starts_on": "2026-09-01",
            "ends_on": "2027-08-31",
            "generated_file_url": "/tenant-files/1/content",
            "signed_file_url": "/tenant-files/2/content",
            "licensor_snapshot_json": normalize_legal_party(_complete_licensor()),
            "client_snapshot_json": normalize_legal_party(_complete_company()),
            "terms_snapshot_json": {
                "plan": "pro",
                "monthlyFee": "15000.00",
                "currency": "RUB",
                "maxProjects": 10,
                "maxUsers": 50,
                "startsOn": "2026-09-01",
                "endsOn": "2027-08-31",
            },
        }
        overlap = build_contract_status_transition(contract, "active", [{
            "id": 202,
            "company_id": 42,
            "contract_type": "platform_license",
            "status": "active",
            "starts_on": "2027-01-01",
            "ends_on": None,
        }])
        self.assertIn(
            "active_contract_period_overlap",
            {item["code"] for item in overlap["blockers"]},
        )

        same = build_contract_status_transition(
            {**contract, "status": "active"},
            "active",
        )
        self.assertTrue(same["ok"])
        self.assertFalse(same["changed"])


if __name__ == "__main__":
    unittest.main()
