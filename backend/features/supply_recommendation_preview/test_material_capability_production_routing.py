import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def normalized_source(path):
    return " ".join(path.read_text(encoding="utf-8").split())


class MaterialCapabilityProductionRoutingTests(unittest.TestCase):
    def test_revocation_prefix_is_proxied_to_the_backend_without_spa_fallback(self):
        nginx = normalized_source(
            ROOT / "ops-nginx-stroyka-public-api.conf"
        )
        marker = (
            "location ^~ /supplier-material-capability-confirmations/ {"
        )

        self.assertTrue(
            marker in nginx,
            f"missing nginx backend location: {marker}",
        )
        block = nginx.split(marker, 1)[1].split("}", 1)[0]
        self.assertEqual(
            block.count("proxy_pass http://127.0.0.1:8001;"), 1
        )
        self.assertNotIn("try_files", block)

    def test_public_smoke_distinguishes_all_three_backend_routes_from_spa(self):
        smoke = normalized_source(ROOT / "scripts" / "prod-smoke-check.sh")
        expected_probes = (
            (
                'check_not_spa_fallback "material capability proof route" '
                '"$BASE_URL/supply-requests/2147483647/items/0/'
                'material-capability-proof" "404 422"'
            ),
            (
                'check_not_spa_fallback "material capability confirmation route" '
                '"$BASE_URL/supply-requests/2147483647/items/0/'
                'material-capability-confirmations" "404 405"'
            ),
            (
                'check_not_spa_fallback "material capability revocation route" '
                '"$BASE_URL/supplier-material-capability-confirmations/'
                '2147483647/revocations" "404 405"'
            ),
        )

        for probe in expected_probes:
            with self.subTest(probe=probe):
                self.assertTrue(
                    probe in smoke,
                    f"missing read-only production smoke probe: {probe}",
                )

    def test_routing_artifacts_do_not_enable_capability_feature_flags(self):
        sources = (
            normalized_source(ROOT / "ops-nginx-stroyka-public-api.conf"),
            normalized_source(ROOT / "scripts" / "prod-smoke-check.sh"),
            normalized_source(ROOT / "deploy.sh"),
        )

        for source in sources:
            self.assertNotIn(
                "SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true", source
            )
            self.assertNotIn(
                "REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true",
                source,
            )


if __name__ == "__main__":
    unittest.main()
