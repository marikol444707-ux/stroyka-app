import os
import unittest
from backend.features.supplier_offers import test_response_postgres as support

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class RequestCompaniesPostgresTests(unittest.TestCase):
    setUpClass=classmethod(support.SupplierResponsePostgresTests.setUpClass.__func__)
    api=support.SupplierResponsePostgresTests.api
    sql=support.SupplierResponsePostgresTests.sql
    quote=support.SupplierResponsePostgresTests.quote
    def test_customer_name_is_returned_only_with_addressed_request(self):
        offer,_,_=self.quote()
        self.sql("UPDATE companies SET name='PRIVATE unrelated buyer' WHERE id=3")
        requests=self.api('supplier','GET','/supply-requests')
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0]['id'],offer['requestId'])
        self.assertEqual(requests[0]['companyName'],'SUPPLY CHAIN company 2')
        self.assertNotIn('PRIVATE unrelated buyer',str(requests))
        self.assertEqual(self.api('stranger_supplier','GET','/supply-requests'),[])
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE request_id=%s',(offer['requestId'],))
        self.assertEqual(self.api('supplier','GET','/supply-requests'),[])
