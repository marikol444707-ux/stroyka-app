import json
import unittest

from backend.features.supplier_access.offer_party_snapshot import (
    OfferPartySnapshotError,
    build_offer_party_snapshot,
    validate_offer_party_snapshot,
)


class OfferPartySnapshotTests(unittest.TestCase):
    def sample(self):
        return build_offer_party_snapshot(
            offer_id=17,
            request_id=31,
            company_id=2,
            supplier_id=9,
            buyer={
                "full_name": 'ООО "Покупатель"',
                "inn": "1234567890",
                "email": "BUYER@EXAMPLE.RU",
            },
            supplier={
                "name": 'ООО "Поставщик"',
                "inn": "0987654321",
            },
            actor={"id": 14, "name": "Анна", "email": "anna@example.ru"},
            frozen_at="2026-10-01T10:00:00Z",
        )

    def test_builds_two_distinct_parties_without_inventing_missing_values(self):
        snapshot = self.sample()
        self.assertEqual(snapshot["buyer"]["fullName"], 'ООО "Покупатель"')
        self.assertEqual(snapshot["buyer"]["email"], "buyer@example.ru")
        self.assertEqual(snapshot["supplier"]["fullName"], 'ООО "Поставщик"')
        self.assertNotIn("bankName", snapshot["supplier"])
        self.assertNotIn("rs", snapshot["supplier"])
        self.assertNotIn("directorPosition", snapshot["buyer"])
        self.assertNotEqual(snapshot["buyer"], snapshot["supplier"])

    def test_validation_rejects_scope_substitution(self):
        snapshot = self.sample()
        with self.assertRaisesRegex(OfferPartySnapshotError, "scope_mismatch"):
            validate_offer_party_snapshot(
                snapshot,
                offer_id=17,
                request_id=31,
                company_id=3,
                supplier_id=9,
            )

    def test_json_round_trip_is_strict(self):
        snapshot = self.sample()
        restored = validate_offer_party_snapshot(
            json.dumps(snapshot, ensure_ascii=False),
            offer_id=17,
            request_id=31,
            company_id=2,
            supplier_id=9,
        )
        self.assertEqual(restored, snapshot)
        altered = dict(snapshot, unexpected=True)
        with self.assertRaisesRegex(OfferPartySnapshotError, "invalid"):
            validate_offer_party_snapshot(
                altered,
                offer_id=17,
                request_id=31,
                company_id=2,
                supplier_id=9,
            )


if __name__ == "__main__":
    unittest.main()
