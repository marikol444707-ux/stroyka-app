import hashlib
import json
import unittest

from fastapi import HTTPException


def digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class InvoiceRequisitesTests(unittest.TestCase):
    def snapshot(self):
        party = {
            "fullName": "ООО Покупатель", "inn": "7702222222", "kpp": "770201001",
            "ogrn": "", "legalAddress": "Москва", "bankName": "Банк покупателя",
            "bik": "044525001", "rs": "40702810000000000001",
            "ks": "30101810000000000001", "directorName": "", "directorPosition": "",
            "basis": "", "phone": "", "email": "",
        }
        return {
            "number": "Д-1", "date": "2026-09-22",
            "buyer": {**party, "companyId": 2},
            "payer": {**party, "companyId": 2},
            "supplier": {
                **party, "supplierId": 7, "fullName": "ООО Поставщик",
                "inn": "2632090186", "bankName": "Банк поставщика",
                "bik": "044525411", "rs": "40702810415590000143",
                "ks": "30101810145250000411",
            },
            "paymentTerms": "Отсрочка 30 дней", "signatureStatus": "not_verified",
            "appliedToAccounting": False, "missingRequisites": [],
        }

    def project(self, snapshot=None, **changes):
        from .invoice_requisites import invoice_requisites_projection
        snapshot = snapshot or self.snapshot()
        args = dict(snapshot=snapshot, snapshot_hash=digest(snapshot), contract_version_id=31,
                    company_id=2, supplier_id=7)
        args.update(changes)
        return invoice_requisites_projection(**args)

    def test_returns_exact_payer_and_supplier_payment_details(self):
        result = self.project()
        self.assertEqual(result["contractVersionId"], 31)
        self.assertEqual(result["contractNumber"], "Д-1")
        self.assertEqual(result["payer"], {
            "companyId": 2, "fullName": "ООО Покупатель", "inn": "7702222222",
            "kpp": "770201001",
        })
        self.assertEqual(result["supplier"], {
            "supplierId": 7, "fullName": "ООО Поставщик", "inn": "2632090186",
            "kpp": "770201001", "bankName": "Банк поставщика", "bik": "044525411",
            "rs": "40702810415590000143", "ks": "30101810145250000411",
        })
        self.assertEqual(result["paymentTerms"], "Отсрочка 30 дней")

    def test_rejects_hash_or_identity_mismatch(self):
        for changes in ({"snapshot_hash": "0" * 64}, {"company_id": 3}, {"supplier_id": 8}):
            with self.subTest(changes=changes), self.assertRaises(HTTPException) as error:
                self.project(**changes)
            self.assertEqual(error.exception.status_code, 409)

    def test_rejects_malformed_contract_fields_instead_of_coercing_them(self):
        for field in ("number", "date", "paymentTerms"):
            snapshot = self.snapshot()
            snapshot[field] = 123
            with self.subTest(field=field), self.assertRaises(HTTPException) as error:
                self.project(snapshot=snapshot)
            self.assertEqual(error.exception.status_code, 409)

    def test_does_not_duplicate_buyer_when_buyer_equals_payer(self):
        self.assertNotIn("buyer", self.project())

    def test_preserves_a_legacy_distinct_payer_without_changing_invoice_owner(self):
        snapshot = self.snapshot()
        snapshot["payer"] = {**snapshot["payer"], "companyId": 3, "fullName": "ООО Плательщик"}
        result = self.project(snapshot=snapshot)
        self.assertEqual(result["buyer"]["companyId"], 2)
        self.assertEqual(result["payer"]["companyId"], 3)


if __name__ == "__main__":
    unittest.main()
