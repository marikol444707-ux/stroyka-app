import unittest

# Smoke test enumerating presence of key supply->invoice->warehouse->payment modules
# This test does not touch production and only imports code to verify the chain's
# programmatic presence. It is intentionally non-destructive and suitable for dev CI.


class SupplyChainSmokeTest(unittest.TestCase):
    def test_import_chain_modules(self):
        # Import modules that participate in the supply -> invoice -> warehouse -> payment flow
        import importlib

        modules = [
            "backend.features.supply_recommendation_preview",
            "backend.features.supplier_offers",
            "backend.features.supplier_invoices",
            "backend.features.warehouse_receipts",
            "backend.features.accounting_payments",
            "backend.features.payments",
        ]

        missing = []
        for m in modules:
            try:
                importlib.import_module(m)
            except Exception as exc:  # pragma: no cover - smoke should surface import errors
                missing.append((m, str(exc)))

        if missing:
            self.fail("Missing or failing modules in supply->invoice->warehouse->payment chain: %r" % missing)


if __name__ == "__main__":
    unittest.main()
