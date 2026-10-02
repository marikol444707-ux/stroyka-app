from decimal import Decimal
import unittest

from .service import parse_create, side_view


class IntercompanyWarehouseTransferServiceTests(unittest.TestCase):
    def test_create_requires_a_different_destination_and_positive_finite_quantity(self):
        with self.assertRaisesRegex(ValueError, "другую компанию"):
            parse_create({"destinationCompanyId": 2, "sourceStockId": 7, "quantity": "1", "reason": "Передача"}, 2)
        for value in ("0", "-1", "NaN", "Infinity", "bad"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "количество"):
                parse_create({"destinationCompanyId": 3, "sourceStockId": 7, "quantity": value, "reason": "Передача"}, 2)

    def test_create_normalizes_only_authoritative_identifiers_and_reason(self):
        parsed = parse_create({
            "destinationCompanyId": "3", "sourceStockId": "7", "quantity": "1.2500",
            "reason": "  Для второго объекта  ", "requestId": "7a990fae-9d83-4c5d-b22e-8f31d370e5f7",
        }, 2)
        self.assertEqual(parsed, {
            "destinationCompanyId": 3, "sourceStockId": 7, "quantity": Decimal("1.2500"),
            "reason": "Для второго объекта", "requestId": "7a990fae-9d83-4c5d-b22e-8f31d370e5f7",
        })

    def test_each_company_sees_its_own_document_and_minimum_counterparty_data(self):
        row = {
            "id": 12, "sourceCompanyId": 2, "destinationCompanyId": 3,
            "sourceCompanyName": "Источник", "destinationCompanyName": "Получатель",
            "sourceDocument": {"kind": "dispatch", "private": "source-only"},
            "destinationDocument": {"kind": "receipt", "private": "destination-only"},
            "unitPrice": "99.00", "category": "private category",
        }
        source = side_view(row, 2)
        destination = side_view(row, 3)
        self.assertEqual((source["side"], source["document"]["kind"]), ("source", "dispatch"))
        self.assertEqual(source["counterparty"], {"companyId": 3, "name": "Получатель"})
        self.assertEqual((destination["side"], destination["document"]["kind"]), ("destination", "receipt"))
        self.assertEqual(destination["counterparty"], {"companyId": 2, "name": "Источник"})
        self.assertNotIn("sourceDocument", destination)
        self.assertNotIn("destinationDocument", source)
        self.assertNotIn("unitPrice", destination)
        self.assertNotIn("category", destination)
        self.assertNotIn("sourceStockId", destination)
