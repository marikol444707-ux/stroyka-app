import unittest

from fastapi import HTTPException

from backend.features.platform_admin.client_contract_documents import (
    MAX_SIGNED_CONTRACT_BYTES,
    render_client_contract_pdf,
    validate_signed_contract_upload,
)


def contract_snapshot():
    return {
        "number": "STK-2026-0101",
        "contract_date": "2026-09-02",
        "licensor_snapshot_json": {
            "legalForm": "individual_entrepreneur",
            "legalName": "ИП Буцькин Николай Сергеевич",
            "inn": "261103507630",
            "ogrnip": "309264413800022",
            "legalAddress": "Ставропольский край",
            "settlementAccount": "40802810000000000001",
            "bankName": "Тестовый банк",
            "bankBik": "040000001",
            "correspondentAccount": "30101810000000000001",
            "signatoryName": "Буцькин Николай Сергеевич",
            "signatoryBasis": "записи в ЕГРИП",
        },
        "client_snapshot_json": {
            "legalForm": "legal_entity",
            "legalName": "ООО Клиент",
            "inn": "2635000000",
            "kpp": "263501001",
            "ogrn": "1022600000000",
            "legalAddress": "г. Ставрополь",
            "settlementAccount": "40702810000000000001",
            "bankName": "Банк клиента",
            "bankBik": "040000002",
            "correspondentAccount": "30101810000000000002",
            "signatoryName": "Иванов Иван Иванович",
            "signatoryBasis": "Устав",
        },
        "terms_snapshot_json": {
            "contractType": "platform_license",
            "plan": "pro",
            "monthlyFee": "49900.00",
            "currency": "RUB",
            "maxProjects": 10,
            "maxUsers": 40,
            "startsOn": "2026-09-02",
            "endsOn": None,
            "termsVersion": "platform-license-v1",
        },
    }


class ClientContractDocumentTests(unittest.TestCase):
    def test_pdf_uses_frozen_parties_and_terms_and_disclaims_automatic_payment(self):
        rendered = render_client_contract_pdf(contract_snapshot())

        self.assertTrue(rendered.content.startswith(b"%PDF-"))
        self.assertGreater(len(rendered.content), 1000)
        self.assertEqual(rendered.filename, "STK-2026-0101.pdf")
        self.assertIn("ИП Буцькин Николай Сергеевич", rendered.plain_text)
        self.assertIn("ООО Клиент", rendered.plain_text)
        self.assertIn("49 900,00 RUB", rendered.plain_text)
        self.assertIn("10 объектов", rendered.plain_text)
        self.assertIn("40 пользователей", rendered.plain_text)
        self.assertIn(
            "Автоматическое списание денежных средств не производится",
            rendered.plain_text,
        )

    def test_pdf_rejects_contract_without_frozen_party_details(self):
        source = contract_snapshot()
        source["client_snapshot_json"] = {}

        with self.assertRaises(ValueError) as raised:
            render_client_contract_pdf(source)

        self.assertEqual(str(raised.exception), "client_contract_snapshot_incomplete")

    def test_signed_upload_accepts_only_nonempty_pdf(self):
        result = validate_signed_contract_upload(
            "подписанный-договор.pdf",
            "application/pdf",
            b"%PDF-1.7\ncontract",
        )

        self.assertEqual(result["filename"], "подписанный-договор.pdf")
        self.assertEqual(result["contentType"], "application/pdf")
        self.assertEqual(result["size"], 17)

    def test_signed_upload_rejects_spoofed_and_oversized_files(self):
        for filename, content_type, content, status in (
            ("contract.txt", "text/plain", b"%PDF-1.7", 415),
            ("contract.pdf", "application/pdf", b"not a pdf", 415),
            ("contract.pdf", "application/pdf", b"", 422),
            (
                "contract.pdf",
                "application/pdf",
                b"%PDF-" + b"0" * MAX_SIGNED_CONTRACT_BYTES,
                413,
            ),
        ):
            with self.subTest(filename=filename, content_type=content_type, status=status):
                with self.assertRaises(HTTPException) as raised:
                    validate_signed_contract_upload(filename, content_type, content)
                self.assertEqual(raised.exception.status_code, status)


if __name__ == "__main__":
    unittest.main()
