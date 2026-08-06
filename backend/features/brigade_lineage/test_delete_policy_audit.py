import unittest
from pathlib import Path

from backend.features.brigade_lineage.delete_policy_audit import (
    audit_estimate_delete_policy,
)


GOOD_SOURCE = '''
DEPENDENCY_CHECKS = (
    (
        "contract estimate lineage",
        """SELECT COUNT(*)
             FROM brigade_contract_items bci
             JOIN estimate_versions ev
               ON ev.id=bci.source_estimate_version_id
            WHERE ev.estimate_id=%s""",
    ),
    (
        "legacy contract lineage",
        """SELECT COUNT(*) FROM brigade_contract_items
            WHERE source_type='legacy' AND estimate_item_key LIKE %s""",
    ),
)
'''


class EstimateDeletePolicyAuditTests(unittest.TestCase):
    def test_exact_version_join_and_explicit_legacy_fallback_are_ready(self):
        report = audit_estimate_delete_policy(source=GOOD_SOURCE)

        self.assertTrue(report["ok"])
        self.assertTrue(report["deleteRestrictionsReady"])
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["writesAttempted"], 0)

    def test_fuzzy_unscoped_contract_key_fails_closed(self):
        source = """
DEPENDENCY_CHECKS = (
    ('contract items', 'SELECT COUNT(*) FROM brigade_contract_items WHERE estimate_item_key LIKE %s'),
)
"""

        report = audit_estimate_delete_policy(source=source)

        self.assertFalse(report["ok"])
        self.assertFalse(report["deleteRestrictionsReady"])
        self.assertEqual(report["violations"], [
            "exactEstimateVersionBlockerMissing",
            "legacyFallbackNotScoped",
        ])

    def test_estimate_filter_must_use_the_joined_version_alias(self):
        source = '''
DEPENDENCY_CHECKS = (
    ('wrong exact blocker', """SELECT COUNT(*)
        FROM brigade_contract_items bci
        JOIN estimate_versions ev
          ON ev.id=bci.source_estimate_version_id
        WHERE bci.estimate_id=%s"""),
)
'''

        report = audit_estimate_delete_policy(source=source)

        self.assertEqual(
            report["violations"],
            ["exactEstimateVersionBlockerMissing"],
        )

    def test_repository_policy_is_ready_without_exposing_sql(self):
        repo_root = Path(__file__).resolve().parents[3]

        report = audit_estimate_delete_policy(repo_root=repo_root)

        self.assertTrue(report["deleteRestrictionsReady"])
        self.assertEqual(report["violations"], [])
        self.assertNotIn("SELECT", str(report))

    def test_parse_failure_is_bounded_and_fails_closed(self):
        report = audit_estimate_delete_policy(source="DEPENDENCY_CHECKS = (")

        self.assertEqual(report["violations"], ["sourceParseError"])
        self.assertNotIn("DEPENDENCY_CHECKS", str(report))


if __name__ == "__main__":
    unittest.main()
