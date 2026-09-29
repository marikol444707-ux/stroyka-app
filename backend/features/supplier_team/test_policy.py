import unittest
from backend.features.supplier_team.policy import offer_policy, leader_policy

class TeamPolicyTests(unittest.TestCase):
    def test_alias_is_not_untrusted_sql(self):
        with self.assertRaises(ValueError):
            offer_policy(7, 'o; SELECT secret')

    def test_parameterized_actor_and_missing_actor(self):
        sql, params = offer_policy(7)
        self.assertNotIn('=7', sql)
        self.assertTrue(params)
        self.assertTrue(all(p == 7 for p in params))
        self.assertEqual(offer_policy(None), ('FALSE', []))
        self.assertEqual(leader_policy(None), ('FALSE', []))
