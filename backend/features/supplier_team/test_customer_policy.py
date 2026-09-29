import unittest
from unittest.mock import patch
from backend.features.supplier_team.policy import offer_policy

class CustomerPolicyTests(unittest.TestCase):
    @patch.dict('os.environ', {'SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED':'1'})
    def test_customer_scope_replaces_individual_offer_scope(self):
        sql, params = offer_policy(7)
        self.assertIn('supplier_customer_assignments', sql)
        self.assertIn('supplier_offers.company_id', sql)
        self.assertNotIn('supplier_offer_assignments', sql)
        self.assertEqual(params, [7])
