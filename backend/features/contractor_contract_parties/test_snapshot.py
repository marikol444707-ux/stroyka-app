import unittest

from fastapi import HTTPException

from .snapshot import build_contract_snapshot, snapshot_digest


COMPANY = {
    "company_id": 3, "full_name": "ООО Альянс", "inn": "2611008712",
    "kpp": "261101001", "ogrn": "1234567890123", "legal_address": "Ставрополь",
    "director_name": "Петров П.П.", "director_position": "Директор", "basis": "Устава",
    "bank_name": "Банк", "bik": "044525104", "rs": "4" * 20, "ks": "3" * 20,
}
CONTRACTOR = {
    "user_id": 41, "full_name": "Иванов Иван Иванович", "passport": "07 01 123456, МВД",
    "inn": "263200000001", "contract_type": "ИП", "bank_account": "4" * 20,
    "bank_name": "Банк ИП", "phone": "+79990000000", "ogrnip": "3" * 15,
}
CONTRACT = {
    "id": 71, "company_id": 3, "project_id": 17, "project_name": "Лицей 4",
    "contractor_id": 41, "contractor_type": "ИП", "brigade_name": "Иванов И.И.",
    "signed_at": "2026-10-01", "contract_scan_url": "/tenant-files/77/content",
    "source_file_id": 77,
}


class ContractorContractSnapshotTests(unittest.TestCase):
    def test_builds_exact_frozen_parties(self):
        result = build_contract_snapshot(CONTRACT, COMPANY, CONTRACTOR, {"id": 9, "name": "Директор"})
        self.assertEqual(result["customer"]["companyId"], 3)
        self.assertEqual(result["contractor"]["userId"], 41)
        self.assertEqual(result["contractor"]["ogrnip"], "3" * 15)
        self.assertEqual(result["source"]["fileId"], 77)
        self.assertEqual(len(snapshot_digest(result)), 64)

    def test_rejects_other_contractor_profile(self):
        with self.assertRaises(HTTPException) as raised:
            build_contract_snapshot(CONTRACT, COMPANY, {**CONTRACTOR, "user_id": 42}, {"id": 9})
        self.assertEqual(raised.exception.status_code, 409)

    def test_requires_individual_identity_and_payment_requisites(self):
        with self.assertRaises(HTTPException) as raised:
            build_contract_snapshot(
                {**CONTRACT, "contractor_type": "ГПХ"},
                COMPANY,
                {**CONTRACTOR, "passport": "", "bank_account": ""},
                {"id": 9},
            )
        self.assertIn("паспорт", raised.exception.detail)

    def test_requires_complete_legal_entity_identity(self):
        legal = {
            **CONTRACTOR,
            "full_name": "ООО Исполнитель",
            "contract_type": "ООО",
            "kpp": "",
            "ogrn": "1234567890123",
            "legal_address": "Ставрополь",
            "signatory_name": "Сидоров С.С.",
            "signatory_position": "Директор",
            "signatory_basis": "Устава",
        }
        with self.assertRaises(HTTPException) as raised:
            build_contract_snapshot({**CONTRACT, "contractor_type": "Субподрядчик"}, COMPANY, legal, {"id": 9})
        self.assertIn("КПП", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
