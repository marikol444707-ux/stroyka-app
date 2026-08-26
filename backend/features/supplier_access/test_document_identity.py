import unittest

from backend.features.supplier_access.document_identity import (
    build_document_supplier_payload,
    has_legal_supplier_identity,
)


class DocumentSupplierIdentityTests(unittest.TestCase):
    def test_builds_supplier_payload_from_recognized_requisites(self):
        payload = build_document_supplier_payload(
            {
                "supplierRequisites": {
                    "name": 'ООО "Старт-Строй"',
                    "inn": "26 3200-1234",
                    "kpp": "263201001",
                    "ogrn": "1022600001234",
                    "bankAccount": "40702810900000000001",
                }
            },
            fallback_name="Название из накладной",
        )

        self.assertEqual(payload["supplierName"], 'ООО "Старт-Строй"')
        self.assertEqual(payload["supplierInn"], "2632001234")
        self.assertEqual(payload["supplierKpp"], "263201001")
        self.assertEqual(payload["supplierOgrn"], "1022600001234")
        self.assertEqual(payload["bankAccount"], "40702810900000000001")
        self.assertTrue(has_legal_supplier_identity(payload))

    def test_rejects_name_only_identity_for_automatic_creation(self):
        payload = build_document_supplier_payload({}, fallback_name='ООО "Старт-Строй"')

        self.assertEqual(payload["supplierName"], 'ООО "Старт-Строй"')
        self.assertFalse(has_legal_supplier_identity(payload))


if __name__ == "__main__":
    unittest.main()
