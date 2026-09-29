import hashlib
import json
import unittest

from .legacy_contract_registry import classify_contract, _plan_sha


def fixture(**changes):
    snapshot = {"supplier": {"supplierId": 5}, "buyer": {"companyId": 12}, "payer": {"companyId": 12}}
    row = {"id": 1, "company_id": 12, "offer_id": 40, "party_version": 1,
           "source_file_id": 31, "snapshot_json": snapshot,
           "snapshot_hash": hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
           "supplier_exists": True, "buyer_exists": True, "payer_exists": True,
           "file_exists": True, "file_company_id": 12, "deletion_status": "active",
           "offer_exists": True, "offer_company_id": 12, "offer_supplier_id": 5,
           "party_exists": True, "party_company_id": 12, "party_supplier_id": 5,
           "party_buyer_company_id": 12, "party_payer_company_id": 12,
           "registry_id": None}
    row.update(changes)
    return row


class LegacyRegistryClassifierTest(unittest.TestCase):
    def test_exact_saved_identity_is_ready_and_plan_is_stable(self):
        item = classify_contract(fixture())
        self.assertEqual(item["status"], "ready")
        self.assertEqual(_plan_sha([item]), _plan_sha([item]))

    def test_every_broken_proof_is_quarantined(self):
        cases = [
            {"snapshot_hash": "0" * 64}, {"file_company_id": 99}, {"deletion_status": "deleting"},
            {"offer_supplier_id": 6}, {"party_payer_company_id": 99}, {"supplier_exists": False},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(classify_contract(fixture(**changes))["status"], "quarantined")

    def test_valid_existing_mapping_is_idempotent(self):
        item = classify_contract(fixture(registry_id=8, registry_company_id=12,
            registry_supplier_id=5, registry_buyer_company_id=12, registry_payer_company_id=12))
        self.assertEqual(item["status"], "alreadyLinked")
        self.assertEqual(_plan_sha([item]), hashlib.sha256(b"[]").hexdigest())

    def test_invalid_existing_mapping_is_quarantined(self):
        item = classify_contract(fixture(registry_id=8, registry_company_id=12,
            registry_supplier_id=6, registry_buyer_company_id=12, registry_payer_company_id=12))
        self.assertEqual(item["status"], "quarantined")
        self.assertIn("invalid_existing_registry_link", item["reasons"])


if __name__ == "__main__":
    unittest.main()
